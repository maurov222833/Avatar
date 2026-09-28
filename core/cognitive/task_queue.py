from typing import List, Dict, Optional, Set, Any
from core.cognitive.models import Plan, Task, TaskState, TaskResult

class TaskQueue:
    """
    Cola de tareas cognitiva para administración de dependencias y ejecución continua.
    """
    def __init__(self, plan: Plan):
        plan.validate()
        self.plan = plan
        self.tasks_by_id: Dict[str, Task] = {t.task_id: t for t in plan.tasks}
        self.results_by_id: Dict[str, TaskResult] = {}
        self.completed_task_ids: Set[str] = set()
        self.failed_task_ids: Set[str] = set()
        self.skipped_task_ids: Set[str] = set()

    def get_next_ready_task(self) -> Optional[Task]:
        """
        Retorna la siguiente tarea lista para ser ejecutada (sus dependencias están en COMPLETED).
        """
        for task in self.plan.tasks:
            if task.state in (TaskState.CREATED, TaskState.READY):
                # Verificar si todas sus dependencias están completadas exitosamente
                deps_satisfied = all(dep in self.completed_task_ids for dep in task.dependencies)
                deps_failed = any(dep in self.failed_task_ids or dep in self.skipped_task_ids for dep in task.dependencies)

                if deps_failed:
                    # Si alguna dependencia falló, marcar esta tarea como SKIPPED
                    task.state = TaskState.SKIPPED
                    self.skipped_task_ids.add(task.task_id)
                    continue

                if deps_satisfied:
                    if task.state == TaskState.CREATED:
                        task.transition_to(TaskState.READY)
                    return task
        return None

    def mark_executing(self, task_id: str):
        task = self.tasks_by_id.get(task_id)
        if task and task.state == TaskState.READY:
            task.transition_to(TaskState.EXECUTING)

    def mark_observing(self, task_id: str):
        task = self.tasks_by_id.get(task_id)
        if task and task.state == TaskState.EXECUTING:
            task.transition_to(TaskState.OBSERVING)

    def mark_verifying(self, task_id: str):
        task = self.tasks_by_id.get(task_id)
        if task and task.state == TaskState.OBSERVING:
            task.transition_to(TaskState.VERIFYING)

    def mark_completed(self, task_id: str, result: TaskResult):
        task = self.tasks_by_id.get(task_id)
        if task:
            if task.state == TaskState.VERIFYING:
                task.transition_to(TaskState.COMPLETED)
            elif task.state != TaskState.COMPLETED:
                task.state = TaskState.COMPLETED
            self.results_by_id[task_id] = result
            self.completed_task_ids.add(task_id)

    def mark_failed(self, task_id: str, result: TaskResult):
        task = self.tasks_by_id.get(task_id)
        if task:
            if task.state in (TaskState.EXECUTING, TaskState.OBSERVING, TaskState.VERIFYING):
                task.transition_to(TaskState.FAILED)
            elif task.state != TaskState.FAILED:
                task.state = TaskState.FAILED
            self.results_by_id[task_id] = result
            self.failed_task_ids.add(task_id)
            # Propagar bloqueo a dependientes
            self._propagate_skips()

    def _propagate_skips(self):
        for task in self.plan.tasks:
            if task.state in (TaskState.CREATED, TaskState.READY):
                if any(dep in self.failed_task_ids or dep in self.skipped_task_ids for dep in task.dependencies):
                    task.state = TaskState.SKIPPED
                    self.skipped_task_ids.add(task.task_id)

    def is_finished(self) -> bool:
        terminal_states = (TaskState.COMPLETED, TaskState.FAILED, TaskState.SKIPPED)
        return all(t.state in terminal_states for t in self.plan.tasks)

    def get_progress_summary(self) -> Dict[str, Any]:
        total = len(self.plan.tasks)
        completed = len(self.completed_task_ids)
        failed = len(self.failed_task_ids)
        skipped = len(self.skipped_task_ids)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "is_finished": self.is_finished(),
            "all_success": completed == total
        }
