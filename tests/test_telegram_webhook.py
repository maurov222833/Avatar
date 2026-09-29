"""F-06 / Telegram: deleteWebhook before polling; status reports daemon+webhook."""
from __future__ import annotations

import unittest
from unittest import mock


class TestTelegramWebhookClear(unittest.TestCase):
    def test_start_polling_deletes_webhook_first(self):
        from bridges.telegram_bridge import TelegramBridge

        b = TelegramBridge.__new__(TelegramBridge)
        b.bot_token = "1:AA"
        b.base_url = "https://api.telegram.org/bot1:AA"
        b.allowed_chat_ids = set()
        b.auto_enroll_first_private = True
        b.last_update_id = 0
        calls = []

        b.api_webhook_info = lambda: {"ok": True, "url": "https://evil.example/hook"}
        b.api_delete_webhook = lambda drop_pending=False: calls.append("delete") or {"ok": True}
        b.api_get_me = lambda: {"ok": True, "username": "XBot"}

        # One empty getUpdates then break via side effect
        n = {"i": 0}

        def fake_get(url, timeout=35):
            n["i"] += 1
            if n["i"] > 1:
                raise KeyboardInterrupt()
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = {"ok": True, "result": []}
            resp.text = ""
            return resp

        with mock.patch("bridges.telegram_bridge.requests.get", side_effect=fake_get), \
                mock.patch("bridges.telegram_bridge.time.sleep", return_value=None):
            try:
                b.start_polling()
            except KeyboardInterrupt:
                pass
        self.assertEqual(calls, ["delete"])


if __name__ == "__main__":
    unittest.main()
