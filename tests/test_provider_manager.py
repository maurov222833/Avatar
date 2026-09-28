import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.llm_provider import (
    LLMProvider,
    ProviderManager,
    ProviderCapabilities,
    ProviderHealth,
    BaseAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
    OllamaAdapter
)

class TestProviderManager(unittest.TestCase):

    def setUp(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "test_config_manager.json")
        sample_cfg = {
            "default_provider": "gemini",
            "gemini": {"api_key": "TEST_GEMINI_KEY", "model": "gemini-3.6-flash"},
            "openai": {"api_key": "TEST_OPENAI_KEY", "model": "gpt-4o-mini"},
            "groq": {"api_key": "TEST_GROQ_KEY", "model": "qwen/qwen3.8-27b", "url": "https://api.groq.com/openai/v1/chat/completions"},
            "github": {"api_key": "TEST_GITHUB_TOKEN", "model": "gpt-4o", "url": "https://models.inference.ai.azure.com/chat/completions"},
            "lmstudio": {"url": "http://localhost:1234/v1/chat/completions", "model": "local-model"},
            "ollama": {"url": "http://localhost:11434", "model": "qwen2.5-coder:1.5b"}
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(sample_cfg, f)

        self.llm = LLMProvider(config_path=self.config_path)

    def tearDown(self):
        if os.path.exists(self.config_path):
            try:
                os.remove(self.config_path)
            except Exception:
                pass

    def test_001_capabilities_structure(self):
        """Verifica que las capacidades estén correctamente definidas."""
        caps = ProviderCapabilities(text=True, function_calling=True, multi_turn=True, json_schema=True)
        self.assertTrue(caps.text)
        self.assertTrue(caps.function_calling)
        self.assertTrue(caps.multi_turn)
        self.assertTrue(caps.json_schema)
        self.assertFalse(caps.vision)

    def test_002_health_report_structure(self):
        """Verifica el reporte de salud para todos los proveedores."""
        report = self.llm.get_health_report()
        self.assertIn("gemini", report)
        self.assertIn("openai", report)
        self.assertIn("groq", report)
        self.assertIn("github", report)
        self.assertIn("lmstudio", report)
        self.assertIn("ollama", report)
        
        for p, data in report.items():
            self.assertEqual(data["provider"], p)
            self.assertIn("status", data)
            self.assertIn("message", data)
            self.assertIn("capabilities", data)

    def test_003_manager_adapter_retrieval(self):
        """Verifica que ProviderManager retorne los adaptadores correctos."""
        manager = self.llm.manager
        gemini_adapter = manager.get_adapter("gemini")
        self.assertIsInstance(gemini_adapter, GeminiAdapter)
        
        groq_adapter = manager.get_adapter("groq")
        self.assertIsInstance(groq_adapter, OpenAICompatibleAdapter)
        self.assertEqual(groq_adapter.provider_name, "groq")

        chatgpt_adapter = manager.get_adapter("chatgpt")
        self.assertIsInstance(chatgpt_adapter, OpenAICompatibleAdapter)
        self.assertEqual(chatgpt_adapter.provider_name, "openai")

    @patch("requests.post")
    def test_004_gemini_adapter_query(self, mock_post):
        """Verifica la invocación a través de GeminiAdapter."""
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hola desde Gemini Adapter"}]}}]
        }
        mock_post.return_value = mock_res

        resp = self.llm.generate_response("System Prompt", "User Prompt")
        self.assertEqual(resp, "Hola desde Gemini Adapter")

    @patch("requests.post")
    def test_005_openai_adapter_tools(self, mock_post):
        """Verifica Function Calling a través de OpenAICompatibleAdapter."""
        self.llm.config["default_provider"] = "openai"
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_123",
                        "function": {
                            "name": "COMMAND",
                            "arguments": "{\"command\": \"dir\"}"
                        }
                    }]
                }
            }]
        }
        mock_post.return_value = mock_res

        res = self.llm.generate_response_with_tools("System Prompt", [{"parts": [{"text": "run dir"}]}])
        self.assertEqual(res["type"], "function_call")
        self.assertEqual(res["provider"], "openai")
        self.assertEqual(res["name"], "COMMAND")
        self.assertEqual(res["args"], {"command": "dir"})

if __name__ == "__main__":
    unittest.main()
