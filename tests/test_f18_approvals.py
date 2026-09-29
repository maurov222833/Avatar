"""F-18: approval-gated acts queue as PENDING and can be resolved later."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import (
    ActChokepoint,
    ActPolicy,
    ActStatus,
    EXEC_APPROVAL_REASON,
)
from core.state_db import StateEngine


class _TempDb:
    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="avatar_f18_")
        self.db = StateEngine(db_path=os.path.join(self.dir, "state.db"))
        return self.db

    def __exit__(self, *exc):
        return False


class TestF18ApprovalsQueue(unittest.TestCase):
    def test_command_without_approver_is_pending_not_silent_deny(self):
        with _TempDb() as db:
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=True),
                executors={"COMMAND": lambda a: ran.append(a["command"]) or f"ran:{a['command']}"},
            )
            out = cp.perform("COMMAND", {"command": "echo hello"}, mission_id="m1")
            self.assertIn("[PENDING_APPROVAL:", out)
            self.assertIn(EXEC_APPROVAL_REASON, out)
            self.assertEqual(ran, [])
            acts = cp.list_acts()
            self.assertEqual(acts[-1]["status"], ActStatus.PENDING_APPROVAL)
            pending = cp.list_pending_approvals()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["act_type"], "COMMAND")

    def test_resolve_approve_executes_and_clears_queue(self):
        with _TempDb() as db:
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=True),
                executors={"COMMAND": lambda a: ran.append(a["command"]) or f"ran:{a['command']}"},
            )
            out = cp.perform("COMMAND", {"command": "echo yes"})
            approval_id = out.split("[PENDING_APPROVAL:", 1)[1].split("]", 1)[0]
            result = cp.resolve_approval(approval_id, approved=True, resolver="test")
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "EXECUTED")
            self.assertEqual(ran, ["echo yes"])
            self.assertEqual(cp.list_pending_approvals(), [])
            stored = cp.get_approval(approval_id)
            self.assertEqual(stored["status"], "EXECUTED")
            self.assertIn("ran:echo yes", stored["result"])

    def test_resolve_reject_does_not_execute(self):
        with _TempDb() as db:
            ran = []
            cp = ActChokepoint(
                state_db=db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=True),
                executors={"COMMAND": lambda a: ran.append(a["command"]) or "ran"},
            )
            out = cp.perform("COMMAND", {"command": "echo no"})
            approval_id = out.split("[PENDING_APPROVAL:", 1)[1].split("]", 1)[0]
            result = cp.resolve_approval(approval_id, approved=False, resolver="test")
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "REJECTED")
            self.assertEqual(ran, [])
            self.assertEqual(cp.list_pending_approvals(), [])

    def test_http_pending_and_resolve_endpoints(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi not installed")

        # Pin AVATAR_HOME so server/orchestrator share an isolated DB.
        home = tempfile.mkdtemp(prefix="avatar_f18_http_")
        os.environ["AVATAR_HOME"] = home
        os.makedirs(os.path.join(home, "memory"), exist_ok=True)
        # Force a fresh shared orchestrator for this home.
        from core import runtime
        runtime.reset_shared_orchestrator()

        import importlib
        import server
        importlib.reload(server)
        client = TestClient(server.app)
        headers = server.auth_headers()

        r = client.post(
            "/api/terminal/execute",
            json={"command": "echo F18_HTTP"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()["output"]
        self.assertIn("PENDING_APPROVAL", body)
        approval_id = body.split("[PENDING_APPROVAL:", 1)[1].split("]", 1)[0]

        listed = client.get("/api/approvals/pending", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)
        self.assertEqual(listed.json()["pending"][0]["approval_id"], approval_id)

        resolved = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approved": True, "resolver": "test"},
            headers=headers,
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "EXECUTED")
        self.assertIn("F18_HTTP", resolved.json()["result"])

        empty = client.get("/api/approvals/pending", headers=headers)
        self.assertEqual(empty.json()["count"], 0)

        runtime.reset_shared_orchestrator()


if __name__ == "__main__":
    unittest.main()
