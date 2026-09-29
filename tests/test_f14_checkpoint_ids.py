"""F-14: checkpoint task ids must be unique per mission, and a failed pre-checkpoint aborts the tool."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.checkpoint_engine import CheckpointEngine
from core.cognitive.continuous_loop import ContinuousExecutionEngine
from core.cognitive.models import Goal, GoalState, Plan, Task, TaskState, TaskResultStatus
from core.cognitive.planner import Planner
from core.orchestrator import AvatarOrchestrator
from core.state_db import StateEngine


class TestF14CheckpointIds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "f14.db")
        self.engine = StateEngine(db_path=self.db_path)
        self.addCleanup(self.engine.close)
        self.checkpoint = CheckpointEngine(state_db=self.engine)

    def test_scope_plan_task_ids_is_stable_and_unique_per_mission(self):
        goal = Goal(goal_id="g1", objective="x", success_criteria=[])
        plan = Planner().create_plan_from_task_specs(
            goal,
            [
                {"task_id": "T1", "tool": "LIST_DIR", "arguments": {"dir_path": "."}, "description": "a", "dependencies": []},
                {"task_id": "T2", "tool": "LIST_DIR", "arguments": {"dir_path": "."}, "description": "b", "dependencies": ["T1"]},
            ],
        )
        AvatarOrchestrator._scope_plan_task_ids(plan, "msn_aaaaaaaa")
        self.assertEqual(plan.tasks[0].task_id, "T1_msn_aaaaaaaa")
        self.assertEqual(plan.tasks[1].task_id, "T2_msn_aaaaaaaa")
        self.assertEqual(plan.tasks[1].dependencies, ["T1_msn_aaaaaaaa"])
        AvatarOrchestrator._scope_plan_task_ids(plan, "msn_aaaaaaaa")
        self.assertEqual(plan.tasks[0].task_id, "T1_msn_aaaaaaaa")

    def test_two_missions_do_not_collide_on_short_task_ids(self):
        calls = []

        def dispatcher(tool, args):
            calls.append((tool, args))
            return "ok"

        def run_mission(mission_id: str):
            self.engine.create_mission(
                mission_id=mission_id,
                raw_prompt="multi",
                declare_no_requirements=True,
            )
            goal = Goal(goal_id=mission_id, objective="multi", success_criteria=[])
            goal.metadata["mission_id"] = mission_id
            plan = Planner().create_plan_from_task_specs(
                goal,
                [
                    {"task_id": "T1", "tool": "LIST_DIR", "arguments": {"dir_path": "."}, "description": "list", "dependencies": []},
                    {"task_id": "T2", "tool": "LIST_DIR", "arguments": {"dir_path": "."}, "description": "list2", "dependencies": ["T1"]},
                ],
            )
            AvatarOrchestrator._scope_plan_task_ids(plan, mission_id)
            for idx, task in enumerate(plan.tasks):
                self.engine.create_planner_task(
                    task_id=task.task_id,
                    mission_id=mission_id,
                    step_index=idx + 1,
                    description=task.description,
                    tool_name=task.tool,
                    tool_args=task.arguments,
                    status="PENDING",
                )
            loop = ContinuousExecutionEngine(
                tool_dispatcher=dispatcher,
                checkpoint_engine=self.checkpoint,
            )
            return loop.execute_continuous_plan(goal, plan)

        first = run_mission("msn_mission_one_aaaa")
        second = run_mission("msn_mission_two_bbbb")
        self.assertEqual(first["summary"]["completed"], 2)
        self.assertEqual(second["summary"]["completed"], 2)
        self.assertEqual(len(calls), 4)
        ids = [row["task_id"] for row in self.engine.get_planner_tasks("msn_mission_one_aaaa")]
        ids += [row["task_id"] for row in self.engine.get_planner_tasks("msn_mission_two_bbbb")]
        self.assertEqual(
            sorted(ids),
            sorted([
                "T1_msn_mission_one_aaaa",
                "T2_msn_mission_one_aaaa",
                "T1_msn_mission_two_bbbb",
                "T2_msn_mission_two_bbbb",
            ]),
        )
        self.assertNotIn("T1", ids)
        self.assertNotIn("T2", ids)

    def test_pre_checkpoint_failure_does_not_run_the_tool(self):
        goal = Goal(goal_id="g_abort", objective="x", success_criteria=[])
        goal.metadata["mission_id"] = "msn_abort_cccc"
        plan = Planner().create_plan_from_task_specs(
            goal,
            [
                {"task_id": "T1", "tool": "LIST_DIR", "arguments": {"dir_path": "."}, "description": "a", "dependencies": []},
            ],
        )
        AvatarOrchestrator._scope_plan_task_ids(plan, "msn_abort_cccc")
        calls = []

        class BoomCheckpoint:
            def save_pre_tool_checkpoint(self, **kwargs):
                raise RuntimeError("UNIQUE constraint failed: planner_tasks.task_id")

            def save_post_tool_checkpoint(self, **kwargs):
                raise AssertionError("post should not run")

            def mark_verified(self, **kwargs):
                raise AssertionError("verify should not run")

        loop = ContinuousExecutionEngine(
            tool_dispatcher=lambda tool, args: calls.append(1) or "should-not-run",
            checkpoint_engine=BoomCheckpoint(),
            max_auto_retries_per_task=0,
        )
        res = loop.execute_continuous_plan(goal, plan)
        self.assertEqual(calls, [])
        self.assertEqual(res["summary"]["completed"], 0)
        self.assertEqual(res["trace"][0]["state"], TaskState.FAILED)
        self.assertIn("Checkpoint", res["trace"][0]["output"])
        self.assertEqual(res["trace"][0]["task_result"].status, TaskResultStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
