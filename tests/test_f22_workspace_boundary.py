"""F-22: workspace boundary must not treat Windows drive paths as relative on POSIX."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.file_tool import FileTool
from tools.shell_tool import ShellTool


class TestF22WorkspaceBoundary(unittest.TestCase):
    def test_windows_drive_path_is_outside_on_posix(self):
        if os.name == "nt":
            self.skipTest("drive-letter ambiguity is a POSIX abspath issue")
        ws = FileTool.get_allowed_workspace()
        outside = r"C:\Windows\System32\calc.exe"
        self.assertFalse(FileTool.is_within_workspace(outside, ws))
        self.assertIn("[Seguridad]", FileTool.read_file(outside))
        self.assertFalse(ShellTool.is_within_workspace(r"C:\Windows", ws))
        self.assertIn("[Seguridad]", ShellTool.execute_command("dir", cwd=r"C:\Windows"))

    def test_unix_absolute_outside_is_blocked(self):
        if os.name == "nt":
            self.skipTest("unix absolute path check")
        self.assertIn("[Seguridad]", FileTool.read_file("/etc/passwd"))


if __name__ == "__main__":
    unittest.main()
