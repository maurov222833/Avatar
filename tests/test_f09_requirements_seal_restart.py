"""F-09: a requirements seal from another process must not crash or block resume.

Same-process tampering, where the seal still names the current key and the HMAC
fails, stays a hard block and is never rewritten as "no requirements".
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cognitive.mission_completion_gate import MissionCompletionGate
from core.resume_engine import MissionResumeStatus, ResumeEngine
from core.state_db import StateEngine


def _child(db_path: str) -> None:
    engine = StateEngine(db_path=db_path)
    try:
        plain = engine.get_mission("msn-plain")
        pending = engine.get_mission("msn-pending")
        plain_auth = MissionCompletionGate.evaluate_and_authorize("msn-plain", state_db=engine)
        resume = ResumeEngine(state_db=engine).evaluate_mission_for_resume("msn-pending")
        report = {
            "plain_intact": engine.verify_requirements_integrity(plain),
            "plain_state": engine.requirements_seal_state(plain),
            "plain_status": plain_auth.authorized_status,
            "plain_reasons": list(plain_auth.verdict.blocking_reasons),
            "pending_resume": resume[0],
            "pending_blocked": engine.get_mission("msn-pending")["status"] == "BLOCKED",
        }
    finally:
        engine.close()
    print(json.dumps(report))


class TestF09RequirementsSealRestart(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "f09.db")
        self.engine = StateEngine(db_path=self.db_path)

    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def test_same_process_column_edit_blocks_and_is_not_downgraded(self):
        mission = self.engine.create_mission(
            mission_id="msn-tamper",
            raw_prompt="probe",
            required_capabilities=["CAP_STATE_ENGINE"],
        )
        self.assertTrue(self.engine.verify_requirements_integrity(self.engine.get_mission(mission)))
        with self.engine._lock:
            conn = self.engine._get_connection()
            conn.execute(
                "UPDATE missions SET required_capabilities='[]', requirements_declared=0"
                " WHERE mission_id=?",
                (mission,),
            )
            conn.commit()
        auth = MissionCompletionGate.evaluate_and_authorize(mission, state_db=self.engine)
        self.assertEqual(auth.authorized_status, "BLOCKED")
        self.assertNotEqual(auth.authorized_status, "NO_REQUIREMENTS_DECLARED")
        self.assertTrue(
            any("REQUIREMENTS_INTEGRITY_FAILURE" in reason for reason in auth.verdict.blocking_reasons)
        )
        self.assertEqual(self.engine.update_mission_status(mission), "BLOCKED")
        self.assertEqual(self.engine.get_mission(mission)["status"], "BLOCKED")

    def test_wiped_seal_still_blocks(self):
        mission = self.engine.create_mission(
            mission_id="msn-wiped",
            raw_prompt="probe",
            declare_no_requirements=True,
        )
        with self.engine._lock:
            conn = self.engine._get_connection()
            conn.execute(
                "UPDATE missions SET requirements_seal='' WHERE mission_id=?",
                (mission,),
            )
            conn.commit()
        auth = MissionCompletionGate.evaluate_and_authorize(mission, state_db=self.engine)
        self.assertEqual(auth.authorized_status, "BLOCKED")
        self.assertNotEqual(auth.authorized_status, "NO_REQUIREMENTS_DECLARED")

    def test_restart_leaves_the_mission_resumable(self):
        self.engine.create_mission(
            mission_id="msn-plain",
            raw_prompt="probe",
            declare_no_requirements=True,
        )
        self.engine.create_mission(
            mission_id="msn-pending",
            raw_prompt="probe",
            required_capabilities=["CAP_STATE_ENGINE"],
        )
        self.engine.create_planner_task(
            task_id="task-1",
            mission_id="msn-pending",
            step_index=0,
            description="pendiente",
            tool_name="LIST_DIR",
            tool_args={"path": "."},
            status="PENDING",
        )
        self.engine.close()

        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), self.db_path],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(report["plain_intact"])
        self.assertEqual(report["plain_state"], "intact")
        self.assertEqual(report["plain_status"], "NO_REQUIREMENTS_DECLARED")
        self.assertFalse(
            any("REQUIREMENTS_INTEGRITY_FAILURE" in reason for reason in report["plain_reasons"])
        )
        self.assertEqual(report["pending_resume"], MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME)
        self.assertFalse(report["pending_blocked"])

    def test_forged_seal_does_not_complete_the_mission(self):
        cases = {
            "msn-forged": ("v2:0000000000000000:" + ("ab" * 32), "BLOCKED"),
            "msn-legacy": ("cd" * 32, "IN_PROGRESS"),
        }
        for mission_id, (seal, expected) in cases.items():
            self.engine.create_mission(
                mission_id=mission_id,
                raw_prompt="probe",
                required_capabilities=["CAP_STATE_ENGINE"],
            )
            with self.engine._lock:
                conn = self.engine._get_connection()
                conn.execute(
                    "UPDATE missions SET required_capabilities='[]', requirements_declared=0,"
                    " requirements_seal=? WHERE mission_id=?",
                    (seal, mission_id),
                )
                conn.commit()
            auth = MissionCompletionGate.evaluate_and_authorize(mission_id, state_db=self.engine)
            self.assertEqual(auth.authorized_status, expected, seal)
            self.assertFalse(auth.verdict.can_complete, seal)
            self.assertNotEqual(auth.authorized_status, "NO_REQUIREMENTS_DECLARED", seal)
            persisted = self.engine.update_mission_status(mission_id)
            self.assertEqual(persisted, expected, seal)

    def test_resume_does_not_report_completion_for_a_forged_seal(self):
        mission = self.engine.create_mission(
            mission_id="msn-resume-forged",
            raw_prompt="probe",
            required_capabilities=["CAP_STATE_ENGINE"],
        )
        self.engine.create_planner_task(
            task_id="task-verified",
            mission_id=mission,
            step_index=0,
            description="hecha",
            tool_name="LIST_DIR",
            tool_args={"path": "."},
            status="VERIFIED",
        )
        forged = "v2:0000000000000000:" + ("ab" * 32)
        with self.engine._lock:
            conn = self.engine._get_connection()
            conn.execute(
                "UPDATE missions SET required_capabilities='[]', requirements_declared=0,"
                " requirements_seal=? WHERE mission_id=?",
                (forged, mission),
            )
            conn.commit()
        result = ResumeEngine(state_db=self.engine).resume_active_mission(mission)
        self.assertNotIn(result["status"], ("COMPLETED", "NO_REQUIREMENTS_DECLARED"))
        self.assertEqual(self.engine.get_mission(mission)["status"], "BLOCKED")

    def test_status_write_matches_the_row_that_was_checked(self):
        mission = self.engine.create_mission(
            mission_id="msn-race",
            raw_prompt="probe",
            declare_no_requirements=True,
        )
        snapshot = self.engine.get_mission(mission)
        with self.engine._lock:
            conn = self.engine._get_connection()
            conn.execute(
                "UPDATE missions SET required_capabilities='[]', requirements_declared=0,"
                " requirements_seal='' WHERE mission_id=?",
                (mission,),
            )
            conn.commit()
        persisted = self.engine._persist_mission_status(
            mission, "NO_REQUIREMENTS_DECLARED", snapshot=snapshot
        )
        self.assertEqual(persisted, "BLOCKED")
        self.assertEqual(self.engine.get_mission(mission)["status"], "BLOCKED")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].endswith(".db"):
        _child(sys.argv[1])
    else:
        unittest.main()
