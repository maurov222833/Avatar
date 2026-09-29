"""D-6: WhatsApp 24/7 shares the process orchestrator (or HTTP when configured)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestD6WhatsAppCoreBinding(unittest.TestCase):
    def test_in_process_mode_injects_shared_orchestrator(self):
        import whatsapp_24x7 as wa
        from core.runtime import get_shared_orchestrator, reset_shared_orchestrator

        reset_shared_orchestrator()
        shared = get_shared_orchestrator()
        captured = {}

        class FakeReader:
            def close(self):
                pass

        class FakeBridge:
            def __init__(self, **kw):
                captured.update(kw)
                self.orchestrator = kw.get("orchestrator")

            def start_live_bridge(self, *a, **k):
                return {"processed": 0}

        with mock.patch("bridges.whatsapp_bridge.WhatsAppBridge", FakeBridge), \
             mock.patch("bridges.whatsapp_reader.WhatsAppWebReader", return_value=FakeReader()):
            outcome, note = wa.run_cycle({}, max_polls=1)

        self.assertEqual(outcome, "STOP")
        self.assertIs(captured.get("orchestrator"), shared)
        reset_shared_orchestrator()

    def test_http_mode_requires_token(self):
        import whatsapp_24x7 as wa

        class FakeReader:
            def close(self):
                pass

        with mock.patch("bridges.whatsapp_reader.WhatsAppWebReader", return_value=FakeReader()):
            outcome, note = wa.run_cycle({"core_mode": "http"}, max_polls=1)
        self.assertEqual(outcome, "FAIL")
        self.assertIn("D-6", note)


if __name__ == "__main__":
    unittest.main()
