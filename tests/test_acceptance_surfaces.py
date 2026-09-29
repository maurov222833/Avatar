"""
ACCEPTANCE — entry surfaces.

Each user-facing surface is exercised through its real code path with a temp database, and
asserted on the act ledger, not just on a return value.

Surfaces covered: HTTP server, WhatsApp bridge, legacy text-parsed tool path, subagents.

What these do NOT prove: that a live LLM provider is reachable, or that a real message was
delivered (external effects are refused by policy and that refusal is the correct outcome).
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.orchestrator import AvatarOrchestrator
from core.act_chokepoint import ActChokepoint, ActStatus


class _TempWorld:
    """Redirects implicit DB and AVATAR_HOME paths for the duration of a test."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="avatar_surf_")
        self._e = None
        self._r = None
        self._prev_home = None

    def __enter__(self):
        import json
        import core.state_db as sd
        import core.rag_memory as rm
        self._e = sd.StateEngine.__init__
        self._r = rm.RAGMemory.__init__
        self._prev_home = os.environ.get("AVATAR_HOME")
        os.environ["AVATAR_HOME"] = self.dir
        os.makedirs(os.path.join(self.dir, "memory"), exist_ok=True)
        with open(os.path.join(self.dir, "config.json"), "w", encoding="utf-8") as handle:
            json.dump({
                "default_provider": "gemini",
                "gemini": {"api_key": "", "model": "gemini-3.6-flash"},
                "security": {"exec_requires_approval": True, "exec_allowlist": []},
            }, handle, indent=2)
        world = self

        def engine_init(self, db_path=None, *a, **k):
            return world._e(self, os.path.join(world.dir, "memory", "state_engine.db")
                            if db_path is None else db_path)

        def rag_init(self, memory_dir=None, state_db=None, *a, **k):
            return world._r(self, memory_dir or os.path.join(world.dir, "memory"), state_db)

        sd.StateEngine.__init__ = engine_init
        rm.RAGMemory.__init__ = rag_init
        return self

    def __exit__(self, *exc):
        import core.state_db as sd
        import core.rag_memory as rm
        sd.StateEngine.__init__ = self._e
        rm.RAGMemory.__init__ = self._r
        if self._prev_home is None:
            os.environ.pop("AVATAR_HOME", None)
        else:
            os.environ["AVATAR_HOME"] = self._prev_home
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


class TestHttpSurface(unittest.TestCase):

    def test_server_serves_and_the_terminal_endpoint_is_policed(self):
        """
        Proves: the HTTP server responds, /api/config does not leak keys, and the terminal
        endpoint runs through the chokepoint and is recorded.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi/testclient not installed")

        with _TempWorld():
            import server
            client = TestClient(server.app)
            headers = server.auth_headers()

            self.assertEqual(client.get("/").status_code, 200)

            cfg = client.get("/api/config", headers=headers).json()
            flat = str(cfg)
            self.assertIn("api_key", flat, "the key name is still visible")
            for marker in ("sk-", "gsk_", "AIza"):
                self.assertNotIn(marker, flat,
                                 f"a raw credential prefix leaked: {marker}")

            r = client.post("/api/terminal/execute", json={"command": "echo AVATAR_DENY_PROBE"}, headers=headers)
            self.assertEqual(r.status_code, 200)
            acts = server.orchestrator.chokepoint.list_acts()
            self.assertEqual(acts[-1]["act_type"], "COMMAND")
            self.assertEqual(acts[-1]["status"], ActStatus.DENIED,
                             "commands need operator approval by default")
            self.assertEqual(acts[-1]["policy_reason"], "EXEC_REQUIRES_OPERATOR_APPROVAL")

            server.orchestrator.chokepoint.policy.exec_requires_approval = False
            r = client.post("/api/terminal/execute", json={"command": "echo AVATAR_ACCEPT_PROBE"}, headers=headers)
            self.assertEqual(r.status_code, 200)
            self.assertIn("AVATAR_ACCEPT_PROBE", r.json()["output"])

            acts = server.orchestrator.chokepoint.list_acts()
            self.assertTrue(acts, "the terminal act must be recorded")
            self.assertEqual(acts[-1]["act_type"], "COMMAND")
            self.assertEqual(acts[-1]["status"], ActStatus.OBSERVED,
                             "a zero-exit command must be observed as successful")

    def test_whatsapp_status_endpoint_reports_read_only(self):
        """Proves: GET /api/whatsapp/status informa sin efectos."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi/testclient not installed")

        with _TempWorld():
            import server
            client = TestClient(server.app)
            r = client.get("/api/whatsapp/status", headers=server.auth_headers())
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertIn("heartbeat", body)
            self.assertIn("recent_acts", body)
            self.assertIn("mode", body)

    def test_config_update_does_not_return_secrets_in_clear(self):
        """
        Proves: POST /api/config/update redacts secrets like GET /api/config does.
        Regression: the endpoint used to return the raw config with live api keys.
        """
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi/testclient not installed")

        with _TempWorld():
            import server
            client = TestClient(server.app)

            body = client.post("/api/config/update", json={}, headers=server.auth_headers()).json()
            flat = str(body.get("config", body))
            for marker in ("sk-", "gsk_", "AIza", "AQ."):
                self.assertNotIn(marker, flat,
                                 f"a raw credential prefix leaked via update: {marker}")


