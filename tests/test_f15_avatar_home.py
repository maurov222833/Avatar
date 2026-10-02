"""F-15: config and memory resolve through AVATAR_HOME, not a hardcoded drive letter."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import paths
from core.llm_provider import LLMProvider
from core.orchestrator import AvatarOrchestrator
from core.rag_memory import RAGMemory


class TestF15AvatarHome(unittest.TestCase):
    def setUp(self):
        self.prev = os.environ.get("AVATAR_HOME")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["AVATAR_HOME"] = self.tmp.name
        os.makedirs(os.path.join(self.tmp.name, "memory"), exist_ok=True)
        with open(os.path.join(self.tmp.name, "config.json"), "w", encoding="utf-8") as handle:
            json.dump({"default_provider": "gemini", "gemini": {"api_key": ""}}, handle)

    def tearDown(self):
        if self.prev is None:
            os.environ.pop("AVATAR_HOME", None)
        else:
            os.environ["AVATAR_HOME"] = self.prev

    def test_paths_follow_avatar_home(self):
        self.assertEqual(paths.avatar_home(), os.path.abspath(self.tmp.name))
        self.assertEqual(paths.config_path(), os.path.join(os.path.abspath(self.tmp.name), "config.json"))
        self.assertEqual(paths.memory_dir(), os.path.join(os.path.abspath(self.tmp.name), "memory"))
        self.assertNotIn("PROYECTOS ANTIGRAVITY", paths.config_path())
        self.assertNotIn("PROYECTOS ANTIGRAVITY", paths.memory_dir())

    def test_llm_and_orchestrator_share_the_same_config_file(self):
        llm = LLMProvider()
        orch = AvatarOrchestrator()
        self.assertEqual(os.path.abspath(llm.config_path), os.path.abspath(paths.config_path()))
        self.assertEqual(
            os.path.abspath(orch.llm.config_path),
            os.path.abspath(paths.config_path()),
        )
        from tools.file_tool import FileTool
        from tools.shell_tool import ShellTool
        self.assertEqual(ShellTool.get_allowed_workspace(), FileTool.get_allowed_workspace())

    def test_rag_uses_memory_under_home_when_asked(self):
        rag = RAGMemory(memory_dir=paths.memory_dir())
        self.assertEqual(os.path.abspath(rag.memory_dir), os.path.abspath(paths.memory_dir()))

    def test_cleanup_closes_the_sqlite_file_inside_the_temp_dir(self):
        import core.state_db as sd
        folder = tempfile.TemporaryDirectory()
        db = os.path.join(folder.name, "memory", "state_engine.db")
        os.makedirs(os.path.dirname(db), exist_ok=True)
        engine = sd.StateEngine(db_path=db)
        self.assertIsNotNone(engine._conn)
        folder.cleanup()
        self.assertIsNone(engine._conn)
        self.assertFalse(os.path.exists(db))

    def test_default_without_env_is_repo_root(self):
        os.environ.pop("AVATAR_HOME", None)
        try:
            repo = os.path.dirname(os.path.dirname(os.path.abspath(paths.__file__)))
            self.assertEqual(paths.avatar_home(), repo)
            self.assertEqual(paths.config_path(), os.path.join(repo, "config.json"))
            self.assertEqual(paths.memory_dir(), os.path.join(repo, "memory"))
        finally:
            os.environ["AVATAR_HOME"] = self.tmp.name


if __name__ == "__main__":
    unittest.main()
