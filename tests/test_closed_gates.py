"""Las puertas que Mauro pidió cerrar no arrancan efectos."""
from __future__ import annotations

import ast
import os
import unittest

from core.closed_gates import (
    charter_gate,
    hotkey_gate,
    merge_to_main,
    opinion_gate,
    real_ide_gate,
    reject_ide_argv,
    whatsapp_gate,
)
from core.command_risk import classify_command


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ClosedGateTests(unittest.TestCase):
    def test_real_ide_stays_off_and_never_receives_force(self):
        roster = {"real_ides_enabled": False}
        caps = {"per_session": 0, "per_day": 0, "per_month": 0, "currency": "TODO_MAURO"}
        self.assertEqual(real_ide_gate(roster, caps, {}), "REAL_IDE_OFF")
        ready = {"real_ides_enabled": True}
        self.assertEqual(real_ide_gate(ready, caps, {"CURSOR_API_KEY": "local-test"}), "REAL_IDE_NO_BUDGET")
        funded = {"per_session": 1, "per_day": 1, "per_month": 1, "currency": "USD"}
        self.assertEqual(real_ide_gate(ready, funded, {}), "REAL_IDE_NO_KEY")
        self.assertEqual(real_ide_gate(ready, funded, {"CURSOR_API_KEY": "local-test"}), "REAL_IDE_NOT_LAUNCHED")
        self.assertEqual(reject_ide_argv(["agent", "-p", "--force"]), "REAL_IDE_FORCE_DENIED")
        self.assertEqual(reject_ide_argv(["agent", "-p", "--yolo"]), "REAL_IDE_FORCE_DENIED")
        with open(os.path.join(ROOT, "core", "closed_gates.py"), encoding="utf-8") as handle:
            source = handle.read()
        tree = ast.parse(source)
        imported = [node.names[0].name for node in tree.body if isinstance(node, ast.Import)]
        imported += [alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names]
        self.assertNotIn("subprocess", imported)

    def test_charter_hotkey_whatsapp_and_merge_stay_closed(self):
        self.assertEqual(charter_gate({"enabled": False, "display_name": "TODO_MAURO", "decides_alone": []}), "CARTA_SIN_RESPUESTAS")
        self.assertEqual(charter_gate({"enabled": True, "display_name": "Mauro"}), "CARTA_NO_SE_ENCIENDE_SOLA")
        self.assertEqual(hotkey_gate({"hotkey_listener": False}), "HOTKEY_LISTENER_OFF")
        self.assertEqual(hotkey_gate({"hotkey_listener": True}), "HOTKEY_LISTENER_NOT_INSTALLED")
        self.assertEqual(whatsapp_gate({"whatsapp": {"enabled": False}}), "WHATSAPP_PARKED")
        self.assertEqual(whatsapp_gate({"whatsapp": {"enabled": True}}), "WHATSAPP_REFUSED")
        queued = merge_to_main("main")
        self.assertEqual(queued["status"], "QUEUED")
        self.assertEqual(merge_to_main("master")["status"], "QUEUED")

    def test_powershell_classifier_does_not_lower_danger(self):
        self.assertEqual(classify_command("iex whoami")[0], "PROHIBITED")
        self.assertEqual(classify_command("Invoke-Expression whoami")[0], "PROHIBITED")
        self.assertEqual(classify_command("powershell -Command Set-ExecutionPolicy Bypass")[0], "PROHIBITED")
        self.assertEqual(classify_command("powershell -EncodedCommand QQ==")[0], "PROHIBITED")
        self.assertEqual(classify_command("git status")[0], "A")
        self.assertEqual(classify_command("powershell -Command git status")[0], "C")

    def test_second_opinion_does_not_call_a_model(self):
        blocked = opinion_gate(per_session=0, currency="TODO_MAURO")
        self.assertEqual(blocked["status"], "NO_BUDGET")
        self.assertFalse(blocked["called"])
        funded = opinion_gate(per_session=100, currency="USD")
        self.assertEqual(funded["status"], "NOT_SENT")
        self.assertFalse(funded["called"])


if __name__ == "__main__":
    unittest.main()
