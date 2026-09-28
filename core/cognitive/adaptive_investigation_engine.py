from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import uuid
import time
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskEvidence, TaskResult, TaskResultStatus, EvidenceGap
from core.cognitive.verifier import Verifier
from core.cognitive.recovery_engine import RecoveryEngine
from core.cognitive.replanner import Replanner
from core.cognitive.anti_loop import AntiLoopDetector
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier, VerifiedFact
from core.cognitive.semantic_mission_engine import SemanticMissionEngine

class InvestigationState(str, Enum):
    IDLE = "IDLE"
    HYPOTHESIZING = "HYPOTHESIZING"
    EXECUTING_PROBE = "EXECUTING_PROBE"
    EVALUATING_EVIDENCE = "EVALUATING_EVIDENCE"
    MUTATING_STRATEGY = "MUTATING_STRATEGY"
    CONCLUDED_SUCCESS = "CONCLUDED_SUCCESS"
    CONCLUDED_NO_ACTION = "CONCLUDED_NO_ACTION"
    EXHAUSTED_INSUFFICIENT = "EXHAUSTED_INSUFFICIENT"
    BLOCKED = "BLOCKED"

class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    INVESTIGATING = "INVESTIGATING"
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"

@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    proposed_tool: Optional[str] = None
    supporting_evidence: List[TaskEvidence] = field(default_factory=list)
    refuting_evidence: List[TaskEvidence] = field(default_factory=list)

@dataclass
class ResearchBudget:
    max_steps: int = 15
    current_step: int = 0
    max_failed_steps_consecutive: int = 3
    current_failed_steps_consecutive: int = 0
    max_hypothesis_retries: int = 2

    def is_exhausted(self) -> bool:
        return (self.current_step >= self.max_steps or 
                self.current_failed_steps_consecutive >= self.max_failed_steps_consecutive)

@dataclass
class InvestigationResult:
    goal_id: str
    state: InvestigationState
    conclusion_status: str  # SUCCESS, NO_ACTION_REQUIRED, FAILED, BLOCKED, INSUFFICIENT_EVIDENCE
    reason: str
    hypotheses: List[Hypothesis] = field(default_factory=list)
    verified_facts: List[VerifiedFact] = field(default_factory=list)
    executed_tasks_count: int = 0

