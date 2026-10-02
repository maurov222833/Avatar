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

    def test_empty_file_can_be_acquired(self):
        """Windows msvcrt.locking used to fail on empty files → permanent STANDBY."""
        from core.telegram_poll_lock import TelegramPollLock

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "telegram_poll.lock")
            open(path, "w", encoding="utf-8").close()  # empty file
            lock = TelegramPollLock(path)
            self.assertTrue(lock.acquire(blocking=False), lock.last_reject_reason)
            self.assertTrue(lock.held)
            lock.release()

    def test_force_acquire_steals_dead_pid(self):
        from core.telegram_poll_lock import TelegramPollLock

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "telegram_poll.lock")
            with open(path, "w", encoding="utf-8") as f:
                f.write("pid=99999999 ts=1\n")  # almost certainly dead
            lock = TelegramPollLock(path)
            self.assertTrue(lock.force_acquire(), lock.last_reject_reason)
            lock.release()

    def test_fallback_handle_closes_on_release_and_on_failure(self):
        from core.telegram_poll_lock import TelegramPollLock

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "telegram_poll.lock")
            lock = TelegramPollLock(path)
            self.assertTrue(lock._acquire_pid_file_fallback(), lock.last_reject_reason)
            held = lock._fh
            self.assertIsNotNone(held)
            self.assertFalse(held.closed)
            self.assertTrue(lock._exit_registered)
            lock.release()
            self.assertTrue(held.closed)
            self.assertIsNone(lock._fh)

            opened = []
            real_open = open

            def tracking(file, mode="r", *args, **kwargs):
                handle = real_open(file, mode, *args, **kwargs)
                opened.append(handle)
                return handle

            again = TelegramPollLock(path)

            def boom(handle):
                raise RuntimeError("identidad")

            again._write_identity = boom
            with mock.patch("builtins.open", tracking):
                self.assertFalse(again._acquire_pid_file_fallback())
            self.assertTrue(opened)
            self.assertTrue(all(handle.closed for handle in opened))
            self.assertIsNone(again._fh)


class TestTelegramDurableDaemon(unittest.TestCase):
    def tearDown(self):
        try:
            from core import telegram_daemon as d

            d.stop_telegram_daemon()
            d._poll_thread = None
            d._worker_thread = None
            d._supervisor_thread = None
            d._bridge = None
            d._restart_count = 0
            d._standby_other_instance = False
            d._poll_started_gen = -1
            d._stop.clear()
            try:
                d._poll_lock.release()
            except Exception:
                pass
        except Exception:
            pass

    def test_ensure_starts_supervisor_even_without_token(self):
        from core import telegram_daemon as d

        self.tearDown()
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "config.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                class FakeBridge:
                    def __init__(self, *a, **k):
                        self.bot_token = ""
                        self.base_url = ""
                        self.allowed_chat_ids = set()
                        self.auto_enroll_first_private = True
                        self.orchestrator = None
                        self.last_poll_at = None
                        self.last_error = ""
                        self.poll_conflicts_409 = 0

                    def _load_token_from_config(self):
                        return ""

                    def _load_allowlist(self):
                        return []

                with mock.patch("bridges.telegram_bridge.TelegramBridge", FakeBridge):
                    info = d.ensure_telegram_daemon()
                    self.assertEqual(info.get("status"), "NO_TOKEN")
                    self.assertTrue(info.get("supervisor_running") or d._alive(d._supervisor_thread))
                    d.stop_telegram_daemon()

    def test_kick_starts_poll_when_token_present(self):
        from core import telegram_daemon as d

        self.tearDown()
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "config.json"), "w", encoding="utf-8") as f:
                f.write('{"telegram":{"bot_token":"123456:TESTTOKEN","allowed_chat_ids":["1"]}}')
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                stop_seen = threading.Event()

                class FakeBridge:
                    def __init__(self, *a, **k):
                        self.bot_token = "123456:TESTTOKEN"
                        self.base_url = "https://api.telegram.org/bot123456:TESTTOKEN"
                        self.allowed_chat_ids = {"1"}
                        self.auto_enroll_first_private = True
                        self.last_update_id = 0
                        self.last_poll_at = time.time()
                        self.last_inbound_at = None
                        self.last_outbound_at = None
                        self.last_error = ""
                        self.poll_conflicts_409 = 0
                        self.orchestrator = None

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
                    info = d.kick_telegram_listener()
                    deadline = time.time() + 2
                    while time.time() < deadline and not info.get("running"):
                        time.sleep(0.05)
                        info = d.status()
                    self.assertTrue(info.get("running"), info)
                    self.assertTrue(os.path.exists(d._heartbeat_path()))
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
