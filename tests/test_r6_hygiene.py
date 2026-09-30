"""R6: autoloop gone; text parser follows ToolRegistry ∪ ACT_TYPES."""
from __future__ import annotations

import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestR6Hygiene(unittest.TestCase):
    def test_autoloop_module_removed(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "core", "autoloop.py")))
        import importlib
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("core.autoloop")

    def test_parse_accepts_desktop_hotkey_from_registry(self):
        from core.cognitive.tool_registry import ToolRegistry
        from core.orchestrator import AvatarOrchestrator

        names = set(ToolRegistry.list_tools())
        self.assertIn("DESKTOP_HOTKEY", names)
        self.assertIn("AUDIO_CONTROL", names)
        self.assertIn("WHATSAPP_SEND", names)
        tool, args = AvatarOrchestrator._parse_tool_action(
            None,
            'ACCION: DESKTOP_HOTKEY\nPARAMETROS: minimize',
        )
        # unbound: call via instance-less by using the function on a dummy
        # _parse_tool_action uses self only implicitly? It is an instance method
        # but doesn't use self. Call through the class with a dummy self.
        self.assertEqual(tool, "DESKTOP_HOTKEY")
        self.assertIn("minimize", str(args))

    def test_subagents_still_importable_for_acceptance_surface(self):
        from core.subagents import AntigravityProxyAgent
        self.assertTrue(callable(AntigravityProxyAgent.execute_unattended_task))


if __name__ == "__main__":
    unittest.main()
