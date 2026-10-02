"""D-7 / Fase 3b: in-process watchdog ticks over approvals and safe resumes."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.act_chokepoint import ActChokepoint, ActPolicy
from core.orchestrator import AvatarOrchestrator
from core.resume_engine import MissionResumeStatus, ResumeEngine
from core.state_db import StateEngine
from core.watchdog import Watchdog, WatchdogConfig
from tests.scratch_dir import work_dir


class _TempWorld:
    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="avatar_wd_")
        self.db = StateEngine(db_path=os.path.join(self.dir, "state.db"))
        return self

    def __exit__(self, *a):
        return False


class TestWatchdog(unittest.TestCase):
    def test_tick_reports_pending_approvals_without_resolving(self):
        with _TempWorld() as world:
            orch = AvatarOrchestrator()
            orch.state_db = world.db
            orch.chokepoint = ActChokepoint(
                state_db=world.db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=True),
                executors={"COMMAND": lambda a: "ran"},
            )
            orch.resume_engine = ResumeEngine(state_db=world.db)
            out = orch.chokepoint.perform("COMMAND", {"command": "echo wd"})
            self.assertIn("PENDING_APPROVAL", out)

            wd = Watchdog(orch, WatchdogConfig(auto_resume_safe=False))
            report = wd.tick()
            self.assertEqual(report.to_dict()["pending_count"], 1)
            self.assertEqual(orch.chokepoint.list_pending_approvals()[0]["status"], "PENDING")

    def test_tick_auto_resumes_only_safe_missions(self):
        with _TempWorld() as world:
            orch = AvatarOrchestrator()
            orch.state_db = world.db
            orch.resume_engine = ResumeEngine(state_db=world.db)
            orch.chokepoint = ActChokepoint(
                state_db=world.db,
                policy=ActPolicy(dry_run=False, exec_requires_approval=False),
                executors={"LIST_DIR": lambda a: "ok"},
            )

            calls = []

            def fake_resume(mission_id):
                calls.append(mission_id)
                return {"status": "OK", "mission_id": mission_id, "message": "resumed"}

            orch.resume_mission = fake_resume

            def inspect():
                return [
                    {"mission_id": "safe-1"},
                    {"mission_id": "uncertain-1"},
                    {"mission_id": "failed-1"},
                ]

            def evaluate(mission_id):
                if mission_id.startswith("safe"):
                    return (MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME, {"task_id": "t1"}, "ok")
                if mission_id.startswith("uncertain"):
                    return (MissionResumeStatus.ACTIVE_MISSION_UNCERTAIN, {"task_id": "t2"}, "block")
                return (MissionResumeStatus.ACTIVE_MISSION_FAILED, {"task_id": "t3"}, "fail")

            orch.resume_engine.inspect_active_missions = inspect
            orch.resume_engine.evaluate_mission_for_resume = evaluate

            wd = Watchdog(orch, WatchdogConfig(auto_resume_safe=True, max_resumes_per_tick=5))
            report = wd.tick()
            self.assertEqual(calls, ["safe-1"])
            self.assertEqual(len(report.resumed), 1)
            self.assertEqual(len(report.skipped_uncertain), 1)
            self.assertEqual(len(report.skipped_failed), 1)

    def test_night_does_not_resume_and_a_backup_is_kept(self):
        source = work_dir("wd_src_")
        with open(os.path.join(source, "a.txt"), "w", encoding="utf-8") as handle:
            handle.write("dato")
        dest = work_dir("wd_dst_")
        halt_path = os.path.join(tempfile.mkdtemp(), "halt.json")
        orch = mock.Mock()
        orch.config = {}
        orch.chokepoint = None
        orch.resume_engine.inspect_active_missions.return_value = [{"mission_id": "safe-1"}]
        orch.resume_engine.evaluate_mission_for_resume.return_value = (
            MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME, {"task_id": "t"}, "ok",
        )
        wd = Watchdog(orch, WatchdogConfig(
            night_mode=True, backup_source=source, backup_dest=dest,
        ))
        with mock.patch.dict(os.environ, {"AVATAR_HALT_PATH": halt_path}):
            report = wd.tick()
        orch.resume_mission.assert_not_called()
        self.assertIn("night_no_resume", report.notes)
        self.assertTrue(any(note.startswith("backup:") for note in report.notes))
        from core.path_guard import authorize_path
        stamp = next(name for name in os.listdir(dest) if not name.startswith("."))
        decision, reason = authorize_path(
            os.path.join(dest, stamp, "a.txt"), "delete", source,
        )
        self.assertEqual(decision, "DENY")
        self.assertEqual(reason, "PATH_BACKUP_IMMUTABLE")

    def test_disabled_watchdog_is_noop(self):
        orch = AvatarOrchestrator()
        wd = Watchdog(orch, WatchdogConfig(enabled=False))
        report = wd.tick()
        self.assertEqual(report.notes, ["watchdog.disabled"])


if __name__ == "__main__":
    unittest.main()
