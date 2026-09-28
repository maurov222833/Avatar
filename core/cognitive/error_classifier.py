from enum import Enum
from typing import Dict, Any, Optional
from core.cognitive.models import TaskEvidence, TaskResult, TaskResultStatus

class ErrorCategory(str, Enum):
    RECOVERABLE_TOOL_ERROR = "RECOVERABLE_TOOL_ERROR"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    def is_recoverable(self) -> bool:
        unrecoverable = {
            ErrorCategory.PERMISSION_ERROR,
            ErrorCategory.DEPENDENCY_FAILURE
        }
        return self not in unrecoverable

ErrorClass = ErrorCategory

class ErrorClassifier:
    """
    Clasificador determinista de errores para Avatar AI.
    Analiza evidencias y resultados de ejecución para determinar la categoría de fallo.
    """

    @staticmethod
    def classify_error(
        result: TaskResult,
        evidence: Optional[TaskEvidence] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorCategory:
        if result.status == TaskResultStatus.PASS:
            return ErrorCategory.UNKNOWN_ERROR

        error_str = str(result.error or "").lower()
        output_str = ""

        if evidence and isinstance(evidence.value, dict):
            output_str = str(evidence.value.get("raw_output", "")).lower() + " " + str(evidence.value.get("stderr", "")).lower()
            if evidence.value.get("is_timeout"):
                return ErrorCategory.TIMEOUT

        combined = (error_str + " " + output_str).lower()

        if "access is denied" in combined or "permission denied" in combined or "unauthorized" in combined:
            return ErrorCategory.PERMISSION_ERROR

        if "timeout" in combined or "timed out" in combined:
            return ErrorCategory.TIMEOUT

        if "non-existent" in combined or "not found" in combined or "no existe" in combined or "cannot find path" in combined:
            return ErrorCategory.NOT_FOUND

        if "invalid argument" in combined or "syntax error" in combined or "sintaxis" in combined or "incorrect argument" in combined:
            return ErrorCategory.INVALID_ARGUMENT

        if "success criterion failed" in combined or "criterio" in combined:
            return ErrorCategory.VERIFICATION_FAILURE

        if "validation" in combined or "circular dependency" in combined:
            return ErrorCategory.VALIDATION_ERROR

        if "unmet dependencies" in combined or "dependency failed" in combined:
            return ErrorCategory.DEPENDENCY_FAILURE

        if "http" in combined or "connection error" in combined or "503" in combined or "429" in combined:
            return ErrorCategory.EXTERNAL_SERVICE_ERROR

        if "exitcode" in combined or "exit code" in combined or "command failed" in combined:
            return ErrorCategory.RECOVERABLE_TOOL_ERROR

        return ErrorCategory.UNKNOWN_ERROR
