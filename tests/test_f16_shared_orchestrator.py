"""F-16: one orchestrator per process; concurrent turns do not interleave history."""
from __future__ import annotations

import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.telegram_bridge import TelegramBridge
from bridges.whatsapp_bridge import WhatsAppBridge
from core import runtime
from core.orchestrator import AvatarOrchestrator
from core.runtime import get_shared_orchestrator, reset_shared_orchestrator


class TestF16SharedOrchestrator(unittest.TestCase):
    def setUp(self):
        reset_shared_orchestrator()

    def tearDown(self):
        reset_shared_orchestrator()

    def test_server_style_bridges_share_one_instance(self):
        shared = get_shared_orchestrator()
        tg = TelegramBridge(bot_token="123456:TESTTOKENFORTESTS")
        wa = WhatsAppBridge()
        self.assertIs(tg.orchestrator, shared)
        self.assertIs(wa.orchestrator, shared)
        self.assertIs(tg.orchestrator, wa.orchestrator)

    def test_injected_orchestrator_is_not_replaced(self):
        own = AvatarOrchestrator()
        tg = TelegramBridge(bot_token="123456:TESTTOKENFORTESTS", orchestrator=own)
        wa = WhatsAppBridge(orchestrator=own)
        self.assertIs(tg.orchestrator, own)
        self.assertIs(wa.orchestrator, own)
        self.assertIsNot(own, get_shared_orchestrator())

    def test_concurrent_turns_append_without_losing_rows(self):
        orch = get_shared_orchestrator()
        orch.history = []
        replies = {}

        def fake_process(self, user_input, max_steps=5, channel="local"):
            # Simulate a slow turn that mutates history the way the real path does.
            import time
            time.sleep(0.02)
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": f"ack:{user_input}"})
            return f"ack:{user_input}"

        with mock.patch.object(
            AvatarOrchestrator,
            "_process_user_input_unlocked",
            fake_process,
        ):
            errors = []

            def worker(n):
                try:
                    replies[n] = orch.process_user_input(f"msg-{n}")
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(orch.history), 16)
        users = [row["content"] for row in orch.history if row["role"] == "user"]
        self.assertEqual(sorted(users), [f"msg-{i}" for i in range(8)])
        # Each user turn is immediately followed by its assistant ack (no interleave).
        for i in range(0, 16, 2):
            user = orch.history[i]
            assistant = orch.history[i + 1]
            self.assertEqual(user["role"], "user")
            self.assertEqual(assistant["role"], "assistant")
            self.assertEqual(assistant["content"], f"ack:{user['content']}")


if __name__ == "__main__":
    unittest.main()
