"""
Reparación acotada en el facade del proveedor (Mauro la sufrió en vivo).

Casos: modelo invoca tool inexistente ('SEARCH_CODE') y tool-call truncado/400.
Regla: UN solo reintento guiado por caso; si persiste, el error fluye al loop
(SAR/fallback/mensaje ejecutivo). Sin red, sin claves: adaptadores simulados.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_provider import LLMProvider, _allowed_tool_names, _is_tool_parse_error

TOOLS = [{"functionDeclarations": [{"name": "COMMAND"}, {"name": "WRITE_FILE"}]}]


class FakeAdapter:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.last_contents = None

    def get_api_key(self):
        return ""  # sin clave: el fallback a gemini no aplica en estos tests

    def generate_response_with_tools(self, system_prompt, contents, tools=None):
        self.calls += 1
        self.last_contents = contents
        return self.script.pop(0) if self.script else {"type": "provider_error",
                                                       "error": "agotado"}


class FakeManager:
    def __init__(self, adapters):
        self.adapters = adapters

    def get_adapter(self, name):
        return self.adapters.get(name)


def _provider_with(script, provider_name="fake"):
    p = LLMProvider.__new__(LLMProvider)
    p.config = {"default_provider": provider_name,
                provider_name: {}, "gemini": {"api_key": ""}}
    adapter = FakeAdapter(script)
    p.manager = FakeManager({provider_name: adapter,
                             "gemini": FakeAdapter([{"type": "provider_error",
                                                     "error": "no gemini"}])})
    return p, adapter


class TestProviderRepair(unittest.TestCase):

    def test_allowed_names_from_gemini_schema(self):
        self.assertEqual(_allowed_tool_names(TOOLS), {"COMMAND", "WRITE_FILE"})
        self.assertEqual(_allowed_tool_names(
            [{"type": "function", "function": {"name": "X"}}]), {"X"})

    def test_parse_error_markers(self):
        self.assertTrue(_is_tool_parse_error(
            "Failed to parse tool call arguments as JSON"))
        self.assertTrue(_is_tool_parse_error(
            "attempted to call tool 'SEARCH_CODE' which was not in request.tools"))
        self.assertTrue(_is_tool_parse_error("HarmonyError: Tools should have a name"))
        self.assertFalse(_is_tool_parse_error("HTTP 429 quota exceeded"))

    def test_unknown_tool_gets_one_guided_retry(self):
        good = {"type": "function_call", "name": "COMMAND",
                "args": {"command": "echo x"}, "text": ""}
        p, adapter = _provider_with([
            {"type": "function_call", "name": "SEARCH_CODE",
             "args": {"q": "x"}, "text": ""},
            good,
        ])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res, good)
        self.assertEqual(adapter.calls, 2, "exactamente un reintento")
        flat = str(adapter.last_contents)
        self.assertIn("SEARCH_CODE", flat)
        self.assertIn("COMMAND", flat)

    def test_persistent_unknown_tool_degrades_to_text(self):
        p, adapter = _provider_with([
            {"type": "function_call", "name": "NOPE", "args": {}, "text": "hola"},
            {"type": "function_call", "name": "NOPE", "args": {}, "text": "hola"},
        ])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res["type"], "text")
        self.assertEqual(adapter.calls, 2, "sin bucle infinito")

    def test_truncated_tool_call_gets_one_repair_retry(self):
        good = {"type": "function_call", "name": "WRITE_FILE",
                "args": {"file_path": "a.txt", "content": "x"}, "text": ""}
        p, adapter = _provider_with([
            {"type": "provider_error",
             "error": '{"message":"Failed to parse tool call arguments as JSON"'
                      ',"code":"tool_use_failed"}'},
            good,
        ])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res, good)
        self.assertEqual(adapter.calls, 2)

    def test_non_parse_errors_do_not_retry_same_provider(self):
        p, adapter = _provider_with([
            {"type": "provider_error", "error": "HTTP 429 quota exceeded"},
        ])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res["type"], "provider_error")
        # 1 llamada al proveedor + 1 al fallback gemini (que también falla)
        self.assertEqual(adapter.calls, 1)

    def test_canned_empty_text_normalizes_to_provider_empty(self):
        """Una plantilla de vacío no es prosa del modelo: se normaliza."""
        for canned in ("Respuesta vacía del proveedor.", "Respuesta vacía de Gemini.",
                       "Sin contenido devuelto.", "  "):
            p, adapter = _provider_with([
                {"type": "text", "provider": "fake", "text": canned},
            ])
            res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
            self.assertEqual(res["type"], "provider_empty", f"falló con: {canned!r}")
        # Texto real pasa intacto.
        p, adapter = _provider_with([
            {"type": "text", "provider": "fake", "text": "hola Mauro"},
        ])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res["type"], "text")

    def test_local_cascade_off_by_default(self):
        """Sin opt-in, un provider_error se devuelve (comportamiento histórico)."""
        from core.llm_provider import ProviderHealth

        p, adapter = _provider_with([
            {"type": "provider_error", "error": "HTTP 429 quota exceeded"},
        ])
        self.assertFalse(p._local_fallback_enabled())

    def test_local_cascade_uses_healthy_ollama(self):
        from core.llm_provider import ProviderHealth

        p, adapter = _provider_with([
            {"type": "provider_error", "error": "HTTP 429 quota exceeded"},
        ])
        p.config.setdefault("providers", {})["local_fallback"] = True

        answered = {"type": "text", "provider": "ollama",
                    "text": "respuesta local"}

        class HealthyLocal(FakeAdapter):
            def check_health(self):
                return ProviderHealth(provider_name="ollama", status="ACTIVE",
                                      message="ok")

        p.manager.adapters["ollama"] = HealthyLocal([answered])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res, answered)

    def test_local_cascade_skips_unhealthy_and_returns_original(self):
        from core.llm_provider import ProviderHealth

        p, adapter = _provider_with([
            {"type": "provider_error", "error": "HTTP 503 down"},
        ])
        p.config.setdefault("providers", {})["local_fallback"] = True

        class DeadLocal(FakeAdapter):
            def check_health(self):
                return ProviderHealth(provider_name="ollama", status="OFFLINE",
                                      message="no")

        p.manager.adapters["ollama"] = DeadLocal(
            [{"type": "text", "provider": "ollama", "text": "nunca"}])
        res = p.generate_response_with_tools("sys", [{"role": "user"}], TOOLS)
        self.assertEqual(res["type"], "provider_error")
        self.assertIn("503", res["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
