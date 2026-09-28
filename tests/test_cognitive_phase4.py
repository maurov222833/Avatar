import unittest
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskResult, TaskResultStatus, TaskEvidence, Plan
from core.cognitive.error_classifier import ErrorClassifier, ErrorCategory
from core.cognitive.recovery_policy import RecoveryPolicyManager, RecoveryStrategy, RecoveryRecord, RetryBudget
from core.cognitive.anti_loop import AntiLoopDetector
from core.cognitive.replanner import Replanner
from core.cognitive.recovery_engine import RecoveryEngine

class TestCognitivePhase4(unittest.TestCase):

    def setUp(self):
        self.replanner = Replanner()
        self.engine = RecoveryEngine()

    def test_recovery_001_recoverable_error_identified(self):
        """TEST-RECOVERY-001: Error recuperable identificado."""
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, error="Exit code 1 in script")
        cat = ErrorClassifier.classify_error(res)
        self.assertTrue(cat.is_recoverable())
        self.assertEqual(cat, ErrorCategory.RECOVERABLE_TOOL_ERROR)

    def test_recovery_002_unrecoverable_error_identified(self):
        """TEST-RECOVERY-002: Error no recuperable identificado."""
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, error="Access is denied permission error")
        cat = ErrorClassifier.classify_error(res)
        self.assertFalse(cat.is_recoverable())
        self.assertEqual(cat, ErrorCategory.PERMISSION_ERROR)

    def test_recovery_003_retry_limited(self):
        """TEST-RECOVERY-003: Retry limitado."""
        budget = RetryBudget(max_attempts_per_task=2)
        self.assertTrue(budget.can_attempt(1))
        self.assertFalse(budget.can_attempt(2))

    def test_recovery_004_retry_budget_exhausted(self):
        """TEST-RECOVERY-004: Retry budget agotado."""
        budget = RetryBudget(max_recoveries_per_goal=1)
        budget.consume_recovery()
        self.assertFalse(budget.can_attempt(0))

    def test_recovery_005_recovery_record_generated(self):
        """TEST-RECOVERY-005: Recovery record generado."""
        goal = Goal(goal_id="g1", objective="Record test")
        task = Task(task_id="t1", goal_id="g1", description="desc", tool="COMMAND")
        plan = Plan(plan_id="p1", goal_id="g1", tasks=[task])
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, error="Command syntax error")

        new_plan, record = self.engine.handle_task_failure(goal, plan, task, res)
        self.assertIsNotNone(record)
        self.assertEqual(record.task_id, "t1")
        self.assertEqual(record.attempt, 1)
        self.assertEqual(record.error_class, ErrorCategory.INVALID_ARGUMENT)

    def test_recovery_006_retry_same_strategy(self):
        """TEST-RECOVERY-006: RETRY_SAME."""
        strat = RecoveryPolicyManager.get_strategy(ErrorCategory.TIMEOUT, attempt=1)
        self.assertEqual(strat, RecoveryStrategy.RETRY_SAME)

    def test_recovery_007_retry_modified_strategy(self):
        """TEST-RECOVERY-007: RETRY_MODIFIED."""
        strat = RecoveryPolicyManager.get_strategy(ErrorCategory.INVALID_ARGUMENT, attempt=1)
        self.assertEqual(strat, RecoveryStrategy.RETRY_MODIFIED)

    def test_recovery_008_replan_strategy(self):
        """TEST-RECOVERY-008: REPLAN."""
        strat = RecoveryPolicyManager.get_strategy(ErrorCategory.VALIDATION_ERROR, attempt=1)
        self.assertEqual(strat, RecoveryStrategy.REPLAN)

    def test_recovery_009_abort_strategy(self):
        """TEST-RECOVERY-009: ABORT."""
        strat = RecoveryPolicyManager.get_strategy(ErrorCategory.PERMISSION_ERROR, attempt=1)
        self.assertEqual(strat, RecoveryStrategy.ABORT)

    def test_recovery_010_invalid_replan_rejected(self):
        """TEST-RECOVERY-010: Replan inválido rechazado."""
        goal = Goal(goal_id="g1", objective="Invalid replan")
        task = Task(task_id="t1", goal_id="g1", description="desc", tool="COMMAND")
        plan = Plan(plan_id="p1", goal_id="g1", tasks=[task])
        
        # Replacement tool not registered
        invalid_spec = {"tool": "NON_EXISTENT_TOOL", "arguments": {}}
        with self.assertRaises(ValueError):
            self.replanner.generate_replan(goal, plan, task, ErrorCategory.INVALID_ARGUMENT, replacement_task_spec=invalid_spec)

    def test_recovery_011_cyclic_replan_rejected(self):
        """TEST-RECOVERY-011: Replan con ciclo rechazado."""
        goal = Goal(goal_id="g1", objective="Cyclic replan")
        t1 = Task(task_id="t1", goal_id="g1", description="desc", tool="COMMAND")
        t2 = Task(task_id="t2", goal_id="g1", description="desc", tool="COMMAND", dependencies=["t1"])
        plan = Plan(plan_id="p1", goal_id="g1", tasks=[t1, t2])
        
        # Make t1 depend on t2 (creates cycle)
        cyclic_spec = {"tool": "COMMAND", "arguments": {}, "dependencies": ["t2"]}
        with self.assertRaises(ValueError):
            self.replanner.generate_replan(goal, plan, t1, ErrorCategory.INVALID_ARGUMENT, replacement_task_spec=cyclic_spec)

    def test_recovery_012_repeated_error_detected(self):
        """TEST-RECOVERY-012: Mismo error repetido detectado."""
        detector = AntiLoopDetector(max_allowed_repetitions=2)
        detector.record_attempt("t1", {"arg": "val"}, ErrorCategory.TIMEOUT, RecoveryStrategy.RETRY_SAME)
        detector.record_attempt("t1", {"arg": "val"}, ErrorCategory.TIMEOUT, RecoveryStrategy.RETRY_SAME)
        self.assertTrue(detector.is_loop_detected("t1", {"arg": "val"}, ErrorCategory.TIMEOUT, RecoveryStrategy.RETRY_SAME))

    def test_recovery_013_infinite_loop_blocked(self):
        """TEST-RECOVERY-013: Loop infinito bloqueado."""
        detector = AntiLoopDetector(max_allowed_repetitions=1)
        detector.record_attempt("t1", {"arg": "val"}, ErrorCategory.INVALID_ARGUMENT, RecoveryStrategy.RETRY_MODIFIED)
        
        engine = RecoveryEngine(anti_loop=detector)
        goal = Goal(goal_id="g1", objective="Anti loop")
        task = Task(task_id="t1", goal_id="g1", description="desc", tool="COMMAND", arguments={"arg": "val"})
        plan = Plan(plan_id="p1", goal_id="g1", tasks=[task])
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, error="syntax error")

        new_plan, record = engine.handle_task_failure(goal, plan, task, res)
        self.assertEqual(record.strategy, RecoveryStrategy.ABORT)
        self.assertEqual(record.outcome, "ABORTED")

    def test_recovery_014_successful_recovery_requires_pass(self):
        """TEST-RECOVERY-014: Recovery exitoso requiere PASS real."""
        ev = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 0, "stdout": "OK"})
        res = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[ev])
        self.assertTrue(res.status.is_success())
        self.assertEqual(len(res.evidence), 1)

    def test_recovery_015_recovery_without_evidence_cannot_pass(self):
        """TEST-RECOVERY-015: Recovery sin evidencia no puede producir PASS."""
        res_no_ev = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[])
        with self.assertRaises(ValueError):
            res_no_ev.validate()

if __name__ == "__main__":
    unittest.main()
