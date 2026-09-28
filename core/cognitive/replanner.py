import copy
from typing import Dict, Any, List, Optional
from core.cognitive.models import Goal, Task, Plan, TaskState
from core.cognitive.error_classifier import ErrorCategory
from core.cognitive.tool_registry import ToolRegistry, default_tool_registry

class Replanner:
    """
    Replanificador Controlado V2 para Avatar AI.
    Genera planes alternativos validados determinísticamente ante fallos de tareas.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or default_tool_registry

    def generate_replan(
        self,
        goal: Goal,
        current_plan: Plan,
        failed_task: Task,
        error_cat: ErrorCategory,
        modified_arguments: Optional[Dict[str, Any]] = None,
        replacement_task_spec: Optional[Dict[str, Any]] = None
    ) -> Plan:
        # Clonar tareas del plan actual
        new_tasks: List[Task] = []
        
        for task in current_plan.tasks:
            if task.task_id == failed_task.task_id:
                if replacement_task_spec:
                    new_task = Task(
                        task_id=task.task_id,
                        goal_id=goal.goal_id,
                        description=replacement_task_spec.get("description", task.description),
                        tool=replacement_task_spec.get("tool", task.tool),
                        arguments=replacement_task_spec.get("arguments", task.arguments),
                        dependencies=replacement_task_spec.get("dependencies", task.dependencies),
                        state=TaskState.CREATED
                    )
                else:
                    new_task = copy.deepcopy(task)
                    new_task.state = TaskState.CREATED
                    if modified_arguments:
                        new_task.arguments = copy.deepcopy(modified_arguments)
                new_task.validate()
                new_tasks.append(new_task)
            else:
                cloned_task = copy.deepcopy(task)
                if cloned_task.state in (TaskState.FAILED, TaskState.SKIPPED):
                    cloned_task.state = TaskState.CREATED
                new_tasks.append(cloned_task)

        new_plan = Plan(
            plan_id=f"replan-{current_plan.plan_id}-{failed_task.task_id}",
            goal_id=goal.goal_id,
            tasks=new_tasks
        )

        registered_tools = self.tool_registry.list_registered_tools()
        new_plan.validate(registered_tools=registered_tools)
        return new_plan