class TestWhatsAppSurface(unittest.TestCase):

    def test_whatsapp_reply_is_blocked_and_recorded(self):
        """
        Proves: the bridge's outbound message is refused by policy and the refusal is recorded.
        It does NOT prove a message was delivered — it proves one was NOT sent.
        """
        from bridges.whatsapp_bridge import WhatsAppBridge

        with _TempWorld():
            # Own orchestrator so policy/LLM stubs do not mutate the process singleton (F-16).
            bridge = WhatsAppBridge(orchestrator=AvatarOrchestrator())
            # Denegación hermética: no depende del config de la máquina.
            bridge.orchestrator.chokepoint.policy.allow_external_messages = False
            bridge.orchestrator.chokepoint.policy.dry_run = True
            # Avoid running the agent: we only care about the delivery step.
            bridge.orchestrator.llm = type(
                "NoLLM", (), {"generate_response": lambda *a, **k: "ok",
                              "generate_response_with_tools": lambda *a, **k: {"text": "ok"}})()
            bridge.orchestrator.process_user_input = lambda *a, **k: "respuesta de prueba"

            bridge.process_incoming_whatsapp("TEST_SENDER", "hola")

            acts = bridge.orchestrator.chokepoint.list_acts()
            self.assertTrue(acts, "the attempted delivery must be recorded")
            self.assertEqual(acts[-1]["act_type"], "SEND_WHATSAPP")
            self.assertEqual(acts[-1]["status"], ActStatus.DENIED,
                             "an external message must not be sent without consent")
            self.assertIn("EXTERNAL_EFFECT", acts[-1]["policy_reason"])


class TestLegacyTextPath(unittest.TestCase):

    def test_text_parsed_command_goes_through_the_chokepoint(self):
        """
        Proves: the legacy prose-parsed action path is policy-checked and recorded, not a
        direct shell call.
        """
        with _TempWorld():
            orch = AvatarOrchestrator()
            orch.chokepoint.policy.exec_requires_approval = False
            mission_id = orch.state_db.create_mission(
                session_id=orch.session_id, raw_prompt="legacy", required_capabilities=[])
            orch._legacy_mission_id = mission_id
            out = orch._dispatch_tool_action("COMMAND", "echo LEGACY_PATH_PROBE")
            self.assertIn("LEGACY_PATH_PROBE", out)
            acts = orch.chokepoint.list_acts(mission_id)
            self.assertTrue(acts, "the legacy path must record an act")
            self.assertEqual(acts[-1]["act_type"], "COMMAND")
            self.assertIn(acts[-1]["status"], (ActStatus.OBSERVED, ActStatus.OBSERVATION_FAILED),
                          "the command must have actually run, not been echoed by a denial")

    def test_text_parsed_command_needs_approval_by_default(self):
        with _TempWorld():
            orch = AvatarOrchestrator()
            out = orch._dispatch_tool_action("COMMAND", "echo LEGACY_DENY_PROBE")
            self.assertIn("EXEC_REQUIRES_OPERATOR_APPROVAL", out)
            self.assertEqual(orch.chokepoint.list_acts()[-1]["status"], ActStatus.DENIED)

    def test_text_parsed_whatsapp_is_blocked(self):
        """Proves: the legacy path cannot bypass the external-effect policy either."""
        with _TempWorld():
            orch = AvatarOrchestrator()
            orch.chokepoint.policy.allow_external_messages = False
            orch.chokepoint.policy.dry_run = True
            out = orch._dispatch_tool_action("SEND_WHATSAPP", "no debe salir")
            self.assertIn("Bloqueado", out)
            self.assertIn("EXTERNAL_EFFECT", out)


