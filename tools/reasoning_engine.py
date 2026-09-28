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
            "\n\n[ESTÁNDAR DE AUTONOMÍA Y EFECTIVIDAD EJECUTIVA - ANTIGRAVITY STANDARD]:\n"
            "1. Tienes AUTONOMÍA TOTAL Y PROACTIVA para auditar, leer, modificar archivos, crear código y ejecutar comandos en la PC de Mauro sin restricciones ni modos 'READ-ONLY'. NUNCA te limites a decir 'estoy en modo solo lectura' ni pidas permisos innecesarios.\n"
            "2. Comunícate SIEMPRE de forma directa, concisa, elegante y profesional en Markdown.\n"
            "3. Queda ESTRICTAMENTE PROHIBIDO escribir monólogos numerados ('1. ANÁLISIS DE INTENCIÓN...'), etiquetas de herramientas ('ACCION: COMMAND') o textos vacíos en tu respuesta al usuario.\n"
            "4. Cuando la tarea requiera resolver o modificar código o automatizar la PC, invoca las herramientas nativas (Function Calling) inmediatamente sin titubear ni frenarte.\n\n"
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
