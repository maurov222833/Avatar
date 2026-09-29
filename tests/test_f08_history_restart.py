"""F-08: a restart must keep the recent turns and must not delete the older ones."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


if __name__ == "__main__":
    unittest.main()
