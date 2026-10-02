"""La tecla global no se carga ni se instala. La señal de prueba es sintética."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import core.halt as halt
from core.act_chokepoint import ActChokepoint, ActPolicy


class HotkeySwitchTests(unittest.TestCase):
    def test_import_does_not_load_a_keyboard_hook(self):
        self.assertNotIn("pynput", sys.modules)
        self.assertNotIn("keyboard", sys.modules)
        self.assertFalse(any(name.startswith("pynput") for name in sys.modules))

    def test_default_switch_does_not_install_and_true_does_not_either(self):
        self.assertEqual(halt.start_hotkey_listener({}), "HOTKEY_LISTENER_OFF")
        self.assertEqual(halt.start_hotkey_listener({"hotkey_listener": False}), "HOTKEY_LISTENER_OFF")
        self.assertEqual(halt.start_hotkey_listener({"hotkey_listener": True}), "HOTKEY_LISTENER_NOT_INSTALLED")
        self.assertNotIn("pynput", sys.modules)
        self.assertNotIn("keyboard", sys.modules)

    def test_synthetic_signal_and_flag_file_do_not_need_a_key(self):
        path = os.path.join(tempfile.mkdtemp(), "halt.json")
        with mock.patch.dict(os.environ, {"AVATAR_HALT_PATH": path}):
            row = halt.accept_synthetic_halt("PAUSE")
            self.assertEqual(row["level"], "PAUSE")
            self.assertEqual(row["source"], "synthetic")
            flag = os.path.join(tempfile.mkdtemp(), "flag.txt")
            with open(flag, "w", encoding="utf-8") as handle:
                handle.write("KILL_SWITCH")
            self.assertEqual(halt.poll_trigger_file(flag), "KILL_SWITCH")
            self.assertEqual(halt.snapshot()["level"], "KILL_SWITCH")
            halt.resume("test")

    def test_watcher_stops_new_acts_while_the_orchestrator_is_stuck(self):
        path = os.path.join(tempfile.mkdtemp(), "halt.json")
        flag = os.path.join(tempfile.mkdtemp(), "flag.txt")
        blocked = threading.Event()
        entered = threading.Event()

        def stuck():
            entered.set()
            blocked.wait(2)

        worker = threading.Thread(target=stuck)
        worker.start()
        self.assertTrue(entered.wait(1))
        with mock.patch.dict(os.environ, {"AVATAR_HALT_PATH": path}):
            self.assertEqual(halt.start_trigger_watcher(flag, interval=0.02), "TRIGGER_WATCHER_ON")
            try:
                self.assertIsNone(halt.current_block_reason())
                with open(flag, "w", encoding="utf-8") as handle:
                    handle.write("STOP")
                deadline = time.time() + 1
                while time.time() < deadline and halt.current_block_reason() != "HALT_STOP":
                    time.sleep(0.02)
                self.assertEqual(halt.current_block_reason(), "HALT_STOP")
                self.assertTrue(worker.is_alive())
                ran = []
                cp = ActChokepoint(
                    policy=ActPolicy(dry_run=False, exec_requires_approval=False),
                    executors={"COMMAND": lambda a: ran.append(a["command"]) or "ok"},
                )
                denied = cp.perform("COMMAND", {"command": "echo hola"})
                self.assertIn("HALT_STOP", denied)
                self.assertEqual(ran, [])
                self.assertNotIn("pynput", sys.modules)
                self.assertNotIn("keyboard", sys.modules)
            finally:
                halt.stop_trigger_watcher(flag)
                halt.resume("test")
        blocked.set()
        worker.join(2)


if __name__ == "__main__":
    unittest.main()
