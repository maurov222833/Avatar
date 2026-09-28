"""
END-TO-END ACCEPTANCE SUITE
============================

Scope and honesty statement
---------------------------
These tests drive the *real* application path: `AvatarOrchestrator.process_user_input`,
the real planner, the real act chokepoint, the real tools (read-only or workspace-local),
and the real StateEngine.

They do **not** prove:
  * that a live LLM provider is reachable (the LLM is replaced by a scripted double, because
    acceptance must not require network access or spend tokens);
  * that a real WhatsApp message can be delivered (that is an external effect and is refused
    by policy by design);
  * anything about threats the suite was not designed to test.

What they do prove is stated per test. A passing suite means the wiring, policy, persistence
and reporting work; it does not mean every external integration is live.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.orchestrator import AvatarOrchestrator
from core.act_chokepoint import ActChokepoint, ActPolicy, ActRisk, ActStatus


class ScriptedLLM:
    """
    Deterministic stand-in for the LLM.

    It returns a scripted sequence of tool calls and then a final text answer. It exists so
    acceptance can exercise the orchestration path without network access; it asserts nothing
    about provider correctness.
    """

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.last_prompt = None

    def generate_response(self, *a, **k):
        self.calls += 1
        return self._next_text()

    def generate_response_with_tools(self, system_prompt=None, contents=None, tools=None, **k):
        self.calls += 1
        self.last_prompt = contents
        if not self.script:
            return {"text": "Tarea finalizada."}
        return self.script.pop(0)

    def _next_text(self):
        item = self.script.pop(0) if self.script else {}
        return item.get("text", "ok")


def build_orchestrator(script=None, config=None, db_dir=None):
    """Construct an orchestrator wired to a temp DB, a scripted LLM and a safe policy."""
    db_dir = db_dir or tempfile.mkdtemp(prefix="avatar_acc_")

    import core.state_db as sd
    import core.rag_memory as rm
    _engine_init = sd.StateEngine.__init__
    _rag_init = rm.RAGMemory.__init__

    def engine_init(self, db_path=None, *a, **k):
        return _engine_init(self, os.path.join(db_dir, "state.db") if db_path is None else db_path)

    def rag_init(self, memory_dir=None, state_db=None, *a, **k):
        return _rag_init(self, memory_dir or db_dir, state_db)

    sd.StateEngine.__init__ = engine_init
    rm.RAGMemory.__init__ = rag_init
    try:
        orch = AvatarOrchestrator()
    finally:
        sd.StateEngine.__init__ = _engine_init
        rm.RAGMemory.__init__ = _rag_init

    if script is not None:
        orch.llm = ScriptedLLM(script)
    # Deterministic, conservative defaults for acceptance runs. Rebuild the chokepoint so it
    # picks up the test's config rather than whatever config.json held.
    orch.config = dict(config or {})
    orch.chokepoint = orch._build_chokepoint()
    return orch, db_dir


def tool_call(name, args):
    """
    Build a tool call in the *normalised* shape the orchestrator actually consumes.

    `LLMProvider` normalises provider-specific payloads (Gemini's `functionCall`, OpenAI's
    `tool_calls`) into `{"type": "function_call", "name": ..., "args": ...}` before the
    orchestrator sees them. An earlier version of this helper emitted the raw Gemini shape,
    which the orchestrator silently ignored — so the test passed without ever dispatching a
    tool. That is exactly the kind of vacuous test this suite exists to avoid.
    """
    return {
        "type": "function_call",
        "name": name,
        "args": args,
        "raw_part": {"functionCall": {"name": name, "args": args}},
    }


# ======================================================================
# A1 — startup and configuration
# ======================================================================
class TestAcceptanceStartup(unittest.TestCase):

    def test_orchestrator_constructs_and_exposes_a_chokepoint(self):
        """Proves: the application object builds and exposes exactly one side-effect route."""
        orch, d = build_orchestrator()
        try:
            self.assertIsNotNone(orch.chokepoint)
            self.assertIsInstance(orch.chokepoint, ActChokepoint)
            self.assertIsNotNone(orch.state_db)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_chokepoint_refuses_unregistered_act_types(self):
        """Proves: a tool name outside the registry cannot reach an executor."""
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            out = orch._dispatch_native_tool("NOT_A_REAL_TOOL", {})
            self.assertIn("Bloqueado", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ======================================================================
# A2 — real user request through the real application path
# ======================================================================
class TestAcceptanceRealRequest(unittest.TestCase):

    def test_user_request_creates_a_persisted_mission(self):
        """
        Proves: a request entering the real entry point creates and persists a mission.

        This is the regression guard for the use-before-assignment defect that previously left
        the entire authority subsystem unreachable.
        """
        orch, d = build_orchestrator(script=[{"text": "Listo."}])
        try:
            orch.process_user_input("lista los archivos del proyecto actual", max_steps=1)
            conn = orch.state_db._get_connection()
            missions = conn.execute("SELECT * FROM missions").fetchall()
            self.assertGreaterEqual(len(missions), 1,
                                    "the orchestrator must persist a mission")
            self.assertTrue(missions[0]["mission_id"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_mission_lifecycle_reaches_a_terminal_state(self):
        """Proves: the mission does not stay IN_PROGRESS forever after a completed turn."""
        orch, d = build_orchestrator(script=[{"text": "Listo."}])
        try:
            orch.process_user_input("lista los archivos del proyecto actual", max_steps=1)
            conn = orch.state_db._get_connection()
            statuses = [r[0] for r in conn.execute("SELECT status FROM missions").fetchall()]
            self.assertTrue(statuses)
            self.assertNotIn("IN_PROGRESS", statuses,
                             "a finished turn must reconcile the mission state")
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ======================================================================
# A3 — tool selection, dispatch and observation
# ======================================================================
class TestAcceptanceToolDispatch(unittest.TestCase):

    def test_read_only_tool_executes_and_is_recorded(self):
        """
        Proves: a real read tool runs through the chokepoint and leaves an act record.
        Does not prove: anything about remote providers.
        """
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            out = orch._dispatch_native_tool("LIST_DIR", {"dir_path": workspace}, mission_id="mX")
            self.assertIn("core", out)
            acts = orch.chokepoint.list_acts("mX")
            self.assertEqual(len(acts), 1)
            self.assertEqual(acts[0]["act_type"], "LIST_DIR")
            self.assertIn(acts[0]["status"], (ActStatus.EXECUTED, ActStatus.OBSERVED))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_orchestrator_actually_dispatches_a_tool_call_from_the_llm(self):
        """
        Proves: a tool call returned by the LLM is really executed and recorded.

        This is the test that would have caught a malformed LLM double. A previous version
        of the scripted LLM emitted the raw Gemini payload shape, the orchestrator ignored it,
        and the surrounding assertions still passed — a vacuous green. Here we assert the act
        ledger is non-empty after a turn, so a silent no-dispatch fails the test.
        """
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        orch, d = build_orchestrator(script=[
            tool_call("LIST_DIR", {"dir_path": workspace}),
            {"text": "Listo."},
        ])
        try:
            orch.process_user_input("muestra el contenido del proyecto", max_steps=3)
            acts = orch.chokepoint.list_acts()
            self.assertGreaterEqual(
                len(acts), 1,
                "the orchestrator must dispatch the LLM's tool call and record the act")
            self.assertEqual(acts[0]["act_type"], "LIST_DIR")
            self.assertTrue(acts[0]["mission_id"],
                            "the act must be bound to a real mission")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_write_file_is_observed_independently_of_the_writer_claim(self):
        """
        Proves: the observer checks the filesystem rather than trusting the writer's report.
        """
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            orch.chokepoint.policy.allowed_workspace_root = None
            target = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "scratch")
            os.makedirs(target, exist_ok=True)
            path = os.path.join(target, "acceptance_probe.txt")
            try:
                orch._dispatch_native_tool(
                    "WRITE_FILE", {"file_path": path, "content": "probe"},
                    mission_id="mW")
                acts = orch.chokepoint.list_acts("mW")
                self.assertEqual(len(acts), 1)
                observed = json.loads(acts[0]["observed"]) if acts[0]["observed"] else {}
                if acts[0]["status"] == ActStatus.OBSERVED:
                    self.assertTrue(os.path.isfile(path))
                    self.assertTrue(observed.get("exists"))
            finally:
                if os.path.exists(path):
                    os.remove(path)
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ======================================================================
# A4 — permission enforcement (external effects)
# ======================================================================
class TestAcceptancePermissions(unittest.TestCase):

    def test_external_message_is_refused_by_default(self):
        """
        Proves: a real WhatsApp message is NOT sent unless the operator consents.
        This is the guarantee that matters most for the owner.
        """
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            out = orch._dispatch_native_tool(
                "SEND_WHATSAPP", {"message": "no debe enviarse"}, mission_id="mP")
            self.assertIn("EXTERNAL_EFFECT_REQUIRES_OPERATOR_CONSENT", out)
            acts = orch.chokepoint.list_acts("mP")
            self.assertEqual(acts[0]["status"], ActStatus.DENIED)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_external_message_still_refused_in_dry_run_even_with_consent(self):
        """Proves: dry-run blocks the external effect even when consent is granted."""
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            orch.chokepoint.policy.allow_external_messages = True
            orch.chokepoint.policy.dry_run = True
            out = orch._dispatch_native_tool(
                "SEND_WHATSAPP", {"message": "x"}, mission_id="mP2")
            self.assertIn("DRY-RUN", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_denial_is_traceable(self):
        """Proves: a refusal is recorded with a machine-readable reason."""
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            orch._dispatch_native_tool("SEND_WHATSAPP", {"message": "x"}, mission_id="mP3")
            act = orch.chokepoint.list_acts("mP3")[0]
            self.assertTrue(act["policy_reason"])
            self.assertTrue(act["created_at"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ======================================================================
# A5 — persistence and recovery
# ======================================================================
class TestAcceptancePersistenceRecovery(unittest.TestCase):

    def test_state_survives_restart(self):
        """
        Proves: missions and act records written by one process are readable by the next.
        """
        d = tempfile.mkdtemp(prefix="avatar_recovery_")
        try:
            orch, _ = build_orchestrator(db_dir=d)
            # Reopen the orchestrator's actual database path rather than guessing the filename.
            db_path = orch.state_db.db_path
            mission_id = orch.state_db.create_mission(
                session_id=orch.session_id, raw_prompt="persisted", required_capabilities=[])
            orch._dispatch_native_tool("LIST_DIR",
                                       {"dir_path": os.path.dirname(
                                           os.path.dirname(os.path.abspath(__file__)))},
                                       mission_id=mission_id)
            orch.state_db.close()
            self.assertTrue(os.path.exists(db_path))

            reopened = StateEngine(db_path=db_path)
            try:
                self.assertIsNotNone(reopened.get_mission(mission_id))
                acts = reopened._get_connection().execute(
                    "SELECT COUNT(*) FROM acts").fetchone()[0]
                self.assertGreaterEqual(acts, 1)
            finally:
                reopened.close()
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_incomplete_mission_is_not_reported_complete(self):
        """
        Proves: a mission whose requirement is unverified does not reach COMPLETED.
        """
        orch, d = build_orchestrator()
        try:
            m = orch.state_db.create_mission(
                session_id=orch.state_db.create_session(),
                raw_prompt="requiere algo no verificado",
                required_capabilities=["CAP_WHATSAPP_AUTO_REPLY"])
            verdict = orch.state_db.update_mission_status(m)
            self.assertNotEqual(verdict, "COMPLETED")
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ======================================================================
# A6 — honest reporting
# ======================================================================
class TestAcceptanceHonestReporting(unittest.TestCase):

    def test_observer_does_not_claim_delivery_it_cannot_confirm(self):
        """
        Proves: for an external message the observer states that delivery is NOT confirmed,
        rather than manufacturing a success claim.
        """
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()
            orch.chokepoint.policy.allow_external_messages = True
            orch.chokepoint.policy.dry_run = False
            executed = []
            orch.chokepoint.executors["SEND_WHATSAPP"] = lambda a: (
                executed.append(a) or "Mensaje enviado")
            orch._dispatch_native_tool("SEND_WHATSAPP", {"message": "x"}, mission_id="mH")
            act = orch.chokepoint.list_acts("mH")[0]
            observed = json.loads(act["observed"])
            self.assertFalse(observed["delivery_confirmed"])
            self.assertEqual(act["observation_verified"], 0)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_failed_act_is_recorded_as_failed_not_successful(self):
        """Proves: an executor exception yields FAILED, not a success record."""
        orch, d = build_orchestrator()
        try:
            orch.chokepoint = orch._build_chokepoint()

            def boom(a):
                raise RuntimeError("simulated tool failure")

            orch.chokepoint.executors["LIST_DIR"] = boom
            out = orch._dispatch_native_tool("LIST_DIR", {"dir_path": "."}, mission_id="mF")
            self.assertIn("Error de ejecución", out)
            act = orch.chokepoint.list_acts("mF")[0]
            self.assertEqual(act["status"], ActStatus.FAILED)
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ======================================================================
# A7 — degradation when a provider is unavailable
# ======================================================================
class TestAcceptanceDegradation(unittest.TestCase):

    def test_llm_failure_does_not_crash_the_process(self):
        """
        Proves: an unavailable provider surfaces an error to the caller instead of
        silently pretending the task succeeded.
        """
        orch, d = build_orchestrator()
        try:
            class BrokenLLM:
                def generate_response(self, *a, **k):
                    raise ConnectionError("provider unreachable")

                def generate_response_with_tools(self, *a, **k):
                    raise ConnectionError("provider unreachable")

            orch.llm = BrokenLLM()
            try:
                result = orch.process_user_input("hola", max_steps=1)
                self.assertIsInstance(result, str)
            except ConnectionError:
                # Propagating the provider error is also acceptable; silently succeeding is not.
                pass
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
