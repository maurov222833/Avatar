import uuid
import re
from typing import Dict, Any, List, Optional
from core.cognitive.models import (
    Goal,
    GoalState,
    Task,
    TaskState,
    TaskEvidence,
    TaskResult,
    TaskResultStatus,
    Plan,
    TaskStateMachine,
)

# Informes que Avatar emite cuando la herramienta no corrió o falló, y que no
# traen un ExitCode de PowerShell. Se miran al inicio del texto: un listado que
# solo menciona la palabra "error" no es un fallo.
_DENIED_OR_ERROR_PREFIXES = (
    "[Bloqueado por política",
    "Bloqueado por política",
    "[DRY-RUN]",
    "[Seguridad]",
    "[Error",
    "RESULT:ERROR",
)

_POWERSHELL_EXIT_CODE = re.compile(
    r"\[Resultado PowerShell \(ExitCode:\s*(-?\d+)\)\]:"
)


def unstructured_tool_output_failed(raw_output: str) -> bool:
    """True cuando el informe es una denegación o un error y no trae ExitCode."""
    if not isinstance(raw_output, str) or not raw_output:
        return False
    if _POWERSHELL_EXIT_CODE.search(raw_output):
        return False
    head = raw_output.lstrip()
    return any(head.startswith(prefix) for prefix in _DENIED_OR_ERROR_PREFIXES)


class CognitiveAdapter:
    """
    Adaptador Cognitivo V2 para Avatar AI.
    Conecta el flujo de ejecución de Avatar (Orchestrator + Function Calling)
    con los contratos formales de models.py (Goal, Task, Plan, TaskEvidence, TaskResult).
    """

    @staticmethod
    def create_goal(objective: str, goal_id: Optional[str] = None) -> Goal:
        if not goal_id:
            goal_id = f"goal-{uuid.uuid4().hex[:8]}"
        goal = Goal(
            goal_id=goal_id,
            objective=objective,
            status=GoalState.CREATED
        )
        goal.validate()
        return goal

    @staticmethod
    def create_task(
        goal_id: str,
        tool: str,
        arguments: Dict[str, Any],
        description: str = "",
        task_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None
    ) -> Task:
        if not task_id:
            task_id = f"task-{uuid.uuid4().hex[:8]}"
        if not description:
            description = f"Execute tool {tool} with args {arguments}"
        
        task = Task(
            task_id=task_id,
            goal_id=goal_id,
            description=description,
            tool=tool,
            arguments=arguments,
            dependencies=dependencies or [],
            state=TaskState.CREATED
        )
        task.validate()
        return task

    @staticmethod
    def create_single_task_plan(goal: Goal, task: Task, plan_id: Optional[str] = None) -> Plan:
        if not plan_id:
            plan_id = f"plan-{goal.goal_id}"
        
        plan = Plan(
            plan_id=plan_id,
            goal_id=goal.goal_id,
            tasks=[task]
        )
        plan.validate()
        return plan

    @staticmethod
    def create_evidence_from_tool_output(tool_name: str, raw_output: str) -> Optional[TaskEvidence]:
        if raw_output is None:
            return None

        exit_code = 0
        stdout = raw_output
        stderr = ""

        # El ExitCode de PowerShell manda. Sin él, una denegación o un error
        # del propio Avatar no puede quedar como éxito (exit_code 0 → PASS).
        match = _POWERSHELL_EXIT_CODE.search(raw_output)
        if match:
            exit_code = int(match.group(1))
        elif unstructured_tool_output_failed(raw_output):
            exit_code = 1
            stderr = raw_output.strip()

        # Extraer stdout y stderr si están formateados
        if "stdout:" in raw_output:
            parts = raw_output.split("stdout:")
            subparts = parts[1].split("stderr:")
            stdout = subparts[0].strip()
            if len(subparts) > 1:
                stderr = subparts[1].strip()

        evidence = TaskEvidence(
            source=tool_name,
            type="command_result",
            value={
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "raw_output": raw_output
            },
            reliability=1.0
        )
        evidence.validate()
        return evidence

    @staticmethod
    def build_task_result(
        task_id: str,
        evidence: Optional[TaskEvidence] = None,
        forced_status: Optional[TaskResultStatus] = None,
        criteria: Optional[Dict[str, Any]] = None
    ) -> TaskResult:
        """
        Construye determinísticamente un TaskResult delegando al Verifier oficial.
        El Verifier es la ÚNICA AUTORIDAD de éxito del sistema.
        """
        if forced_status is not None:
            if forced_status == TaskResultStatus.PASS and not evidence:
                raise ValueError("Cannot set PASS status without valid supporting evidence.")
            result = TaskResult(
                task_id=task_id,
                status=forced_status,
                evidence=[evidence] if evidence else []
            )
            result.validate()
            return result

        from core.cognitive.verifier import Verifier
        return Verifier.verify(task_id=task_id, evidence=evidence, criteria=criteria)

    @staticmethod
    def build_result_from_llm_text_attempt(task_id: str, llm_text: str) -> TaskResult:
        """
        Intento de declarar éxito basado ÚNICAMENTE en texto de LLM.
        Regla Cognitiva: El texto del LLM NO constituye evidencia. Retorna UNKNOWN o NO_EVIDENCE.
        """
        result = TaskResult(
            task_id=task_id,
            status=TaskResultStatus.NO_EVIDENCE,
            evidence=[],
            outputs={"llm_text": llm_text},
            error="LLM text response alone does not constitute system execution evidence."
        )
        result.validate()
        return result
