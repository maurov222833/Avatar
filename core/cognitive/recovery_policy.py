from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from core.cognitive.error_classifier import ErrorCategory
from core.cognitive.models import TaskEvidence

class RecoveryStrategy(str, Enum):
    RETRY_SAME = "RETRY_SAME"
    RETRY_MODIFIED = "RETRY_MODIFIED"
    REPLAN = "REPLAN"
    ABORT = "ABORT"

@dataclass
class RecoveryRecord:
    task_id: str
    attempt: int
    error_class: ErrorCategory
    previous_state: str
    strategy: RecoveryStrategy
    reason: str
    evidence: Optional[TaskEvidence] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    outcome: str = "PENDING"  # RECOVERY_SUCCESS, RECOVERY_FAILED, ABORTED

    def validate(self) -> None:
        if not self.task_id:
            raise ValueError("RecoveryRecord must have a task_id")
        if self.attempt <= 0:
            raise ValueError("RecoveryRecord attempt must be >= 1")

@dataclass
class RetryBudget:
    max_attempts_per_task: int = 3
    max_recoveries_per_goal: int = 5
    max_total_execution_steps: int = 30
    current_recoveries: int = 0
    current_steps: int = 0

    def can_attempt(self, task_attempts: int) -> bool:
        if task_attempts >= self.max_attempts_per_task:
            return False
        if self.current_recoveries >= self.max_recoveries_per_goal:
            return False
        if self.current_steps >= self.max_total_execution_steps:
            return False
        return True

    def consume_recovery(self):
        self.current_recoveries += 1

class RecoveryPolicyManager:
    """
    Políticas deterministas de recuperación para Avatar AI.
    """
    POLICY_MAP: Dict[ErrorCategory, List[RecoveryStrategy]] = {
        ErrorCategory.TIMEOUT: [RecoveryStrategy.RETRY_SAME, RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.ABORT],
        ErrorCategory.INVALID_ARGUMENT: [RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.REPLAN, RecoveryStrategy.ABORT],
        ErrorCategory.VERIFICATION_FAILURE: [RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.REPLAN, RecoveryStrategy.ABORT],
        ErrorCategory.NOT_FOUND: [RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.REPLAN, RecoveryStrategy.ABORT],
        ErrorCategory.RECOVERABLE_TOOL_ERROR: [RecoveryStrategy.RETRY_SAME, RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.ABORT],
        ErrorCategory.EXTERNAL_SERVICE_ERROR: [RecoveryStrategy.RETRY_SAME, RecoveryStrategy.ABORT],
        ErrorCategory.VALIDATION_ERROR: [RecoveryStrategy.REPLAN, RecoveryStrategy.ABORT],
        ErrorCategory.PERMISSION_ERROR: [RecoveryStrategy.ABORT],
        ErrorCategory.DEPENDENCY_FAILURE: [RecoveryStrategy.ABORT],
        ErrorCategory.UNKNOWN_ERROR: [RecoveryStrategy.RETRY_SAME, RecoveryStrategy.ABORT]
    }

    @classmethod
    def get_strategy(cls, error_cat: ErrorCategory, attempt: int) -> RecoveryStrategy:
        strategies = cls.POLICY_MAP.get(error_cat, [RecoveryStrategy.ABORT])
        index = min(attempt - 1, len(strategies) - 1)
        if index < 0:
            index = 0
        return strategies[index]

    @classmethod
    def determine_strategy(cls, error_info_or_cat: Any, attempt: int = 1, max_attempts: int = 3) -> RecoveryStrategy:
        if attempt >= max_attempts:
            return RecoveryStrategy.ABORT
        cat = getattr(error_info_or_cat, "category", error_info_or_cat)
        if isinstance(cat, str):
            try:
                cat = ErrorCategory(cat)
            except Exception:
                cat = ErrorCategory.UNKNOWN_ERROR
        return cls.get_strategy(cat, attempt)

RecoveryPolicy = RecoveryPolicyManager
