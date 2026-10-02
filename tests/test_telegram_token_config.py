"""Fix: owner can save Telegram token without TOOL_CALL_CONTAINS_SECRET false positive."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTelegramTokenConfigPath(unittest.TestCase):
    KEY = "AIzaSyFakeGeminiKeyValueForTests123456"

    def test_rewrite_config_with_loaded_key_is_allowed(self):
        """WRITE_FILE to AVATAR_HOME/config.json may repeat a loaded provider key."""
        from core.llm_provider import LLMProvider
        from core.paths import config_path

        home = tempfile.mkdtemp(prefix="avatar_tg_cfg_")
        os.environ["AVATAR_HOME"] = home
        os.makedirs(os.path.join(home, "memory"), exist_ok=True)
        cfg_path = config_path()
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"gemini": {"api_key": self.KEY}}, f)

        content = json.dumps({
            "gemini": {"api_key": self.KEY},
            "telegram": {"bot_token": "8956558509:AAEFakeTelegramTokenValue_abcdefghij"},
        })
        body = {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "WRITE_FILE",
            "args": {"file_path": cfg_path, "content": content},
        }}]}}]}
        resp = mock.Mock(status_code=200, text="", json=lambda: body)
        p = LLMProvider(config_path=cfg_path)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": self.KEY}), \
                mock.patch("requests.post", return_value=resp):
            p.config["default_provider"] = "gemini"
            p.config.setdefault("gemini", {})["api_key"] = self.KEY
            res = p.generate_response_with_tools(
                "s", [{"role": "user", "parts": [{"text": "guarda token"}]}],
                [{"functionDeclarations": [{"name": "WRITE_FILE"}]}],
            )
        self.assertEqual(res["type"], "function_call", res)
        self.assertEqual(res["name"], "WRITE_FILE")

    def test_command_still_refuses_loaded_key(self):
        from core.llm_provider import LLMProvider

        home = tempfile.mkdtemp(prefix="avatar_tg_cmd_")
        cfg_path = os.path.join(home, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"gemini": {"api_key": self.KEY}}, f)
        body = {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "COMMAND",
            "args": {"command": f"echo {self.KEY}"},
        }}]}}]}
        resp = mock.Mock(status_code=200, text="", json=lambda: body)
        p = LLMProvider(config_path=cfg_path)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": self.KEY}), \
                mock.patch("requests.post", return_value=resp):
            p.config["default_provider"] = "gemini"
            p.config.setdefault("gemini", {})["api_key"] = self.KEY
            res = p.generate_response_with_tools(
                "s", [{"role": "user", "parts": [{"text": "x"}]}],
                [{"functionDeclarations": [{"name": "COMMAND"}]}],
            )
        self.assertEqual(res["type"], "provider_error")
        self.assertEqual(res["reason"], "TOOL_CALL_CONTAINS_SECRET")
        self.assertIn("UPDATE_CONFIG", res["error"])
        self.assertTrue(res.get("recoverable"))

    def test_update_config_saves_telegram_token_without_echo(self):
        home = tempfile.mkdtemp(prefix="avatar_tg_upd_")
        prev = os.environ.get("AVATAR_HOME")
        os.environ["AVATAR_HOME"] = home
        os.makedirs(os.path.join(home, "memory"), exist_ok=True)
        from core.paths import config_path
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump({"gemini": {"api_key": "x"}, "telegram": {}}, f)

        from core import runtime
        runtime.reset_shared_orchestrator()
        try:
            from core.orchestrator import AvatarOrchestrator
            orch = AvatarOrchestrator()
            token = "8956558509:AAEFakeTelegramTokenValue_abcdefghijklmnop"
            out = orch.chokepoint.perform(
                "UPDATE_CONFIG",
                {"key": "telegram.bot_token", "value": token},
                mission_id="m1",
            )
            self.assertIn("RESULT:OK", out)
            self.assertNotIn(token, out)
            with open(config_path(), encoding="utf-8") as handle:
                stored = json.load(handle)
            self.assertEqual(stored["telegram"]["bot_token"], token)
        finally:
            runtime.reset_shared_orchestrator()
            if prev is None:
                os.environ.pop("AVATAR_HOME", None)
            else:
                os.environ["AVATAR_HOME"] = prev
                runtime.reset_shared_orchestrator()

    def test_system_prompt_teaches_update_config_not_token_splitting(self):
        from core.orchestrator import AvatarOrchestrator
        orch = AvatarOrchestrator()
        prompt = orch.system_prompt.lower()
        self.assertIn("update_config", prompt)
        self.assertIn("telegram.bot_token", prompt)
        self.assertIn("partir", prompt)


if __name__ == "__main__":
    unittest.main()
