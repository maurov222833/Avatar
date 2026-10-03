"""
Acts nativos de WhatsApp + corte de relleno.

El modelo improvisaba con COMMAND+python porque no tenía herramientas de
WhatsApp. Estos tests prueban que existen, que SEND exige consentimiento y que
las rachas de solo-lectura no posan como avance.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import (
    ActChokepoint, ActPolicy, ActStatus, ACT_TYPES,
    _observe_whatsapp_report,
)
from core.checkpoint_engine import CheckpointEngine
from core.cognitive.models import TaskResult, TaskResultStatus
from core.cognitive.tool_registry import ToolRegistry


class _TempWorld:
    def __init__(self):
        import tempfile as _t
        self.dir = _t.mkdtemp(prefix="avatar_wa_acts_")
        self._e = None
        self._r = None

    def __enter__(self):
        import core.state_db as sd
        import core.rag_memory as rm
        self._e = sd.StateEngine.__init__
        self._r = rm.RAGMemory.__init__
        world = self

        def engine_init(self, db_path=None, *a, **k):
            return world._e(self, os.path.join(world.dir, "state_engine.db")
                            if db_path is None else db_path)

        def rag_init(self, memory_dir=None, state_db=None, *a, **k):
            return world._r(self, memory_dir or world.dir, state_db)

        sd.StateEngine.__init__ = engine_init
        rm.RAGMemory.__init__ = rag_init
        return self

    def __exit__(self, *exc):
        import core.state_db as sd
        import core.rag_memory as rm
        import shutil
        sd.StateEngine.__init__ = self._e
        rm.RAGMemory.__init__ = self._r
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


class TestNativeActs(unittest.TestCase):

    def test_acts_registered_with_right_risks(self):
        from core.act_chokepoint import ActRisk
        self.assertEqual(ACT_TYPES["WHATSAPP_STATUS"], ActRisk.READ)
        self.assertEqual(ACT_TYPES["WHATSAPP_READ"], ActRisk.READ)
        self.assertEqual(ACT_TYPES["WHATSAPP_SEND"], ActRisk.EXTERNAL_MESSAGE)

    def test_schema_declares_the_three_tools(self):
        from core.orchestrator import AVATAR_TOOLS_SCHEMA
        from core.llm_provider import _allowed_tool_names
        names = _allowed_tool_names(AVATAR_TOOLS_SCHEMA)
        for expected in ("WHATSAPP_STATUS", "WHATSAPP_READ", "WHATSAPP_SEND"):
            self.assertIn(expected, names)

    def test_registry_lists_them(self):
        self.assertIn("WHATSAPP_SEND", ToolRegistry.list_tools())
        self.assertIn("WHATSAPP_READ", ToolRegistry.list_tools())

    def test_send_requires_consent_status_read_do_not(self):
        with _TempWorld():
            from core.state_db import StateEngine
            db = StateEngine()
            cp = ActChokepoint(
                state_db=db, policy=ActPolicy(),
                executors={"WHATSAPP_STATUS": lambda a: "RESULT:OK estado=LOGGED_IN",
                           "WHATSAPP_READ": lambda a: "RESULT:OK 1 mensajes",
                           "WHATSAPP_SEND": lambda a: "[READBACK_VERIFIED] ok"})
            cp.perform("WHATSAPP_STATUS", {}, mission_id="m")
            cp.perform("WHATSAPP_READ", {}, mission_id="m")
            cp.perform("WHATSAPP_SEND", {"message": "hola"}, mission_id="m")
            acts = {a["act_type"]: a for a in cp.list_acts("m")}
            self.assertEqual(acts["WHATSAPP_STATUS"]["status"], ActStatus.OBSERVED)
            self.assertEqual(acts["WHATSAPP_READ"]["status"], ActStatus.OBSERVED)
            self.assertEqual(acts["WHATSAPP_SEND"]["status"], ActStatus.DENIED)

    def test_observer_markers(self):
        ok = _observe_whatsapp_report({}, "RESULT:OK estado=LOGGED_IN")
        self.assertTrue(ok["verified"])
        err = _observe_whatsapp_report({}, "RESULT:ERROR CHAT_NOT_FOUND: nada")
        self.assertFalse(err["verified"])

    def test_checkpoint_classification(self):
        from core.checkpoint_engine import IdempotencyClass
        self.assertEqual(CheckpointEngine.classify_idempotency("WHATSAPP_STATUS", {}),
                         IdempotencyClass.IDEMPOTENT)
        self.assertEqual(CheckpointEngine.classify_idempotency("WHATSAPP_READ", {}),
                         IdempotencyClass.IDEMPOTENT)
        self.assertEqual(CheckpointEngine.classify_idempotency("WHATSAPP_SEND", {}),
                         IdempotencyClass.NON_IDEMPOTENT)

    def test_run_blocking_works_inside_asyncio_loop(self):
        """La GUI invoca desde un loop asyncio: el lector debe correr igual."""
        import asyncio
        from bridges.whatsapp_reader import run_blocking, WhatsAppReadError

        async def main():
            return run_blocking(lambda: 42)

        self.assertEqual(asyncio.run(main()), 42)

    def test_run_blocking_propagates_errors_and_timeouts(self):
        import time
        from bridges.whatsapp_reader import run_blocking, WhatsAppReadError

        def boom():
            raise WhatsAppReadError(WhatsAppReadError.DOM_UNRECOGNIZED, "x")

        with self.assertRaises(WhatsAppReadError):
            run_blocking(boom)

        def slow():
            time.sleep(30)
            return 1

        with self.assertRaises(WhatsAppReadError):
            run_blocking(slow, timeout_s=1)

    def test_profile_lock_serializes_two_owners(self):
        import json as _json
        import tempfile as _t
        import time as _time
        from bridges.whatsapp_reader import WhatsAppWebReader, WhatsAppReadError

        prof = os.path.join(_t.mkdtemp(prefix="avatar_lock_"), "prof")
        os.makedirs(prof)
        r1 = WhatsAppWebReader(profile_dir=prof)
        r2 = WhatsAppWebReader(profile_dir=prof)
        r1._take_lock()
        try:
            with self.assertRaises(WhatsAppReadError) as ctx:
                r2._take_lock()
            self.assertIn("PERFIL_OCUPADO", str(ctx.exception))
            # Lock rancio (viejo) se toma por encima.
            with open(r1._lock_path(), "w", encoding="utf-8") as f:
                _json.dump({"pid": 999999, "ts": _time.time() - 9999}, f)
            r2._take_lock()  # no debe lanzar
            r2._release_lock()
            self.assertFalse(os.path.exists(r1._lock_path()))
        finally:
            r1._release_lock()


class TestFillerCutoff(unittest.TestCase):

    def test_read_only_ok_is_reported_as_observation(self):
        with _TempWorld():
            from core.orchestrator import AvatarOrchestrator
            orch = AvatarOrchestrator()
            summary = [{"tool_name": "LIST_DIR", "output": "a\nb",
                        "task_result": TaskResult(task_id="t",
                                                  status=TaskResultStatus.PASS),
                        "task": None, "goal": None, "verified_fact": None}]
            msg = orch._build_executive_fallback(summary)
            self.assertIn("Solo observ", msg)
            self.assertNotIn("completada", msg)

    def test_verified_read_does_not_dump_the_file_as_a_completed_task(self):
        """Una lectura con hecho «verificado» no es una tarea hecha ni se pega el fuente."""
        with _TempWorld():
            from core.orchestrator import AvatarOrchestrator, _note_unwritten_fix
            orch = AvatarOrchestrator()
            bridge = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "bridges", "whatsapp_bridge.py",
            )
            with open(bridge, encoding="utf-8") as handle:
                body = handle.read()
            summary = [{"tool_name": "READ_FILE", "output": body,
                        "args": {"file_path": "bridges/whatsapp_bridge.py"},
                        "task_result": TaskResult(task_id="t",
                                                  status=TaskResultStatus.PASS),
                        "task": None, "goal": None, "verified_fact": object()}]
            msg = orch._build_executive_fallback(summary)
            self.assertIn("Solo observ", msg)
            self.assertNotIn("completada", msg)
            self.assertNotIn("import time", msg)
            self.assertNotIn("Garantizar resolución", msg)

            script = [{
                "type": "function_call", "name": "READ_FILE",
                "args": {"file_path": "bridges/whatsapp_bridge.py"}, "text": "",
            }] * 5

            def stub(**k):
                return script.pop(0) if script else {"type": "provider_empty", "error": "x"}

            calls = []

            def stub(**k):
                calls.append(k.get("tools"))
                return script.pop(0) if script else {"type": "provider_empty", "error": "x"}

            orch.llm.generate_response_with_tools = stub
            ran = []
            orch._dispatch_native_tool = lambda *a, **k: ran.append(a) or "NO"
            out = orch.process_user_input(
                "Ahora dime, te hemos realizado unos cambios con WhatsAPP, "
                "dime, sabes que se mejoro?",
                max_steps=5,
            )
            self.assertFalse(ran)
            self.assertTrue(calls)
            self.assertIsNone(calls[0])
            self.assertIn("No ejecuté herramientas", out)
            self.assertNotIn("import time", out)
            self.assertNotIn("Tarea completada", out)
            self.assertNotIn("Estado de la misión", out)
            self.assertNotIn("BLOCKED", out)

            def prose(**k):
                self.assertIsNone(k.get("tools"))
                return {"type": "text", "text": "No tengo ese registro en este turno."}

            orch.llm.generate_response_with_tools = prose
            answered = orch.process_user_input(
                "Qué se mejoró en la integración de WhatsApp?")
            self.assertIn("No tengo ese registro", answered)
            self.assertNotIn("Estado de la misión", answered)
            self.assertNotIn("Tarea completada", answered)

            lie = (
                "Corrección aplicada. He reajustado el foco contextual "
                "para priorizar la conversación."
            )
            noted = _note_unwritten_fix(lie, [])
            self.assertIn("no modifiqué ningún archivo", noted)
            written = _note_unwritten_fix(lie, [{
                "tool_name": "WRITE_FILE",
                "task_result": TaskResult(task_id="w", status=TaskResultStatus.PASS),
            }])
            self.assertNotIn("no modifiqué ningún archivo", written)

    def test_filler_storm_breaks_with_direction_ask(self):
        with _TempWorld():
            from core.orchestrator import AvatarOrchestrator
            orch = AvatarOrchestrator()
            script = [
                {"type": "function_call", "name": "LIST_DIR",
                 "args": {"dir_path": "."}, "text": ""},
                {"type": "provider_empty", "error": "x"},
                {"type": "function_call", "name": "READ_FILE",
                 "args": {"file_path": "requirements.txt"}, "text": ""},
                {"type": "provider_empty", "error": "x"},
                {"type": "provider_empty", "error": "x"},
            ]
            calls = []

            def stub(**k):
                calls.append(1)
                return script.pop(0) if script else {"type": "text", "text": ""}

            orch.llm.generate_response_with_tools = stub
            out = orch.process_user_input(
                "analiza la arquitectura del proyecto", max_steps=6)
            self.assertIn("solo leyendo", out)
            self.assertLessEqual(len(calls), 5)


    def test_sweep_kills_only_own_profile_pids(self):
        import tempfile as _t
        from unittest.mock import patch
        from bridges.whatsapp_reader import WhatsAppWebReader

        prof = os.path.join(_t.mkdtemp(prefix="avatar_sweep_"), "prof")
        os.makedirs(prof)
        r = WhatsAppWebReader(profile_dir=prof)
        csv_out = ('Node,CommandLine,ProcessId\n'
                   f'PC,"chrome.exe --user-data-dir={prof}",1111\n'
                   'PC,"chrome.exe --user-data-dir=C:\\Users\\Mauro\\Chrome",2222\n')

        class _Res:
            stdout = csv_out

        killed = []
        real_run = __import__("subprocess").run

        def fake_run(cmd, **k):
            if cmd[0] == "wmic":
                return _Res()
            killed.append(cmd[2])  # ["taskkill", "/PID", pid, "/F"]
            return _Res()

        with patch("subprocess.run", side_effect=fake_run):
            self.assertEqual(r._own_chromium_pids(), ["1111"])
            r._kill_own_chromium()
        self.assertEqual(killed, ["1111"])

    def test_close_without_launch_releases_lock_fast(self):
        import tempfile as _t
        import time as _time
        from bridges.whatsapp_reader import WhatsAppWebReader

        prof = os.path.join(_t.mkdtemp(prefix="avatar_close_"), "prof")
        os.makedirs(prof)
        r = WhatsAppWebReader(profile_dir=prof)
        r._take_lock()
        self.assertTrue(os.path.exists(r._lock_path()))
        t0 = _time.time()
        r.close()
        self.assertLess(_time.time() - t0, 60)
        self.assertFalse(os.path.exists(r._lock_path()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
