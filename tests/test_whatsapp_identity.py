"""El chat propio entra exacto. C o más se confirma con un id numérico de Telegram."""
from __future__ import annotations

import os
import tempfile
import unittest


class ChatIdentityTests(unittest.TestCase):
    def test_exact_unique_own_chat_rejects_lookalikes_and_groups(self):
        from bridges.whatsapp_reader import (
            WhatsAppReadError, accept_configured_chat,
        )
        own = "Mauro Vanegas 2025"
        self.assertEqual(accept_configured_chat(own, own, 1, False), "")
        self.assertEqual(
            accept_configured_chat(own, own + " ", 1, False),
            WhatsAppReadError.CHAT_NOT_UNIQUE,
        )
        self.assertEqual(
            accept_configured_chat(own, "mauro vanegas 2025", 1, False),
            WhatsAppReadError.CHAT_NOT_UNIQUE,
        )
        self.assertEqual(
            accept_configured_chat(own, own, 2, False),
            WhatsAppReadError.CHAT_NOT_UNIQUE,
        )
        self.assertEqual(
            accept_configured_chat(own, own, 1, True),
            WhatsAppReadError.GROUP_REJECTED,
        )

    def test_poll_stops_on_a_group_and_on_a_near_miss_sender(self):
        from bridges.whatsapp_bridge import WhatsAppBridge
        from bridges.whatsapp_reader import WhatsAppMessage, WhatsAppReadError

        class Reader:
            sent_texts = set()
            chat_gate = WhatsAppReadError.GROUP_REJECTED

            def read_recent(self, limit=10):
                raise AssertionError("un grupo no se lee")

        bridge = WhatsAppBridge(poll_seconds=0, authorized_senders=["Mauro Vanegas 2025"])
        with self.assertRaises(WhatsAppReadError) as caught:
            bridge._poll_loop(Reader(), "Mauro Vanegas 2025", max_polls=1)
        self.assertEqual(caught.exception.code, WhatsAppReadError.GROUP_REJECTED)

        class OpenReader:
            sent_texts = set()
            chat_gate = ""

            def read_recent(self, limit=10):
                return [WhatsAppMessage(
                    msg_id="m", incoming=True, sender="Mauro Vanegas 2025 ", text="hola",
                )]

        seen = []
        bridge = WhatsAppBridge(poll_seconds=0, authorized_senders=["Mauro Vanegas 2025"])
        bridge.orchestrator = type("O", (), {
            "process_user_input": lambda *a, **k: seen.append(a) or "ok",
            "origin_channel": "",
        })()
        bridge._deliver = lambda **k: "delivered"
        bridge._poll_loop(OpenReader(), "Mauro Vanegas 2025", max_polls=1)
        self.assertEqual(seen, [])


class WhatsAppLevelCTests(unittest.TestCase):
    def test_level_c_waits_for_a_numeric_telegram_id(self):
        from core.act_chokepoint import (
            ActChokepoint, ActPolicy, ActStatus, WHATSAPP_LEVEL_C_REQUIRES_TELEGRAM,
        )
        from core.state_db import StateEngine

        ran = []
        with tempfile.TemporaryDirectory() as folder:
            db = StateEngine(db_path=os.path.join(folder, "state_engine.db"))
            try:
                cp = ActChokepoint(
                    state_db=db,
                    policy=ActPolicy(
                        exec_requires_approval=False,
                        trusted_telegram_chat_ids=("111",),
                    ),
                    executors={
                        "COMMAND": lambda a: ran.append(a) or "ran-command",
                        "LIST_DIR": lambda a: ran.append(("list", a)) or "listed",
                    },
                )
                listed = cp.perform(
                    "LIST_DIR", {"dir_path": "."}, origin="whatsapp")
                self.assertEqual(listed, "listed")
                queued = cp.perform(
                    "COMMAND", {"command": "echo hola"}, origin="whatsapp")
                self.assertIn(WHATSAPP_LEVEL_C_REQUIRES_TELEGRAM, queued)
                self.assertEqual(ran, [("list", {"dir_path": "."})])
                approval_id = queued.split("]", 1)[0].split(":", 1)[1]
                denied = cp.resolve_approval(
                    approval_id, True, resolver="Mauro Vanegas 2025")
                self.assertEqual(denied["error"], "TELEGRAM_NUMERIC_ID_REQUIRED")
                stranger = cp.resolve_approval(approval_id, True, resolver="222")
                self.assertEqual(stranger["error"], "TELEGRAM_NUMERIC_ID_REQUIRED")
                self.assertEqual([a["status"] for a in cp.list_acts()
                                  if a["act_type"] == "COMMAND"],
                                 [ActStatus.PENDING_APPROVAL])
                accepted = cp.resolve_approval(approval_id, True, resolver="111")
                self.assertTrue(accepted["ok"], accepted)
                self.assertEqual(ran[-1]["command"], "echo hola")
            finally:
                db.close()

    def test_telegram_approve_uses_the_numeric_chat_id(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.act_chokepoint import ActChokepoint, ActPolicy

        sent = []
        cp = ActChokepoint(
            policy=ActPolicy(trusted_telegram_chat_ids=("111",)),
            executors={"LIST_DIR": lambda a: "listed"},
        )
        orch = type("O", (), {"chokepoint": cp, "_build_chokepoint": lambda self: cp})()
        bridge = TelegramBridge(
            bot_token="123456:TEST",
            allowed_chat_ids=["111"],
            orchestrator=orch,
        )
        bridge.send_message = lambda chat, text: sent.append((chat, text))
        message = {
            "message_id": 7,
            "text": "/approve apr_missing",
            "chat": {"id": 111, "type": "private"},
            "from": {"id": 111, "is_bot": False},
        }
        bridge.handle_message(message)
        self.assertTrue(sent)
        self.assertIn("111", sent[-1][0])
        self.assertNotIn("Mauro", sent[-1][1])
