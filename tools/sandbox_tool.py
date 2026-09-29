import os
import sys
import subprocess
import shutil
from typing import Optional

from core.paths import sandbox_dir as default_sandbox_dir

class SandboxTool:
    """
    MÓDULO 4: Entorno de Pruebas Aislado (Sandbox Venv) para Proyecto Avatar.
    Permite probar código experimental en una caja de cristal aislada sin riesgo para Windows.
    """
    def __init__(self, sandbox_dir: Optional[str] = None):
        self.sandbox_dir = sandbox_dir if sandbox_dir is not None else default_sandbox_dir()

    @staticmethod
    def create_sandbox() -> str:
        sandbox_path = default_sandbox_dir()
        try:
            if not os.path.exists(sandbox_path):
                subprocess.run([sys.executable, "-m", "venv", sandbox_path], check=True)
                return f"[OK]: Entorno aislado Sandbox creado en {sandbox_path}"
            return f"[OK]: Sandbox activo en {sandbox_path}"
        except Exception as e:
            return f"[Error al crear Sandbox]: {str(e)}"

    @staticmethod
    def run_in_sandbox(script_path: str) -> str:
        sandbox_path = default_sandbox_dir()
        sandbox_python = os.path.join(sandbox_path, "Scripts", "python.exe")
        if not os.path.exists(sandbox_python):
            sandbox_python = os.path.join(sandbox_path, "bin", "python")
        if not os.path.exists(sandbox_python):
            SandboxTool.create_sandbox()
            
        try:
            res = subprocess.run([sandbox_python, script_path], capture_output=True, text=True, timeout=60)
            return f"[Salida Sandbox]:\n{res.stdout}\n[Errores]:\n{res.stderr}"
        except Exception as e:
            return f"[Error de ejecución en Sandbox]: {str(e)}"