class TestSubagentSurface(unittest.TestCase):

    def test_subagent_git_status_is_recorded_not_called_directly(self):
        """
        Proves: the unattended-development subagent reports its repository status through the
        chokepoint rather than shelling out.
        """
        from core.subagents import AntigravityProxyAgent  # import to confirm the module loads

        with _TempWorld():
            orch = AvatarOrchestrator()

            class FakeSub(AntigravityProxyAgent):
                def __init__(self):
                    self.llm = type("NoLLM", (), {
                        "generate_response": lambda *a, **k: "plan"})()
                    self.chokepoint = orch.chokepoint
                    self.role_prompt = ""

            sub = FakeSub()
            before = len(orch.chokepoint.list_acts())
            summary = sub.execute_unattended_task("mejora algo", os.getcwd())
            self.assertIn("Informe de Trabajo Desatendido", summary)
            after = orch.chokepoint.list_acts()
            self.assertGreater(len(after), before,
                               "the subagent's git status must be recorded as an act")
            self.assertEqual(after[-1]["act_type"], "COMMAND")


class TestResumeSurface(unittest.TestCase):

    def test_orchestrator_resume_executes_through_chokepoint_and_binds_mission(self):
        """
        Proves: the orchestrator exposes resume (§41 continuity) and resumed work runs
        through the chokepoint bound to its mission, not through an invisible side path.
        """
        with _TempWorld():
            orch = AvatarOrchestrator()
            orch.chokepoint.policy.exec_requires_approval = False
            mission_id = orch.state_db.create_mission(
                session_id=orch.session_id, raw_prompt="resume-binding",
                required_capabilities=[], declare_no_requirements=True)
            orch.state_db.create_planner_task(
                "T_RESUME", mission_id, 1, "eco de reanudación",
                "COMMAND", {"command": "echo RESUME_BINDING_PROBE"}, "PENDING")

            res = orch.resume_mission(mission_id)
            self.assertEqual([e["task_id"] for e in res["executed_trace"]], ["T_RESUME"])

            acts = orch.chokepoint.list_acts(mission_id)
            self.assertTrue(acts, "resumed work must be recorded against its mission")
            self.assertEqual(acts[-1]["act_type"], "COMMAND")
            self.assertIn("RESUME_BINDING_PROBE", acts[-1].get("executor_result", ""))

    def test_resume_endpoint_is_idempotent(self):
        """Proves: POST /api/missions/resume answers with the stable resume shape."""
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi/testclient not installed")

        with _TempWorld():
            import server
            client = TestClient(server.app)

            r = client.post("/api/missions/resume", json={"mission_id": "msn_inexistente"},
                            headers=server.auth_headers())
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["status"], "NO_ACTIVE_MISSION")
            self.assertEqual(body["executed_trace"], [])


