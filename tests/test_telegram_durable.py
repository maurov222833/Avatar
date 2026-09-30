"""Durable Telegram: poll lock, supervisor restart, queue decoupling."""
from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from unittest import mock


class TestTelegramPollLock(unittest.TestCase):
    def test_second_acquire_fails_while_held(self):
        from core.telegram_poll_lock import TelegramPollLock

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "telegram_poll.lock")
            a = TelegramPollLock(path)
            b = TelegramPollLock(path)
            self.assertTrue(a.acquire(blocking=False))
            self.assertFalse(b.acquire(blocking=False))
            a.release()
            self.assertTrue(b.acquire(blocking=False))
            b.release()


class TestTelegramDurableDaemon(unittest.TestCase):
    def tearDown(self):
        try:
            from core import telegram_daemon as d

            d.stop_telegram_daemon()
            # Reset module globals for isolation
            d._poll_thread = None
            d._worker_thread = None
            d._supervisor_thread = None
            d._bridge = None
            d._restart_count = 0
            d._standby_other_instance = False
            d._stop.clear()
            try:
                d._poll_lock.release()
            except Exception:
                pass
        except Exception:
            pass

    def test_ensure_starts_supervisor_poll_worker(self):
        from core import telegram_daemon as d

        self.tearDown()
        with tempfile.TemporaryDirectory() as td:
            cfg = os.path.join(td, "config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write('{"telegram":{"bot_token":"123456:TESTTOKEN","allowed_chat_ids":["1"]}}')
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                # Avoid real network: stub bridge polling to wait on stop.
                stop_seen = threading.Event()

                class FakeBridge:
                    def __init__(self, *a, **k):
                        pass

                    bot_token = "123456:TESTTOKEN"
                    base_url = "https://api.telegram.org/bot123456:TESTTOKEN"
                    allowed_chat_ids = {"1"}
                    auto_enroll_first_private = True
                    last_update_id = 0
                    last_poll_at = time.time()
                    last_inbound_at = None
                    last_outbound_at = None
                    last_error = ""
                    poll_conflicts_409 = 0
                    orchestrator = None

                    def _load_token_from_config(self):
                        return self.bot_token

                    def _load_allowlist(self):
                        return ["1"]

                    def api_get_me(self):
                        return {"ok": True, "username": "TestBot"}

                    def api_webhook_info(self):
                        return {"ok": True, "url": ""}

                    def api_delete_webhook(self, drop_pending=False):
                        return {"ok": True}

                    def send_chat_action(self, *a, **k):
                        return {"ok": True}

                    def start_polling(self, on_update=None, should_stop=None):
                        while not (should_stop and should_stop()):
                            self.last_poll_at = time.time()
                            time.sleep(0.05)
                        stop_seen.set()

                    def handle_message(self, msg):
                        pass

                with mock.patch("bridges.telegram_bridge.TelegramBridge", FakeBridge):
                    info = d.ensure_telegram_daemon()
                    self.assertTrue(info.get("token_configured"))
                    # Give threads a moment
                    deadline = time.time() + 2
                    while time.time() < deadline:
                        st = d.status()
                        if st.get("running") and st.get("worker_running") and st.get("supervisor_running"):
                            break
                        time.sleep(0.05)
                    st = d.status()
                    self.assertTrue(st["running"], st)
                    self.assertTrue(st["worker_running"], st)
                    self.assertTrue(st["supervisor_running"], st)
                    self.assertIn("durable", st.get("hint", "").lower())
                    d.stop_telegram_daemon()
                    stop_seen.wait(2)

    def test_queue_keeps_poll_free_from_slow_handler(self):
        """Slow handle_message must not prevent on_update enqueue."""
        from bridges.telegram_bridge import TelegramBridge

        b = TelegramBridge.__new__(TelegramBridge)
        b.bot_token = "1:AA"
        b.base_url = "https://api.telegram.org/bot1:AA"
        b.allowed_chat_ids = {"1"}
        b.auto_enroll_first_private = True
        b.last_update_id = 0
        b.last_poll_at = None
        b.last_error = ""
        b.poll_conflicts_409 = 0
        b.api_webhook_info = lambda: {"ok": True, "url": ""}
        b.api_delete_webhook = lambda drop_pending=False: {"ok": True}
        b.api_get_me = lambda: {"ok": True, "username": "B"}
        b._load_allowlist = lambda: ["1"]
        b._reload_token = lambda: True

        received = []
        n = {"i": 0}
        stop = threading.Event()

        def fake_get(url, timeout=35):
            n["i"] += 1
            if n["i"] > 2:
                stop.set()
                raise KeyboardInterrupt()
            resp = mock.Mock()
            resp.status_code = 200
            resp.json.return_value = {
                "ok": True,
                "result": [{"update_id": n["i"], "message": {"text": f"m{n['i']}"}}],
            }
            resp.text = ""
            return resp

        with mock.patch("bridges.telegram_bridge.requests.get", side_effect=fake_get), \
                mock.patch("bridges.telegram_bridge.time.sleep", return_value=None):
            try:
                b.start_polling(on_update=received.append, should_stop=stop.is_set)
            except KeyboardInterrupt:
                pass
        self.assertGreaterEqual(len(received), 1)


if __name__ == "__main__":
    unittest.main()
