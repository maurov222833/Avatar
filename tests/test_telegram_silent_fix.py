"""Telegram must never look “dead”: always reply or surface errors."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest import mock


def _msg(user_id=111, text="hola", chat_type="private"):
    return {
        "message_id": 1,
        "from": {"id": user_id, "is_bot": False, "username": "mauro"},
        "chat": {"id": user_id, "type": chat_type},
        "text": text,
    }


class TestTelegramSilentFailureFixes(unittest.TestCase):
    def _bridge(self, allowed=("111",)):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator

        with mock.patch.dict(os.environ, {"TELEGRAM_ALLOWED_CHAT_IDS": ",".join(allowed)}):
            orch = AvatarOrchestrator()
            b = TelegramBridge(
                bot_token="123456:TEST",
                allowed_chat_ids=list(allowed),
                orchestrator=orch,
                auto_enroll_first_private=False,
            )
        b.sent = []
        b.actions = []
        b.send_message = lambda chat_id, text: (
            b.sent.append((str(chat_id), text)) or {"ok": True, "message_id": 1}
        )
        b.send_chat_action = lambda chat_id, action="typing": (
            b.actions.append((str(chat_id), action)) or {"ok": True}
        )
        return b

    def test_empty_model_reply_still_sends_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                b = self._bridge()
                b.orchestrator.process_user_input = lambda text, **kw: ""
                b.handle_message(_msg(text="Como te sientes hoy?"))
                self.assertEqual(b.actions, [("111", "typing")])
                self.assertEqual(len(b.sent), 1)
                self.assertIn("Te escuché", b.sent[0][1])

    def test_orchestrator_exception_still_replies(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                b = self._bridge()

                def boom(text, **kw):
                    raise RuntimeError("provider down")

                b.orchestrator.process_user_input = boom
                b.handle_message(_msg(text="hola"))
                self.assertEqual(len(b.sent), 1)
                self.assertIn("falló", b.sent[0][1].lower())

    def test_send_message_rejects_blank_body(self):
        from bridges.telegram_bridge import TelegramBridge

        b = TelegramBridge.__new__(TelegramBridge)
        b.bot_token = "1:AA"
        b.base_url = "https://api.telegram.org/bot1:AA"
        b.last_outbound_at = None
        b.last_error = ""
        b._redact = lambda t: str(t)
        captured = {}

        def fake_post(url, json=None, timeout=10):
            captured["payload"] = json
            resp = mock.Mock()
            resp.status_code = 200
            resp.content = b'{"ok":true,"result":{"message_id":9}}'
            resp.json.return_value = {"ok": True, "result": {"message_id": 9}}
            return resp

        with mock.patch("bridges.telegram_bridge.requests.post", side_effect=fake_post):
            out = b.send_message("111", "   ")
        self.assertTrue(out["ok"])
        self.assertTrue(captured["payload"]["text"].strip())
        self.assertIn("Te escuché", captured["payload"]["text"])

    def test_rejection_cooldown_re_notifies(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                b = self._bridge(allowed=("999",))  # Mauro 111 not allowlisted
                b.handle_message(_msg(user_id=111, text="hola"))
                b.handle_message(_msg(user_id=111, text="hola otra vez"))
                # Second within cooldown → only one notice
                self.assertEqual(len(b.sent), 1)
                # Expire cooldown
                key = ("111", "111")
                b._reported_chats[key] = time.monotonic() - 200
                b.handle_message(_msg(user_id=111, text="hola de nuevo"))
                self.assertEqual(len(b.sent), 2)
                self.assertIn("allowlist", b.sent[-1][1].lower())

    def test_status_skips_getupdates_peek_when_daemon_running(self):
        from core.orchestrator import AvatarOrchestrator

        peeks = []

        class FakeBridge:
            bot_token = "1:AA"
            allowed_chat_ids = {"111"}

            def api_get_me(self):
                return {"ok": True, "username": "Bot", "id": 1}

            def api_webhook_info(self):
                return {"ok": True, "url": ""}

            def api_delete_webhook(self, drop_pending=False):
                return {"ok": True}

            def api_recent_private_chat_ids(self, limit=20):
                peeks.append(1)
                return [{"chat_id": "111"}]

        orch = AvatarOrchestrator.__new__(AvatarOrchestrator)
        orch._telegram_bridge = lambda: FakeBridge()
        with mock.patch("core.telegram_daemon.status", return_value={"running": True, "poll_conflicts_409": 0}):
            import json
            out = orch._exec_telegram("status", {})
            data = json.loads(out)
        self.assertEqual(peeks, [])
        self.assertEqual(data["recent_private_chats"], [])


if __name__ == "__main__":
    unittest.main()
