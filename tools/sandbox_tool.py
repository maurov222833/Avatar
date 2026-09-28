import os
import sys
import subprocess
import shutil

class SandboxTool:
    """
    MÓDULO 4: Entorno de Pruebas Aislado (Sandbox Venv) para Proyecto Avatar.
    Permite probar código experimental en una caja de cristal aislada sin riesgo para Windows.
    """
    def __init__(self, sandbox_dir: str = "b:/PROYECTOS ANTIGRAVITY/Avatar/sandbox_env"):
        self.sandbox_dir = sandbox_dir

    def create_sandbox() -> str:
        sandbox_path = "b:/PROYECTOS ANTIGRAVITY/Avatar/sandbox_env"
        try:
            if not os.path.exists(sandbox_path):
                subprocess.run([sys.executable, "-m", "venv", sandbox_path], check=True)
                return f"[OK]: Entorno aislado Sandbox creado en {sandbox_path}"
            return f"[OK]: Sandbox activo en {sandbox_path}"
        except Exception as e:
            return f"[Error al crear Sandbox]: {str(e)}"

    @staticmethod
    def run_in_sandbox(script_path: str) -> str:
        sandbox_python = os.path.join("b:/PROYECTOS ANTIGRAVITY/Avatar/sandbox_env", "Scripts", "python.exe")
        if not os.path.exists(sandbox_python):
            SandboxTool.create_sandbox()
            
        try:
            res = subprocess.run([sandbox_python, script_path], capture_output=True, text=True, timeout=60)
            return f"[Salida Sandbox]:\n{res.stdout}\n[Errores]:\n{res.stderr}"
        except Exception as e:
            return f"[Error de ejecución en Sandbox]: {str(e)}"
