"""Subagentes de desarrollo desatendido.

Producción (orquestador, server, Telegram) no importa este módulo.
Lo ejercita `tests/test_acceptance_surfaces.py`: el proxy registra
`git status` por el chokepoint. No borrar mientras ese contrato exista.
"""
from core.llm_provider import LLMProvider
from tools.shell_tool import ShellTool
from tools.file_tool import FileTool

class CoderAgent:
    """Sub-Agente especializado en Arquitectura de Software y Código de Alta Calidad."""
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.role_prompt = (
            "Eres el AGENTE PROGRAMADOR ELITE de Avatar.\n"
            "Tu misión es escribir código limpio, modular, optimizado y sin errores.\n"
            "Usa patrones de diseño avanzados y documenta tu solución."
        )

    def generate_code(self, task_description: str) -> str:
        prompt = f"Desarrolla la siguiente solución de código:\n{task_description}"
        return self.llm.generate_response(self.role_prompt, prompt)


class TesterAgent:
    """Sub-Agente especializado en Auditoría, Pruebas Unitarias y Diagnóstico de Consola."""
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.role_prompt = (
            "Eres el AGENTE AUDITOR Y TESTER de Avatar.\n"
            "Tu objetivo es inspeccionar el código, ejecutar pruebas unitarias y diagnosticar fallos en la terminal."
        )

    def analyze_test_output(self, command_output: str) -> str:
        prompt = f"Analiza la salida del siguiente comando de prueba y determina si hubo errores:\n{command_output}"
        return self.llm.generate_response(self.role_prompt, prompt)


class AntigravityProxyAgent:
    """
    Sub-Agente 'Avatar Humano' especializado en colaborar con Antigravity en la CLI.
    Permite delegar la supervisión de un proyecto para que avance desatendido sin que el usuario esté presente.
    """
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.role_prompt = (
            "Eres el AVATAR SUPERVISOR DE DESARROLLO de Avatar.\n"
            "Representas al usuario humano. Tu trabajo es dar instrucciones a la CLI de Antigravity,\n"
            "monitorear los cambios, correr verificaciones y reportar el progreso al usuario."
        )

    def execute_unattended_task(self, project_path: str, instruction: str) -> str:
        """
        Ejecuta una tarea desatendida en el proyecto indicado y retorna un informe completo.
        """
        print(f"\n🤖 [Avatar Proxy]: Asumiendo control del desarrollo en '{project_path}'...")
        
        # 1. Crear instrucción detallada
        plan = self.llm.generate_response(
            self.role_prompt,
            f"Diseña un plan de ejecución paso a paso para cumplir esta meta en {project_path}:\n{instruction}"
        )

        # 2. Estado real del repositorio, vía el chokepoint para que quede registrado.
        #    Antes llamaba a ShellTool directamente, saltándose política y registro.
        if getattr(self, "chokepoint", None) is not None:
            log_result = self.chokepoint.perform(
                act_type="COMMAND",
                args={"command": "git status"},
                mission_id=f"subagent-{abs(hash(instruction)) % 10**8}",
                task_id="git-status",
                execution_id=f"sub-exec-{abs(hash(project_path)) % 10**8}",
            )
        else:
            log_result = "(chokepoint no disponible; estado del repositorio no consultado)"

        # 3. Formatear informe final para el usuario
        summary = (
            f"✅ [Informe de Trabajo Desatendido]\n"
            f"Proyecto: {project_path}\n"
            f"Meta: {instruction}\n\n"
            f"📋 Plan Ejecutado:\n{plan}\n\n"
            f"🔍 Estado Final de la Terminal:\n{log_result}"
        )
        return summary


def run_scoped(chokepoint, scope: str, act_type: str, args: dict, mission_id: str) -> str:
    """Un subagente no hereda el disco entero. La escritura fuera del alcance no llega al acto."""
    from core.path_guard import ALLOW, authorize_path
    target = (args or {}).get("file_path") or ""
    if target:
        decision, reason = authorize_path(target, "write", scope)
        if decision != ALLOW:
            return reason
    return chokepoint.perform(
        act_type=act_type,
        args=args,
        mission_id=mission_id,
        task_id="subagent",
        execution_id="subagent",
    )
