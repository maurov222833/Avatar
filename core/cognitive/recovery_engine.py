from typing import Dict, Any, List, Optional, Tuple
from core.cognitive.models import Goal, Task, Plan, TaskState, TaskResult, TaskResultStatus, TaskEvidence
from core.cognitive.error_classifier import ErrorClassifier, ErrorCategory
from core.cognitive.recovery_policy import RecoveryPolicyManager, RecoveryStrategy, RecoveryRecord, RetryBudget
from core.cognitive.anti_loop import AntiLoopDetector
from core.cognitive.replanner import Replanner

class RecoveryEngine:
    """
    Motor de Recuperación y Replanificación Controlada V2 para Avatar AI (Fase 4).
    """

    def __init__(
        self,
        budget: Optional[RetryBudget] = None,
        anti_loop: Optional[AntiLoopDetector] = None,
        replanner: Optional[Replanner] = None
    ):
        self.budget = budget or RetryBudget()
        self.anti_loop = anti_loop or AntiLoopDetector()
        self.replanner = replanner or Replanner()
        self.records: List[RecoveryRecord] = []

    def handle_task_failure(
        self,
        goal: Goal,
        plan: Plan,
        task: Task,
        result: TaskResult,
        evidence: Optional[TaskEvidence] = None,
        modified_arguments: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Plan], RecoveryRecord]:
        error_cat = ErrorClassifier.classify_error(result, evidence)
        task.retry_count += 1
        
        strategy = RecoveryPolicyManager.get_strategy(error_cat, task.retry_count)

        # 1. Comprobar presupuesto de reintentos
        if not self.budget.can_attempt(task.retry_count):
            strategy = RecoveryStrategy.ABORT

        # 2. Comprobar detección de bucles infinitos
        if strategy != RecoveryStrategy.ABORT and self.anti_loop.is_loop_detected(task.task_id, task.arguments, error_cat, strategy):
            strategy = RecoveryStrategy.ABORT

        # Registrar intento en anti-loop detector
        self.anti_loop.record_attempt(task.task_id, task.arguments, error_cat, strategy)

        record = RecoveryRecord(
            task_id=task.task_id,
            attempt=task.retry_count,
            error_class=error_cat,
            previous_state=task.state.value,
            strategy=strategy,
            reason=f"Task {task.task_id} failed with {error_cat.value}: {result.error}",
            evidence=evidence
        )
        record.validate()
        self.records.append(record)

        if strategy == RecoveryStrategy.ABORT:
            record.outcome = "ABORTED"
            return None, record

        self.budget.consume_recovery()

        # Transición de estado: FAILED/EXECUTING -> RECOVERING -> READY
        try:
            if task.state == TaskState.EXECUTING or task.state == TaskState.FAILED:
                task.state = TaskState.RECOVERING
                task.transition_to(TaskState.READY)
        except Exception:
            task.state = TaskState.READY

        new_plan = plan
        if strategy in (RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.REPLAN):
            try:
                new_plan = self.replanner.generate_replan(
                    goal=goal,
                    current_plan=plan,
                    failed_task=task,
                    error_cat=error_cat,
                    modified_arguments=modified_arguments
                )
            except Exception as e:
                # Si la replanificación falla en validación, abortar
                record.outcome = "ABORTED"
                task.state = TaskState.FAILED
                return None, record

        record.outcome = "RECOVERING"
        return new_plan, record
