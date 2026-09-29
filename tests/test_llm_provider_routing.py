import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock

cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cwd not in sys.path:
    sys.path.insert(0, cwd)

from core.llm_provider import LLMProvider

class TestLLMProviderRouting(unittest.TestCase):

    def setUp(self):
        self.provider = LLMProvider()
        # Hermético: la cascada local depende del config real de la máquina;
        # estos tests verifican el comportamiento base sin ella.
        self.provider.config.setdefault("providers", {})["local_fallback"] = False
        # Fake key so mocked HTTP paths are reached (F-22); never a real credential.
        self.provider.config.setdefault("gemini", {})["api_key"] = "TEST_GEMINI_KEY_FOR_UNITTESTS"

    def test_001_provider_selection_persists(self):
        self.provider.config["default_provider"] = "groq"
        self.assertEqual(self.provider.get_active_provider(), "groq")
        self.provider.config["default_provider"] = "gemini"
        self.assertEqual(self.provider.get_active_provider(), "gemini")

    def test_002_invalid_provider_fallback(self):
        self.provider.config["default_provider"] = "unknown_provider"
        active = self.provider.get_active_provider()
        self.assertEqual(active, "unknown_provider")

    @patch("requests.post")
    def test_003_gemini_429_returns_structured_error(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 429
        mock_res.text = json.dumps({"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})
        mock_post.return_value = mock_res

        self.provider.config["default_provider"] = "gemini"
        res = self.provider.generate_response_with_tools("System", [{"role": "user", "parts": [{"text": "Hi"}]}])
        
        self.assertEqual(res["type"], "provider_error")
        self.assertEqual(res["provider"], "gemini")
        self.assertEqual(res["status_code"], 429)
        self.assertEqual(res["reason"], "QUOTA_EXHAUSTED")
        self.assertTrue(res["recoverable"])

    def test_004_openai_unavailable_without_key(self):
        self.provider.config["default_provider"] = "openai"
        with patch.object(self.provider, "_get_api_key", return_value=""):
            res = self.provider.generate_response_with_tools("System", [{"role": "user", "parts": [{"text": "Hi"}]}])
            self.assertEqual(res["type"], "provider_error")
            self.assertEqual(res["provider"], "openai")
            self.assertEqual(res["status_code"], 401)
            self.assertEqual(res["reason"], "MISSING_API_KEY")

    def test_005_groq_unavailable_without_key(self):
        self.provider.config["default_provider"] = "groq"
        with patch.object(self.provider, "_get_api_key", return_value=""):
            res = self.provider.generate_response_with_tools("System", [{"role": "user", "parts": [{"text": "Hi"}]}])
            self.assertEqual(res["type"], "provider_error")
            self.assertEqual(res["provider"], "groq")
            self.assertEqual(res["status_code"], 401)

    @patch("requests.post")
    def test_006_no_accidental_gemini_call_when_groq_selected(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "LIST_DIR", "arguments": "{\"dir_path\": \".\"}"}
                    }]
                }
            }]
        }
        mock_post.return_value = mock_res

        self.provider.config["default_provider"] = "groq"
        with patch.object(self.provider, "_get_api_key", return_value="gsk_testkey"):
            res = self.provider.generate_response_with_tools("System", [{"role": "user", "parts": [{"text": "List dir"}]}])
            
            # Verify URL passed to requests.post was Groq, NOT Gemini
            args, kwargs = mock_post.call_args
            self.assertIn("api.groq.com", args[0])
            self.assertNotIn("generativelanguage.googleapis.com", args[0])
            self.assertEqual(res["type"], "function_call")
            self.assertEqual(res["provider"], "groq")
            self.assertEqual(res["name"], "LIST_DIR")

    @patch("requests.post")
    def test_007_no_accidental_gemini_call_when_openai_selected(self, mock_post):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "choices": [{
                "message": {"content": "Hello from OpenAI"}
            }]
        }
        mock_post.return_value = mock_res

        self.provider.config["default_provider"] = "openai"
        with patch.object(self.provider, "_get_api_key", return_value="sk-testkey"):
            res = self.provider.generate_response_with_tools("System", [{"role": "user", "parts": [{"text": "Hi"}]}])
            
            args, kwargs = mock_post.call_args
            self.assertIn("api.openai.com", args[0])
            self.assertNotIn("generativelanguage.googleapis.com", args[0])
            self.assertEqual(res["type"], "text")
            self.assertEqual(res["provider"], "openai")
            self.assertEqual(res["text"], "Hello from OpenAI")

if __name__ == "__main__":
    unittest.main()
