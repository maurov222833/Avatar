from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.cognitive.adapter import _POWERSHELL_EXIT_CODE, unstructured_tool_output_failed
from core.cognitive.models import TaskEvidence

class CommandObserver:
    """
    Observador especializado en capturar y estructurar evidencias de comandos del sistema.
    Transforma salidas brutas de ejecución en objetos TaskEvidence inmutables.
    """

    @staticmethod
    def observe_command(tool_name: str, raw_output: str, started_at: Optional[str] = None) -> TaskEvidence:
        completed_at = datetime.now(timezone.utc).isoformat()
        if not started_at:
            started_at = completed_at

        if raw_output is None:
            raw_output = ""

        exit_code = -1
        stdout = raw_output
        stderr = ""
        is_timeout = False

        if "[Error]: El comando tardó demasiado (Timeout de 120s)." in raw_output:
            is_timeout = True
            exit_code = 124
            stderr = raw_output
            stdout = ""
        if "[Error" in raw_output or "Error:" in raw_output:
            exit_code = 1
            stderr = raw_output
            stdout = ""
        elif "[Éxito]:" in raw_output or raw_output.startswith("[Éxito]"):
            exit_code = 0
            stdout = raw_output
            stderr = ""
        else:
            match = _POWERSHELL_EXIT_CODE.search(raw_output)
            if match:
                exit_code = int(match.group(1))
            elif unstructured_tool_output_failed(raw_output):
                exit_code = 1
                stderr = raw_output.strip()
                stdout = ""
            else:
                exit_code = 0

        if "stdout:" in raw_output or "stderr:" in raw_output:
            if "stdout:" in raw_output and "stderr:" in raw_output:
                parts = raw_output.split("stdout:")
                subparts = parts[1].split("stderr:")
                stdout = subparts[0].strip()
                stderr = subparts[1].strip()
            elif "stderr:" in raw_output:
                parts = raw_output.split("stderr:")
                stdout = ""
                stderr = parts[1].strip()
            elif "stdout:" in raw_output:
                parts = raw_output.split("stdout:")
                stdout = parts[1].strip()
                stderr = ""

        evidence = TaskEvidence(
            source=tool_name,
            type="command_observation",
            value={
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "is_timeout": is_timeout,
                "raw_output": raw_output,
                "started_at": started_at,
                "completed_at": completed_at
            },
            reliability=1.0
        )
        evidence.validate()
        return evidence
