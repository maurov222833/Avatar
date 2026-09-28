from enum import Enum
import re
from typing import Dict, Any, List, Optional
from core.cognitive.models import Goal, GoalState, TaskState, TaskResultStatus, TaskEvidence
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.verifier import Verifier
from core.cognitive.observer import CommandObserver
from core.cognitive.error_classifier import ErrorClassifier
from core.cognitive.recovery_engine import RecoveryEngine
from core.cognitive.anti_loop import AntiLoopDetector

class InteractionType(str, Enum):
    CONVERSATION_NORMAL = "CONVERSATION_NORMAL"
    INFORMATIVE_QUERY = "INFORMATIVE_QUERY"
    DIRECT_ACTION = "DIRECT_ACTION"
    OPEN_ENGINEERING_MISSION = "OPEN_ENGINEERING_MISSION"

class SemanticMissionEngine:
    """
    Motor de Misión Autónoma Semántica V2 para Avatar AI (Fase 8).
    Clasifica intenciones y gestiona misiones de ingeniería abiertas
    impidiendo la finalización prematura tras herramientas iniciales (ej: LIST_DIR).
    """

    @staticmethod
    def classify_interaction(user_input: str) -> InteractionType:
        if not user_input or not user_input.strip():
            return InteractionType.CONVERSATION_NORMAL

        text = user_input.strip()
        text_lower = text.lower()

        # 0. Restricciones negativas / Modo Forense / Instrucciones de Auditoría Explícita
        negative_action_patterns = [
            "no ejecutes", "no ejecutar", "no ejecutes nada", "no modifiques", 
            "no utilices herramientas", "no usar herramientas", "solo analiza", "solo investiga", "solo audita",
            "modo forense", "audita el siguiente", "audita los siguientes", "audita si", "audita el ejemplo",
            "audita reglas"
        ]
        has_negative_constraint = any(p in text_lower for p in negative_action_patterns)

        # 1. Conversación Normal
        norm_text = text_lower.translate(str.maketrans("áéíóúüñàèìòù", "aeiouunaeiou"))
        norm_text = re.sub(r'[^\w\s]', '', norm_text).strip()
        greetings = [
            "hola", "buenos dias", "buenas tardes", "buenas noches", "como estas",
            "gracias", "saludos", "estas ahi", "estas listo",
            "estas listo para trabajar", "avatar estas ahi",
            "quien eres", "que puedes hacer", "estas disponible"
        ]
        if any(norm_text == g or norm_text.startswith(g + " ") or g in norm_text for g in greetings) and len(text.split()) <= 10 and not has_negative_constraint:
            return InteractionType.CONVERSATION_NORMAL

        # 2. Misión de Ingeniería Abierta / Auditoría / Diagnóstico
        mission_keywords = [
            "analiza", "analizar", "investiga", "investigar", "determina", "determinar",
            "diagnostica", "diagnosticar", "evalúa", "evaluar", "audita", "auditar",
            "busca debilidades", "encuentra fallos", "revisa arquitectura", "comprueba autonomía"
        ]
        is_open_mission = any(kw in text_lower for kw in mission_keywords) and (len(text.split()) >= 3 or has_negative_constraint)

        if has_negative_constraint or is_open_mission:
            if is_open_mission:
                return InteractionType.OPEN_ENGINEERING_MISSION
            return InteractionType.INFORMATIVE_QUERY

        # 3. Acción Directa Explícita (comandos shell o herramientas directas o especificaciones multi-tarea)
        direct_prefixes = ["ejecuta ", "ejecutar ", "ejecuta:", "ejecutar:", "run ", "cmd: ", "command: ", "read_file: ", "list_dir: "]
        is_direct_prefix = any(text_lower.startswith(prefix) or ("\nejecuta:" in text_lower) or ("\nejecuta\n" in text_lower) for prefix in direct_prefixes)

        # Reconocer formato explícito de lista de tareas ejecutables (ej: "1. Tarea 1: echo...", "Tarea 1: python...")
        matching_task_lines = []
        for raw_l in text.splitlines():
            cl = re.sub(r'^(?:#+|-|\*|(?:Tarea|Task|T)?\s*\d+[\.\)\:\-])\s*', '', raw_l.strip(), flags=re.IGNORECASE).strip()
            cl = re.sub(r'^(?:Tarea|Task|T)\s*\d+[\.\)\:\-]\s*', '', cl, flags=re.IGNORECASE).strip()
            cl_lower = cl.lower()
            if cl and (cl.startswith(":") or any(cl_lower.startswith(k) for k in ["command:", "read_file:", "write_file:", "list_dir:", "echo ", "python ", "python3 ", "pytest", "unittest", "git ", "dir ", "ls ", "mkdir ", "copy ", "del "])):
                matching_task_lines.append(cl)

        is_explicit_multi_task = len(matching_task_lines) >= 2

        if (is_direct_prefix or is_explicit_multi_task) and not has_negative_constraint:
            return InteractionType.DIRECT_ACTION

        # 4. Consulta Informativa por defecto para preguntas o textos explicativos
        if "?" in text or text_lower.startswith(("qué", "cómo", "por qué", "explica", "explicar", "cuál")):
            return InteractionType.INFORMATIVE_QUERY

        return InteractionType.INFORMATIVE_QUERY

    @staticmethod
    def format_structured_error_context(raw_output: str, max_chars: int = 2000) -> str:
        """
        Formatea el contexto estructurado de un error priorizando el rastreo de pila (traceback),
        la excepción raíz (e.g. RuntimeError, ModuleNotFoundError) y los códigos de salida,
        garantizando que no se trunque la causa raíz a 120 caracteres.
        """
        if not raw_output or not raw_output.strip():
            return "No error details available."

        text = raw_output.strip()
        lines = text.splitlines()

        tb_lines = []
        exception_lines = []
        in_tb = False

        for line in lines:
            line_str = line.strip()
            if "traceback (most recent call last):" in line_str.lower() or "traceback:" in line_str.lower():
                in_tb = True
                tb_lines.append(line)
                continue

            if in_tb:
                tb_lines.append(line)
                if re.match(r'^[A-Za-z0-9_]+(?:Error|Exception|Fault|Warning):', line_str):
                    exception_lines.append(line_str)
                    in_tb = False
            else:
                if re.match(r'^[A-Za-z0-9_]+(?:Error|Exception|Fault|Warning):', line_str):
                    exception_lines.append(line_str)

        structured_parts = []
        if exception_lines:
            structured_parts.append(f"ROOT EXCEPTION: {'; '.join(exception_lines)}")

        if tb_lines:
            tb_block = "\n".join(tb_lines)
            structured_parts.append(f"TRACEBACK:\n{tb_block}")

        if structured_parts:
            combined = "\n".join(structured_parts)
            if len(combined) <= max_chars:
                tail_chars = max_chars - len(combined) - 50
                if tail_chars > 100 and len(text) > len(combined):
                    combined += f"\nOUTPUT SNIPPET:\n{text[-tail_chars:]}"
                return combined[:max_chars]

        if len(text) <= max_chars:
            return text
        
        return text[-max_chars:]

    @staticmethod
    def is_evidence_sufficient_for_goal(
        goal: Goal,
        executed_steps: List[Dict[str, Any]],
        llm_text: str,
        state_db=None,
        capability_registry=None
    ) -> Dict[str, Any]:
        """
        Evalúa determinísticamente si la evidencia acumulada justifica la finalización del Goal.
        Impide la finalización si solo se ejecutó LIST_DIR, pip install, o si falta inspección/prueba técnica real.

        AVISO DE AUTORIDAD: esta evaluación es **consultiva**. Devuelve un `GoalState` en
        memoria y no escribe ningún estado de misión. La única vía que persiste COMPLETED es
        `StateEngine.complete_mission_with_authorization`, que vuelve a derivar el veredicto
        desde los requirements persistidos de la misión.
        """
        if not executed_steps:
            return {
                "sufficient": False,
                "reason": "No tools have been executed yet.",
                "status": GoalState.EXECUTING
            }

        successful_steps = [s for s in executed_steps if s.get("task_result") and s["task_result"].status.is_success()]
        failed_steps = [s for s in executed_steps if s.get("task_result") and not s["task_result"].status.is_success()]

        if not successful_steps:
            last_err = failed_steps[-1]["output"] if failed_steps else "Tool execution failed."
            formatted_err = SemanticMissionEngine.format_structured_error_context(last_err)
            return {
                "sufficient": False,
                "reason": f"No successful tool executions completed yet. Last error: {formatted_err}",
                "status": GoalState.EXECUTING
            }

        successful_tools = [s.get("tool_name") for s in successful_steps]
        outputs_concat = " ".join([str(s.get("output", "")) for s in successful_steps]).lower()

        # REGLA FUNDAMENTAL 1: LIST_DIR aislado NO concluye una misión de ingeniería abierta
        if all(t == "LIST_DIR" for t in successful_tools):
            return {
                "sufficient": False,
                "reason": "Only directory listing has been performed. Technical investigation requires reading code files or running diagnostic tests.",
                "status": GoalState.EXECUTING
            }

        # REGLA FUNDAMENTAL 2: pip install o setup no constituye investigación o prueba de código
        if "pip install" in outputs_concat or "successfully installed" in outputs_concat:
            has_test_or_read = any(t == "READ_FILE" or (t == "COMMAND" and any(k in str(s.get("args", "")).lower() for k in ["unittest", "pytest", "python -m"])) for s, t in zip(successful_steps, successful_tools) if "pip install" not in str(s.get("args", "")).lower())
            if not has_test_or_read:
                return {
                    "sufficient": False,
                    "reason": "Package installation alone is not code investigation. Technical evidence requires evaluating implementation details or execution behavior.",
                    "status": GoalState.EXECUTING
                }

        text_lower = llm_text.lower()

        # Si el texto es solo un saludo conversacional genérico preguntando qué hacer
        if any(greeting in text_lower for greeting in ["¿qué tarea deseas", "¿qué directiva o tarea", "qué proyecto o tarea", "estoy listo para programar"]) and len(text_lower.split()) < 50:
            return {
                "sufficient": False,
                "reason": "Returned generic conversational prompt instead of technical investigation findings or evidence report.",
                "status": GoalState.EXECUTING
            }

        # Comprobar si se detectó formalmente NO_ACTION_REQUIRED o conclusión justificada
        if "no_action_required" in text_lower or "no se requiere modificación" in text_lower or "no existe debilidad" in text_lower or "no real weakness" in text_lower:
            return {
                "sufficient": True,
                "reason": "Investigation concluded no code modification is required based on gathered evidence.",
                "status": GoalState.COMPLETED,
                "conclusion": "NO_ACTION_REQUIRED"
            }

        # Si se realizaron lecturas de código o ejecuciones de pruebas exitosas y hay informe técnico
        has_real_investigation = any(t == "READ_FILE" or (t == "COMMAND" and ("unittest" in str(s.get("args", "")).lower() or "pytest" in str(s.get("args", "")).lower())) for s, t in zip(successful_steps, successful_tools))
        if has_real_investigation:
            critical_gaps = 0
            blocking_findings = 0
            from core.cognitive.mission_completion_gate import MissionCompletionGate, MissionStatus
            required_caps = goal.metadata.get("required_capabilities", [])
            gate_res = MissionCompletionGate.evaluate_mission_completion(
                mission_id=goal.goal_id,
                required_capabilities=required_caps,
                critical_gaps=critical_gaps,
                blocking_findings=blocking_findings,
                capability_registry=capability_registry,
                state_db=state_db
            )

            if not gate_res.can_complete:
                return {
                    "sufficient": True,
                    "reason": f"Investigación completada pero existen brechas críticas o hallazgos bloqueantes pendientes: {'; '.join(gate_res.blocking_reasons)}",
                    "status": GoalState.EXECUTING,
                    "conclusion": gate_res.mission_status
                }

            return {
                "sufficient": True,
                "reason": "Investigation gathered multi-tool technical evidence successfully.",
                "status": GoalState.COMPLETED,
                "conclusion": "COMPLETED"
            }

        return {
            "sufficient": False,
            "reason": "Further investigation required to collect concrete technical evidence.",
            "status": GoalState.EXECUTING
        }
