"""La tecla global no se carga ni se instala. La señal de prueba es sintética."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import core.halt as halt


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


if __name__ == "__main__":
    unittest.main()
