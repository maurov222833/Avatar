"""Telegram status/send/test acts — bidirectional probe without COMMAND scripts."""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import ACT_TYPES, ActChokepoint, ActPolicy, ActRisk, ActStatus
from core.orchestrator import AVATAR_TOOLS_SCHEMA, AvatarOrchestrator
from core.state_db import StateEngine


def _schema_names():
    return {d["name"] for d in AVATAR_TOOLS_SCHEMA[0]["functionDeclarations"]}


class TestTelegramActs(unittest.TestCase):
    def test_schema_and_risks(self):
        names = _schema_names()
        for act in ("TELEGRAM_STATUS", "TELEGRAM_SEND", "TELEGRAM_TEST"):
            self.assertIn(act, names)
            self.assertIn(act, ACT_TYPES)
        self.assertEqual(ACT_TYPES["TELEGRAM_STATUS"], ActRisk.READ)
        self.assertEqual(ACT_TYPES["TELEGRAM_SEND"], ActRisk.EXTERNAL_MESSAGE)
        self.assertEqual(ACT_TYPES["TELEGRAM_TEST"], ActRisk.EXTERNAL_MESSAGE)

    def test_prompt_forbids_script_improvisation(self):
        orch = AvatarOrchestrator()
        p = orch.system_prompt.lower()
        self.assertIn("telegram_test", p)
        self.assertIn("prohibido improvisar", p)

    def test_status_via_chokepoint_with_mocked_api(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_tg_st_"))
            db = stack.enter_context(contextlib.closing(StateEngine(db_path=os.path.join(tmp, "s.db"))))
            orch = AvatarOrchestrator.__new__(AvatarOrchestrator)
            orch.state_db = db
            orch.config = {"telegram": {"bot_token": "1:AAFAKE", "allowed_chat_ids": []}}
            orch.checkpoint_engine = None
            orch.memory = None
            orch.llm = None
            orch.chokepoint = None

            class FakeBridge:
                bot_token = "1:AAFAKE"
                allowed_chat_ids = set()

                def api_get_me(self):
                    return {"ok": True, "username": "AvatarTestBot", "id": 99}

                def api_webhook_info(self):
                    return {"ok": True, "url": "", "pending_update_count": 0}

                def api_delete_webhook(self, drop_pending=False):
                    return {"ok": True}

                def api_recent_private_chat_ids(self, limit=20):
                    return [{"chat_id": "111", "username": "mauro"}]

            orch._telegram_bridge = lambda: FakeBridge()
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=True),
                executors={"TELEGRAM_STATUS": lambda a: orch._exec_telegram("status", a)},
            )
            out = cp.perform("TELEGRAM_STATUS", {}, mission_id="m")
            data = json.loads(out)
            self.assertTrue(data["success"])
            self.assertEqual(data["bot"]["username"], "AvatarTestBot")
            self.assertIn("hint", data)
            self.assertTrue(data["hint"])

    def test_send_to_allowlisted_chat_skips_dry_run(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_tg_send_"))
            db = stack.enter_context(contextlib.closing(StateEngine(db_path=os.path.join(tmp, "s.db"))))
            sent = []

            class FakeBridge:
                bot_token = "1:AA"
                allowed_chat_ids = {"42"}

                def send_message(self, chat_id, text):
                    sent.append((chat_id, text))
                    return {"ok": True, "chat_id": chat_id, "message_id": 7}

            orch = AvatarOrchestrator.__new__(AvatarOrchestrator)
            orch._telegram_bridge = lambda: FakeBridge()
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(
                    dry_run=True,
                    allow_external_messages=False,
                    trusted_telegram_chat_ids=("42",),
                ),
                executors={"TELEGRAM_SEND": lambda a: orch._exec_telegram("send", a)},
            )
            out = cp.perform(
                "TELEGRAM_SEND",
                {"chat_id": "42", "message": "hola"},
                mission_id="m",
            )
            data = json.loads(out)
            self.assertTrue(data["success"])
            self.assertEqual(sent, [("42", "hola")])
            self.assertNotEqual(cp.list_acts("m")[-1]["status"], ActStatus.DENIED)

    def test_send_to_unknown_chat_blocked_by_dry_run(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_tg_block_"))
            db = stack.enter_context(contextlib.closing(StateEngine(db_path=os.path.join(tmp, "s.db"))))
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(
                    dry_run=True,
                    allow_external_messages=False,
                    trusted_telegram_chat_ids=("42",),
                ),
                executors={"TELEGRAM_SEND": lambda a: "should-not-run"},
            )
            out = cp.perform(
                "TELEGRAM_SEND",
                {"chat_id": "999", "message": "no"},
                mission_id="m",
            )
            self.assertTrue(
                "DRY-RUN" in out or "EXTERNAL_EFFECT_REQUIRES_OPERATOR_CONSENT" in out,
                out,
            )
            self.assertEqual(cp.list_acts("m")[-1]["status"], ActStatus.DENIED)

    def test_telegram_test_reports_missing_allowlist(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_tg_test_"))
            db = stack.enter_context(contextlib.closing(StateEngine(db_path=os.path.join(tmp, "s.db"))))

            class FakeBridge:
                bot_token = "1:AA"
                allowed_chat_ids = set()

                def api_get_me(self):
                    return {"ok": True, "username": "BotX", "id": 1}

                def api_recent_private_chat_ids(self, limit=20):
                    return [{"chat_id": "777", "first_name": "Mauro"}]

                def send_message(self, *a, **k):
                    raise AssertionError("should not send")

            orch = AvatarOrchestrator.__new__(AvatarOrchestrator)
            orch._telegram_bridge = lambda: FakeBridge()
            orch._exec_update_config = lambda a: "no"
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=True, allow_external_messages=False),
                executors={"TELEGRAM_TEST": lambda a: orch._exec_telegram("test", a)},
            )
            out = cp.perform("TELEGRAM_TEST", {}, mission_id="m")
            data = json.loads(out)
            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "ALLOWLIST_EMPTY")
            self.assertEqual(data["recent_private_chats"][0]["chat_id"], "777")


if __name__ == "__main__":
    unittest.main()
