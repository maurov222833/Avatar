from typing import Dict, Any, Optional, List
from core.cognitive.models import TaskEvidence, TaskResult, TaskResultStatus

class Verifier:
    """
    Motor de verificación determinista de criterios de éxito.
    Evalúa evidencia estructurada contra criterios explícitos sin heurísticas del LLM.
    """

    @staticmethod
    def verify(
        task_id: str,
        evidence: Optional[TaskEvidence],
        criteria: Optional[Dict[str, Any]] = None
    ) -> TaskResult:
        if evidence is None:
            res = TaskResult(
                task_id=task_id,
                status=TaskResultStatus.NO_EVIDENCE,
                evidence=[],
                error="No evidence captured for task execution."
            )
            res.validate()
            return res

        if not isinstance(evidence.value, dict):
            res = TaskResult(
                task_id=task_id,
                status=TaskResultStatus.UNKNOWN,
                evidence=[evidence],
                error="Evidence value format is invalid or ambiguous."
            )
            res.validate()
            return res

        exit_code = evidence.value.get("exit_code")
        stdout = evidence.value.get("stdout", "")
        stderr = evidence.value.get("stderr", "")

        if exit_code is None:
            res = TaskResult(
                task_id=task_id,
                status=TaskResultStatus.UNKNOWN,
                evidence=[evidence],
                error="Evidence lacks exit_code attribute."
            )
            res.validate()
            return res

        # Criterios por defecto
        if not criteria:
            criteria = {}

        expected_exit_code = criteria.get("exit_code", 0)
        expected_stdout_contains = criteria.get("expected_stdout_contains")

        # 1. Comprobar Exit Code
        if exit_code != expected_exit_code:
            res = TaskResult(
                task_id=task_id,
                status=TaskResultStatus.FAIL,
                evidence=[evidence],
                error=f"Exit code {exit_code} does not match expected {expected_exit_code}. stderr: {stderr}"
            )
            res.validate()
            return res

        # 2. Comprobar criterios de texto de salida si fueron especificados
        full_output = f"{stdout}\n{stderr}\n{evidence.value.get('raw_output', '')}".strip()
        if expected_stdout_contains:
            patterns: List[str] = (
                [expected_stdout_contains]
                if isinstance(expected_stdout_contains, str)
                else expected_stdout_contains
            )

            for pattern in patterns:
                if pattern not in stdout and pattern not in full_output:
                    res = TaskResult(
                        task_id=task_id,
                        status=TaskResultStatus.FAIL,
                        evidence=[evidence],
                        error=f"Success criterion failed: '{pattern}' not found in output. Actual output: '{full_output}'"
                    )
                    res.validate()
                    return res

        # Todos los criterios cumplidos determinísticamente
        res = TaskResult(
            task_id=task_id,
            status=TaskResultStatus.PASS,
            evidence=[evidence],
            outputs={"stdout": stdout, "exit_code": exit_code}
        )
        res.validate()
        return res
