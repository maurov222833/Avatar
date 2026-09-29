"""F-08: a restart must keep the recent turns and must not delete the older ones."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rag_memory import RAGMemory
from core.state_db import StateEngine


def _messages(count: int):
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i:03d}"}
        for i in range(count)
    ]


class TestF08HistoryRestart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "f08.db")
        self.engine = StateEngine(db_path=self.db_path)

    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def test_reload_returns_the_recent_window_in_order(self):
        self.engine.sync_history(_messages(120))
        self.engine.close()
        reopened = StateEngine(db_path=self.db_path)
        try:
            loaded = reopened.load_history()
        finally:
            reopened.close()
        self.assertEqual(len(loaded), 50)
        self.assertEqual(loaded[0]["content"], "msg-070")
        self.assertEqual(loaded[-1]["content"], "msg-119")

    def test_next_save_after_restart_keeps_the_older_rows(self):
        self.engine.sync_history(_messages(120))
        self.engine.close()
        reopened = StateEngine(db_path=self.db_path)
        try:
            loaded = reopened.load_history()
            loaded.append({"role": "user", "content": "msg-new"})
            reopened.sync_history(loaded)
            stored = reopened.load_history(limit=1000)
        finally:
            reopened.close()
        contents = [row["content"] for row in stored]
        self.assertEqual(len(stored), 121)
        self.assertEqual(contents[0], "msg-000")
        self.assertEqual(contents[-2], "msg-119")
        self.assertEqual(contents[-1], "msg-new")
        self.assertIn("msg-069", contents)

    def test_saving_the_same_window_again_does_not_duplicate(self):
        first = _messages(4)
        self.engine.sync_history(first)
        self.engine.sync_history(first + [{"role": "user", "content": "msg-004"}])
        self.engine.sync_history(self.engine.load_history(limit=1000))
        stored = self.engine.load_history(limit=1000)
        self.assertEqual([row["content"] for row in stored], [f"msg-{i:03d}" for i in range(5)])

    def test_repeated_text_after_restart_is_not_dropped(self):
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(60)])
        self.engine.close()
        reopened = StateEngine(db_path=self.db_path)
        try:
            loaded = reopened.load_history()
            loaded.append({"role": "user", "content": "ok"})
            reopened.sync_history(loaded)
            stored = reopened.load_history(limit=1000)
        finally:
            reopened.close()
        self.assertEqual(len(stored), 61)
        self.assertEqual(stored[-1]["content"], "ok")

    def test_repeated_text_without_ids_keeps_the_new_turn(self):
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(60)])
        fresh = [{"role": "user", "content": "ok"} for _ in range(51)]
        self.engine.sync_history(fresh)
        stored = self.engine.load_history(limit=1000)
        self.assertEqual(len(stored), 61)
        self.assertTrue(all(row["content"] == "ok" for row in stored))

    def test_two_extra_repeated_turns_without_ids_are_kept(self):
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(60)])
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(52)])
        self.assertEqual(len(self.engine.load_history(limit=1000)), 62)

    def test_repeated_user_turn_before_a_new_assistant_turn_without_ids(self):
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(60)])
        incoming = [{"role": "user", "content": "ok"} for _ in range(51)]
        incoming.append({"role": "assistant", "content": "ok"})
        self.engine.sync_history(incoming)
        stored = self.engine.load_history(limit=1000)
        self.assertEqual(len(stored), 62)
        self.assertEqual(stored[-2]["role"], "user")
        self.assertEqual(stored[-1]["role"], "assistant")

    def test_window_of_repeated_text_after_distinct_turns_keeps_the_new_copy(self):
        stored_first = _messages(10) + [{"role": "user", "content": "ok"} for _ in range(60)]
        self.engine.sync_history(stored_first)
        incoming = [{"role": "user", "content": "ok"} for _ in range(51)]
        self.engine.sync_history(incoming)
        stored = self.engine.load_history(limit=1000)
        self.assertEqual(len(stored), 71)
        self.assertEqual(stored[0]["content"], "msg-000")

    def test_full_resend_without_ids_does_not_duplicate(self):
        self.engine.sync_history(_messages(60))
        self.engine.sync_history(_messages(60))
        self.engine.sync_history(_messages(60) + [{"role": "user", "content": "msg-060"}])
        stored = self.engine.load_history(limit=1000)
        self.assertEqual([row["content"] for row in stored], [f"msg-{i:03d}" for i in range(61)])

    def test_identical_full_resend_and_plain_window_do_not_duplicate(self):
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(60)])
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(60)])
        self.engine.sync_history([{"role": "user", "content": "ok"} for _ in range(50)])
        self.assertEqual(len(self.engine.load_history(limit=1000)), 60)


class TestF08HistoryJsonFallback(unittest.TestCase):
    def test_json_keeps_rows_outside_the_window_and_migrates_them(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        memory_dir = tmp.name
        db_path = os.path.join(memory_dir, "state_engine.db")
        engine = StateEngine(db_path=db_path)
        rag = RAGMemory(memory_dir=memory_dir, state_db=engine)
        rag.save_history(_messages(120))
        window = engine.load_history()
        window.append({"role": "user", "content": "msg-new"})
        rag.save_history(window)
        engine.close()

        with open(rag.history_file, encoding="utf-8") as handle:
            dumped = json.load(handle)
        self.assertEqual(len(dumped), 121)
        self.assertEqual(dumped[0]["content"], "msg-000")
        self.assertEqual(dumped[-1]["content"], "msg-new")
        self.assertIn("id", dumped[0])

        for suffix in ("", "-wal", "-shm"):
            path = db_path + suffix
            if os.path.exists(path):
                os.remove(path)

        restored = RAGMemory(memory_dir=memory_dir)
        self.addCleanup(restored.state_db.close)
        stored = restored.state_db.load_history(limit=1000)
        self.assertEqual(len(stored), 121)
        self.assertEqual(stored[0]["content"], "msg-000")
        self.assertEqual(stored[-1]["content"], "msg-new")


if __name__ == "__main__":
    unittest.main()
