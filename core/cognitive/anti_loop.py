import json
from typing import List, Dict, Any, Tuple
from core.cognitive.error_classifier import ErrorCategory
from core.cognitive.recovery_policy import RecoveryStrategy

class AntiLoopDetector:
    """
    Detector anti-bucles infinitos para el motor de recuperación de Avatar AI.
    Impide reintentos infinitos sobre la misma combinación de tarea, argumentos, estrategia y error.
    """

    def __init__(self, max_allowed_repetitions: int = 2):
        self.max_allowed_repetitions = max_allowed_repetitions
        self.history: List[Tuple[str, str, ErrorCategory, RecoveryStrategy]] = []

    def record_attempt(
        self,
        task_id: str,
        arguments: Dict[str, Any],
        error_cat: ErrorCategory,
        strategy: RecoveryStrategy
    ):
        args_str = json.dumps(arguments, sort_keys=True)
        self.history.append((task_id, args_str, error_cat, strategy))

    def is_loop_detected(
        self,
        task_id: str,
        arguments: Dict[str, Any],
        error_cat: ErrorCategory,
        strategy: RecoveryStrategy
    ) -> bool:
        args_str = json.dumps(arguments, sort_keys=True)
        target_entry = (task_id, args_str, error_cat, strategy)
        
        count = sum(1 for entry in self.history if entry == target_entry)
        return count >= self.max_allowed_repetitions
