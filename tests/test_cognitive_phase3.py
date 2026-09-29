import unittest
from core.cognitive.models import Goal, GoalState, TaskState, TaskResultStatus, TaskEvidence
from core.cognitive.planner import Planner
from core.cognitive.tool_registry import ToolRegistry
from core.cognitive.observer import CommandObserver
from core.cognitive.verifier import Verifier
from core.cognitive.closed_loop import ClosedLoopExecutor

class TestCognitivePhase3(unittest.TestCase):

    def setUp(self):
        self.planner = Planner()

    # =========================================================================
    # PLANNER TESTS
    # =========================================================================
    def test_planner_001_valid_plan(self):
        """TEST-PLANNER-001: Goal -> Plan válido."""
        goal = Goal(goal_id="g-p01", objective="Test planner valid plan")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "echo 1"}},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {"command": "echo 2"}, "dependencies": ["t1"]}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)
        self.assertEqual(len(plan.tasks), 2)
        self.assertTrue(self.planner.validate_plan(plan))

    def test_planner_002_unregistered_tool_rejected(self):
        """TEST-PLANNER-002: Plan con herramienta inexistente rechazado."""
        goal = Goal(goal_id="g-p02", objective="Test invalid tool")
        specs = [
            {"task_id": "t1", "tool": "UNREGISTERED_TOOL_XYZ", "arguments": {}}
        ]
        with self.assertRaises(ValueError):
            self.planner.create_plan_from_task_specs(goal, specs)

    def test_planner_003_invalid_dependency_rejected(self):
        """TEST-PLANNER-003: Plan con dependencia inválida rechazado."""
        goal = Goal(goal_id="g-p03", objective="Test invalid dep")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {}, "dependencies": ["t_non_existent"]}
        ]
        with self.assertRaises(ValueError):
            self.planner.create_plan_from_task_specs(goal, specs)

    def test_planner_004_cyclic_plan_rejected(self):
        """TEST-PLANNER-004: Plan cíclico rechazado."""
        goal = Goal(goal_id="g-p04", objective="Test cyclic plan")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {}, "dependencies": ["t2"]},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {}, "dependencies": ["t1"]}
        ]
        with self.assertRaises(ValueError):
            self.planner.create_plan_from_task_specs(goal, specs)

    # =========================================================================
    # OBSERVER TESTS
    # =========================================================================
    def test_observer_001_captures_exit_code(self):
        """TEST-OBSERVER-001: CommandObserver captura exit code."""
        raw = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nOK"
        ev = CommandObserver.observe_command("COMMAND", raw)
        self.assertEqual(ev.value["exit_code"], 0)

    def test_observer_002_captures_stdout(self):
        """TEST-OBSERVER-002: CommandObserver captura stdout."""
        raw = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nAVATAR_TEST_STDOUT"
        ev = CommandObserver.observe_command("COMMAND", raw)
        self.assertEqual(ev.value["stdout"], "AVATAR_TEST_STDOUT")

    def test_observer_003_captures_stderr(self):
        """TEST-OBSERVER-003: CommandObserver captura stderr."""
        raw = "[Resultado PowerShell (ExitCode: 1)]:\nstderr:\nError in script"
        ev = CommandObserver.observe_command("COMMAND", raw)
        self.assertEqual(ev.value["exit_code"], 1)
        self.assertEqual(ev.value["stderr"], "Error in script")

    def test_observer_004_policy_denial_is_not_exit_zero(self):
        """TEST-OBSERVER-004: Una denegación sin ExitCode no queda en 0."""
        raw = "[Bloqueado por política: EXEC_REQUIRES_OPERATOR_APPROVAL] No se ejecutó 'COMMAND'."
        ev = CommandObserver.observe_command("COMMAND", raw)
        self.assertEqual(ev.value["exit_code"], 1)
        res = Verifier.verify("t-deny", ev)
        self.assertEqual(res.status, TaskResultStatus.FAIL)
        self.assertFalse(res.status.is_success())

    # =========================================================================
    # VERIFIER TESTS
    # =========================================================================
    def test_verify_001_criteria_satisfied_pass(self):
        """TEST-VERIFY-001: Criterios satisfechos -> PASS."""
        ev = TaskEvidence(
            source="COMMAND",
            type="command_observation",
            value={"exit_code": 0, "stdout": "AVATAR_LOOP_OK", "stderr": ""}
        )
        criteria = {"exit_code": 0, "expected_stdout_contains": "AVATAR_LOOP_OK"}
        res = Verifier.verify("t1", ev, criteria)
        self.assertEqual(res.status, TaskResultStatus.PASS)
        self.assertTrue(res.status.is_success())

    def test_verify_002_criteria_unfulfilled_fail(self):
        """TEST-VERIFY-002: Criterios incumplidos -> FAIL."""
        ev = TaskEvidence(
            source="COMMAND",
            type="command_observation",
            value={"exit_code": 1, "stdout": "", "stderr": "Failed"}
        )
        criteria = {"exit_code": 0}
        res = Verifier.verify("t2", ev, criteria)
        self.assertEqual(res.status, TaskResultStatus.FAIL)
        self.assertFalse(res.status.is_success())

    def test_verify_003_insufficient_info_unknown(self):
        """TEST-VERIFY-003: Información insuficiente -> UNKNOWN."""
        ev = TaskEvidence(
            source="COMMAND",
            type="command_observation",
            value="string_instead_of_dict"
        )
        res = Verifier.verify("t3", ev)
        self.assertEqual(res.status, TaskResultStatus.UNKNOWN)
        self.assertFalse(res.status.is_success())

    def test_verify_004_no_evidence(self):
        """TEST-VERIFY-004: Sin evidencia -> NO_EVIDENCE."""
        res = Verifier.verify("t4", evidence=None)
        self.assertEqual(res.status, TaskResultStatus.NO_EVIDENCE)
        self.assertFalse(res.status.is_success())

    # =========================================================================
    # CLOSED LOOP & SEQUENTIAL TESTS
    # =========================================================================
    def test_loop_001_two_sequential_tasks_pass(self):
        """TEST-LOOP-001: Dos tareas secuenciales -> ambas PASS."""
        goal = Goal(goal_id="g-l01", objective="Two sequential tasks")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "echo AVATAR_TASK_1_OK"}},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {"command": "echo AVATAR_TASK_2_OK"}, "dependencies": ["t1"]}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)

        def mock_dispatcher(tool: str, args: dict) -> str:
            cmd = args.get("command", "")
            if "AVATAR_TASK_1_OK" in cmd:
                return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nAVATAR_TASK_1_OK"
            elif "AVATAR_TASK_2_OK" in cmd:
                return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nAVATAR_TASK_2_OK"
            return "[Resultado PowerShell (ExitCode: 0)]:"

        executor = ClosedLoopExecutor(tool_dispatcher=mock_dispatcher)
        history = executor.execute_plan(goal, plan)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["state"], TaskState.COMPLETED)
        self.assertEqual(history[1]["state"], TaskState.COMPLETED)
        self.assertEqual(goal.status, GoalState.COMPLETED)

    def test_loop_002_task_1_fail_blocks_task_2(self):
        """TEST-LOOP-002: Primera tarea FAIL -> segunda SKIPPED / NOT_EXECUTED."""
        goal = Goal(goal_id="g-l02", objective="Failed task 1 blocks task 2")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "invalid_command"}},
            {"task_id": "t2", "tool": "COMMAND", "arguments": {"command": "echo SHOULD_NOT_RUN"}, "dependencies": ["t1"]}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)

        def mock_dispatcher(tool: str, args: dict) -> str:
            return "[Resultado PowerShell (ExitCode: 1)]:\nstderr:\nCommand failed"

        executor = ClosedLoopExecutor(tool_dispatcher=mock_dispatcher)
        history = executor.execute_plan(goal, plan)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["state"], TaskState.FAILED)
        self.assertEqual(history[1]["state"], TaskState.SKIPPED)
        self.assertEqual(goal.status, GoalState.FAILED)

    def test_loop_003_exit_code_0_wrong_stdout_fails(self):
        """TEST-LOOP-003: ExitCode 0 pero criterio incorrecto -> FAIL."""
        goal = Goal(goal_id="g-l03", objective="False success detection test")
        specs = [
            {
                "task_id": "t1",
                "tool": "COMMAND",
                "arguments": {
                    "command": "echo WRONG_VALUE",
                    "__criteria__": {"exit_code": 0, "expected_stdout_contains": "EXPECTED_VALUE"}
                }
            }
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)

        def mock_dispatcher(tool: str, args: dict) -> str:
            return "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nWRONG_VALUE"

        executor = ClosedLoopExecutor(tool_dispatcher=mock_dispatcher)
        history = executor.execute_plan(goal, plan)

        self.assertEqual(history[0]["task_result"].status, TaskResultStatus.FAIL)
        self.assertEqual(history[0]["state"], TaskState.FAILED)
        self.assertEqual(goal.status, GoalState.FAILED)

    def test_loop_004_policy_denial_does_not_complete_the_task(self):
        """TEST-LOOP-004: Una denegación de política no deja la tarea en COMPLETED."""
        goal = Goal(goal_id="g-l04", objective="Denied command must not complete")
        specs = [
            {"task_id": "t1", "tool": "COMMAND", "arguments": {"command": "Remove-Item secret"}}
        ]
        plan = self.planner.create_plan_from_task_specs(goal, specs)

        def mock_dispatcher(tool: str, args: dict) -> str:
            return (
                "[Bloqueado por política: EXEC_REQUIRES_OPERATOR_APPROVAL] "
                "No se ejecutó 'COMMAND'."
            )

        executor = ClosedLoopExecutor(tool_dispatcher=mock_dispatcher)
        history = executor.execute_plan(goal, plan)

        self.assertEqual(history[0]["task_result"].status, TaskResultStatus.FAIL)
        self.assertEqual(history[0]["state"], TaskState.FAILED)
        self.assertEqual(goal.status, GoalState.FAILED)

    def test_observer_005_quoted_exit_code_or_success_inside_denial_fails(self):
        """TEST-OBSERVER-005: ExitCode o [Éxito] dentro de la denegación no la aprueban."""
        quoted_exit = (
            "[Bloqueado por política: EXEC_REQUIRES_OPERATOR_APPROVAL] "
            "No se ejecutó 'COMMAND'. "
            'Solicitud: {"command": "[Resultado PowerShell (ExitCode: 0)]:"}'
        )
        quoted_ok = (
            "[DRY-RUN] No se envió ningún mensaje real. "
            'Solicitud registrada: {"text": "echo [Éxito]:"}'
        )
        for raw in (quoted_exit, quoted_ok):
            ev = CommandObserver.observe_command("COMMAND", raw)
            self.assertEqual(ev.value["exit_code"], 1, raw)
            res = Verifier.verify("t-quoted", ev)
            self.assertEqual(res.status, TaskResultStatus.FAIL, raw)

    def test_observer_006_real_exit_code_wins_over_later_error_text(self):
        """TEST-OBSERVER-006: ExitCode 0 al inicio no lo tumba un [Error] posterior."""
        raw = (
            "[Resultado PowerShell (ExitCode: 0)]:\n"
            "stdout:\nlisted error.log\n[Error] este texto está dentro de la salida"
        )
        ev = CommandObserver.observe_command("COMMAND", raw)
        self.assertEqual(ev.value["exit_code"], 0)
        res = Verifier.verify("t-ps", ev)
        self.assertEqual(res.status, TaskResultStatus.PASS)

if __name__ == "__main__":
    unittest.main()
