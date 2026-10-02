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
            env["AVATAR_HOME"] = folder
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

    def test_windows_python_exe_argv_pins_over_an_inherited_home(self):
        decoy = tempfile.mkdtemp(prefix="decoy_home_")
        script = textwrap.dedent(
            """
            import os
            import sys
            sys.argv = ["python.exe -m unittest", "discover", "-s", "tests", "-q"]
            from core.test_home import pin_test_home, running_as_test
            from core.state_db import StateEngine

            assert running_as_test(), sys.argv
            home = pin_test_home()
            assert "avatar_test_" in home, home
            assert os.environ["AVATAR_HOME"] == home
            assert home != os.environ["DECOY_HOME"]
            assert "TELEGRAM_BOT_TOKEN" not in os.environ
            engine = StateEngine()
            try:
                assert engine.db_path.startswith(home), engine.db_path
            finally:
                engine.close()

            sys.argv = [r"C:\\Python\\python.exe", "-m", "unittest", "discover"]
            assert running_as_test()
            sys.argv = [r"C:\\Python\\python.exe", "whatsapp_24x7.py"]
            assert not running_as_test()
            """
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = _REPO + os.pathsep + env.get("PYTHONPATH", "")
        env["AVATAR_HOME"] = decoy
        env["DECOY_HOME"] = decoy
        env["TELEGRAM_BOT_TOKEN"] = "123456:NOT-A-REAL-TOKEN"
        done = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + "\n" + done.stderr)
        self.assertFalse(os.path.exists(os.path.join(decoy, "memory", "state_engine.db")))

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

    def test_external_hosts_cannot_be_resolved_or_connected(self):
        import socket
        from core.test_home import ExternalNetworkBlocked
        with self.assertRaises(ExternalNetworkBlocked):
            socket.getaddrinfo("api.telegram.org", 443)
        sock = socket.socket()
        try:
            with self.assertRaises(ExternalNetworkBlocked):
                sock.connect(("1.1.1.1", 443))
        finally:
            sock.close()
        self.assertTrue(socket.getaddrinfo("127.0.0.1", 9))

    def test_child_processes_keep_a_fictional_token_and_the_guard(self):
        import textwrap
        from core.test_home import FICTIONAL_TELEGRAM_TOKEN, remember_real_token
        real = "999999:REAL-TOKEN-SHOULD-NOT-LEAK"
        remember_real_token(real)
        script = textwrap.dedent(
            """
            import os
            import socket
            from core.test_home import ExternalNetworkBlocked, FICTIONAL_TELEGRAM_TOKEN
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            assert token == FICTIONAL_TELEGRAM_TOKEN, token
            assert token != "999999:REAL-TOKEN-SHOULD-NOT-LEAK"
            try:
                socket.getaddrinfo("api.telegram.org", 443)
            except ExternalNetworkBlocked:
                pass
            else:
                raise SystemExit("el hijo resolvió api.telegram.org")
            """
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = _REPO + os.pathsep + env.get("PYTHONPATH", "")
        env["TELEGRAM_BOT_TOKEN"] = real
        done = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 0, done.stdout + "\n" + done.stderr)

    def test_popen_stays_a_class_so_asyncio_can_subclass_it(self):
        import subprocess
        from core.test_home import _install_subprocess_scrub
        _install_subprocess_scrub()
        self.assertIsInstance(subprocess.Popen, type)

        class _LikeWindowsAsyncio(subprocess.Popen):
            pass

        self.assertTrue(issubclass(_LikeWindowsAsyncio, subprocess.Popen))

    def test_server_and_whatsapp_runner_do_not_install_the_guard(self):
        for name in ("server.py", "whatsapp_24x7.py"):
            with open(os.path.join(_REPO, name), encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn("install_network_guard", source)