class AdaptiveInvestigationEngine:
    """
    Motor de Investigación Adaptativa para Avatar AI (Fase 9).
    Gobernador cognitivo de misiones abiertas. Coordina la formulación de hipótesis,
    la mutación adaptativa de estrategias, la verificación física y los límites de presupuesto.
    NO contiene recetas hardcodeadas (general y no específico).
    """

    def __init__(self, goal: Goal, budget: Optional[ResearchBudget] = None):
        self.goal = goal
        self.state = InvestigationState.IDLE
        self.budget = budget or ResearchBudget()
        self.hypotheses: List[Hypothesis] = []
        self.active_hypothesis: Optional[Hypothesis] = None
        self.verified_facts: List[VerifiedFact] = []
        self.evidence_history: List[TaskEvidence] = []

    def start_investigation(self) -> InvestigationState:
        self.state = InvestigationState.HYPOTHESIZING
        # Formular hipótesis inicial
        init_hyp = Hypothesis(
            hypothesis_id=f"hyp-{uuid.uuid4().hex[:8]}",
            statement=f"La misión '{self.goal.objective}' requiere investigación adaptativa del sistema.",
            status=HypothesisStatus.PROPOSED
        )
        self.hypotheses.append(init_hyp)
        self.active_hypothesis = init_hyp
        return self.state

    def propose_hypothesis(self, statement: str, proposed_tool: Optional[str] = None) -> Hypothesis:
        # Prevenir hipótesis duplicadas refutadas
        for h in self.hypotheses:
            if h.statement == statement and h.status == HypothesisStatus.REFUTED:
                # Retornar la hipótesis refutada para evitar ciclo
                return h

        h = Hypothesis(
            hypothesis_id=f"hyp-{uuid.uuid4().hex[:8]}",
            statement=statement,
            status=HypothesisStatus.PROPOSED,
            proposed_tool=proposed_tool
        )
        self.hypotheses.append(h)
        self.active_hypothesis = h
        self.state = InvestigationState.HYPOTHESIZING
        return h

    def calculate_evidence_gap(
        self,
        goal: Goal,
        executed_steps_count: int,
        last_task: Task,
        last_evidence: Optional[TaskEvidence]
    ) -> EvidenceGap:
        tool_name = last_task.tool if last_task else "UNKNOWN"
        
        if tool_name == "LIST_DIR":
            current_ev = "Estructura de directorios y lista de archivos del proyecto."
            req_ev = f"Evidencia sobre la implementación interna del código, arquitectura o comportamiento técnico para el objetivo: '{goal.objective}'."
            gap = "Únicamente se posee la lista de archivos. Falta inspección del código fuente o ejecución de pruebas de diagnóstico."
            target = "Obtener evidencia sobre la implementación interna de los componentes principales, flujo del sistema o estado de las pruebas."
        elif tool_name == "READ_FILE":
            file_ref = last_task.arguments.get("file_path", "archivo") if last_task and last_task.arguments else "archivo"
            current_ev = f"Inspección del contenido del archivo '{file_ref}'."
            req_ev = f"Evidencia completa de verificación funcional o diagnóstico para el objetivo: '{goal.objective}'."
            gap = "Se ha inspeccionado código fuente, pero falta verificar la ejecución funcional o analizar componentes dependientes."
            target = "Obtener evidencia funcional mediante ejecución de pruebas diagnósticas o inspección de módulos relacionados."
        else:
            current_ev = f"Ejecución exitosa de herramienta {tool_name}."
            req_ev = f"Evidencia comprobable suficiente para satisfacer el objetivo: '{goal.objective}'."
            gap = "La evidencia física recopilada es parcial y requiere mayor profundización."
            target = "Obtener nueva evidencia técnica comprobable que fundamente las conclusiones o cambios en el sistema."

        return EvidenceGap(
            current_evidence=current_ev,
            required_evidence=req_ev,
            evidence_gap=gap,
            next_information_target=target,
            rationale=f"Paso {executed_steps_count} completado con éxito, pero la investigación requiere recopilar evidencia adicional.",
            confidence=0.9
        )

    def evaluate_task_step(
        self,
        task: Task,
        evidence: Optional[TaskEvidence],
        task_result: TaskResult,
        verified_fact: Optional[VerifiedFact] = None
    ) -> Dict[str, Any]:
        self.budget.current_step += 1
        self.state = InvestigationState.EVALUATING_EVIDENCE

        if evidence:
            self.evidence_history.append(evidence)
        if verified_fact:
            self.verified_facts.append(verified_fact)

        is_success = task_result.status.is_success()

        if is_success:
            self.budget.current_failed_steps_consecutive = 0
            if self.active_hypothesis:
                self.active_hypothesis.status = HypothesisStatus.CONFIRMED
                if evidence:
                    self.active_hypothesis.supporting_evidence.append(evidence)
        else:
            self.budget.current_failed_steps_consecutive += 1
            if self.active_hypothesis:
                self.active_hypothesis.status = HypothesisStatus.REFUTED
                if evidence:
                    self.active_hypothesis.refuting_evidence.append(evidence)

        # Evaluar presupuesto
        if self.budget.is_exhausted():
            self.state = InvestigationState.EXHAUSTED_INSUFFICIENT
            return {
                "action": "TERMINATE",
                "status": "INSUFFICIENT_EVIDENCE",
                "reason": "Research budget or consecutive tool failure limit exhausted.",
                "state": self.state
            }

        # Si la herramienta falló, activar mutación adaptativa / replanning
        if not is_success:
            self.state = InvestigationState.MUTATING_STRATEGY
            # Invocar RecoveryEngine de forma integrada
            rec_engine = RecoveryEngine()
            dummy_plan = TaskEvidence(source="adapter", type="dummy", value={}, reliability=1.0)
            new_plan, record = rec_engine.handle_task_failure(
                goal=self.goal,
                plan=None,
                task=task,
                result=task_result,
                evidence=evidence
            )
            raw_err = task_result.error or (evidence.value.get("stdout", "") if evidence and isinstance(evidence.value, dict) else "")
            formatted_err = SemanticMissionEngine.format_structured_error_context(str(raw_err))
            cognitive_instruction = (
                f"[MOTOR DE INVESTIGACIÓN ADAPTATIVA - MUTACIÓN DE ESTRATEGIA]:\n"
                f"La herramienta '{task.tool}' falló. Estrategia de recuperación sugerida: [{record.strategy.value}].\n"
                f"Detalle del error:\n{formatted_err}\n"
                "INSTRUCCIÓN COGNITIVA:\n"
                "- No re-ejecutes exactamente la misma orden sin modificar parámetros o entorno.\n"
                "- Reevalúa la causa del fallo y selecciona una estrategia o herramienta alternativa entre tus herramientas disponibles.\n"
                "- Emite inmediatamente la llamada a herramienta adecuada."
            )
            return {
                "action": "RECOVER_OR_REPLAN",
                "status": "EXECUTING",
                "reason": f"Tool execution failed. Strategy mutation suggested: {record.strategy.value}",
                "recovery_plan": {"action": record.strategy.value, "record": record},
                "cognitive_instruction": cognitive_instruction,
                "formatted_error": formatted_err,
                "state": self.state
            }

        # Cuando la herramienta se ejecuta con éxito pero se requiere mayor evidencia (SUCCESS + INSUFFICIENT_EVIDENCE)
        evidence_gap_obj = self.calculate_evidence_gap(
            goal=self.goal,
            executed_steps_count=self.budget.current_step,
            last_task=task,
            last_evidence=evidence
        )
        cognitive_instruction = evidence_gap_obj.format_cognitive_instruction()

        self.state = InvestigationState.EXECUTING_PROBE
        return {
            "action": "CONTINUE",
            "status": "EXECUTING",
            "reason": "Step completed successfully. Continuing investigation with evidence gap analysis.",
            "evidence_gap": evidence_gap_obj.to_dict(),
            "cognitive_instruction": cognitive_instruction,
            "state": self.state
        }

    def evaluate_mission_conclusion(
        self,
        executed_steps: List[Dict[str, Any]],
        llm_text: str
    ) -> InvestigationResult:
        """
        Determina de forma determinista la conclusión de la misión abierta.
        Garantiza que la investigación concluya formalmente solo bajo criterios justificados.
        """
        has_verified_facts = any(f.verified for f in self.verified_facts)
        text_lower = llm_text.lower()

        # 1. Caso NO_ACTION_REQUIRED: evidenciado por pruebas de regresión exitosas sin cambio necesario
        if ("no_action_required" in text_lower or "no se requiere modificación" in text_lower or "no existe debilidad" in text_lower) and has_verified_facts:
            self.state = InvestigationState.CONCLUDED_NO_ACTION
            return InvestigationResult(
                goal_id=self.goal.goal_id,
                state=self.state,
                conclusion_status="NO_ACTION_REQUIRED",
                reason="Investigation proved no modification required backed by verified physical facts.",
                hypotheses=self.hypotheses,
                verified_facts=self.verified_facts,
                executed_tasks_count=len(executed_steps)
            )

        # 2. Caso SUCCESS: comprobado por modificación física verificada en disco + suite de pruebas PASS
        has_file_write_fact = any(f.fact_type in ["WRITE_FILE", "MODIFY_FILE"] and f.verified for f in self.verified_facts)
        has_test_fact = any(f.fact_type == "TEST" and f.verified for f in self.verified_facts)

        if has_file_write_fact and has_test_fact:
            self.state = InvestigationState.CONCLUDED_SUCCESS
            return InvestigationResult(
                goal_id=self.goal.goal_id,
                state=self.state,
                conclusion_status="SUCCESS",
                reason="Engineering mission completed with verified file changes and clean test suite regression.",
                hypotheses=self.hypotheses,
                verified_facts=self.verified_facts,
                executed_tasks_count=len(executed_steps)
            )

        # 3. Caso INSUFFICIENT_EVIDENCE por presupuesto o falta de verificación física
        if self.budget.is_exhausted() or not has_verified_facts:
            self.state = InvestigationState.EXHAUSTED_INSUFFICIENT
            return InvestigationResult(
                goal_id=self.goal.goal_id,
                state=self.state,
                conclusion_status="INSUFFICIENT_EVIDENCE",
                reason="Investigation did not collect sufficient verified physical facts before step limit.",
                hypotheses=self.hypotheses,
                verified_facts=self.verified_facts,
                executed_tasks_count=len(executed_steps)
            )

        # Caso FAILED genérico
        return InvestigationResult(
            goal_id=self.goal.goal_id,
            state=InvestigationState.BLOCKED,
            conclusion_status="BLOCKED",
            reason="Mission blocked due to unresolvable environment or tool errors.",
            hypotheses=self.hypotheses,
            verified_facts=self.verified_facts,
            executed_tasks_count=len(executed_steps)
        )
