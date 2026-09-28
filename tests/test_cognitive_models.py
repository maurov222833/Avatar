import unittest
from core.cognitive.models import (
    Goal,
    GoalState,
    Task,
    TaskState,
    TaskEvidence,
    TaskResult,
    TaskResultStatus,
    TaskStateMachine,
    RiskLevel,
    ToolDefinition,
    Plan,
)

class TestCognitiveModels(unittest.TestCase):

    # =========================================================================
    # GOAL TESTS
    # =========================================================================
    def test_goal_001_valid(self):
        """TEST-GOAL-001: Goal válido."""
        goal = Goal(
            goal_id="goal-001",
            objective="Audit project code autonomy",
            constraints=["read-only"],
            success_criteria=["audit report created"]
        )
        goal.validate()
        self.assertEqual(goal.goal_id, "goal-001")
        self.assertEqual(goal.status, GoalState.CREATED)

    def test_goal_002_invalid(self):
        """TEST-GOAL-002: Goal inválido."""
        invalid_goal_1 = Goal(goal_id="", objective="Valid objective")
        with self.assertRaises(ValueError):
            invalid_goal_1.validate()

        invalid_goal_2 = Goal(goal_id="goal-002", objective="")
        with self.assertRaises(ValueError):
            invalid_goal_2.validate()

    # =========================================================================
    # TASK TESTS
    # =========================================================================
    def test_task_001_valid(self):
        """TEST-TASK-001: Task válida."""
        task = Task(
            task_id="task-001",
            goal_id="goal-001",
            description="Run audit tests",
            tool="shell_tool",
            arguments={"command": "echo test"}
        )
        task.validate()
        self.assertEqual(task.task_id, "task-001")
        self.assertEqual(task.state, TaskState.CREATED)

    def test_task_002_invalid(self):
        """TEST-TASK-002: Task inválida."""
        invalid_task = Task(
            task_id="",
            goal_id="goal-001",
            description="Invalid task",
            tool="shell_tool"
        )
        with self.assertRaises(ValueError):
            invalid_task.validate()

        invalid_retry_task = Task(
            task_id="task-002",
            goal_id="goal-001",
            description="Task with negative retries",
            tool="shell_tool",
            retry_count=-1
        )
        with self.assertRaises(ValueError):
            invalid_retry_task.validate()

    # =========================================================================
    # STATE MACHINE TRANSITION TESTS
    # =========================================================================
    def test_state_001_created_to_ready(self):
        """TEST-STATE-001: Transición CREATED -> READY."""
        task = Task(
            task_id="task-101",
            goal_id="goal-001",
            description="State test",
            tool="shell_tool"
        )
        self.assertEqual(task.state, TaskState.CREATED)
        task.transition_to(TaskState.READY)
        self.assertEqual(task.state, TaskState.READY)

    def test_state_002_ready_to_executing(self):
        """TEST-STATE-002: Transición READY -> EXECUTING."""
        task = Task(
            task_id="task-102",
            goal_id="goal-001",
            description="State test",
            tool="shell_tool",
            state=TaskState.READY
        )
        task.transition_to(TaskState.EXECUTING)
        self.assertEqual(task.state, TaskState.EXECUTING)

    def test_state_003_executing_to_observing(self):
        """TEST-STATE-003: Transición EXECUTING -> OBSERVING."""
        task = Task(
            task_id="task-103",
            goal_id="goal-001",
            description="State test",
            tool="shell_tool",
            state=TaskState.EXECUTING
        )
        task.transition_to(TaskState.OBSERVING)
        self.assertEqual(task.state, TaskState.OBSERVING)

    def test_state_004_observing_to_verifying(self):
        """TEST-STATE-004: Transición OBSERVING -> VERIFYING."""
        task = Task(
            task_id="task-104",
            goal_id="goal-001",
            description="State test",
            tool="shell_tool",
            state=TaskState.OBSERVING
        )
        task.transition_to(TaskState.VERIFYING)
        self.assertEqual(task.state, TaskState.VERIFYING)

    def test_state_005_verifying_to_completed(self):
        """TEST-STATE-005: Transición VERIFYING -> COMPLETED."""
        task = Task(
            task_id="task-105",
            goal_id="goal-001",
            description="State test",
            tool="shell_tool",
            state=TaskState.VERIFYING
        )
        task.transition_to(TaskState.COMPLETED)
        self.assertEqual(task.state, TaskState.COMPLETED)

    def test_state_006_invalid_transition_rejected(self):
        """TEST-STATE-006: Transición inválida debe ser rechazada."""
        task = Task(
            task_id="task-106",
            goal_id="goal-001",
            description="Invalid state test",
            tool="shell_tool",
            state=TaskState.CREATED
        )
        # CREATED cannot jump directly to COMPLETED
        with self.assertRaises(ValueError):
            task.transition_to(TaskState.COMPLETED)

        self.assertFalse(TaskStateMachine.can_transition(TaskState.CREATED, TaskState.COMPLETED))

    # =========================================================================
    # TASK EVIDENCE TESTS
    # =========================================================================
    def test_evidence_001_valid(self):
        """TEST-EVIDENCE-001: TaskEvidence válida."""
        ev = TaskEvidence(
            source="shell_tool",
            type="stdout",
            value="AVATAR_BASELINE_OK",
            reliability=1.0
        )
        ev.validate()
        self.assertEqual(ev.source, "shell_tool")
        self.assertEqual(ev.reliability, 1.0)

        invalid_ev = TaskEvidence(source="", type="stdout", value="data")
        with self.assertRaises(ValueError):
            invalid_ev.validate()

    # =========================================================================
    # TASK RESULT & DETERMINISTIC VALIDATION TESTS
    # =========================================================================
    def test_result_001_pass_produces_success_true(self):
        """TEST-RESULT-001 & Deterministic Check: PASS produce success=True."""
        self.assertTrue(TaskResultStatus.PASS.is_success())
        ev = TaskEvidence(source="shell_tool", type="exit_code", value=0)
        res = TaskResult(
            task_id="task-201",
            status=TaskResultStatus.PASS,
            evidence=[ev]
        )
        res.validate()
        self.assertTrue(res.status.is_success())

        # Test that PASS without evidence raises ValueError
        res_no_ev = TaskResult(task_id="task-201", status=TaskResultStatus.PASS, evidence=[])
        with self.assertRaises(ValueError):
            res_no_ev.validate()

    def test_result_002_fail_produces_success_false(self):
        """TEST-RESULT-002 & Deterministic Check: FAIL produce success=False."""
        self.assertFalse(TaskResultStatus.FAIL.is_success())
        res = TaskResult(
            task_id="task-202",
            status=TaskResultStatus.FAIL,
            error="Command returned non-zero exit code"
        )
        res.validate()
        self.assertFalse(res.status.is_success())

    def test_result_003_partial_produces_success_false(self):
        """TEST-RESULT-003 & Deterministic Check: PARTIAL produce success=False."""
        self.assertFalse(TaskResultStatus.PARTIAL.is_success())
        res = TaskResult(
            task_id="task-203",
            status=TaskResultStatus.PARTIAL
        )
        res.validate()
        self.assertFalse(res.status.is_success())

    def test_result_004_unknown_produces_success_false(self):
        """TEST-RESULT-004 & Deterministic Check: UNKNOWN produce success=False."""
        self.assertFalse(TaskResultStatus.UNKNOWN.is_success())
        res = TaskResult(
            task_id="task-204",
            status=TaskResultStatus.UNKNOWN
        )
        res.validate()
        self.assertFalse(res.status.is_success())

    def test_result_005_no_evidence_produces_success_false(self):
        """TEST-RESULT-005 & Deterministic Check: NO_EVIDENCE produce success=False."""
        self.assertFalse(TaskResultStatus.NO_EVIDENCE.is_success())
        res = TaskResult(
            task_id="task-205",
            status=TaskResultStatus.NO_EVIDENCE
        )
        res.validate()
        self.assertFalse(res.status.is_success())

    # =========================================================================
    # PLAN & DAG TESTS
    # =========================================================================
    def test_plan_001_valid(self):
        """TEST-PLAN-001: Plan válido."""
        t1 = Task(task_id="t1", goal_id="g1", description="Step 1", tool="tool_a")
        t2 = Task(task_id="t2", goal_id="g1", description="Step 2", tool="tool_b", dependencies=["t1"])
        plan = Plan(plan_id="plan-001", goal_id="g1", tasks=[t1, t2])
        plan.validate(registered_tools=["tool_a", "tool_b"])
        self.assertEqual(len(plan.tasks), 2)

    def test_plan_002_nonexistent_dependency(self):
        """TEST-PLAN-002: Dependencia inexistente."""
        t1 = Task(task_id="t1", goal_id="g1", description="Step 1", tool="tool_a", dependencies=["t_nonexistent"])
        plan = Plan(plan_id="plan-002", goal_id="g1", tasks=[t1])
        with self.assertRaises(ValueError):
            plan.validate()

    def test_plan_003_cycle_detection(self):
        """TEST-PLAN-003: Detección de ciclo."""
        t1 = Task(task_id="t1", goal_id="g1", description="Step 1", tool="tool_a", dependencies=["t2"])
        t2 = Task(task_id="t2", goal_id="g1", description="Step 2", tool="tool_b", dependencies=["t1"])
        plan = Plan(plan_id="plan-003", goal_id="g1", tasks=[t1, t2])
        with self.assertRaises(ValueError) as ctx:
            plan.validate()
        self.assertIn("Circular dependency", str(ctx.exception))

    # =========================================================================
    # TOOL DEFINITION TESTS
    # =========================================================================
    def test_tool_001_valid(self):
        """TEST-TOOL-001: ToolDefinition válida."""
        tool = ToolDefinition(
            name="shell_tool",
            description="Execute shell command",
            risk_level=RiskLevel.MEDIUM
        )
        tool.validate()
        self.assertEqual(tool.name, "shell_tool")
        self.assertEqual(tool.risk_level, RiskLevel.MEDIUM)

    def test_tool_002_invalid(self):
        """TEST-TOOL-002: ToolDefinition inválida."""
        tool = ToolDefinition(name="", description="Invalid tool")
        with self.assertRaises(ValueError):
            tool.validate()

    # =========================================================================
    # RISK LEVEL TESTS
    # =========================================================================
    def test_risk_001_valid(self):
        """TEST-RISK-001: RiskLevel válido."""
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        self.assertEqual(len(levels), 4)
        self.assertEqual(RiskLevel.LOW.value, "LOW")
        self.assertEqual(RiskLevel.CRITICAL.value, "CRITICAL")

if __name__ == "__main__":
    unittest.main()
