"""
U1 — Contención de canales y ejecución.

Pruebas deterministas, sin red ni proveedores reales:
  - EXEC exige aprobación por defecto; allowlist estricta; aprobador humano opcional.
  - Telegram rechaza todo sin allowlist y enruta captura/pausa por el chokepoint.
  - WhatsApp por defecto solo acepta entrantes del chat objetivo.
  - La clave de Gemini viaja en cabecera y ningún error la devuelve en claro.
"""
import os
import sys
import json
import tempfile
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import (
    ActChokepoint, ActPolicy, ActStatus, EXEC_APPROVAL_REASON, command_matches_allowlist)
from core.redaction import REDACTED, redact_secret_text


class _TempWorld:
    """Redirige las rutas implícitas de BD a un directorio temporal."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="avatar_u1_")

    def __enter__(self):
        import core.state_db as sd
        import core.rag_memory as rm
        self._e = sd.StateEngine.__init__
        self._r = rm.RAGMemory.__init__
        world = self

        def engine_init(self, db_path=None, *a, **k):
            return world._e(self, os.path.join(world.dir, "state_engine.db")
                            if db_path is None else db_path)

        def rag_init(self, memory_dir=None, state_db=None, *a, **k):
            return world._r(self, memory_dir or world.dir, state_db)

        sd.StateEngine.__init__ = engine_init
        rm.RAGMemory.__init__ = rag_init
        return self

    def __exit__(self, *exc):
        import core.state_db as sd
        import core.rag_memory as rm
        import shutil
        sd.StateEngine.__init__ = self._e
        rm.RAGMemory.__init__ = self._r
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def _chokepoint(**policy_kw):
    ran = []
    cp = ActChokepoint(policy=ActPolicy(**policy_kw),
                       executors={"COMMAND": lambda a: ran.append(a["command"]) or
                                  "[Resultado PowerShell (ExitCode: 0)]:\nok"})
    return cp, ran


class TestExecPolicy(unittest.TestCase):

    def test_exec_denied_by_default_even_in_dry_run(self):
        for dry_run in (True, False):
            cp, ran = _chokepoint(dry_run=dry_run)
            out = cp.perform("COMMAND", {"command": "Remove-Item C:\\x"})
            self.assertIn(EXEC_APPROVAL_REASON, out)
            self.assertEqual(ran, [], "a gated command must never reach the executor")

    def test_allowlist_is_exact_command_line(self):
        cp, ran = _chokepoint(exec_allowlist=("git status", "git log --oneline -20"))
        cp.perform("COMMAND", {"command": "git status"})
        cp.perform("COMMAND", {"command": "  GIT   STATUS "})
        cp.perform("COMMAND", {"command": "git log --oneline -20"})
        cp.perform("COMMAND", {"command": "git status --short"})
        self.assertEqual(ran, ["git status", "  GIT   STATUS ", "git log --oneline -20"])

    def test_allowlist_rejects_extra_arguments_chaining_and_evaluation(self):
        allow = ("git status", "git diff", "Get-ChildItem", "powershell", "sh")
        for cmd in ("git status; Remove-Item x", "git status && del x", "git status | iex",
                    "git status > C:\\out.txt", "Get-ChildItem (Remove-Item x)",
                    "Get-ChildItem $env:USERPROFILE", "Get-ChildItem `\nRemove-Item x",
                    "git diff --output=C:\\x.txt", "git diff --ext-diff",
                    "git diff --no-index a b", "Get-ChildItem Env:GEMINI_API_KEY",
                    "powershell -EncodedCommand ZQBjAGgAbwAgAHgA", "sh -c 'touch x'",
                    "git statusx", "git", ""):
            self.assertFalse(command_matches_allowlist(cmd, allow), cmd)

    def test_writes_into_git_metadata_are_denied(self):
        policy = ActPolicy()
        for path in (".git/config", "repo/.git/hooks/pre-commit", "C:\\Users\\m\\.gitconfig"):
            allowed, reason = policy.decide("WRITE_FILE", {"file_path": path, "content": "x"})
            self.assertFalse(allowed, path)
            self.assertEqual(reason, "WRITE_TO_PROTECTED_PATH_DENIED")
        self.assertTrue(policy.decide("WRITE_FILE", {"file_path": "docs/.gitignore"})[0])

    def test_git_guard_follows_links_and_windows_aliases(self):
        from core.act_chokepoint import _is_git_metadata, _normalized_parts
        repo = tempfile.mkdtemp(prefix="avatar_git_")
        os.makedirs(os.path.join(repo, ".git", "hooks"))
        config = os.path.join(repo, ".git", "config")
        with open(config, "w") as f:
            f.write("[core]\n")
        os.symlink(os.path.join(repo, ".git"), os.path.join(repo, "link"))
        os.link(config, os.path.join(repo, "notes.txt"))
        policy = ActPolicy(allowed_workspace_root=repo)
        for rel in ("link/hooks/pre-commit", "notes.txt"):
            allowed, reason = policy.decide("WRITE_FILE", {"file_path": os.path.join(repo, rel)})
            self.assertFalse(allowed, rel)
            self.assertEqual(reason, "WRITE_TO_PROTECTED_PATH_DENIED")
        for alias in ("C:/repo/.git./hooks/pre-commit", "C:/repo/.git /hooks/x",
                      "C:/repo/.GIT.../config", "C:/Users/m/.gitconfig.",
                      "C:/Users/m/.gitconfig::$DATA", "C:/repo/.git::$INDEX_ALLOCATION/x",
                      "C:/Program Files/Git/etc/gitconfig"):
            self.assertTrue(_is_git_metadata(_normalized_parts(alias)), alias)
        xdg = tempfile.mkdtemp(prefix="avatar_xdg_")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": xdg}):
            self.assertFalse(policy.decide("WRITE_FILE", {
                "file_path": os.path.join(xdg, "git", "config")})[0])
            self.assertTrue(ActPolicy().decide("WRITE_FILE", {
                "file_path": os.path.join(repo, "proj", ".config", "git", "README.md")})[0])

    def test_git_guard_has_no_false_positives_on_ordinary_files(self):
        from core.act_chokepoint import _is_git_metadata, _normalized_parts
        for path in ("C:/repo/src/gitlab.py", "C:/repo/notes/gitconfig", "C:/repo/docs/GitConfig",
                     "C:/repo/src/git/main.py", "C:/repo/my.gitconfig", "C:/repo/docs/.gitignore"):
            self.assertFalse(_is_git_metadata(_normalized_parts(path)), path)
        work = tempfile.mkdtemp(prefix="avatar_links_")
        readme = os.path.join(work, "readme.txt")
        with open(readme, "w") as f:
            f.write("x")
        os.link(readme, os.path.join(work, "readme-link.txt"))
        self.assertTrue(ActPolicy().decide("WRITE_FILE", {"file_path": readme})[0])

    def test_approver_approves_and_rejects(self):
        cp, ran = _chokepoint()
        cp.approver = lambda act, args: args["command"] == "echo yes"
        cp.perform("COMMAND", {"command": "echo yes"})
        denied = cp.perform("COMMAND", {"command": "echo no"})
        self.assertEqual(ran, ["echo yes"])
        self.assertIn("REJECTED_BY_OPERATOR", denied)

    def test_approver_error_fails_closed(self):
        cp, ran = _chokepoint()

        def broken(act, args):
            raise RuntimeError("no tty")
        cp.approver = broken
        cp.perform("COMMAND", {"command": "echo x"})
        self.assertEqual(ran, [])

    def test_approval_can_be_disabled_explicitly(self):
        cp, ran = _chokepoint(exec_requires_approval=False)
        cp.perform("COMMAND", {"command": "echo x"})
        self.assertEqual(ran, ["echo x"])

    def test_workspace_root_is_not_a_string_prefix(self):
        root = tempfile.mkdtemp(prefix="avatar_root_")
        policy = ActPolicy(allowed_workspace_root=root)
        allowed, _ = policy.decide("WRITE_FILE", {"file_path": os.path.join(root, "a.txt")})
        sibling, reason = policy.decide("WRITE_FILE", {"file_path": root + "_evil/a.txt"})
        self.assertTrue(allowed)
        self.assertFalse(sibling)
        self.assertIn("WRITE_OUTSIDE_ALLOWED_ROOT", reason)


class TestOrchestratorPolicy(unittest.TestCase):

    def test_orchestrator_defaults_require_approval(self):
        from core.orchestrator import AvatarOrchestrator
        with _TempWorld():
            orch = AvatarOrchestrator()
            orch.config = {"security": {}}
            orch.chokepoint = orch._build_chokepoint()
            mode = orch.operating_mode()
            self.assertEqual(mode["exec"], "APPROVAL_REQUIRED")
            out = orch._dispatch_native_tool("COMMAND", {"command": "echo hi"})
            self.assertIn(EXEC_APPROVAL_REASON, out)
            self.assertIn("PENDING_APPROVAL", out)
            self.assertEqual(orch.chokepoint.list_acts()[-1]["status"], ActStatus.PENDING_APPROVAL)

    def test_config_allowlist_is_honored(self):
        from core.orchestrator import AvatarOrchestrator
        with _TempWorld():
            orch = AvatarOrchestrator()
            orch.config = {"security": {"exec_allowlist": ["git status"]}}
            orch.chokepoint = orch._build_chokepoint()
            allowed, reason = orch.chokepoint.policy.decide("COMMAND", {"command": "git status"})
            self.assertTrue(allowed)
            self.assertEqual(reason, "ALLOWED_BY_EXEC_ALLOWLIST")

    def test_real_powershell_effect_only_after_approval(self):
        import shutil
        from core.orchestrator import AvatarOrchestrator
        if not shutil.which("powershell"):
            self.skipTest("powershell not installed")
        with _TempWorld() as world:
            target = os.path.join(world.dir, "u1_probe.txt")
            cmd = f"New-Item -ItemType File -Path '{target}'"
            orch = AvatarOrchestrator()
            orch.config = {"security": {"allowed_workspace": world.dir}}
            orch.chokepoint = orch._build_chokepoint()
            with mock.patch("tools.shell_tool.ShellTool.get_allowed_workspace",
                            return_value=world.dir):
                orch._dispatch_native_tool("COMMAND", {"command": cmd})
                self.assertFalse(os.path.exists(target), "denied command must have no effect")
                orch.chokepoint.approver = lambda act, args: True
                orch._dispatch_native_tool("COMMAND", {"command": cmd})
            self.assertTrue(os.path.exists(target), "approved command must really run")
            statuses = [(a["policy_reason"], a["status"]) for a in orch.chokepoint.list_acts()]
            self.assertEqual(statuses[0], (EXEC_APPROVAL_REASON, ActStatus.PENDING_APPROVAL))
            self.assertEqual(statuses[1], ("APPROVED_BY_OPERATOR", ActStatus.OBSERVED))

    def test_cli_approver_defaults_to_no(self):
        from interface.cli import tty_exec_approver
        with mock.patch("builtins.input", return_value=""):
            self.assertFalse(tty_exec_approver("COMMAND", {"command": "echo x"}))
        with mock.patch("builtins.input", return_value="s"):
            self.assertTrue(tty_exec_approver("COMMAND", {"command": "echo x"}))
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(tty_exec_approver("COMMAND", {"command": "echo x"}))


def _tg_message(user_id=111, chat_id=None, chat_type="private", username="mauro", text="hola"):
    return {"chat": {"id": user_id if chat_id is None else chat_id, "type": chat_type},
            "from": {"id": user_id, "username": username, "is_bot": False}, "text": text}


class TestTelegramAllowlist(unittest.TestCase):

    def _bridge(self, **kw):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator
        with mock.patch.dict(os.environ, {"TELEGRAM_ALLOWED_CHAT_IDS": ""}):
            defaults = {"auto_enroll_first_private": False}
            defaults.update(kw)
            b = TelegramBridge(
                bot_token="123456:TEST",
                orchestrator=AvatarOrchestrator(),
                **defaults,
            )
        b.sent = []
        b.send_message = lambda chat_id, text: b.sent.append((chat_id, text))
        b.send_photo = lambda chat_id, path, caption="": b.sent.append((chat_id, "PHOTO"))
        b.orchestrator.process_user_input = lambda text, **kw: f"eco: {text}"
        return b

    def test_no_allowlist_rejects_everything(self):
        with _TempWorld():
            b = self._bridge(allowed_chat_ids=[], auto_enroll_first_private=False)
            b.handle_message(_tg_message(text="captura de pantalla"))
            b.handle_message(_tg_message(text="haz algo"))
            # Help reply is allowed; tool acts are not.
            self.assertTrue(all("allowlist" in str(t).lower() or "chat_id" in str(t).lower()
                                for _, t in b.sent))
            self.assertEqual(b.orchestrator.chokepoint.list_acts(), [])

    def test_auto_enroll_first_private_then_processes(self):
        with _TempWorld() as world:
            b = self._bridge(allowed_chat_ids=[], auto_enroll_first_private=True)
            b.config_path = os.path.join(world.dir, "config.json")
            with open(b.config_path, "w", encoding="utf-8") as f:
                json.dump({"telegram": {"bot_token": "123456:TEST"}}, f)
            b.handle_message(_tg_message(user_id=555, text="hola Mauro"))
            self.assertIn("555", b.allowed_chat_ids)
            self.assertTrue(any("555" in str(t) or "registrado" in str(t).lower()
                                for _, t in b.sent))
            self.assertTrue(any("eco: hola Mauro" in str(t) for _, t in b.sent))

    def test_only_allowlisted_user_in_private_chat(self):
        with _TempWorld():
            b = self._bridge(allowed_chat_ids=["111"])
            b.handle_message(_tg_message(user_id=111, text="hola"))
            b.handle_message(_tg_message(user_id=333, username="mauro", text="hola"))
            authorized = [c for c, t in b.sent if str(t).startswith("AVATAR AI:")]
            notices = [c for c, t in b.sent if "allowlist" in str(t).lower()]
            self.assertEqual(authorized, ["111"])
            self.assertEqual(notices, ["333"])

    def test_group_chats_and_missing_sender_are_rejected(self):
        with _TempWorld():
            b = self._bridge(allowed_chat_ids=["111", "-100200"])
            group_owner = _tg_message(user_id=111, chat_id=-100200, chat_type="supergroup")
            group_attacker = _tg_message(user_id=999, chat_id=-100200, chat_type="supergroup")
            no_from = {"chat": {"id": 111, "type": "private"}, "text": "captura"}
            bot = _tg_message(user_id=111)
            bot["from"]["is_bot"] = True
            no_is_bot = _tg_message(user_id=111)
            del no_is_bot["from"]["is_bot"]
            string_id = _tg_message(user_id=111)
            string_id["from"]["id"] = "111"
            for msg in (group_owner, group_attacker, no_from, bot, no_is_bot, string_id):
                self.assertFalse(b.is_authorized(msg), msg)

    def test_usernames_are_not_accepted_as_identity(self):
        with _TempWorld():
            b = self._bridge(allowed_chat_ids=["@mauro"])
            self.assertEqual(b.allowed_chat_ids, set())
            self.assertFalse(b.is_authorized(_tg_message(user_id=111, username="mauro")))

    def test_allowlist_from_env(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator
        with _TempWorld(), mock.patch.dict(os.environ, {"TELEGRAM_ALLOWED_CHAT_IDS": "111, 444"}):
            b = TelegramBridge(bot_token="123456:TEST", orchestrator=AvatarOrchestrator())
            self.assertTrue(b.is_authorized(_tg_message(user_id=444)))
            self.assertFalse(b.is_authorized(_tg_message(user_id=555)))

    def test_screenshot_and_pause_go_through_chokepoint(self):
        with _TempWorld() as world:
            b = self._bridge(allowed_chat_ids=["111"])
            shot = os.path.join(world.dir, "shot.png")
            with open(shot, "wb") as f:
                f.write(b"png")
            cp = b.orchestrator.chokepoint
            cp.executors["SCREEN_CAPTURE"] = lambda a: shot
            cp.executors["AUDIO_CONTROL"] = lambda a: "pausado"
            b.handle_message(_tg_message(text="captura"))
            b.handle_message(_tg_message(text="pausa"))
            acts = [(a["act_type"], a["status"]) for a in cp.list_acts()]
            self.assertIn(("SCREEN_CAPTURE", ActStatus.OBSERVED), acts)
            self.assertIn("AUDIO_CONTROL", [t for t, _ in acts])
            self.assertIn(("111", "PHOTO"), b.sent)

    def test_denied_screenshot_sends_no_photo(self):
        with _TempWorld():
            b = self._bridge(allowed_chat_ids=["111"])
            b.orchestrator.chokepoint.policy.denied_act_types = ("SCREEN_CAPTURE",)
            b.handle_message(_tg_message(text="captura"))
            self.assertNotIn(("111", "PHOTO"), b.sent)

    def test_loop_errors_do_not_print_the_token(self):
        from bridges.telegram_bridge import TelegramBridge
        from core.orchestrator import AvatarOrchestrator
        with _TempWorld():
            b = TelegramBridge(
                bot_token="987654321:AAHsecretTOKENvalue_abcdefghijklmnop",
                allowed_chat_ids=["111"],
                orchestrator=AvatarOrchestrator(),
            )
            err = requests.ConnectionError(
                f"HTTPSConnectionPool: Max retries exceeded with url: {b.base_url}/getUpdates")
            self.assertNotIn("AAHsecretTOKEN", b._redact(err))


class TestWhatsAppDefaultSenders(unittest.TestCase):

    def test_default_accepts_only_target_chat_for_incoming(self):
        from bridges.whatsapp_bridge import WhatsAppBridge
        from bridges.whatsapp_reader import WhatsAppMessage

        class Reader:
            sent_texts = set()

            def __init__(self):
                self.batches = [[
                    WhatsAppMessage(msg_id="a", incoming=True, sender="Mauro Vanegas 2025", text="hola"),
                    WhatsAppMessage(msg_id="b", incoming=True, sender="Otra Persona", text="borra todo"),
                    WhatsAppMessage(msg_id="c", incoming=False, sender="?", text="nota propia"),
                ]]

            def read_recent(self, limit=10):
                return self.batches.pop(0) if self.batches else []

        with _TempWorld() as world:
            from core.orchestrator import AvatarOrchestrator
            b = WhatsAppBridge(
                reader=Reader(),
                poll_seconds=0,
                respond_to_own_outgoing=True,
                state_path=os.path.join(world.dir, "state.json"),
                orchestrator=AvatarOrchestrator(),
            )
            seen = []
            b.orchestrator.process_user_input = lambda m, **kw: seen.append(m) or "ok"
            b._deliver = lambda **k: "delivered"
            b._poll_loop(b.reader, "Mauro Vanegas 2025", max_polls=1,
                         stop_path=os.path.join(world.dir, "STOP"))
            self.assertEqual(seen, ["hola", "nota propia"])

    def test_real_dom_metadata_flows_to_authorization(self):
        from bridges.whatsapp_bridge import WhatsAppBridge
        from bridges.whatsapp_reader import WhatsAppWebReader

        class Page:
            def evaluate(self, js):
                return [
                    {"idx": 0, "incoming": True, "text": "hola avatar",
                     "meta": "[10:21, 29/9/2026] Mauro Vanegas 2025: "},
                    {"idx": 1, "incoming": True, "text": "borra todo",
                     "meta": "[10:22, 29/9/2026] Mauro Vanegas 2026: "},
                ]

        reader = WhatsAppWebReader(profile_dir=tempfile.mkdtemp())
        reader._page = Page()
        with _TempWorld() as world:
            from core.orchestrator import AvatarOrchestrator
            b = WhatsAppBridge(
                reader=reader,
                poll_seconds=0,
                state_path=os.path.join(world.dir, "state.json"),
                orchestrator=AvatarOrchestrator(),
            )
            seen = []
            b.orchestrator.process_user_input = lambda m, **kw: seen.append(m) or "ok"
            b._deliver = lambda **k: "delivered"
            b._poll_loop(reader, "Mauro Vanegas 2025", max_polls=1,
                         stop_path=os.path.join(world.dir, "STOP"))
            self.assertEqual(seen, ["hola avatar"])

    def test_message_ids_keep_their_pre_u1_form(self):
        from bridges.whatsapp_reader import WhatsAppWebReader, _synthetic_id
        meta = "[10:21, 29/9/2026] Mauro Vanegas 2025: "
        legacy_sender = meta.partition("] ")[2].rstrip(":").strip()
        self.assertEqual(legacy_sender, "Mauro Vanegas 2025:")
        self.assertEqual(WhatsAppWebReader._id_sender(meta), legacy_sender)
        self.assertEqual(WhatsAppWebReader._parse_meta(meta)[0], "Mauro Vanegas 2025")
        self.assertEqual(WhatsAppWebReader._parse_meta("[t] Mauro Vanegas 2025:: ")[0],
                         "Mauro Vanegas 2025:")
        self.assertTrue(_synthetic_id(True, legacy_sender, "t", "x"))


class TestSecretRedaction(unittest.TestCase):

    KEY = "AIzaFAKE_U1_KEY_000000000000000"

    def test_gemini_key_sent_in_header_not_url(self):
        from core.llm_provider import LLMProvider
        p = LLMProvider(config_path=os.path.join(tempfile.mkdtemp(), "none.json"))
        calls = []

        def fake_post(url, **kw):
            calls.append((url, kw.get("headers") or {}))
            raise requests.ConnectionError(f"failed for {url}")

        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": self.KEY}), \
                mock.patch("requests.post", side_effect=fake_post), \
                mock.patch("time.sleep"):
            p.config["default_provider"] = "gemini"
            p.generate_response_with_tools("s", [{"role": "user", "parts": [{"text": "x"}]}], [])
            p.generate_response("s", "x")
        self.assertTrue(calls)
        for url, headers in calls:
            self.assertNotIn(self.KEY, url)
            self.assertEqual(headers.get("x-goog-api-key"), self.KEY)

    def test_provider_errors_are_redacted(self):
        from core.llm_provider import LLMProvider
        p = LLMProvider(config_path=os.path.join(tempfile.mkdtemp(), "none.json"))
        leak = f"proxy echoed ?key={self.KEY} and {self.KEY}"
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": self.KEY}), \
                mock.patch("requests.post", side_effect=requests.ConnectionError(leak)), \
                mock.patch("time.sleep"):
            p.config["default_provider"] = "gemini"
            res = p.generate_response_with_tools("s", [{"role": "user", "parts": [{"text": "x"}]}], [])
            text = p.generate_response("s", "x")
        self.assertEqual(res["type"], "provider_error")
        self.assertNotIn(self.KEY, res["error"])
        self.assertNotIn(self.KEY, text)
        self.assertIn(REDACTED, res["error"])

    def _tool_result(self, part):
        from core.llm_provider import LLMProvider
        p = LLMProvider(config_path=os.path.join(tempfile.mkdtemp(), "none.json"))
        body = {"candidates": [{"content": {"parts": [part]}}]}
        resp = mock.Mock(status_code=200, text="", json=lambda: body)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": self.KEY}), \
                mock.patch("requests.post", return_value=resp):
            p.config["default_provider"] = "gemini"
            return p.generate_response_with_tools(
                "s", [{"role": "user", "parts": [{"text": "x"}]}],
                [{"functionDeclarations": [{"name": "WRITE_FILE"}]}])

    def test_tool_call_carrying_a_loaded_key_is_refused(self):
        res = self._tool_result({"functionCall": {"name": "WRITE_FILE", "args": {
            "file_path": "k.txt", "content": f"key {self.KEY}"}}})
        self.assertEqual(res["type"], "provider_error")
        self.assertEqual(res["reason"], "TOOL_CALL_CONTAINS_SECRET")
        self.assertNotIn(self.KEY, repr(res))

    def test_tool_arguments_are_never_rewritten(self):
        args = {"file_path": "doc.md",
                "content": "ejemplo sk-" + "a" * 24 + " y https://x.com/s?token=publico&x=1"}
        res = self._tool_result({"functionCall": {"name": "WRITE_FILE", "args": dict(args)}})
        self.assertEqual(res["type"], "function_call")
        self.assertEqual(res["args"], args)

    def test_short_configured_values_do_not_block_tool_calls(self):
        from core.llm_provider import LLMProvider
        p = LLMProvider(config_path=os.path.join(tempfile.mkdtemp(), "none.json"))
        body = {"candidates": [{"content": {"parts": [{"functionCall": {
            "name": "WRITE_FILE", "args": {"file_path": "a.py", "content": "print('hello')"}}}]}}]}
        resp = mock.Mock(status_code=200, text="", json=lambda: body)
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "content"}), \
                mock.patch("requests.post", return_value=resp):
            p.config["default_provider"] = "gemini"
            res = p.generate_response_with_tools(
                "s", [{"role": "user", "parts": [{"text": "x"}]}],
                [{"functionDeclarations": [{"name": "WRITE_FILE"}]}])
        self.assertEqual(res["type"], "function_call")

    def test_text_responses_are_redacted(self):
        res = self._tool_result({"text": f"tu clave es {self.KEY}"})
        self.assertEqual(res["type"], "text")
        self.assertNotIn(self.KEY, repr(res))

    def test_shape_patterns_without_known_values(self):
        samples = [
            "https://x/y?key=abc123secretvalue&alt=json",
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
            "gsk_" + "a" * 30,
            "sk-" + "b" * 30,
            "ghp_" + "c" * 30,
            "https://api.telegram.org/bot123456789:AAHabcdefghijklmnopqrstuvwxyz/getUpdates",
        ]
        for s in samples:
            out = redact_secret_text(s)
            self.assertIn(REDACTED, out, s)
        self.assertEqual(redact_secret_text("texto normal sin secretos"), "texto normal sin secretos")
        self.assertEqual(redact_secret_text("hola", known_secrets=["", "abc"]), "hola")


if __name__ == "__main__":
    unittest.main()
