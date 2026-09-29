import json
import os
import requests
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from core.redaction import redact_secret_text

#: Providers whose keys are redacted from any text the facade returns.
_KEYED_PROVIDERS = ("gemini", "openai", "groq", "github")


def _gemini_headers(api_key: str) -> Dict[str, str]:
    # Header auth keeps the key out of URLs, which requests echoes into exception messages.
    return {"Content-Type": "application/json", "x-goog-api-key": api_key}


@dataclass
class ProviderCapabilities:
    """Capacidades soportadas por un proveedor LLM."""
    text: bool = True
    function_calling: bool = True
    multi_turn: bool = True
    json_schema: bool = True
    vision: bool = False
    streaming: bool = False

@dataclass
class ProviderHealth:
    """Estado de salud y accesibilidad de un proveedor LLM."""
    provider_name: str
    status: str  # "ACTIVE", "MISSING_KEY", "OFFLINE", "UNAVAILABLE"
    message: str
    latency_ms: float = 0.0

class BaseAdapter:
    """Interfaz base para todos los adaptadores de proveedores LLM."""
    def __init__(self, config_manager):
        self.config_manager = config_manager

    @property
    def provider_name(self) -> str:
        raise NotImplementedError

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def get_api_key(self) -> str:
        return self.config_manager._get_api_key(self.provider_name)

    def check_health(self) -> ProviderHealth:
        key = self.get_api_key()
        if not key and self.provider_name in ["gemini", "openai", "groq", "github"]:
            return ProviderHealth(
                provider_name=self.provider_name,
                status="MISSING_KEY",
                message=f"Falta la clave API ({self.provider_name.upper()}_API_KEY)."
            )
        return ProviderHealth(
            provider_name=self.provider_name,
            status="ACTIVE",
            message="Proveedor configurado y listo."
        )

    def generate_response(self, system_prompt: str, prompt: str, history: List[Dict[str, str]] = None) -> str:
        raise NotImplementedError

    def generate_response_with_tools(self, system_prompt: str, contents: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError


class GeminiAdapter(BaseAdapter):
    @property
    def provider_name(self) -> str:
        return "gemini"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(text=True, function_calling=True, multi_turn=True, json_schema=True, vision=False, streaming=False)

    def generate_response(self, system_prompt: str, prompt: str, history: List[Dict[str, str]] = None) -> str:
        gemini_cfg = self.config_manager.config.get("gemini", {})
        api_key = self.get_api_key()
        model = gemini_cfg.get("model", "gemini-3.6-flash")

        if not api_key:
            return (
                "⚠️ [Aviso Gemini API]: No se ha ingresado una API Key de Gemini válida.\n"
                "Para configurar tu clave:\n"
                "1. Define la variable de entorno GEMINI_API_KEY o crea el archivo .env.\n"
                "2. O pégala en el archivo config.json en la propiedad 'gemini.api_key'."
            )

        contents = []
        if history:
            for turn in history[-20:]:
                role = "user" if turn.get("role") in ["user", "human"] else "model"
                content_text = turn.get("content", "")
                if content_text:
                    contents.append({"role": role, "parts": [{"text": content_text}]})
        
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }

        last_error = ""
        fallback_models = [model, "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
        seen = set()
        fallback_models = [m for m in fallback_models if not (m in seen or seen.add(m))]

        for current_model in fallback_models:
            current_url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
            for attempt in range(1, 3):
                try:
                    res = requests.post(current_url, json=payload,
                                        headers=_gemini_headers(api_key), timeout=60)
                    if res.status_code == 200:
                        data = res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            text = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
                            return text if text else "Respuesta vacía de Gemini."
                        return "Sin respuesta generada por Gemini."
                    elif res.status_code in [503, 429]:
                        last_error = f"[Error Gemini API {res.status_code}]: {res.text}"
                        break
                    else:
                        last_error = f"[Error Gemini API {res.status_code}]: {res.text}"
                except Exception as e:
                    last_error = f"[Error de conexión con Gemini API]: {str(e)}"
                    time.sleep(1)

        return last_error

    def generate_response_with_tools(self, system_prompt: str, contents: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        gemini_cfg = self.config_manager.config.get("gemini", {})
        api_key = self.get_api_key()
        model = gemini_cfg.get("model", "gemini-3.6-flash")

        if not api_key:
            return {
                "type": "provider_error",
                "provider": "gemini",
                "error": "No GEMINI_API_KEY configured in .env or config.json",
                "status_code": 401,
                "reason": "MISSING_API_KEY",
                "recoverable": True
            }

        sanitized_contents = []
        for msg in contents:
            m_copy = dict(msg)
            if m_copy.get("role") == "function":
                m_copy["role"] = "user"
            sanitized_contents.append(m_copy)

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": sanitized_contents,
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096}
        }
        if tools:
            payload["tools"] = tools

        fallback_models = [model, "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
        seen = set()
        fallback_models = [m for m in fallback_models if not (m in seen or seen.add(m))]

        last_err = ""
        last_status = 500

        for current_model in fallback_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
            try:
                res = requests.post(url, json=payload, headers=_gemini_headers(api_key), timeout=60)
                last_status = res.status_code
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "functionCall" in part:
                                fn = part["functionCall"]
                                return {
                                    "type": "function_call",
                                    "provider": "gemini",
                                    "name": fn.get("name"),
                                    "args": fn.get("args", {}),
                                    "raw_part": part
                                }
                            elif "text" in part and part["text"].strip():
                                return {
                                    "type": "text",
                                    "provider": "gemini",
                                    "text": part["text"],
                                    "raw_part": part
                                }
                        return {"type": "text", "provider": "gemini", "text": "Respuesta procesada correctamente."}
                elif res.status_code in [503, 429]:
                    last_err = f"HTTP {res.status_code}: {res.text[:200]}"
                    continue
                else:
                    last_err = f"HTTP {res.status_code}: {res.text[:200]}"
                    return {
                        "type": "provider_error",
                        "provider": "gemini",
                        "error": last_err,
                        "status_code": res.status_code,
                        "reason": "QUOTA_EXHAUSTED" if res.status_code == 429 else "HTTP_ERROR",
                        "recoverable": True
                    }
            except Exception as e:
                last_err = str(e)
                continue

        return {
            "type": "provider_error",
            "provider": "gemini",
            "error": f"All fallback models failed ({last_err})",
            "status_code": last_status,
            "reason": "QUOTA_EXHAUSTED" if last_status == 429 else "PROVIDER_UNAVAILABLE",
            "recoverable": True
        }


class OpenAICompatibleAdapter(BaseAdapter):
    """Adaptador genérico para APIs compatibles con la especificación de OpenAI (OpenAI, Groq, GitHub Models, LM Studio, Ollama)."""
    def __init__(self, config_manager, name: str, default_model: str, default_url: str):
        super().__init__(config_manager)
        self._name = name
        self.default_model = default_model
        self.default_url = default_url

    @property
    def provider_name(self) -> str:
        return self._name

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(text=True, function_calling=True, multi_turn=True, json_schema=True, vision=(self._name in ["openai", "github"]), streaming=False)

    def check_health(self) -> ProviderHealth:
        if self._name in ["lmstudio", "ollama"]:
            url = self.config_manager.config.get(self._name, {}).get("url", self.default_url)
            base_url = url.replace("/v1/chat/completions", "").replace("/api/chat", "")
            try:
                res = requests.get(base_url, timeout=3)
                if res.status_code in [200, 404]:
                    return ProviderHealth(provider_name=self._name, status="ACTIVE", message=f"Servidor local activo en {base_url}.")
            except Exception:
                return ProviderHealth(provider_name=self._name, status="OFFLINE", message=f"No se pudo conectar al servidor local en {base_url}.")
        return super().check_health()

    def generate_response(self, system_prompt: str, prompt: str, history: List[Dict[str, str]] = None) -> str:
        p_cfg = self.config_manager.config.get(self.provider_name, {})
        api_key = self.get_api_key()
        model = p_cfg.get("model", self.default_model)
        url = p_cfg.get("url", self.default_url)

        if self.provider_name in ["openai", "groq", "github"] and not api_key:
            return f"⚠️ [Aviso {self.provider_name.upper()} API]: No se ha ingresado una API Key válida para {self.provider_name.upper()}."

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": prompt})

        fallback_models = [model]
        if self.provider_name == "groq":
            fallback_models.extend(["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"])
        seen = set()
        fallback_models = [m for m in fallback_models if not (m in seen or seen.add(m))]

        last_error = ""
        for current_model in fallback_models:
            payload = {"model": current_model, "messages": messages, "temperature": 0.2, "max_tokens": 1000}
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "Sin respuesta.")
                    return "Sin contenido devuelto."
                elif res.status_code in [429, 503]:
                    last_error = f"[Error {self.provider_name.upper()} API {res.status_code}]: {res.text[:200]}"
                    continue
                else:
                    return f"[Error {self.provider_name.upper()} API {res.status_code}]: {res.text[:200]}"
            except Exception as e:
                last_error = f"[Error de conexión con {self.provider_name.upper()} API]: {str(e)}"
                continue

        return last_error

    @staticmethod
    def _prune_messages_for_token_limit(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Podar historial y truncar mensajes extremadamente largos para evitar HTTP 413 / ITPM limits."""
        if not messages:
            return []
        
        pruned = []
        if messages[0].get("role") == "system":
            pruned.append(messages[0])
            user_turns = messages[1:]
        else:
            user_turns = messages

        if len(user_turns) > 2:
            user_turns = user_turns[-2:]

        for msg in user_turns:
            m_copy = dict(msg)
            content = m_copy.get("content")
            if isinstance(content, str) and len(content) > 3500:
                m_copy["content"] = content[:1800] + "\n\n[... [CONTENIDO EXTENSO TRUNCADO PARA LÍMITE DE CUOTA DE TOKENS] ...]\n\n" + content[-1500:]
            pruned.append(m_copy)

        return pruned

    def generate_response_with_tools(self, system_prompt: str, contents: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        p_cfg = self.config_manager.config.get(self.provider_name, {})
        api_key = self.get_api_key()
        model = p_cfg.get("model", self.default_model)
        url = p_cfg.get("url", self.default_url)

        if self.provider_name in ["openai", "groq", "github"] and not api_key:
            return {
                "type": "provider_error",
                "provider": self.provider_name,
                "error": f"No API key provided for {self.provider_name.upper()}",
                "status_code": 401,
                "reason": "MISSING_API_KEY",
                "recoverable": True
            }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        def _sanitize_schema(obj):
            if isinstance(obj, dict):
                return {k: (v.lower() if k == "type" and isinstance(v, str) else _sanitize_schema(v)) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize_schema(i) for i in obj]
            return obj

        o_tools = []
        if tools:
            for t_group in tools:
                for f_decl in t_group.get("functionDeclarations", []):
                    o_tools.append({
                        "type": "function",
                        "function": {
                            "name": f_decl.get("name"),
                            "description": f_decl.get("description", ""),
                            "parameters": _sanitize_schema(f_decl.get("parameters", {}))
                        }
                    })

        o_messages = [{"role": "system", "content": system_prompt}]
        sliced_contents = contents[-10:] if contents else []
        for msg in sliced_contents:
            role = msg.get("role")
            parts = msg.get("parts", [])
            text_content = ""
            fn_call = None
            fn_resp = None
            for p in parts:
                if "text" in p:
                    text_content += p["text"]
                if "functionCall" in p:
                    fn_call = p["functionCall"]
                if "functionResponse" in p:
                    fn_resp = p["functionResponse"]

            if fn_resp:
                o_messages.append({
                    "role": "tool",
                    "tool_call_id": fn_resp.get("id", "call_default"),
                    "content": json.dumps(fn_resp.get("response", {}))
                })
            elif fn_call:
                o_messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": fn_call.get("id", "call_default"),
                        "type": "function",
                        "function": {
                            "name": fn_call.get("name"),
                            "arguments": json.dumps(fn_call.get("args", {}))
                        }
                    }]
                })
            else:
                o_role = "assistant" if role in ["model", "assistant"] else "user"
                o_messages.append({"role": o_role, "content": text_content})

        fallback_models = [model]
        if self.provider_name == "groq":
            fallback_models.extend(["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"])
        seen = set()
        fallback_models = [m for m in fallback_models if not (m in seen or seen.add(m))]

        last_err = ""
        last_status = 500

        for current_model in fallback_models:
            attempts_to_try = [o_messages, self._prune_messages_for_token_limit(o_messages)]
            for att_messages in attempts_to_try:
                payload = {"model": current_model, "messages": att_messages, "temperature": 0.1, "max_tokens": 1000}
                if o_tools:
                    payload["tools"] = o_tools

                try:
                    res = requests.post(url, json=payload, headers=headers, timeout=60)
                    last_status = res.status_code
                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            if msg.get("tool_calls"):
                                tc = msg["tool_calls"][0]
                                fn = tc.get("function", {})
                                raw_args = fn.get("arguments", {})
                                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                return {
                                    "type": "function_call",
                                    "provider": self.provider_name,
                                    "name": fn.get("name"),
                                    "args": parsed_args,
                                    "raw_part": {
                                        "functionCall": {
                                            "name": fn.get("name"),
                                            "args": parsed_args,
                                            "id": tc.get("id", "call_default")
                                        }
                                    }
                                }
                            elif msg.get("content"):
                                return {
                                    "type": "text",
                                    "provider": self.provider_name,
                                    "text": msg["content"],
                                    "raw_part": {"text": msg["content"]}
                                }
                        return {"type": "text", "provider": self.provider_name, "text": "Respuesta vacía del proveedor."}
                    elif res.status_code in [413, 429, 503] or (res.status_code == 400 and ("token" in res.text.lower() or "large" in res.text.lower())):
                        last_err = f"HTTP {res.status_code}: {res.text[:200]}"
                        continue
                    else:
                        return {
                            "type": "provider_error",
                            "provider": self.provider_name,
                            "error": f"HTTP {res.status_code}: {res.text[:200]}",
                            "status_code": res.status_code,
                            "reason": "QUOTA_EXHAUSTED" if res.status_code in [413, 429] else "PROVIDER_ERROR",
                            "recoverable": True
                        }
                except Exception as e:
                    last_err = str(e)
                    continue

        return {
            "type": "provider_error",
            "provider": self.provider_name,
            "error": f"All fallback models failed ({last_err})",
            "status_code": last_status,
            "reason": "QUOTA_EXHAUSTED" if last_status in [413, 429] else "PROVIDER_UNAVAILABLE",
            "recoverable": True
        }


class OllamaAdapter(BaseAdapter):
    @property
    def provider_name(self) -> str:
        return "ollama"

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(text=True, function_calling=False, multi_turn=True, json_schema=True, vision=False, streaming=False)

    def check_health(self) -> ProviderHealth:
        ollama_cfg = self.config_manager.config.get("ollama", {})
        url = ollama_cfg.get("url", "http://localhost:11434")
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                return ProviderHealth(provider_name="ollama", status="ACTIVE", message=f"Ollama local activo en {url}.")
        except Exception:
            pass
        return ProviderHealth(provider_name="ollama", status="OFFLINE", message=f"No se pudo conectar a Ollama local en {url}.")

    def generate_response(self, system_prompt: str, prompt: str, history: List[Dict[str, str]] = None) -> str:
        ollama_cfg = self.config_manager.config.get("ollama", {})
        url = f"{ollama_cfg.get('url', 'http://localhost:11434')}/api/chat"
        model = ollama_cfg.get("model", "qwen2.5-coder:1.5b")

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model, "messages": messages, "stream": False}
        try:
            res = requests.post(url, json=payload, timeout=300)
            if res.status_code == 200:
                data = res.json()
                return data.get("message", {}).get("content", "Sin respuesta del modelo local.")
            else:
                return f"[Error Ollama {res.status_code}]: Asegúrate de que Ollama esté ejecutándose con el modelo {model}."
        except requests.exceptions.ConnectionError:
            return f"[Aviso Ollama]: No se pudo conectar a Ollama local en {url}."
        except Exception as e:
            return f"[Error de conexión con IA Local]: {str(e)}"

    def generate_response_with_tools(self, system_prompt: str, contents: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Intentar llamada mediante endpoint OpenAI compatible de Ollama primero
        comp_adapter = OpenAICompatibleAdapter(self.config_manager, "ollama", "qwen2.5-coder:1.5b", "http://localhost:11434/v1/chat/completions")
        res_ol = comp_adapter.generate_response_with_tools(system_prompt, contents, tools)
        if res_ol.get("type") != "provider_error":
            return res_ol
        
        # Fallback a consulta simple de texto
        txt = self.generate_response(system_prompt, contents[-1]["parts"][0]["text"] if contents else "", None)
        return {"type": "text", "provider": "ollama", "text": txt}


class ProviderManager:
    """Administrador centralizado y agnóstico de proveedores LLM."""
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.adapters: Dict[str, BaseAdapter] = {
            "gemini": GeminiAdapter(config_manager),
            "openai": OpenAICompatibleAdapter(config_manager, "openai", "gpt-4o-mini", "https://api.openai.com/v1/chat/completions"),
            "groq": OpenAICompatibleAdapter(config_manager, "groq", "qwen/qwen3.8-27b", "https://api.groq.com/openai/v1/chat/completions"),
            "github": OpenAICompatibleAdapter(config_manager, "github", "gpt-4o", "https://models.inference.ai.azure.com/chat/completions"),
            "lmstudio": OpenAICompatibleAdapter(config_manager, "lmstudio", "local-model", "http://localhost:1234/v1/chat/completions"),
            "ollama": OllamaAdapter(config_manager)
        }

    def get_adapter(self, provider_name: str) -> BaseAdapter:
        p = provider_name.lower().strip()
        if p == "chatgpt":
            p = "openai"
        return self.adapters.get(p, self.adapters["gemini"])

    def check_all_health(self) -> Dict[str, Dict[str, Any]]:
        health_report = {}
        for name, adapter in self.adapters.items():
            h = adapter.check_health()
            caps = adapter.get_capabilities()
            health_report[name] = {
                "provider": name,
                "status": h.status,
                "message": h.message,
                "capabilities": {
                    "text": caps.text,
                    "function_calling": caps.function_calling,
                    "multi_turn": caps.multi_turn,
                    "json_schema": caps.json_schema,
                    "vision": caps.vision,
                    "streaming": caps.streaming
                }
            }
        return health_report


def _allowed_tool_names(tools) -> set:
    """Nombres de herramientas del schema, en cualquiera de sus formas."""
    names = set()
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        for f in t.get("functionDeclarations") or []:
            if isinstance(f, dict) and f.get("name"):
                names.add(f["name"])
        fn = t.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            names.add(fn["name"])
        if t.get("name") and "functionDeclarations" not in t:
            names.add(t["name"])
    return names


_PARSE_ERROR_MARKERS = (
    "parse tool call", "tool_use_failed", "tool call validation failed",
    "not in request.tools", "failed_generation", "tools should have a name",
    "harmony", "invalid_request_error",
)


# Textos plantilla que los adaptadores devuelven cuando la API responde 200 sin
# contenido aprovechable. NO son prosa del modelo: el facade los normaliza a
# provider_empty para que el orquestador los trate como silencio, jamás como
# mensaje al dueño.
_EMPTY_TEXTS = frozenset([
    "", "respuesta vacía del proveedor.", "respuesta vacía de gemini.",
    "sin respuesta generada por gemini.", "sin respuesta.",
    "sin contenido devuelto.", "sin respuesta del modelo local.",
])


def _is_tool_parse_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    return any(m in lowered for m in _PARSE_ERROR_MARKERS)


def _repair_contents(contents, allowed: set, malformed: bool = False,
                     bad_name: str = ""):
    """Añade una instrucción de reparación acotada para UN solo reintento."""
    allowed_txt = ", ".join(sorted(allowed)) if allowed else "ninguna listada"
    if malformed:
        hint = ("Tu tool-call llegó truncado o con JSON inválido y fue rechazado. "
                f"Re-emite el MISMO tool-call completo y válido usando solo: {allowed_txt}.")
    else:
        hint = (f"La herramienta '{bad_name}' no existe. Usa EXCLUSIVAMENTE una de: "
                f"{allowed_txt}. Re-emite tu respuesta completa.")
    return list(contents or []) + [{"role": "user", "parts": [{"text": hint}]}]


class LLMProvider:
    """
    LLM Provider Manager & Router Agnóstico (Fachada Principal).
    Mantiene compatibilidad 100% con la interfaz previa mientras delega en ProviderManager.
    """
    def __init__(self, config_path: str = "b:/PROYECTOS ANTIGRAVITY/Avatar/config.json"):
        self.config_path = config_path
        self.load_config()
        self.manager = ProviderManager(self)

    def _load_env(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k_str = k.strip()
                            v_str = v.strip().strip("'\"")
                            os.environ[k_str] = v_str
            except Exception:
                pass

    def _get_api_key(self, provider: str) -> str:
        self._load_env()
        p = provider.lower()
        keys_to_check = [f"{p.upper()}_API_KEY"]
        if p == "github":
            keys_to_check.append("GITHUB_TOKEN")
        elif p in ["openai", "chatgpt"]:
            keys_to_check.append("OPENAI_API_KEY")
        
        for k in keys_to_check:
            val = os.getenv(k)
            if val and not val.startswith("YOUR_"):
                return val.strip()
        cfg_val = self.config.get(p, {}).get("api_key", "").strip()
        if cfg_val and not cfg_val.startswith("YOUR_"):
            return cfg_val
        return ""

    def load_config(self, force: bool = False):
        if hasattr(self, "config") and self.config and not force:
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception:
            self.config = {
                "default_provider": "gemini",
                "gemini": {"api_key": "", "model": "gemini-3.6-flash"},
                "groq": {"api_key": "", "model": "qwen/qwen3.8-27b", "url": "https://api.groq.com/openai/v1/chat/completions"},
                "github": {"api_key": "", "model": "gpt-4o", "url": "https://models.inference.ai.azure.com/chat/completions"},
                "openai": {"api_key": "", "model": "gpt-4o-mini"},
                "lmstudio": {"url": "http://localhost:1234/v1/chat/completions", "model": "local-model"},
                "ollama": {"url": "http://localhost:11434", "model": "qwen2.5-coder:1.5b"}
            }

    def get_active_provider(self) -> str:
        if not hasattr(self, "config") or not self.config:
            self.load_config()
        return self.config.get("default_provider", "gemini").lower()

    def get_health_report(self) -> Dict[str, Dict[str, Any]]:
        return self.manager.check_all_health()

    def _local_fallback_enabled(self) -> bool:
        """Cascada a modelos locales solo con opt-in explícito (no cambia el
        comportamiento por defecto: sin flag, un provider_error se devuelve)."""
        try:
            return bool((self.config or {}).get("providers", {}).get("local_fallback", False))
        except Exception:
            return False

    def _known_secrets(self) -> List[str]:
        keys = []
        for name in _KEYED_PROVIDERS:
            try:
                keys.append(self._get_api_key(name))
            except Exception:
                continue
        return [k for k in keys if k]

    def redact(self, text):
        return redact_secret_text(text, self._known_secrets())

    def generate_response(self, system_prompt: str, prompt: str, history: List[Dict[str, str]] = None) -> str:
        provider = self.get_active_provider()
        adapter = self.manager.get_adapter(provider)
        return self.redact(adapter.generate_response(system_prompt, prompt, history))

    def generate_response_with_tools(self, system_prompt: str, contents: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self._generate_response_with_tools_unredacted(system_prompt, contents, tools)
        if isinstance(res, dict) and res.get("type") == "provider_error":
            res = dict(res)
            res["error"] = self.redact(res.get("error", ""))
        return res

    def _generate_response_with_tools_unredacted(self, system_prompt: str, contents: List[Dict[str, Any]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        provider = self.get_active_provider()
        adapter = self.manager.get_adapter(provider)
        res = adapter.generate_response_with_tools(system_prompt, contents, tools)

        # Normalización: una plantilla de vacío no es texto del modelo.
        if res.get("type") == "text" and (res.get("text") or "").strip().lower() in _EMPTY_TEXTS:
            res = {"type": "provider_empty", "provider": res.get("provider", provider),
                   "error": "La API respondió sin contenido aprovechable."}

        # Reparación 1: el modelo invocó una herramienta que no existe en el schema
        # (p. ej. 'SEARCH_CODE'). Un solo reintento guiado con la lista permitida;
        # si persiste, se devuelve como texto para que el loop/SAR/fallback decidan.
        if res.get("type") == "function_call" and tools:
            allowed = _allowed_tool_names(tools)
            if allowed and res.get("name") not in allowed:
                print(f"[LLMProvider]: Tool desconocido '{res.get('name')}'; reintento guiado.")
                res = adapter.generate_response_with_tools(
                    system_prompt,
                    _repair_contents(contents, allowed, bad_name=res.get("name") or "?"),
                    tools)
                if res.get("type") == "function_call" and res.get("name") not in allowed:
                    res = {"type": "text", "text": res.get("text", "")}

        # Reparación 2: el tool-call llegó truncado o con JSON inválido (400 del
        # proveedor). Un solo reintento pidiendo re-emisión completa.
        if res.get("type") == "provider_error" and _is_tool_parse_error(res.get("error", "")):
            print("[LLMProvider]: Tool-call malformado; reintento con reparación.")
            retry = adapter.generate_response_with_tools(
                system_prompt, _repair_contents(contents, _allowed_tool_names(tools),
                                               malformed=True), tools)
            if retry.get("type") != "provider_error":
                return retry

        if res.get("type") == "provider_error" and provider != "gemini":
            gemini_adapter = self.manager.get_adapter("gemini")
            if gemini_adapter and gemini_adapter.get_api_key():
                print(f"[LLMProvider]: Proveedor '{provider}' falló con error. Derivando automáticamente a Gemini...")
                res_gemini = gemini_adapter.generate_response_with_tools(system_prompt, contents, tools)
                if res_gemini.get("type") != "provider_error":
                    return res_gemini

        # Última red: modelos locales (sin costo, sin red). Solo con opt-in, solo si
        # están sanos, y devolviendo el error original si también fallan.
        if res.get("type") == "provider_error" and self._local_fallback_enabled():
            for local_name in ("ollama", "lmstudio"):
                if local_name == provider:
                    continue
                try:
                    local_adapter = self.manager.get_adapter(local_name)
                    if local_adapter is None:
                        continue
                    if local_adapter.check_health().status != "ACTIVE":
                        continue
                    print(f"[LLMProvider]: Cayendo al modelo local '{local_name}'...")
                    res_local = local_adapter.generate_response_with_tools(
                        system_prompt, contents, tools)
                    if res_local.get("type") != "provider_error":
                        return res_local
                except Exception:
                    continue
        return res
