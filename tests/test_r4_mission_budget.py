"""R4: per-mission act and LLM call budgets."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import (
    MISSION_ACT_BUDGET_EXCEEDED,
    ActChokepoint,
    ActPolicy,
    ActStatus,
)
from core.state_db import StateEngine


class TestR4MissionBudget(unittest.TestCase):
    def test_max_acts_per_mission_blocks_further_acts(self):
        with tempfile.TemporaryDirectory(prefix="avatar_r4_") as tmp:
            db = StateEngine(db_path=os.path.join(tmp, "state.db"))
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(
                    dry_run=False,
                    exec_requires_approval=False,
                    max_acts_per_mission=2,
                ),
                executors={
                    "LIST_DIR": lambda a: ran.append("ok") or "a\nb",
                },
            )
            self.assertNotIn("Bloqueado", cp.perform("LIST_DIR", {"dir_path": "."}, mission_id="m"))
            self.assertNotIn("Bloqueado", cp.perform("LIST_DIR", {"dir_path": "."}, mission_id="m"))
            out = cp.perform("LIST_DIR", {"dir_path": "."}, mission_id="m")
            self.assertIn(MISSION_ACT_BUDGET_EXCEEDED, out)
            self.assertEqual(len(ran), 2)
            self.assertEqual(cp.list_acts("m")[-1]["status"], ActStatus.DENIED)
            self.assertEqual(cp.list_acts("m")[-1]["policy_reason"], MISSION_ACT_BUDGET_EXCEEDED)

    def test_budget_is_per_mission(self):
        with tempfile.TemporaryDirectory(prefix="avatar_r4b_") as tmp:
            db = StateEngine(db_path=os.path.join(tmp, "state.db"))
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(
                    dry_run=False,
                    exec_requires_approval=False,
                    max_acts_per_mission=1,
                ),
                executors={"LIST_DIR": lambda a: ran.append(1) or "ok"},
            )
            cp.perform("LIST_DIR", {"dir_path": "."}, mission_id="a")
            blocked = cp.perform("LIST_DIR", {"dir_path": "."}, mission_id="a")
            self.assertIn(MISSION_ACT_BUDGET_EXCEEDED, blocked)
            ok = cp.perform("LIST_DIR", {"dir_path": "."}, mission_id="b")
            self.assertNotIn("Bloqueado", ok)
            self.assertEqual(len(ran), 2)

    def test_orchestrator_reads_budget_from_config(self):
        home = tempfile.mkdtemp(prefix="avatar_r4_orch_")
        prev_home = os.environ.get("AVATAR_HOME")
        os.environ["AVATAR_HOME"] = home
        os.makedirs(os.path.join(home, "memory"), exist_ok=True)
        cfg = os.path.join(home, "config.json")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(
                '{"autonomy":{"max_acts_per_mission":7,"max_llm_calls_per_mission":3,'
                '"dry_run":true},"security":{"exec_requires_approval":true}}'
            )
        from core import runtime
        runtime.reset_shared_orchestrator()
        try:
            from core.orchestrator import AvatarOrchestrator
            orch = AvatarOrchestrator()
            self.assertEqual(orch.chokepoint.policy.max_acts_per_mission, 7)
            self.assertEqual(orch.max_llm_calls_per_mission, 3)
            mode = orch.operating_mode()
            self.assertEqual(mode["max_acts_per_mission"], 7)
            self.assertEqual(mode["max_llm_calls_per_mission"], 3)
        finally:
            runtime.reset_shared_orchestrator()
            if prev_home is None:
                os.environ.pop("AVATAR_HOME", None)
            else:
                os.environ["AVATAR_HOME"] = prev_home
                runtime.reset_shared_orchestrator()


if __name__ == "__main__":
    unittest.main()
