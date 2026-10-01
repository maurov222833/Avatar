"""Plantillas de instalación: dicen qué falta y no aceptan un secreto."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from core.avatar_config import check_config


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "avatar")


class ConfigCheckTests(unittest.TestCase):
    def test_shipped_templates_list_every_gap_and_stay_off(self):
        code, lines = check_config(CONFIG)
        self.assertEqual(code, 1)
        self.assertIn("FALTA mauro_charter.yaml.display_name", lines)
        self.assertIn("FALTA allowed_paths.yaml.write[0]", lines)
        self.assertIn("FALTA allowed_paths.yaml.mission_trash", lines)
        self.assertIn("FALTA spend_caps.yaml.currency", lines)
        self.assertIn("FALTA markets_watchlist.yaml.key_storage", lines)
        self.assertIn("FALTA channels.yaml.telegram.owner_id", lines)
        self.assertTrue(any(line.startswith("FALTA credentials_manifest.md:") for line in lines))
        self.assertFalse(any(line.startswith("INSEGURO") or line.startswith("SECRETO") for line in lines))

    def test_filled_copy_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(CONFIG, tmp, dirs_exist_ok=True)
            for name in os.listdir(tmp):
                path = os.path.join(tmp, name)
                with open(path, "r", encoding="utf-8") as handle:
                    text = handle.read()
                text = text.replace("TODO_MAURO", "NO_APLICA")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(text)
            code, lines = check_config(tmp)
            self.assertEqual(code, 0, lines)
            self.assertIn("COMPLETO", lines)

    def test_a_secret_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(CONFIG, tmp, dirs_exist_ok=True)
            path = os.path.join(tmp, "channels.yaml")
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("\nnote: api_key=abc123\n")
            code, lines = check_config(tmp)
            self.assertEqual(code, 2)
            self.assertTrue(any(line.startswith("SECRETO") for line in lines))

    def test_cli_on_the_shipped_folder(self):
        env = os.environ.copy()
        env["AVATAR_CONFIG_DIR"] = CONFIG
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "bin", "avatar"), "config", "check"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FALTA mauro_charter.yaml.display_name", result.stdout)


if __name__ == "__main__":
    unittest.main()
