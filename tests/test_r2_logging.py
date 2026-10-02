"""R2 / E-17: structured JSON logging with secret redaction + lockfile."""
from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class TestStructuredLogging(unittest.TestCase):
    def setUp(self):
        # Reset logger state between tests
        import core.logging_util as lu
        lu._CONFIGURED = False
        lu._EXTRA_SECRETS.clear()
        root = logging.getLogger("avatar")
        for handler in list(root.handlers):
            handler.close()
        root.handlers.clear()

    def test_json_log_redacts_known_and_shaped_secrets(self):
        from core.logging_util import (
            JsonFormatter,
            _RedactingFilter,
            configure_logging,
            log,
            register_secrets,
        )

        configure_logging(json_logs=True, force=True)
        secret = "AIzaSyTestSecretKeyValue1234567890"
        register_secrets([secret])

        buf = io.StringIO()
        root = logging.getLogger("avatar")
        root.handlers.clear()
        h = logging.StreamHandler(buf)
        h.setFormatter(JsonFormatter())
        h.addFilter(_RedactingFilter())
        root.addHandler(h)

        log("INFO", f"calling provider with key={secret}", component="LLM")
        log("WARNING", "also gsk_abcdefghijklmnopqrstuvwxyz0123456789", component="LLM")

        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 2)
        for ln in lines:
            obj = json.loads(ln)
            self.assertIn("ts", obj)
            self.assertIn("level", obj)
            self.assertIn("msg", obj)
            self.assertNotIn(secret, ln)
            self.assertNotIn("AIzaSy", ln)
            self.assertNotIn("gsk_abcdefghij", ln)
            self.assertIn("[REDACTED]", obj["msg"])

    def test_plain_formatter_keeps_component(self):
        from core.logging_util import PlainFormatter, configure_logging, get_logger

        configure_logging(json_logs=False, force=True)
        buf = io.StringIO()
        root = logging.getLogger("avatar")
        root.handlers.clear()
        h = logging.StreamHandler(buf)
        h.setFormatter(PlainFormatter())
        root.addHandler(h)

        get_logger("bridge").info("hola", extra={"component": "TelegramBridge"})
        self.assertIn("[TelegramBridge]: hola", buf.getvalue())

    def test_log_file_env(self):
        from core.logging_util import configure_logging, log

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "avatar.jsonl")
            with mock.patch.dict(os.environ, {"AVATAR_LOG_FILE": path, "AVATAR_LOG_JSON": "1"}):
                configure_logging(force=True)
                log("INFO", "file-line", component="Test")
            self.assertTrue(os.path.isfile(path))
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("file-line", content)
            self.assertIn('"level": "INFO"', content)
            root = logging.getLogger("avatar")
            for handler in list(root.handlers):
                handler.close()
            root.handlers.clear()


class TestRequirementsLock(unittest.TestCase):
    def test_lockfile_exists_and_pins_direct_deps(self):
        lock = ROOT / "requirements.lock"
        self.assertTrue(lock.is_file(), "requirements.lock missing (R2)")
        text = lock.read_text(encoding="utf-8")
        self.assertNotIn("google-generativeai", text.lower())
        for req_file in ("requirements.txt", "requirements-dev.txt", "requirements-desktop.txt"):
            for line in (ROOT / req_file).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r"):
                    continue
                if "==" in line:
                    self.assertIn(line, text, f"{line} from {req_file} missing in lock")


if __name__ == "__main__":
    unittest.main()
