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
        # Empty cascade = no automatic peer fallback (hermetic single-provider tests).
        self.provider.config.setdefault("providers", {})["cascade"] = []
        # Isolate usage ledger
        import tempfile
        from core.provider_usage import reset_usage_ledger_for_tests
        self._usage_td = tempfile.TemporaryDirectory()
        reset_usage_ledger_for_tests(
            path=os.path.join(self._usage_td.name, "usage.jsonl")
        )

    def tearDown(self):
        self._usage_td.cleanup()

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


class TestR4HealthCascade(unittest.TestCase):
    def setUp(self):
        import tempfile
        from core.provider_usage import reset_usage_ledger_for_tests

        self.provider = LLMProvider()
        self.provider.config.setdefault("providers", {})["local_fallback"] = False
        self.provider.config["default_provider"] = "groq"
        self.provider.config.setdefault("providers", {})["cascade"] = ["groq", "gemini"]
        self.provider.config.setdefault("gemini", {})["api_key"] = "TEST_GEMINI_KEY_FOR_UNITTESTS"
        self.provider.config.setdefault("groq", {})["api_key"] = "gsk_test_cascade_key_1234567890"
        self._td = tempfile.TemporaryDirectory()
        reset_usage_ledger_for_tests(path=os.path.join(self._td.name, "usage.jsonl"))

    def tearDown(self):
        self._td.cleanup()

    def test_cascade_derives_to_healthy_gemini_when_groq_fails(self):
        groq = self.provider.manager.get_adapter("groq")
        gemini = self.provider.manager.get_adapter("gemini")
        with patch.object(
            groq,
            "generate_response_with_tools",
            return_value={
                "type": "provider_error",
                "provider": "groq",
                "error": "down",
                "status_code": 500,
                "reason": "UPSTREAM",
                "recoverable": True,
            },
        ):
            with patch.object(
                gemini,
                "generate_response_with_tools",
                return_value={"type": "text", "provider": "gemini", "text": "ok from gemini"},
            ) as gcall:
                res = self.provider.generate_response_with_tools(
                    "System", [{"role": "user", "parts": [{"text": "Hi"}]}]
                )
        self.assertEqual(res["type"], "text")
        self.assertEqual(res["provider"], "gemini")
        gcall.assert_called_once()
        summary = self.provider.get_usage_summary(window_seconds=3600)
        self.assertGreaterEqual(summary["by_provider"].get("groq", {}).get("error", 0), 1)
        self.assertGreaterEqual(summary["by_provider"].get("gemini", {}).get("success", 0), 1)

    def test_max_calls_per_hour_blocks(self):
        self.provider.config["default_provider"] = "gemini"
        self.provider.config.setdefault("providers", {})["max_calls_per_hour"] = 1
        self.provider.config["providers"]["cascade"] = []
        gemini = self.provider.manager.get_adapter("gemini")
        with patch.object(
            gemini,
            "generate_response_with_tools",
            return_value={"type": "text", "provider": "gemini", "text": "one"},
        ):
            first = self.provider.generate_response_with_tools(
                "S", [{"role": "user", "parts": [{"text": "a"}]}]
            )
            second = self.provider.generate_response_with_tools(
                "S", [{"role": "user", "parts": [{"text": "b"}]}]
            )
        self.assertEqual(first["type"], "text")
        self.assertEqual(second["type"], "provider_error")
        self.assertEqual(second["reason"], "USAGE_BUDGET_EXCEEDED")

    def test_skips_missing_key_in_cascade(self):
        self.provider.config["providers"]["cascade"] = ["openai", "gemini"]
        self.provider.config["default_provider"] = "openai"
        with patch.object(self.provider, "_get_api_key", side_effect=lambda p: (
            "TEST_GEMINI_KEY_FOR_UNITTESTS" if p == "gemini" else ""
        )):
            gemini = self.provider.manager.get_adapter("gemini")
            with patch.object(
                gemini,
                "generate_response_with_tools",
                return_value={"type": "text", "provider": "gemini", "text": "via gemini"},
            ) as gcall:
                res = self.provider.generate_response_with_tools(
                    "S", [{"role": "user", "parts": [{"text": "hi"}]}]
                )
        self.assertEqual(res["provider"], "gemini")
        gcall.assert_called_once()


if __name__ == "__main__":
    unittest.main()