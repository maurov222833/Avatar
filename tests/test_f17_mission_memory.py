"""F-17: mission summaries are saved and searchable via RAGMemory."""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rag_memory import RAGMemory
from core.state_db import StateEngine


class TestF17MissionMemory(unittest.TestCase):
    def test_save_knowledge_has_caller_via_mission_summary(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_f17_"))
            db = stack.enter_context(contextlib.closing(StateEngine(os.path.join(tmp, "s.db"))))
            mem = RAGMemory(memory_dir=tmp, state_db=db)
            content = mem.save_mission_summary(
                "msn_abc",
                prompt="arregla el parser de facturas PDF",
                status="REPORTED",
                acts=[
                    {"act_type": "READ_FILE"},
                    {"act_type": "WRITE_FILE"},
                    {"act_type": "READ_FILE"},
                ],
            )
            self.assertIn("msn_abc", content)
            self.assertIn("WRITE_FILE", content)
            kb = mem.load_knowledge()
            self.assertTrue(any("msn_abc" in k for k in kb))

            hit = mem.search_knowledge("facturas PDF parser")
            self.assertIn("msn_abc", hit)
            self.assertIn("REPORTED", hit)

    def test_search_matches_content_not_only_title(self):
        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_f17b_"))
            db = stack.enter_context(contextlib.closing(StateEngine(os.path.join(tmp, "s.db"))))
            mem = RAGMemory(memory_dir=tmp, state_db=db)
            mem.save_knowledge("lesson-one", "Usar Playwright headless para scrapers frágiles")
            hit = mem.search_knowledge("Playwright scrapers")
            self.assertIn("Playwright", hit)
            self.assertIn("lesson-one", hit)

    def test_orchestrator_persist_mission_summary_on_reconcile_hook(self):
        from core.orchestrator import AvatarOrchestrator

        with contextlib.ExitStack() as stack:
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="avatar_f17c_"))
            db = stack.enter_context(contextlib.closing(StateEngine(db_path=os.path.join(tmp, "state.db"))))
            sess = db.create_session()
            mid = db.create_mission(
                session_id=sess,
                raw_prompt="instala dependencia requests",
                classified_intent="DIRECT_ACTION",
                status="IN_PROGRESS",
                required_capabilities=[],
                declare_no_requirements=True,
            )
            mem = RAGMemory(memory_dir=tmp, state_db=db)
            orch = AvatarOrchestrator.__new__(AvatarOrchestrator)
            orch.state_db = db
            orch.memory = mem
            orch.chokepoint = MagicMock()
            orch.chokepoint.list_acts.return_value = [
                {"act_type": "COMMAND", "status": "OBSERVED"},
            ]
            orch._persist_mission_summary(mid, status="REPORTED")
            found = mem.search_knowledge("dependencia requests")
            self.assertIn(mid, found)
            self.assertIn("COMMAND", found)


if __name__ == "__main__":
    unittest.main()
