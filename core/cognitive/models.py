from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

class GoalState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class TaskState(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RECOVERING = "RECOVERING"

class TaskResultStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NO_EVIDENCE = "NO_EVIDENCE"

    def is_success(self) -> bool:
        if self in (TaskResultStatus.UNKNOWN, TaskResultStatus.NO_EVIDENCE):
            return False
        return self == TaskResultStatus.PASS

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class Goal:
    goal_id: str
    objective: str
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    status: GoalState = GoalState.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise ValueError("goal_id must be a non-empty string")
        if not self.objective or not isinstance(self.objective, str):
            raise ValueError("objective must be a non-empty string")
        if not isinstance(self.status, GoalState):
            raise ValueError(f"Invalid GoalState: {self.status}")

@dataclass
class TaskEvidence:
    source: str
    type: str
    value: Any
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reliability: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.source or not isinstance(self.source, str):
            raise ValueError("Evidence source must be a non-empty string")
        if not self.type or not isinstance(self.type, str):
            raise ValueError("Evidence type must be a non-empty string")
        if not (0.0 <= self.reliability <= 1.0):
            raise ValueError("Evidence reliability must be between 0.0 and 1.0")

@dataclass
class EvidenceGap:
    """
    Representación formal de la Brecha de Evidencia (Fase 13 / F-06).
    Describe la diferencia entre la evidencia obtenida y la requerida,
    especificando la información objetiva faltante (NEXT_INFORMATION_TARGET).
    """
    current_evidence: str
    required_evidence: str
    evidence_gap: str
    next_information_target: str
    rationale: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_evidence": self.current_evidence,
            "required_evidence": self.required_evidence,
            "evidence_gap": self.evidence_gap,
            "next_information_target": self.next_information_target,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "metadata": self.metadata
        }

    def format_cognitive_instruction(self) -> str:
        return (
            f"[ANÁLISIS DE BRECHA DE EVIDENCIA - EVIDENCE GAP]:\n"
            f"- EVIDENCIA ACTUAL (CURRENT_EVIDENCE): {self.current_evidence}\n"
            f"- EVIDENCIA REQUERIDA (REQUIRED_EVIDENCE): {self.required_evidence}\n"
            f"- BRECHA DE EVIDENCIA (EVIDENCE_GAP): {self.evidence_gap}\n"
            f"- PRÓXIMA INFORMACIÓN REQUERIDA (NEXT_INFORMATION_TARGET): {self.next_information_target}\n\n"
            "INSTRUCCIÓN COGNITIVA:\n"
            "- La exploración inicial de estructura o directorio ya fue completada.\n"
            "- El objetivo requiere obtener evidencia sobre la implementación interna o comportamiento técnico del sistema.\n"
            "- Selecciona e invoca libremente la herramienta nativa adecuada para obtener la próxima información requerida (NEXT_INFORMATION_TARGET)."
        )

@dataclass
class TaskResult:
    task_id: str
    status: TaskResultStatus
    evidence: List[TaskEvidence] = field(default_factory=list)
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamps: Dict[str, str] = field(default_factory=dict)
    verification_info: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(self.status, TaskResultStatus):
            raise ValueError(f"Invalid TaskResultStatus: {self.status}")
        for ev in self.evidence:
            ev.validate()
        if self.status.is_success() and not self.evidence:
            raise ValueError("TaskResult with SUCCESS status must have evidence supporting it.")

class TaskStateMachine:
    VALID_TRANSITIONS = {
        TaskState.CREATED: [TaskState.READY, TaskState.SKIPPED],
        TaskState.READY: [TaskState.EXECUTING, TaskState.SKIPPED],
        TaskState.EXECUTING: [TaskState.OBSERVING, TaskState.FAILED, TaskState.RECOVERING],
        TaskState.OBSERVING: [TaskState.VERIFYING, TaskState.FAILED, TaskState.RECOVERING],
        TaskState.VERIFYING: [TaskState.COMPLETED, TaskState.FAILED, TaskState.RECOVERING],
        TaskState.RECOVERING: [TaskState.READY, TaskState.FAILED],
        TaskState.FAILED: [TaskState.READY],
        TaskState.COMPLETED: [],
        TaskState.SKIPPED: []
    }

    @classmethod
    def can_transition(cls, current: TaskState, target: TaskState) -> bool:
        return target in cls.VALID_TRANSITIONS.get(current, [])

@dataclass
class Task:
    task_id: str
    goal_id: str
    description: str
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    state: TaskState = TaskState.CREATED
    retry_count: int = 0
    max_attempts: int = 3
    evidence: List[TaskEvidence] = field(default_factory=list)
    result: Optional[TaskResult] = None

    def transition_to(self, new_state: TaskState) -> None:
        if not TaskStateMachine.can_transition(self.state, new_state):
            raise ValueError(f"Invalid task state transition from {self.state} to {new_state}")
        self.state = new_state

    def validate(self) -> None:
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("task_id must be a non-empty string")
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise ValueError("goal_id must be a non-empty string")
        if not self.tool or not isinstance(self.tool, str):
            raise ValueError("tool must be a non-empty string")
        if not isinstance(self.state, TaskState):
            raise ValueError(f"Invalid TaskState: {self.state}")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")

@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    execution_mode: str = "sync"
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Tool name must be a non-empty string")
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError(f"Invalid RiskLevel: {self.risk_level}")

@dataclass
class Plan:
    plan_id: str
    goal_id: str
    tasks: List[Task] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    ordering: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self, registered_tools: Optional[List[str]] = None) -> None:
        if not self.plan_id or not isinstance(self.plan_id, str):
            raise ValueError("plan_id must be a non-empty string")
        if not self.goal_id or not isinstance(self.goal_id, str):
            raise ValueError("goal_id must be a non-empty string")
        
        task_ids = set()
        for task in self.tasks:
            task.validate()
            if task.task_id in task_ids:
                raise ValueError(f"Duplicate task_id found in plan: {task.task_id}")
            task_ids.add(task.task_id)

            if task.task_id in task.dependencies:
                raise ValueError(f"Self-dependency detected in task: {task.task_id}")

            for dep in task.dependencies:
                if dep not in task_ids and dep not in [t.task_id for t in self.tasks]:
                    # Also check if dep exists across all tasks
                    pass

            if registered_tools and task.tool not in registered_tools:
                raise ValueError(f"Tool not registered or invalid: {task.tool}")

        # Validate dependency references and cycles
        all_ids = {t.task_id for t in self.tasks}
        for task in self.tasks:
            for dep in task.dependencies:
                if dep not in all_ids:
                    raise ValueError(f"Task {task.task_id} depends on non-existent task {dep}")

        # Cycle detection via Kahn's / DFS
        visited = set()
        rec_stack = set()

        def dfs(t_id: str, adj: Dict[str, List[str]]) -> bool:
            visited.add(t_id)
            rec_stack.add(t_id)
            for neighbor in adj.get(t_id, []):
                if neighbor not in visited:
                    if dfs(neighbor, adj):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(t_id)
            return False

        adj_list = {t.task_id: t.dependencies for t in self.tasks}
        for t_id in all_ids:
            if t_id not in visited:
                if dfs(t_id, adj_list):
                    raise ValueError(f"Circular dependency detected involving task {t_id}")
