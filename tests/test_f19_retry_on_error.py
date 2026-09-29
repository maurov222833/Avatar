"""F-19: processing errors must not mark WhatsApp messages as replied."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.whatsapp_bridge import WhatsAppBridge
from bridges.whatsapp_reader import WhatsAppMessage
from core.orchestrator import AvatarOrchestrator


class TestF19RetryOnError(unittest.TestCase):
    def test_failed_process_keeps_message_retryable(self):
        tmp = tempfile.mkdtemp(prefix="avatar_f19_")
        state = os.path.join(tmp, "state.json")

        class Reader:
            sent_texts = set()

            def read_recent(self, limit=10):
                return [
                    WhatsAppMessage(msg_id="m-retry", incoming=True,
                                    sender="Mauro", text="hola"),
                ]

        orch = AvatarOrchestrator()
        orch.process_user_input = mock.Mock(side_effect=RuntimeError("boom"))
        b = WhatsAppBridge(
            reader=Reader(),
            poll_seconds=0,
            authorized_senders=["Mauro"],
            state_path=state,
            orchestrator=orch,
        )
        b._deliver = lambda **k: "delivered"
        b._poll_loop(b.reader, "Chat", max_polls=1,
                     stop_path=os.path.join(tmp, "STOP"))
        self.assertNotIn("m-retry", b._replied_ids)


if __name__ == "__main__":
    unittest.main()
