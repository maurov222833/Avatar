from typing import Dict, Any, List, Optional, Callable
from core.cognitive.models import Goal, GoalState, TaskState, TaskResult, TaskResultStatus, Plan
from core.cognitive.task_queue import TaskQueue
from core.cognitive.observer import CommandObserver
from core.cognitive.verifier import Verifier

from core.cognitive.recovery_engine import RecoveryEngine
from core.cognitive.recovery_policy import RecoveryStrategy

class ContinuousExecutionEngine:
    """
    Motor de Ejecución Continua y Autodesarrollo Controlado V2 para Avatar AI.
    Mantiene el bucle autónomo sin requerir intervención humana entre tareas ready.
    Soporta CheckpointEngine (Fase 2) para checkpoints atómicos pre/post ejecución de herramientas.
    """

    def __init__(
        self,
        tool_dispatcher: Callable[[str, Dict[str, Any]], str],
        recovery_engine: Optional[RecoveryEngine] = None,
        checkpoint_engine: Optional[Any] = None,
        max_auto_retries_per_task: int = 2,
        max_total_steps: int = 25
    ):
        self.tool_dispatcher = tool_dispatcher
        self.recovery_engine = recovery_engine or RecoveryEngine()
        self.checkpoint_engine = checkpoint_engine
        self.max_auto_retries_per_task = max_auto_retries_per_task
        self.max_total_steps = max_total_steps

    def execute_continuous_plan(self, goal: Goal, plan: Plan) -> Dict[str, Any]:
        plan.validate()
        goal.status = GoalState.EXECUTING

        queue = TaskQueue(plan)
        execution_trace: List[Dict[str, Any]] = []
        step_count = 0

        while not queue.is_finished() and step_count < self.max_total_steps:
            task = queue.get_next_ready_task()
            if not task:
                break

            step_count += 1
            queue.mark_executing(task.task_id)

            attempts = 0
            task_success = False
            last_result: Optional[TaskResult] = None
            last_evidence = None
            last_output = ""

            while attempts <= self.max_auto_retries_per_task and not task_success:
                attempts += 1
                
                # Checkpoint PRE_TOOL_EXECUTION en SQLite WAL
                mission_id = goal.metadata.get("mission_id", f"msn_{goal.goal_id[:8]}")
                if self.checkpoint_engine:
                    try:
                        self.checkpoint_engine.save_pre_tool_checkpoint(
                            mission_id=mission_id,
                            task_id=task.task_id,
                            step_index=step_count,
                            description=task.description,
                            tool_name=task.tool,
                            tool_args=task.arguments
                        )
                    except Exception as chk_err:
                        print(f"[ContinuousExecutionEngine Warning]: Pre-checkpoint failed: {chk_err}")

                # Ejecución nativa del comando
                tool_output = self.tool_dispatcher(task.tool, task.arguments)
                last_output = tool_output

                # Observar salida real del sistema
                queue.mark_observing(task.task_id)
                evidence = CommandObserver.observe_command(task.tool, tool_output)
                last_evidence = evidence

                # Verificar evidencia determinísticamente
                queue.mark_verifying(task.task_id)
                criteria = task.arguments.get("__criteria__", {})
                task_result = Verifier.verify(task.task_id, evidence, criteria)
                last_result = task_result

                if task_result.status.is_success():
                    task_success = True
                    queue.mark_completed(task.task_id, task_result)
                    if self.checkpoint_engine:
                        try:
                            self.checkpoint_engine.save_post_tool_checkpoint(
                                mission_id=mission_id,
                                task_id=task.task_id,
                                execution_output=tool_output,
                                evidence_data={"source": task.tool}
                            )
                            self.checkpoint_engine.mark_verified(
                                mission_id=mission_id,
                                task_id=task.task_id,
                                claim=f"Verified task {task.task_id}",
                                evidence_data={"output": tool_output[:200]}
                            )
                        except Exception as chk_err:
                            print(f"[ContinuousExecutionEngine Warning]: Post-checkpoint failed: {chk_err}")
                else:
                    new_plan, rec_record = self.recovery_engine.handle_task_failure(
                        goal=goal, plan=plan, task=task, result=task_result, evidence=evidence
                    )
                    if rec_record.strategy == RecoveryStrategy.ABORT or not new_plan:
                        queue.mark_failed(task.task_id, task_result)
                        break
                    else:
                        plan = new_plan

            execution_trace.append({
                "step": step_count,
                "task_id": task.task_id,
                "description": task.description,
                "tool": task.tool,
                "arguments": task.arguments,
                "state": task.state,
                "attempts": attempts,
                "output": last_output,
                "evidence": last_evidence,
                "task_result": last_result
            })

            if task.state == TaskState.FAILED:
                # Si una tarea falla críticamente, detener la ejecución del plan
                break

        summary = queue.get_progress_summary()
        if summary["all_success"]:
            goal.status = GoalState.COMPLETED
        else:
            goal.status = GoalState.FAILED

        return {
            "goal_id": goal.goal_id,
            "goal_status": goal.status,
            "summary": summary,
            "trace": execution_trace,
            "queue": queue
        }
