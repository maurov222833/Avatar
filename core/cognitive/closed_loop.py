from typing import Dict, Any, List, Optional, Callable
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskResult, TaskResultStatus, Plan
from core.cognitive.observer import CommandObserver
from core.cognitive.verifier import Verifier

class ClosedLoopExecutor:
    """
    Motor del Bucle Cerrado Cognitivo (Closed-Loop Engine) para Avatar AI.
    Plan → Validar → Tarea → Ejecutar → Observar → Verificar → Siguiente Tarea / Bloqueo.
    """

    def __init__(self, tool_dispatcher: Callable[[str, Dict[str, Any]], str]):
        self.tool_dispatcher = tool_dispatcher

    def execute_plan(self, goal: Goal, plan: Plan) -> List[Dict[str, Any]]:
        plan.validate()
        goal.status = GoalState.EXECUTING

        results_by_task_id: Dict[str, TaskResult] = {}
        execution_history: List[Dict[str, Any]] = []

        # Determinar orden de tareas
        task_map = {t.task_id: t for t in plan.tasks}
        completed_task_ids = set()
        failed_task_ids = set()

        for task in plan.tasks:
            # Comprobar si las dependencias de la tarea fueron satisfechas
            unmet_deps = [dep for dep in task.dependencies if dep not in completed_task_ids]
            if unmet_deps:
                # Tarea no puede ejecutarse debido a dependencias no completadas o fallidas
                task.state = TaskState.SKIPPED
                failed_task_ids.add(task.task_id)
                execution_history.append({
                    "task_id": task.task_id,
                    "state": TaskState.SKIPPED,
                    "reason": f"Unmet dependencies: {unmet_deps}",
                    "task_result": None
                })
                continue

            # 1. Transición a READY -> EXECUTING
            task.transition_to(TaskState.READY)
            task.transition_to(TaskState.EXECUTING)

            # 2. Ejecutar herramienta nativa existente
            tool_output = self.tool_dispatcher(task.tool, task.arguments)

            # 3. Observar salida real del sistema
            task.transition_to(TaskState.OBSERVING)
            evidence = CommandObserver.observe_command(task.tool, tool_output)

            # 4. Verificar evidencia contra criterios explícitos
            task.transition_to(TaskState.VERIFYING)
            criteria = task.arguments.get("__criteria__", {})
            task_result = Verifier.verify(task.task_id, evidence, criteria)

            # 5. Determinar estado final de la tarea y propagación
            if task_result.status.is_success():
                task.transition_to(TaskState.COMPLETED)
                completed_task_ids.add(task.task_id)
            else:
                task.transition_to(TaskState.FAILED)
                failed_task_ids.add(task.task_id)

            results_by_task_id[task.task_id] = task_result
            execution_history.append({
                "task_id": task.task_id,
                "state": task.state,
                "tool_output": tool_output,
                "evidence": evidence,
                "task_result": task_result
            })

        # Actualizar estado final del Goal
        if len(completed_task_ids) == len(plan.tasks):
            goal.status = GoalState.COMPLETED
        else:
            goal.status = GoalState.FAILED

        return execution_history
