"""La forense lee una copia y no toca la base que le pasan."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest


_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LedgerForensicsTests(unittest.TestCase):
    def test_counts_by_day_and_leaves_the_source_bytes_alone(self):
        from tools.ledger_forensics import inspect_database
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "state_engine.db")
            conn = sqlite3.connect(source)
            conn.execute(
                "CREATE TABLE missions (mission_id TEXT, created_at TEXT, status TEXT, raw_prompt TEXT)"
            )
            conn.execute(
                "CREATE TABLE acts (act_id TEXT, created_at TEXT, act_type TEXT, request TEXT)"
            )
            conn.execute(
                "CREATE TABLE history_entries (id INTEGER, timestamp TEXT, role TEXT, content TEXT)"
            )
            conn.execute(
                "INSERT INTO missions VALUES ('m1', '2026-10-02T01:00:00', 'PENDING', 'echo prueba')"
            )
            conn.execute(
                "INSERT INTO acts VALUES ('a1', '2026-10-02T01:00:00', 'COMMAND', 'echo hi')"
            )
            conn.execute(
                "INSERT INTO history_entries VALUES (1, '2026-10-01T22:00:00', 'user', 'hola')"
            )
            conn.commit()
            conn.close()
            with open(source, "rb") as handle:
                before = hashlib.sha256(handle.read()).hexdigest()
            report = inspect_database(source)
            with open(source, "rb") as handle:
                after = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(before, after)
        self.assertIn("mode=ro", report)
        self.assertIn("2026-10-02  PENDING  1", report)
        self.assertIn("2026-10-02  COMMAND  1", report)
        self.assertIn("2026-10-01  user  1", report)
        self.assertIn("misiones  1", report)
        self.assertIn("actos  1", report)

    def test_cli_reads_the_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "vacia.db")
            sqlite3.connect(source).close()
            done = subprocess.run(
                [sys.executable, os.path.join(_REPO, "tools", "ledger_forensics.py"), source],
                cwd=_REPO,
                capture_output=True,
                text=True,
            )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("mode=ro", done.stdout)
