import os
import json

class FileTool:
    """
    Herramienta que permite al Agente Avatar leer, escribir y listar archivos en la PC.
    """
    @staticmethod
    def get_allowed_workspace() -> str:
        from core.paths import config_path as resolve_config_path
        path = resolve_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return os.path.abspath(cfg.get("security", {}).get("allowed_workspace", os.getcwd()))
            except Exception:
                pass
        return os.path.abspath(os.getcwd())

    @staticmethod
    def is_within_workspace(filepath: str, workspace: str) -> bool:
        try:
            # On POSIX, a Windows drive path (C:\...) must not resolve as a child of the repo.
            raw = str(filepath).strip()
            if os.name != "nt":
                if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
                    return False
                norm = raw.replace("\\", "/")
                if norm.startswith("//") or norm.startswith("\\\\"):
                    return False
            target_abs = os.path.abspath(filepath).lower()
            ws_abs = os.path.abspath(workspace).lower()
            return os.path.commonpath([target_abs, ws_abs]) == ws_abs
        except Exception:
            return False

    @staticmethod
    def read_file(filepath: str) -> str:
        workspace = FileTool.get_allowed_workspace()
        if not FileTool.is_within_workspace(filepath, workspace):
            return f"[Seguridad]: Acceso a archivo fuera del workspace denegado ({filepath})."
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[Error al leer archivo {filepath}]: {str(e)}"

    @staticmethod
    def write_file(filepath: str, content: str) -> str:
        workspace = FileTool.get_allowed_workspace()
        if not FileTool.is_within_workspace(filepath, workspace):
            return f"[Seguridad]: Escritura fuera del workspace denegada ({filepath})."
        from core.path_guard import ALLOW, authorize_path
        decision, why = authorize_path(filepath, "write", workspace)
        if decision != ALLOW:
            return f"[Seguridad]: {why} ({filepath})."
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[Éxito]: Archivo creado/actualizado en {filepath}"
        except Exception as e:
            return f"[Error al escribir archivo {filepath}]: {str(e)}"

    @staticmethod
    def list_dir(path: str = ".") -> str:
        workspace = FileTool.get_allowed_workspace()
        if not FileTool.is_within_workspace(path, workspace):
            return f"[Seguridad]: Listado fuera del workspace denegado ({path})."
        try:
            items = os.listdir(path)
            return "\n".join(items) if items else "[Carpeta vacía]"
        except Exception as e:
            return f"[Error al listar directorio {path}]: {str(e)}"

