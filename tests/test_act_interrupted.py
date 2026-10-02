"""Un acto REQUESTED sin resultado es una caída. No se vuelve a ejecutar."""
from __future__ import annotations

import os
import tempfile
import unittest


class InterruptedActTests(unittest.TestCase):
    def test_a_crash_mid_executor_is_interrupted_and_not_rerun(self):
        from core.act_chokepoint import ActChokepoint, ActStatus
        from core.state_db import StateEngine

        calls = []
        with tempfile.TemporaryDirectory() as folder:
            db = StateEngine(db_path=os.path.join(folder, "state_engine.db"))
            try:
                def executor(args):
                    calls.append(dict(args))
                    rows = cp.list_acts()
                    self.assertEqual(rows[0]["status"], ActStatus.REQUESTED)
                    self.assertEqual(rows[0]["idempotency_key"], "clave-1")
                    self.assertFalse(rows[0]["executor_result"])
                    raise KeyboardInterrupt

                cp = ActChokepoint(
                    state_db=db, executors={"READ_FILE": executor})
                with self.assertRaises(KeyboardInterrupt):
                    cp.perform(
                        "READ_FILE",
                        {"file_path": "x", "idempotency_key": "clave-1"},
                    )
                self.assertEqual(len(calls), 1)

                restarted = ActChokepoint(
                    state_db=db, executors={"READ_FILE": executor})
                rows = restarted.list_acts()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["status"], ActStatus.INTERRUPTED)
                self.assertEqual(rows[0]["policy_reason"], "UNVERIFIED")
                self.assertEqual(int(rows[0]["observation_verified"] or 0), 0)
                self.assertEqual(len(calls), 1)

                again = restarted.perform(
                    "READ_FILE",
                    {"file_path": "x", "idempotency_key": "clave-1"},
                )
                self.assertIn("No se reejecuta", again)
                self.assertEqual(len(calls), 1)
            finally:
                db.close()
