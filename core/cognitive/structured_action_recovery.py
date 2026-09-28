import json
import re
import os
from typing import Dict, Any, List, Optional
from core.cognitive.tool_registry import ToolRegistry

class StructuredActionRecoveryLayer:
    """
    Capa de Recuperación de Acciones Estructuradas para Avatar AI (Fase 10).
    Intercepta textos del LLM que contienen intenciones de herramientas en JSON
    y las convierte en llamadas a función normalizadas (Function Call) sin bypass de seguridad.
    NUNCA ejecuta herramientas directamente; devuelve la llamada estructurada al pipeline normal.
    """

    @staticmethod
    def extract_json_candidate(text: str) -> Optional[Dict[str, Any]]:
        if not text or not text.strip():
            return None

        # 1. Buscar bloques ```json ... ```
        json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE)
        if json_block_match:
            try:
                data = json.loads(json_block_match.group(1))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        # 2. Buscar objeto JSON crudo {...} si el texto empieza/termina o contiene JSON aislado
        raw_json_match = re.search(r'(\{[\s\S]*?"action"[\s\S]*?\})', text) or re.search(r'(\{[\s\S]*?"tool"[\s\S]*?\})', text)
        if raw_json_match:
            try:
                data = json.loads(raw_json_match.group(1))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        return None

    @staticmethod
    def extract_and_validate_structured_action(
        raw_text: str,
        tools_schema: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        candidate = StructuredActionRecoveryLayer.extract_json_candidate(raw_text)
        if not candidate:
            return None

        # Identificar nombre de la herramienta
        tool_name = candidate.get("action") or candidate.get("tool") or candidate.get("name") or candidate.get("function")
        args = candidate.get("args") or candidate.get("parameters") or candidate.get("params") or {}

        if not tool_name or not isinstance(tool_name, str):
            return None

        tool_name = tool_name.upper().strip()

        # Normalización de alias comunes
        if tool_name == "EXECUTE_COMMAND" or tool_name == "SHELL" or tool_name == "CMD":
            tool_name = "COMMAND"
        elif tool_name == "READ":
            tool_name = "READ_FILE"
        elif tool_name == "WRITE":
            tool_name = "WRITE_FILE"
        elif tool_name == "LIST":
            tool_name = "LIST_DIR"

        # 1. Validación contra ToolRegistry
        available_tools = ToolRegistry.list_tools() if hasattr(ToolRegistry, 'list_tools') else ["COMMAND", "READ_FILE", "WRITE_FILE", "LIST_DIR", "WEB_SEARCH", "FETCH_URL", "PLAY_AUDIO", "SEND_WHATSAPP"]
        if tool_name not in available_tools and tool_name not in ["COMMAND", "READ_FILE", "WRITE_FILE", "LIST_DIR", "WEB_SEARCH", "FETCH_URL", "PLAY_AUDIO", "SEND_WHATSAPP"]:
            return None

        # Normalize alias args keys
        if not isinstance(args, dict):
            return None

        normalized_args = {}
        if tool_name == "COMMAND":
            cmd = args.get("command") or args.get("cmd") or args.get("path") or args.get("script")
            if not cmd or not isinstance(cmd, str):
                return None
            normalized_args["command"] = cmd

        elif tool_name == "READ_FILE":
            path = args.get("file_path") or args.get("path") or args.get("file")
            if not path or not isinstance(path, str):
                return None
            normalized_args["file_path"] = path

        elif tool_name == "WRITE_FILE":
            path = args.get("file_path") or args.get("path") or args.get("file")
            content = args.get("content") or args.get("text") or args.get("code") or ""
            if not path or not isinstance(path, str):
                return None
            normalized_args["file_path"] = path
            normalized_args["content"] = str(content)

        elif tool_name == "LIST_DIR":
            path = args.get("dir_path") or args.get("path") or args.get("dir") or "."
            normalized_args["dir_path"] = str(path)
        else:
            normalized_args = args

        # 2. Validación de Seguridad / Sandbox (Verificación de workspace para archivos)
        if tool_name in ["READ_FILE", "WRITE_FILE", "LIST_DIR"]:
            target_path = normalized_args.get("file_path") or normalized_args.get("dir_path") or ""
            if ".." in target_path and ("C:" in target_path or "D:" in target_path or "B:" in target_path):
                # Rechazar intento de traversal fuera de ruta permitida
                return None

        # Retornar estructura equivalente a una Function Call nativa
        return {
            "type": "function_call",
            "name": tool_name,
            "args": normalized_args,
            "recovered_from_text": True,
            "raw_part": {
                "functionCall": {
                    "name": tool_name,
                    "args": normalized_args
                }
            }
        }
