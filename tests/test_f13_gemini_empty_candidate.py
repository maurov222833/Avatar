"""F-13: an empty or blocked Gemini candidate must not look like success text."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_provider import LLMProvider, _EMPTY_TEXTS


class _Resp:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        return self._payload


class TestF13GeminiEmptyCandidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prev_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = "fake-key-for-f13-tests-xx"
        self.provider = LLMProvider(config_path=os.path.join(self.tmp.name, "missing.json"))
        self.provider.config["default_provider"] = "gemini"
        self.provider.config.setdefault("providers", {})["local_fallback"] = False

    def tearDown(self):
        if self.prev_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = self.prev_key

    def _call(self, payload):
        with mock.patch("requests.post", return_value=_Resp(payload)):
            return self.provider.generate_response_with_tools(
                "sys",
                [{"role": "user", "parts": [{"text": "x"}]}],
                [],
            )

    def test_safety_block_without_parts_is_not_success_text(self):
        res = self._call({
            "candidates": [{
                "finishReason": "SAFETY",
                "content": {"parts": []},
            }]
        })
        self.assertEqual(res["type"], "provider_empty")
        self.assertNotEqual(
            (res.get("text") or "").strip().lower(),
            "respuesta procesada correctamente.",
        )
        self.assertNotIn("procesada correctamente", (res.get("text") or "").lower())
        self.assertEqual(res.get("finish_reason") or res.get("reason"), "SAFETY")

    def test_empty_parts_without_finish_reason_is_provider_empty(self):
        res = self._call({"candidates": [{"content": {"parts": []}}]})
        self.assertEqual(res["type"], "provider_empty")

    def test_whitespace_only_text_part_is_provider_empty(self):
        res = self._call({
            "candidates": [{
                "content": {"parts": [{"text": "   \n"}]},
            }]
        })
        self.assertEqual(res["type"], "provider_empty")

    def test_no_candidates_with_prompt_block_is_provider_empty(self):
        res = self._call({
            "candidates": [],
            "promptFeedback": {"blockReason": "BLOCKLIST"},
        })
        self.assertEqual(res["type"], "provider_empty")
        self.assertIn(
            res.get("finish_reason") or res.get("reason"),
            ("BLOCKLIST", "NO_CANDIDATES"),
        )

    def test_real_text_still_passes(self):
        res = self._call({
            "candidates": [{
                "content": {"parts": [{"text": "Hola Mauro"}]},
            }]
        })
        self.assertEqual(res["type"], "text")
        self.assertEqual(res["text"], "Hola Mauro")

    def test_function_call_still_passes(self):
        res = self._call({
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "LIST_DIR",
                            "args": {"dir_path": "."},
                        }
                    }]
                }
            }]
        })
        self.assertEqual(res["type"], "function_call")
        self.assertEqual(res["name"], "LIST_DIR")

    def test_canned_success_phrase_is_listed_as_empty(self):
        self.assertIn("respuesta procesada correctamente.", _EMPTY_TEXTS)


if __name__ == "__main__":
    unittest.main()
