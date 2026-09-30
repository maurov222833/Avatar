"""F-20: browser and desktop acts are wired through the chokepoint + schema."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import (
    ACT_TYPES,
    ActChokepoint,
    ActPolicy,
    ActRisk,
    ActStatus,
    UNTRUSTED_INPUT_ACTS,
)
from core.checkpoint_engine import CheckpointEngine, IdempotencyClass
from core.orchestrator import AVATAR_TOOLS_SCHEMA, AvatarOrchestrator
from core.state_db import StateEngine


def _schema_names():
    decls = AVATAR_TOOLS_SCHEMA[0]["functionDeclarations"]
    return {d["name"] for d in decls}


class TestF20SchemaAndTaxonomy(unittest.TestCase):
    def test_browser_and_desktop_in_schema_and_act_types(self):
        names = _schema_names()
        for act in (
            "BROWSER_NAVIGATE", "BROWSER_OBSERVE", "BROWSER_CLICK",
            "BROWSER_FILL", "BROWSER_CLOSE",
            "DESKTOP_CLICK", "DESKTOP_TYPE", "DESKTOP_OBSERVE", "DESKTOP_HOTKEY",
            "SCREEN_CAPTURE",
        ):
            self.assertIn(act, names)
            self.assertIn(act, ACT_TYPES)

    def test_browser_observe_is_untrusted_and_network_acts_classified(self):
        self.assertIn("BROWSER_OBSERVE", UNTRUSTED_INPUT_ACTS)
        self.assertEqual(ACT_TYPES["BROWSER_NAVIGATE"], ActRisk.NETWORK)
        self.assertEqual(ACT_TYPES["BROWSER_CLICK"], ActRisk.NETWORK)
        self.assertEqual(ACT_TYPES["DESKTOP_CLICK"], ActRisk.EXEC)
        self.assertEqual(ACT_TYPES["DESKTOP_TYPE"], ActRisk.EXEC)
        self.assertEqual(ACT_TYPES["DESKTOP_OBSERVE"], ActRisk.READ)
        self.assertEqual(ACT_TYPES["DESKTOP_HOTKEY"], ActRisk.LOCAL_WRITE)

    def test_idempotency_classes(self):
        self.assertEqual(
            CheckpointEngine.classify_idempotency("BROWSER_OBSERVE"),
            IdempotencyClass.IDEMPOTENT,
        )
        self.assertEqual(
            CheckpointEngine.classify_idempotency("BROWSER_NAVIGATE"),
            IdempotencyClass.NON_IDEMPOTENT,
        )
        self.assertEqual(
            CheckpointEngine.classify_idempotency("DESKTOP_CLICK"),
            IdempotencyClass.NON_IDEMPOTENT,
        )


class TestF20ChokepointExecutors(unittest.TestCase):
    def test_browser_navigate_and_observe_via_chokepoint(self):
        with tempfile.TemporaryDirectory(prefix="avatar_f20_") as tmp:
            db = StateEngine(db_path=os.path.join(tmp, "state.db"))
            calls = []

            class FakeBrowser:
                is_launched = True

                def navigate(self, url):
                    calls.append(("navigate", url))
                    return {"success": True, "url": url, "title": "t", "status": 200}

                def observe(self):
                    calls.append(("observe",))
                    return {
                        "success": True,
                        "url": "https://example.test",
                        "title": "t",
                        "visible_text": "[UNTRUSTED_WEB_CONTENT]\nhi\n[/UNTRUSTED_WEB_CONTENT]",
                    }

                def close(self):
                    calls.append(("close",))

            orch = AvatarOrchestrator.__new__(AvatarOrchestrator)
            orch.state_db = db
            orch.config = {}
            orch.checkpoint_engine = None
            orch._browser = FakeBrowser()
            orch._desktop = None
            orch.memory = None
            orch.max_llm_calls_per_mission = None
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=False),
                executors={
                    "BROWSER_NAVIGATE": lambda a: orch._exec_browser("navigate", a),
                    "BROWSER_OBSERVE": lambda a: orch._exec_browser("observe", a),
                    "BROWSER_CLOSE": lambda a: orch._exec_browser("close", a),
                },
            )
            out = cp.perform(
                "BROWSER_NAVIGATE", {"url": "https://example.test/page"}, mission_id="m1")
            data = json.loads(out)
            self.assertTrue(data["success"])
            self.assertEqual(calls[0], ("navigate", "https://example.test/page"))
            act = cp.list_acts("m1")[-1]
            self.assertIn(act["status"], (ActStatus.OBSERVED, ActStatus.EXECUTED))

            obs = cp.perform("BROWSER_OBSERVE", {}, mission_id="m1")
            self.assertIn("UNTRUSTED_WEB_CONTENT", obs)
            self.assertEqual(cp.note_tool_provenance("BROWSER_OBSERVE", {}), "untrusted")
            self.assertTrue(cp.policy.context_contaminated)

            cp.perform("BROWSER_CLOSE", {}, mission_id="m1")
            self.assertIsNone(orch._browser)
            self.assertIn(("close",), calls)

    def test_desktop_hotkey_runs_without_exec_approval(self):
        with tempfile.TemporaryDirectory(prefix="avatar_f20h_") as tmp:
            db = StateEngine(db_path=os.path.join(tmp, "state.db"))
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=True),
                executors={
                    "DESKTOP_HOTKEY": lambda a: ran.append(a) or "[Desktop]: ok",
                },
            )
            out = cp.perform(
                "DESKTOP_HOTKEY",
                {"action": "minimize", "target": "chrome"},
                mission_id="m3",
            )
            self.assertEqual(out, "[Desktop]: ok")
            self.assertEqual(ran[0]["action"], "minimize")
            self.assertNotEqual(cp.list_acts("m3")[-1]["status"], ActStatus.PENDING_APPROVAL)

    def test_desktop_click_requires_approval_without_approver(self):
        with tempfile.TemporaryDirectory(prefix="avatar_f20d_") as tmp:
            db = StateEngine(db_path=os.path.join(tmp, "state.db"))
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=True),
                executors={
                    "DESKTOP_CLICK": lambda a: ran.append(a) or json.dumps(
                        {"success": True, "verified": True}),
                },
            )
            out = cp.perform("DESKTOP_CLICK", {"target": "OK"}, mission_id="m2")
            self.assertIn("PENDING_APPROVAL", out)
            self.assertEqual(ran, [])
            self.assertEqual(cp.list_acts("m2")[-1]["status"], ActStatus.PENDING_APPROVAL)

    def test_orchestrator_registers_browser_desktop_executors(self):
        home = tempfile.mkdtemp(prefix="avatar_f20_orch_")
        prev_home = os.environ.get("AVATAR_HOME")
        os.environ["AVATAR_HOME"] = home
        os.makedirs(os.path.join(home, "memory"), exist_ok=True)
        from core import runtime
        runtime.reset_shared_orchestrator()
        try:
            orch = AvatarOrchestrator()
            self.assertIsNotNone(orch.chokepoint)
            for name in (
                "BROWSER_NAVIGATE", "BROWSER_OBSERVE", "BROWSER_CLICK",
                "BROWSER_FILL", "BROWSER_CLOSE",
                "DESKTOP_OBSERVE", "DESKTOP_CLICK", "DESKTOP_TYPE", "DESKTOP_HOTKEY",
                "SCREEN_CAPTURE",
            ):
                self.assertIn(name, orch.chokepoint.executors)
        finally:
            runtime.reset_shared_orchestrator()
            if prev_home is None:
                os.environ.pop("AVATAR_HOME", None)
            else:
                os.environ["AVATAR_HOME"] = prev_home
                runtime.reset_shared_orchestrator()


if __name__ == "__main__":
    unittest.main()
