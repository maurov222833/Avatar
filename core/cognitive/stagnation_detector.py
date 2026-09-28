from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

class StagnationState(str, Enum):
    ACTIVE = "ACTIVE"
    STAGNANT = "STAGNANT"
    REASSESS = "REASSESS"
    REPLAN = "REPLAN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class StagnationDetector:
    """
    Detector de Estancamiento Cognitivo para Avatar AI (Fase 12 / F-05).
    Detecta patrones de estancamiento como:
    1. Giros de texto consecutivos sin llamadas a herramientas nativas.
    2. Invocaciones repetidas de la misma herramienta con los mismos argumentos.
    3. Comandos fallidos consecutivos repetidos sin cambio de estrategia.
    Asegura la transición de estado: ACTIVE -> STAGNANT -> REASSESS -> REPLAN / INSUFFICIENT_EVIDENCE.
    """

    def __init__(
        self,
        max_consecutive_text_turns: int = 2,
        max_repeated_tool_calls: int = 2,
        max_failed_commands: int = 3
    ):
        self.max_consecutive_text_turns = max_consecutive_text_turns
        self.max_repeated_tool_calls = max_repeated_tool_calls
        self.max_failed_commands = max_failed_commands

        self.state = StagnationState.ACTIVE
        self.consecutive_text_turns = 0
        self.tool_call_history: List[Tuple[str, Dict[str, Any], bool]] = []
        self.failed_command_history: List[str] = []
        self.last_stagnation_reason: Optional[str] = None

    def record_text_turn(self, text: str) -> StagnationState:
        """
        Registra una respuesta de texto del LLM en la que NO se invocó herramienta nativa.
        """
        self.consecutive_text_turns += 1

        if self.consecutive_text_turns == 1:
            self.state = StagnationState.ACTIVE
        elif self.consecutive_text_turns == 2:
            self.state = StagnationState.STAGNANT
            self.last_stagnation_reason = (
                f"LLM produced {self.consecutive_text_turns} consecutive text responses without tool invocations."
            )
        elif self.consecutive_text_turns == 3:
            self.state = StagnationState.REASSESS
            self.last_stagnation_reason = (
                f"LLM produced {self.consecutive_text_turns} consecutive text responses. Reassessment required."
            )
        else:
            self.state = StagnationState.REPLAN
            self.last_stagnation_reason = (
                f"LLM is stuck in text-only loop after {self.consecutive_text_turns} turns. Force strategy change or conclude insufficient evidence."
            )

        return self.state

    def record_tool_call(self, tool_name: str, args: Dict[str, Any], is_success: bool) -> StagnationState:
        """
        Registra la ejecución de una herramienta y restablece el contador de respuestas de texto.
        """
        self.consecutive_text_turns = 0
        self.tool_call_history.append((tool_name, args, is_success))

        # 1. Comprobar repeticiones de la misma herramienta con los mismos argumentos
        recent_same = [
            (t, a) for t, a, _ in self.tool_call_history[-self.max_repeated_tool_calls:]
            if t == tool_name and a == args
        ]
        if len(recent_same) >= self.max_repeated_tool_calls and not is_success:
            self.state = StagnationState.STAGNANT
            self.last_stagnation_reason = (
                f"Tool '{tool_name}' with args {args} was executed {len(recent_same)} times repeatedly and failed."
            )
            return self.state

        # 2. Comprobar comandos fallidos consecutivos
        if not is_success:
            cmd_str = f"{tool_name}:{args}"
            self.failed_command_history.append(cmd_str)
            if len(self.failed_command_history) >= self.max_failed_commands:
                self.state = StagnationState.REASSESS
                self.last_stagnation_reason = (
                    f"Consecutive tool failure limit reached ({len(self.failed_command_history)} failed tools)."
                )
                return self.state
        else:
            self.failed_command_history.clear()

        self.state = StagnationState.ACTIVE
        self.last_stagnation_reason = None
        return self.state

    def get_stagnation_directive(self) -> Optional[str]:
        """
        Genera una directiva operativa clara para inyectar en el contexto del LLM cuando se detecta estancamiento.
        """
        if self.state == StagnationState.ACTIVE:
            return None

        reason = self.last_stagnation_reason or "Cognitive stagnation detected."

        if self.state in [StagnationState.STAGNANT, StagnationState.REASSESS]:
            return (
                f"[DIRECTIVA DE SEÑAL COGNITIVA DE ESTANCAMIENTO - Estado: {self.state.value}]:\n"
                f"Advertencia: {reason}\n"
                "SITUACIÓN COGNITIVA ACTUAL:\n"
                "- No se ha producido nueva evidencia física significativa o se detectó repetición de respuestas/acciones.\n"
                "- Reevalúa la estrategia actual y selecciona autónomamente un nuevo enfoque o herramienta entre tus herramientas disponibles para recopilar la evidencia faltante."
            )
        elif self.state == StagnationState.REPLAN:
            return (
                f"[DIRECTIVA DE REPLANIFICACIÓN POR ESTANCAMIENTO COGNITIVO - Estado: {self.state.value}]:\n"
                f"Advertencia Crítica: {reason}\n"
                "INSTRUCCIÓN DE REPLANIFICACIÓN Y RE-EVALUACIÓN:\n"
                "- El proceso ha entrado en un ciclo de estancamiento prolongado.\n"
                "- Realiza una replanificación adaptativa o concluye formalmente si la evidencia acumulada "
                "es insuficiente ('INSUFFICIENT_EVIDENCE').\n"
                "- Si vas a continuar, debes invocar una herramienta distinta ahora mismo."
            )
        elif self.state == StagnationState.INSUFFICIENT_EVIDENCE:
            return (
                f"[DIRECTIVA DE FINALIZACIÓN POR EVIDENCIA INSUFICIENTE - Estado: {self.state.value}]:\n"
                "Concluye formalmente la misión informando que la evidencia física recopilada es insuficiente "
                "debido a límites de presupuesto o fallos persistentes de herramientas."
            )

        return None

    def reset(self):
        self.state = StagnationState.ACTIVE
        self.consecutive_text_turns = 0
        self.tool_call_history.clear()
        self.failed_command_history.clear()
        self.last_stagnation_reason = None
