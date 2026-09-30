import json
import re
from typing import Dict, Any, List

class ReasoningEngine:
    """
    MOTOR DE RAZONAMIENTO SUPREMO Y REFLEXIÓN LÓGICA (CHAIN-OF-THOUGHT & METACOGNITION).
    Elevado para capacitar a Avatar con razonamiento de nivel élite sin contaminar los mensajes finales del usuario.
    """

    @staticmethod
    def format_supreme_reasoning_prompt(base_prompt: str, context_memory: str = "") -> str:
        """
        Formatea el prompt para obligar a Avatar a responder con elegancia ejecutiva sin monólogos internos.
        """
        reasoning_rules = (
            "\n\n[ESTÁNDAR DE COMUNICACIÓN — intelectual, no burocrático]:\n"
            "1. Autonomía práctica dentro de la política: usa herramientas cuando haga falta "
            "trabajo real. En charla (saludos, ánimo, '¿puedes hacer X?') responde sin tools "
            "ni teatro de 'auditoría de subsistemas'.\n"
            "2. Tono con criterio: claro, elegante, natural. CHARLA = prosa 2-6 frases, "
            "sin plantilla. TRABAJO (tras tools) = qué hiciste + evidencia real + estado, "
            "sin etiquetas *(1) QUÉ HICE* / EVIDENCIA / ESTADO / SIGUIENTE PASO.\n"
            "3. PROHIBIDO monólogos CoT numerados, etiquetas 'ACCION: COMMAND', o inventar "
            "latencias/APIs si no las mediste.\n"
            "4. Si Mauro pide una acción concreta ahora, invoca tools; si pregunta, responde "
            "con juicio y honestidad sobre lo que sí puedes hacer.\n\n"
        )
        
        full_system_prompt = base_prompt + reasoning_rules
        if context_memory:
            full_system_prompt += f"\n[CONOCIMIENTO ACUMULADO RELEVANTE]:\n{context_memory}\n"
        
        return full_system_prompt

    @staticmethod
    def extract_clean_response(raw_text: str) -> str:
        """
        Extrae la respuesta limpia para el usuario aislando cualquier bloque interno CoT.
        Preserva intactos todos los reportes, listas numeradas y respuestas extensas en Markdown.
        """
        if not raw_text:
            return ""
        
        cleaned = raw_text
        
        # 1. Eliminar bloque ```pensamiento_superior ... ```
        cleaned = re.sub(r"```pensamiento_superior.*?```", "", cleaned, flags=re.DOTALL).strip()
        cleaned = re.sub(r"\[PENSAMIENTO_INTERNO\].*?\[/PENSAMIENTO_INTERNO\]", "", cleaned, flags=re.DOTALL).strip()
        
        # 2. Eliminar texto "Abrir en Monaco IDE" si está presente
        cleaned = re.sub(r"(?i)Abrir en Monaco IDE", "", cleaned).strip()
        
        # 3. Eliminar únicamente líneas que sean aisladamente etiquetas de herramientas antiguas
        cleaned = re.sub(r"^ACCION:\s*[A-Z_]+(?:\n|$)", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^PARAMETROS:\s*.*?(?:\n|$)", "", cleaned, flags=re.MULTILINE).strip()
        
        return cleaned if cleaned else raw_text
