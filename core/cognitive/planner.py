import uuid
from typing import List, Dict, Any, Optional
from core.cognitive.models import Goal, Task, Plan, TaskState
from core.cognitive.tool_registry import ToolRegistry, default_tool_registry

class Planner:
    """
    Planificador Estructurado Cognitivo V2 para Avatar AI.
    Genera y valida planes de ejecución acíclicos (DAG) consultando el ToolRegistry.
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or default_tool_registry

    def create_plan_from_task_specs(
        self,
        goal: Goal,
        task_specs: List[Dict[str, Any]],
        plan_id: Optional[str] = None
    ) -> Plan:
        if not plan_id:
            plan_id = f"plan-{goal.goal_id}"

        tasks: List[Task] = []
        seen_task_ids = set()
        for i, spec in enumerate(task_specs):
            raw_task_id = spec.get("task_id")
            if not raw_task_id or raw_task_id in seen_task_ids:
                task_id = f"T{i+1}"
                while task_id in seen_task_ids:
                    task_id = f"T{len(seen_task_ids)+1}"
            else:
                task_id = raw_task_id
            seen_task_ids.add(task_id)

            tool = spec.get("tool", "COMMAND")
            arguments = spec.get("arguments", {})
            description = spec.get("description", f"Ejecutar {tool}")
            dependencies = spec.get("dependencies", [])

            # Si spec tiene success_criteria o expected_stdout_contains, guardarlo en metadata
            metadata = {}
            if "expected_stdout_contains" in spec:
                metadata["expected_stdout_contains"] = spec["expected_stdout_contains"]
            if "exit_code" in spec:
                metadata["exit_code"] = spec["exit_code"]

            task = Task(
                task_id=task_id,
                goal_id=goal.goal_id,
                description=description,
                tool=tool,
                arguments=arguments,
                dependencies=dependencies,
                state=TaskState.CREATED
            )
            if metadata:
                # Guardar en metadata de argumentos u objeto Task si es necesario
                task.arguments["__criteria__"] = metadata

            task.validate()
            tasks.append(task)

        plan = Plan(
            plan_id=plan_id,
            goal_id=goal.goal_id,
            tasks=tasks
        )

        # Validar plan contra ToolRegistry y detección de ciclos
        registered_tools = self.tool_registry.list_registered_tools()
        plan.validate(registered_tools=registered_tools)
        return plan

    def validate_plan(self, plan: Plan) -> bool:
        registered_tools = self.tool_registry.list_registered_tools()
        plan.validate(registered_tools=registered_tools)
        return True
