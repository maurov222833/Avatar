import subprocess
import os
import sys
import json

class ShellTool:
    """
    Herramienta que le permite al Agente Avatar ejecutar comandos reales de PowerShell / CMD en la PC.
    """
    @staticmethod
    def get_allowed_workspace() -> str:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return os.path.abspath(cfg.get("security", {}).get("allowed_workspace", os.getcwd()))
            except Exception:
                pass
        return os.path.abspath(os.getcwd())

    @staticmethod
    def is_within_workspace(target_path: str, workspace_path: str) -> bool:
        try:
            target_abs = os.path.abspath(target_path).lower()
            ws_abs = os.path.abspath(workspace_path).lower()
            return os.path.commonpath([target_abs, ws_abs]) == ws_abs
        except Exception:
            return False

    @staticmethod
    def execute_command(command: str, cwd: str = None) -> str:
        workspace = ShellTool.get_allowed_workspace()
        if not cwd:
            cwd = workspace
        else:
            cwd = os.path.abspath(cwd)

        if not ShellTool.is_within_workspace(cwd, workspace):
            return f"[Seguridad]: Intento de ejecución fuera del workspace permitido ({workspace})."
        
        create_no_window = 0x08000000 if sys.platform == "win32" else 0
        
        try:
            # Ejecutar en PowerShell de Windows sin ventana visible
            process = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=create_no_window
            )
            
            output = process.stdout.strip() if process.stdout else ""
            error = process.stderr.strip() if process.stderr else ""

            result = f"[Resultado PowerShell (ExitCode: {process.returncode})]:\n"
            if output:
                result += f"stdout:\n{output}\n"
            if error:
                result += f"stderr:\n{error}\n"
            if not output and not error:
                result += "[Comando ejecutado exitosamente sin salida de consola.]\n"
            
            return result.strip()
        except subprocess.TimeoutExpired:
            return "[Error]: El comando tardó demasiado (Timeout de 120s)."
        except Exception as e:
            return f"[Error ejecutando comando]: {str(e)}"

