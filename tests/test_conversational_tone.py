"""Telegram/charla tone: no bureaucratic template on casual chat; no AVATAR AI: prefix."""
import os
import tempfile
import unittest
from unittest import mock

from core.cognitive.semantic_mission_engine import InteractionType, SemanticMissionEngine
from tools.reasoning_engine import ReasoningEngine


class TestConversationalTone(unittest.TestCase):

    def test_mauro_telegram_samples_are_conversation(self):
        cases = [
            "Como te sientes hoy?",
            "Cuéntame, si puedes abrir videos en YouTube?",
        ]
        for prompt in cases:
            self.assertEqual(
                SemanticMissionEngine.classify_interaction(prompt),
                InteractionType.CONVERSATION_NORMAL,
                prompt,
            )

    def test_system_prompt_forbids_bureaucratic_template_on_charla(self):
        from core.orchestrator import AvatarOrchestrator

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                orch = AvatarOrchestrator()
                sp = orch.system_prompt
                self.assertIn("CHARLA", sp)
                self.assertIn("PROHIBIDO usar la plantilla QUÉ HICE", sp)
                self.assertNotIn("FORMATO EXPLÍCITO OBLIGATORIO", sp)

    def test_reasoning_engine_aligns_with_intellectual_tone(self):
        p = ReasoningEngine.format_supreme_reasoning_prompt("BASE")
        self.assertIn("intelectual", p.lower())
        self.assertIn("CHARLA", p)
        self.assertNotIn("ANTIGRAVITY STANDARD", p)

    def test_telegram_reply_has_no_avatar_ai_prefix(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator
        from core.act_chokepoint import ActStatus

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(
                os.environ,
                {"AVATAR_HOME": td, "TELEGRAM_ALLOWED_CHAT_IDS": "111"},
            ):
                orch = AvatarOrchestrator()
                b = TelegramBridge(
                    bot_token="123456:TEST",
                    allowed_chat_ids=["111"],
                    orchestrator=orch,
                    auto_enroll_first_private=False,
                )
                b.sent = []
                b.send_message = lambda chat_id, text: b.sent.append((chat_id, text))
                b.orchestrator.process_user_input = lambda text, **kw: (
                    "En forma: canales estables y listo para lo que necesites."
                )
                b.handle_message(
                    {
                        "message_id": 1,
                        "from": {"id": 111, "is_bot": False, "username": "mauro"},
                        "chat": {"id": 111, "type": "private"},
                        "text": "Como te sientes hoy?",
                    }
                )
                self.assertEqual(len(b.sent), 1)
                _, text = b.sent[0]
                self.assertFalse(str(text).startswith("AVATAR AI:"))
                self.assertIn("En forma", text)


if __name__ == "__main__":
    unittest.main()
