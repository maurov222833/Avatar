"""F-12: OpenAI-compatible turns must keep the tool_call id on the tool result."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_provider import OpenAICompatibleAdapter


class _FakeConfig:
    def __init__(self):
        self.config = {
            "groq": {
                "api_key": "fake-key-for-tests",
                "model": "test-model",
                "url": "https://example.test/v1/chat/completions",
            }
        }

    def get_provider_config(self, name):
        return self.config.get(name, {})

    def _get_api_key(self, name):
        return self.config.get(name, {}).get("api_key", "")


class _Resp:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        return self._payload


class TestF12ToolCallId(unittest.TestCase):
    def test_tool_result_reuses_the_assistant_call_id(self):
        adapter = OpenAICompatibleAdapter(_FakeConfig(), "groq", "test-model", "https://example.test/v1")
        contents = [
            {"role": "user", "parts": [{"text": "lista"}]},
            {
                "role": "model",
                "parts": [{
                    "functionCall": {
                        "name": "LIST_DIR",
                        "args": {"dir_path": "."},
                        "id": "call_REAL_123",
                    }
                }],
            },
            {
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": "LIST_DIR",
                        "id": "call_REAL_123",
                        "response": {"output": "a.py"},
                    }
                }],
            },
        ]
        sent = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            sent["payload"] = json
            return _Resp({"choices": [{"message": {"content": "listo"}}]})

        with mock.patch("requests.post", side_effect=fake_post):
            res = adapter.generate_response_with_tools("sys", contents, tools=None)
        self.assertEqual(res["type"], "text")
        msgs = sent["payload"]["messages"]
        tool_ids = [m.get("tool_call_id") for m in msgs if m.get("role") == "tool"]
        call_ids = [
            tc["id"]
            for m in msgs if m.get("tool_calls")
            for tc in m["tool_calls"]
        ]
        self.assertEqual(call_ids, ["call_REAL_123"])
        self.assertEqual(tool_ids, ["call_REAL_123"])

    def test_missing_response_id_must_not_fall_back_to_call_default_when_call_has_id(self):
        """The live bug: orchestrator omitted id on functionResponse."""
        adapter = OpenAICompatibleAdapter(_FakeConfig(), "groq", "test-model", "https://example.test/v1")
        contents = [
            {"role": "user", "parts": [{"text": "lista"}]},
            {
                "role": "model",
                "parts": [{
                    "functionCall": {
                        "name": "LIST_DIR",
                        "args": {"dir_path": "."},
                        "id": "call_REAL_123",
                    }
                }],
            },
            {
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": "LIST_DIR",
                        "response": {"output": "a.py"},
                    }
                }],
            },
        ]
        sent = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            sent["payload"] = json
            return _Resp({"choices": [{"message": {"content": "listo"}}]})

        with mock.patch("requests.post", side_effect=fake_post):
            adapter.generate_response_with_tools("sys", contents, tools=None)
        msgs = sent["payload"]["messages"]
        tool_ids = [m.get("tool_call_id") for m in msgs if m.get("role") == "tool"]
        call_ids = [
            tc["id"]
            for m in msgs if m.get("tool_calls")
            for tc in m["tool_calls"]
        ]
        self.assertEqual(call_ids, ["call_REAL_123"])
        self.assertEqual(tool_ids, call_ids)
        self.assertNotIn("call_default", tool_ids)

    def test_orchestrator_second_turn_keeps_matching_ids(self):
        import core.orchestrator as orch_mod

        os.environ["GROQ_API_KEY"] = "fake"
        os.environ.pop("GEMINI_API_KEY", None)
        orch = orch_mod.AvatarOrchestrator()
        orch.llm.config["default_provider"] = "groq"
        orch.llm.config.setdefault("providers", {})["local_fallback"] = False
        orch.llm.config.setdefault("gemini", {})["api_key"] = ""
        orch.chokepoint.executors["LIST_DIR"] = lambda a: "a.py\nb.py"
        sent = []
        first = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_REAL_123",
                        "type": "function",
                        "function": {
                            "name": "LIST_DIR",
                            "arguments": "{\"dir_path\": \".\"}",
                        },
                    }]
                }
            }]
        }
        second = {"choices": [{"message": {"content": "Hay dos archivos."}}]}
        seq = [first, second, second, second]

        def fake_post(url, json=None, headers=None, timeout=None):
            sent.append(json)
            return _Resp(seq[min(len(sent) - 1, len(seq) - 1)])

        with mock.patch("requests.post", side_effect=fake_post):
            reply = orch.process_user_input("lista los archivos del proyecto ahora")
        self.assertTrue(len(sent) >= 2, reply)
        msgs = sent[1]["messages"]
        tool_ids = [m.get("tool_call_id") for m in msgs if m.get("role") == "tool"]
        call_ids = [
            tc["id"]
            for m in msgs if m.get("tool_calls")
            for tc in m["tool_calls"]
        ]
        self.assertEqual(call_ids, ["call_REAL_123"])
        self.assertEqual(tool_ids, ["call_REAL_123"])
        self.assertIn("Hay dos archivos", reply)

    def test_window_does_not_send_an_orphan_tool_result(self):
        adapter = OpenAICompatibleAdapter(_FakeConfig(), "groq", "test-model", "https://example.test/v1")
        # Eleven turns so [-10:] drops the first user+call and starts on a response.
        contents = [{"role": "user", "parts": [{"text": "start"}]}]
        for i in range(5):
            contents.append({
                "role": "model",
                "parts": [{
                    "functionCall": {
                        "name": "LIST_DIR",
                        "args": {"dir_path": "."},
                        "id": f"call_{i}",
                    }
                }],
            })
            contents.append({
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": "LIST_DIR",
                        "id": f"call_{i}",
                        "response": {"output": str(i)},
                    }
                }],
            })
        self.assertEqual(len(contents), 11)
        contents.append({"role": "user", "parts": [{"text": "y ahora?"}]})
        self.assertEqual(len(contents), 12)
        sent = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            sent["payload"] = json
            return _Resp({"choices": [{"message": {"content": "ok"}}]})

        with mock.patch("requests.post", side_effect=fake_post):
            adapter.generate_response_with_tools("sys", contents, tools=None)
        msgs = sent["payload"]["messages"]
        # After the system message, the window must not start on an orphan tool result.
        self.assertNotEqual(msgs[1].get("role"), "tool")
        last_call = None
        for msg in msgs:
            if msg.get("tool_calls"):
                last_call = msg["tool_calls"][0]["id"]
            elif msg.get("role") == "tool":
                self.assertIsNotNone(last_call)
                self.assertEqual(msg.get("tool_call_id"), last_call)
                last_call = None
        self.assertIsNone(last_call)


if __name__ == "__main__":
    unittest.main()
