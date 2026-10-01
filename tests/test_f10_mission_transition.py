"""F-10: acceptance criteria as data; COMPLETED only when criteria are met."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import ActChokepoint, ActPolicy, ActStatus
from core.mission_transition import (
    CRITERION_ACT_NOT_DENIED,
    CRITERION_ACT_OBSERVED,
    derive_acceptance_criteria,
    evaluate_transition,
    settle_mission,
)
from core.orchestrator import AvatarOrchestrator
from core.state_db import StateEngine


class TestF10MissionTransition(unittest.TestCase):
    def test_without_criteria_only_reported(self):
        v = evaluate_transition(acceptance_criteria=[], acts=[])
        self.assertEqual(v.status, "REPORTED")
        self.assertFalse(v.completed)

    def test_denied_act_never_satisfies_observed(self):
        acts = [{"act_type": "COMMAND", "status": ActStatus.DENIED}]
        criteria = [
            {"type": CRITERION_ACT_OBSERVED, "act_type": "COMMAND"},
            {"type": CRITERION_ACT_NOT_DENIED, "act_type": "COMMAND"},
        ]
        v = evaluate_transition(acceptance_criteria=criteria, acts=acts)
        self.assertEqual(v.status, "BLOCKED")
        self.assertTrue(v.unmet)

    def test_observed_act_completes(self):
        acts = [{"act_type": "WRITE_FILE", "status": ActStatus.OBSERVED}]
        criteria = [
            {"type": CRITERION_ACT_OBSERVED, "act_type": "WRITE_FILE"},
            {"type": CRITERION_ACT_NOT_DENIED, "act_type": "WRITE_FILE"},
        ]
        v = evaluate_transition(acceptance_criteria=criteria, acts=acts)
        self.assertEqual(v.status, "COMPLETED")

    def test_settle_persists_reported(self):
        d = tempfile.mkdtemp(prefix="avatar_f10_")
        db = StateEngine(db_path=os.path.join(d, "state.db"))
        mid = db.create_mission(raw_prompt="hola", declare_no_requirements=True)
        v = settle_mission(db, mid, acts=[])
        self.assertEqual(v.status, "REPORTED")
        self.assertEqual(db.get_mission(mid)["status"], "REPORTED")

    def test_orchestrator_reconcile_uses_f10_not_hmac_for_empty_caps(self):
        d = tempfile.mkdtemp(prefix="avatar_f10_o_")
        os.environ["AVATAR_HOME"] = d
        os.makedirs(os.path.join(d, "memory"), exist_ok=True)
        orch = AvatarOrchestrator()
        mid = orch.state_db.create_mission(
            session_id=orch.session_id,
            raw_prompt="ping",
            declare_no_requirements=True,
        )
        orch.chokepoint = ActChokepoint(
            state_db=orch.state_db,
            policy=ActPolicy(dry_run=False, exec_requires_approval=False),
            executors={"LIST_DIR": lambda a: "ok"},
        )
        status = orch._reconcile_mission(mid)
        self.assertEqual(status, "REPORTED")
        self.assertEqual(orch.state_db.get_mission(mid)["status"], "REPORTED")

    def test_derive_ignores_read_only_tools(self):
        derived = derive_acceptance_criteria("lee algo", [
            {"tool_name": "READ_FILE"},
            {"tool_name": "LIST_DIR"},
        ])
        self.assertEqual(derived, [])
        derived2 = derive_acceptance_criteria("escribe", [
            {"tool_name": "WRITE_FILE"},
        ])
        self.assertTrue(any(c.get("act_type") == "WRITE_FILE" for c in derived2))
        browsed = derive_acceptance_criteria("abre whatsapp", [
            {"tool_name": "BROWSER_NAVIGATE"},
        ])
        self.assertEqual(browsed, [])

    def test_visible_whatsapp_uses_the_system_browser(self):
        from unittest import mock
        from core.system_browser import wants_visible_whatsapp
        self.assertTrue(wants_visible_whatsapp(
            "Abre WhatsApp web y deja la ventana del QR abierta"))
        self.assertFalse(wants_visible_whatsapp("hola, qué tal"))
        orch = AvatarOrchestrator()
        with mock.patch("core.system_browser.open_whatsapp_web", return_value="ABIERTO") as opened:
            text = orch.process_user_input(
                "Abre WhatsApp web y deja la ventana del QR abierta")
        opened.assert_called_once()
        self.assertIn("navegador de tu PC", text)
        self.assertIn("UNVERIFIED", text)
        self.assertNotIn("COMPLETED_VERIFIED", text)


if __name__ == "__main__":
    unittest.main()