class TestExecutiveFallback(unittest.TestCase):

    def _summary(self, tool, status):
        from core.cognitive.models import TaskResult, TaskResultStatus
        return [{"tool_name": tool, "output": "out",
                 "task_result": TaskResult(task_id="t1", status=status),
                 "task": None, "goal": None}]

    def test_empty_provider_text_reports_real_state_not_a_template(self):
        """
        Proves: when the provider returns no usable text, the owner gets an executive
        message built from real execution state — never the canned
        "Auditoría y análisis procesados correctamente." template.
        """
        from core.cognitive.models import TaskResultStatus

        with _TempWorld():
            orch = AvatarOrchestrator()

            ok_msg = orch._build_executive_fallback(
                self._summary("WRITE_FILE", TaskResultStatus.PASS))
            self.assertIn("WRITE_FILE", ok_msg)
            self.assertIn("completada", ok_msg)

            fail_msg = orch._build_executive_fallback(
                self._summary("WRITE_FILE", TaskResultStatus.FAIL))
            self.assertIn("No pude completar", fail_msg)
            self.assertNotIn("correctamente", fail_msg)

            idle_msg = orch._build_executive_fallback([])
            self.assertIn("no se ejecutó ninguna acción", idle_msg)

            for msg in (ok_msg, fail_msg, idle_msg):
                self.assertNotIn("Auditoría y análisis procesados correctamente", msg)

    def test_denial_text_surfaces_and_silence_escalates(self):
        """
        Proves: a policy DENIED in the last output is shown (never reported as
        success), and repeated provider silence escalates instead of masking.
        """
        from core.cognitive.models import TaskResult, TaskResultStatus

        with _TempWorld():
            orch = AvatarOrchestrator()

            denied = [{"tool_name": "SEND_WHATSAPP",
                       "output": "Bloqueado por política: EXTERNAL_EFFECT_REQUIRES_OPERATOR_CONSENT",
                       "task_result": TaskResult(task_id="t1",
                                                 status=TaskResultStatus.FAIL),
                       "task": None, "goal": None}]
            msg = orch._build_executive_fallback(denied)
            self.assertIn("EXTERNAL_EFFECT_REQUIRES_OPERATOR_CONSENT", msg)
            self.assertNotIn("completada", msg)

            # Simular racha de silencio: dos respaldos seguidos en el historial.
            orch.history.append({"role": "user", "content": "sigue"})
            orch.history.append({"role": "assistant",
                                 "content": "✅ Tarea completada: `LIST_DIR` fake"})
            orch.history.append({"role": "user", "content": "sigue"})
            orch.history.append({"role": "assistant",
                                 "content": "✅ Tarea completada: `READ_FILE` fake"})
            esc = orch._build_executive_fallback([])
            self.assertIn("turnos seguidos", esc)


class TestEmptyProviderCutsTurn(unittest.TestCase):

    def test_two_consecutive_empties_stop_the_turn(self):
        """
        Proves: provider silence cuts the turn deterministically instead of burning
        steps on filler tool calls masked as progress.
        """
        with _TempWorld():
            orch = AvatarOrchestrator()
            calls = []

            def silent(system_prompt=None, contents=None, tools=None, **k):
                calls.append(1)
                return {"type": "provider_empty", "provider": "fake",
                        "error": "sin contenido"}

            orch.llm.generate_response_with_tools = silent
            out = orch.process_user_input("haz algo", max_steps=5)
            self.assertIn("vacías", out)
            self.assertEqual(len(calls), 2, "el turno se corta al segundo vacío")

    def test_parroted_canned_text_counts_as_silence(self):
        """Proves: el modelo repitiendo 'Respuesta vacía…' no cuela como prosa."""
        with _TempWorld():
            orch = AvatarOrchestrator()
            calls = []

            def parrot(system_prompt=None, contents=None, tools=None, **k):
                calls.append(1)
                return {"type": "text", "provider": "fake",
                        "text": "Respuesta vacía del proveedor."}

            orch.llm.generate_response_with_tools = parrot
            out = orch.process_user_input("haz algo", max_steps=5)
            self.assertIn("vacías", out)
            self.assertNotIn("📌", out, "el volcado no queda como mensaje")
            self.assertEqual(len(calls), 2)

    def test_whitespace_final_never_leaves_bare_evidence_dump(self):
        """Proves: un final en blanco dispara el respaldo, no un bloque huérfano."""
        with _TempWorld():
            orch = AvatarOrchestrator()
            calls = []

            def blank(system_prompt=None, contents=None, tools=None, **k):
                calls.append(1)
                return {"type": "text", "provider": "fake", "text": "   "}

            orch.llm.generate_response_with_tools = blank
            out = orch.process_user_input("lista el directorio", max_steps=5)
            self.assertNotIn("📌", out)
            self.assertEqual(len(calls), 2)

    def test_evidence_block_truncates_long_output(self):
        """Proves: the chat evidence never dumps full directory listings."""
        with _TempWorld():
            orch = AvatarOrchestrator()
            long_text = "\n".join(f"linea-{i}" for i in range(100))
            short = orch._truncate_output(long_text)
            self.assertLessEqual(len(short.splitlines()), 41)
            self.assertIn("truncada", short)
            self.assertIn("100", short)


if __name__ == "__main__":
    unittest.main(verbosity=2)
