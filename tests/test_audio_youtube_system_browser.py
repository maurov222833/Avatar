"""YouTube/audio: system browser ≠ Playwright; sanitize song titles; AUDIO_CONTROL close."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock


class TestAudioSanitize(unittest.TestCase):
    def test_mauro_telegram_song_request(self):
        from tools.audio_tool import AudioTool

        q = "Si, quiero que reproduscas en YouTube la canción, Bonito bonito."
        self.assertEqual(AudioTool.sanitize_query(q).lower(), "bonito bonito")

    def test_typo_reproduzcas_and_plain_reproduce(self):
        from tools.audio_tool import AudioTool

        self.assertEqual(
            AudioTool.sanitize_query("quiero que reproduzcas Bonito bonito").lower(),
            "bonito bonito",
        )
        self.assertEqual(
            AudioTool.sanitize_query("reproduce Bonito bonito").lower(),
            "bonito bonito",
        )

    def test_pause_does_not_toggle_when_already_paused(self):
        from tools.audio_tool import AudioTool

        AudioTool._is_playing = False
        with mock.patch.object(AudioTool, "_youtube_press_k", return_value=True) as k:
            msg = AudioTool.pause_audio(force="pause")
        k.assert_not_called()
        self.assertIn("Ya estaba en pausa", msg)

    def test_control_audio_routes_close(self):
        from tools.audio_tool import AudioTool

        with mock.patch.object(AudioTool, "close_tab", return_value="CLOSED") as c:
            out = AudioTool.control_audio({"action": "close", "target": "youtube"})
        self.assertEqual(out, "CLOSED")
        c.assert_called_once_with("youtube")

    def test_control_audio_change_and_next(self):
        from tools.audio_tool import AudioTool

        with mock.patch.object(AudioTool, "play_online_music", return_value="PLAY") as p:
            out = AudioTool.control_audio({"action": "change", "query": "Despacito"})
        self.assertEqual(out, "PLAY")
        p.assert_called_once_with("Despacito")
        with mock.patch.object(AudioTool, "next_track", return_value="NEXT") as n:
            self.assertEqual(AudioTool.control_audio({"action": "next"}), "NEXT")
            n.assert_called_once()

    def test_extract_change_and_close(self):
        from tools.audio_tool import AudioTool

        self.assertEqual(
            AudioTool.extract_song_request("Cambia la canción a Despacito").lower(),
            "despacito",
        )
        self.assertEqual(
            AudioTool.extract_close_target("Cierra en concreto solo la pestaña de YouTube"),
            "youtube",
        )
        self.assertIsNone(AudioTool.extract_close_target("hola Mauro"))


class TestTelegramYoutubeCloseShortcut(unittest.TestCase):
    def test_close_youtube_uses_audio_control_not_browser(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator

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
                b.performed = []
                b.send_message = lambda chat_id, text: (
                    b.sent.append((chat_id, text)) or {"ok": True}
                )
                b.send_chat_action = lambda *a, **k: {"ok": True}
                b._perform = lambda act, args, chat_id, task_id, text: (
                    b.performed.append((act, dict(args))) or f"ok:{act}:{args.get('action')}"
                )
                b.handle_message(
                    {
                        "message_id": 1,
                        "from": {"id": 111, "is_bot": False},
                        "chat": {"id": 111, "type": "private"},
                        "text": "Cierra en concreto solo la pestaña de YouTube",
                    }
                )
                self.assertEqual(b.performed[0][0], "AUDIO_CONTROL")
                self.assertEqual(b.performed[0][1].get("action"), "close")
                self.assertEqual(b.performed[0][1].get("target"), "youtube")
                self.assertTrue(any("Cerrando" in str(t) for _, t in b.sent))

    def test_change_song_shortcut(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator

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
                b.performed = []
                b.send_message = lambda chat_id, text: (
                    b.sent.append((chat_id, text)) or {"ok": True}
                )
                b.send_chat_action = lambda *a, **k: {"ok": True}
                b._perform = lambda act, args, chat_id, task_id, text: (
                    b.performed.append((act, dict(args))) or "ok"
                )
                b.handle_message(
                    {
                        "message_id": 1,
                        "from": {"id": 111, "is_bot": False},
                        "chat": {"id": 111, "type": "private"},
                        "text": "Cambia la canción a Despacito",
                    }
                )
                self.assertEqual(b.performed[0][0], "PLAY_AUDIO")
                self.assertEqual(b.performed[0][1]["audio_source"].lower(), "despacito")

    def test_play_sanitizes_si_quiero(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator

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
                b.performed = []
                b.send_message = lambda chat_id, text: (
                    b.sent.append((chat_id, text)) or {"ok": True}
                )
                b.send_chat_action = lambda *a, **k: {"ok": True}
                b._perform = lambda act, args, chat_id, task_id, text: (
                    b.performed.append((act, dict(args))) or "playing"
                )
                b.handle_message(
                    {
                        "message_id": 1,
                        "from": {"id": 111, "is_bot": False},
                        "chat": {"id": 111, "type": "private"},
                        "text": "Si, quiero que reproduscas en YouTube la canción, Bonito bonito.",
                    }
                )
                self.assertEqual(b.performed[0][0], "PLAY_AUDIO")
                self.assertEqual(
                    b.performed[0][1]["audio_source"].lower(),
                    "bonito bonito",
                )


class TestPromptSeparatesBrowsers(unittest.TestCase):
    def test_system_prompt_warns_browser_close_wont_kill_youtube(self):
        from core.orchestrator import AvatarOrchestrator

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AVATAR_HOME": td}):
                orch = AvatarOrchestrator()
                sp = orch.system_prompt
                self.assertIn("AUDIO_CONTROL", sp)
                self.assertIn("BROWSER_*", sp)
                self.assertIn("PLAY_AUDIO", sp)
                names = {d["name"] for d in __import__("core.orchestrator", fromlist=["AVATAR_TOOLS_SCHEMA"]).AVATAR_TOOLS_SCHEMA[0]["functionDeclarations"]}
                self.assertIn("AUDIO_CONTROL", names)
                self.assertIn("ASISTENTE FÍSICO", orch.system_prompt)
                self.assertIn("action=pause|resume|next|previous|close|change", orch.system_prompt)


if __name__ == "__main__":
    unittest.main()
