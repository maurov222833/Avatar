import unittest
from core.cognitive.models import Goal, GoalState, TaskState, TaskResultStatus
from core.cognitive.planner import Planner
from core.cognitive.task_queue import TaskQueue
from core.cognitive.continuous_loop import ContinuousExecutionEngine

class TestSelfDevelopment(unittest.TestCase):

    def setUp(self):
        self.planner = Planner()

    def test_queue_001_dependency_unlocking(self):
        """TEST-QUEUE-001: Cola desbloquea dependencias al completar tareas."""
        goal = Goal(goal_id="g-q01", objective="Test queue unlocking")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "echo 1"}},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {"command": "echo 2"}, "dependencies": ["t1"]}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)
        queue = TaskQueue(plan)

        # Primera tarea lista: t1
        next_task = queue.get_next_ready_task()
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task.task_id, "t1")

        # Ninguna otra lista mientras t1 no se complete
        queue.mark_executing("t1")
        self.assertIsNone(queue.get_next_ready_task())

        # Completar t1 -> t2 se desbloquea
        queue.mark_observing("t1")
        queue.mark_verifying("t1")
        res_mock = type("MockResult", (), {"status": TaskResultStatus.PASS, "evidence": []})()
        queue.mark_completed("t1", res_mock)

        next_task_2 = queue.get_next_ready_task()
        self.assertIsNotNone(next_task_2)
        self.assertEqual(next_task_2.task_id, "t2")

    def test_continuous_001_three_tasks_auto_execution(self):
        """TEST-CONTINUOUS-001: Ejecución continua de 3 tareas dependientes sin pausar."""
        goal = Goal(goal_id="g-c01", objective="Three task auto execution")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "echo T1_OK"}, "expected_stdout_contains": "T1_OK"},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {"command": "echo T2_OK"}, "dependencies": ["t1"], "expected_stdout_contains": "T2_OK"},
            {"task_id": "t3", "tool": "COMMAND", "arguments": {"command": "echo T3_OK"}, "dependencies": ["t2"], "expected_stdout_contains": "T3_OK"}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)

        def mock_dispatcher(tool: str, args: dict) -> str:
            cmd = args.get("command", "")
            if "T1_OK" in cmd:
                return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nT1_OK"
            elif "T2_OK" in cmd:
                return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nT2_OK"
            elif "T3_OK" in cmd:
                return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nT3_OK"
            return "[Resultado PowerShell (ExitCode: 0)]:"

        engine = ContinuousExecutionEngine(tool_dispatcher=mock_dispatcher)
        report = engine.execute_continuous_plan(goal, plan)

        self.assertEqual(report["summary"]["completed"], 3)
        self.assertTrue(report["summary"]["all_success"])
        self.assertEqual(goal.status, GoalState.COMPLETED)

    def test_continuous_002_task_failure_blocks_remaining(self):
        """TEST-CONTINUOUS-002: Fallo en tarea 2 bloquea tarea 3 y marca SKIPPED."""
        goal = Goal(goal_id="g-c02", objective="Failure stops remaining tasks")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "echo T1_OK"}, "expected_stdout_contains": "T1_OK"},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {"command": "fail_command"}, "dependencies": ["t1"]},
            {"task_id": "t3", "tool": "COMMAND", "arguments": {"command": "echo T3_OK"}, "dependencies": ["t2"]}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)

        def mock_dispatcher(tool: str, args: dict) -> str:
            cmd = args.get("command", "")
            if "T1_OK" in cmd:
                return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nT1_OK"
            return "[Resultado PowerShell (ExitCode: 1)]:\nstderr:\nCommand failed"

        engine = ContinuousExecutionEngine(tool_dispatcher=mock_dispatcher)
        report = engine.execute_continuous_plan(goal, plan)

        self.assertEqual(report["summary"]["completed"], 1)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["summary"]["skipped"], 1)
        self.assertFalse(report["summary"]["all_success"])
        self.assertEqual(goal.status, GoalState.FAILED)

if __name__ == "__main__":
    unittest.main()
