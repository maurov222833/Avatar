"""La suite no abre la base operativa ni se queda con el token de Telegram."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest


_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SuiteIsolationTests(unittest.TestCase):
    def test_unittest_discover_does_not_open_the_operational_db(self):
        real = os.path.join(_REPO, "memory", "state_engine.db")
        before = os.path.getsize(real) if os.path.exists(real) else None
        probe = textwrap.dedent(
            """
            import os
            import unittest
            from core.state_db import StateEngine
            from core.paths import avatar_home

            class Probe(unittest.TestCase):
                def test_home_is_temporary(self):
                    repo = os.environ["REPO_ROOT"]
                    engine = StateEngine()
                    try:
                        path = os.path.abspath(engine.db_path)
                    finally:
                        engine.close()
                    self.assertIn("avatar_test_", path)
                    self.assertNotEqual(path, os.path.abspath(os.path.join(repo, "memory", "state_engine.db")))
                    self.assertIn("avatar_test_", avatar_home())
                    self.assertEqual(os.environ.get("TELEGRAM_BOT_TOKEN", ""), "")
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "test_probe.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(probe)
            env = os.environ.copy()
            env["PYTHONPATH"] = _REPO + os.pathsep + env.get("PYTHONPATH", "")
            env["REPO_ROOT"] = _REPO
            env["TELEGRAM_BOT_TOKEN"] = "123456:NOT-A-REAL-TOKEN"
            done = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", folder, "-p", "test_probe.py"],
                cwd=_REPO,
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(done.returncode, 0, done.stdout + "\n" + done.stderr)
        after = os.path.getsize(real) if os.path.exists(real) else None
        self.assertEqual(before, after)

    def test_a_normal_process_keeps_its_home_and_token(self):
        with tempfile.TemporaryDirectory() as home:
            script = (
                "import os\n"
                "from core.paths import avatar_home\n"
                "assert avatar_home() == os.environ['AVATAR_HOME']\n"
                "assert os.environ['TELEGRAM_BOT_TOKEN'] == '123456:NOT-A-REAL-TOKEN'\n"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = _REPO + os.pathsep + env.get("PYTHONPATH", "")
            env["AVATAR_HOME"] = home
            env["TELEGRAM_BOT_TOKEN"] = "123456:NOT-A-REAL-TOKEN"
            done = subprocess.run(
                [sys.executable, "-c", script],
                cwd=_REPO,
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(done.returncode, 0, done.stdout + "\n" + done.stderr)
