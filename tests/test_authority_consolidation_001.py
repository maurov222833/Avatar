import unittest
import os
import shutil
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.checkpoint_engine import CheckpointEngine
from core.resume_engine import ResumeEngine, MissionResumeStatus
from core.cognitive.capability_registry import (
    CapabilityEvidenceRegistry,
    CapabilityEvidence,
    EvidenceType,
    CapabilityStatus,
)
from core.cognitive.mission_completion_gate import MissionCompletionGate, MissionStatus
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.cognitive.authorized_evidence_builder import (
    AUTHORIZED_ORIGIN,
    AuthorizedEvidenceBuilder,
    EvidenceRejected,
)
from core.orchestrator import AvatarOrchestrator

from tests.authority_fixtures import (
    authorized_evidence_for,
    certify_state_engine,
    cleanup,
    make_mission,
    temp_db,
)


class TestAuthorityConsolidation001(unittest.TestCase):
    """
    Boundary tests for the completion gate.

    Rewritten in IMPLEMENTATION 003. Two earlier assertions asserted behaviour that the
    forensic audit identified as a defect, and are now inverted while keeping the adversarial
    case:

      * `test_05` previously built evidence from an arbitrary `COMMAND` fact and expected the
        registry to accept it. A command exit code is not capability evidence (D-6); the test
        now asserts the builder refuses it.
      * `test_06` previously asserted `PARTIAL` for unsigned evidence. The registry now
        reports `NOT_IMPLEMENTED` for a capability with no admitted evidence, which is a
        stronger statement; the essential property (never VERIFIED) is preserved.
    """

    def setUp(self):
        self.db, self.temp_dir = temp_db()
        self.capability_registry = CapabilityEvidenceRegistry(state_db=self.db)
        self.checkpoint_engine = CheckpointEngine(state_db=self.db)
        self.resume_engine = ResumeEngine(state_db=self.db, checkpoint_engine=self.checkpoint_engine)

    def tearDown(self):
        cleanup(self.db, self.temp_dir)

    def test_01_completed_requires_gate_evaluation(self):
        """
        A mission whose required capability is unverified must not reach COMPLETED, and the
        transition API exposes no way to assert a status directly.
        """
        import inspect
        params = list(inspect.signature(self.db.update_mission_status).parameters)
        for removed in ("status", "critical_gaps_with_status", "authorized_by_gate"):
            self.assertNotIn(removed, params)

        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.db.update_mission_status(mission_id)
        self.assertNotEqual(self.db.get_mission(mission_id)["status"], "COMPLETED")

    def test_02_gate_blocks_empty_requirements_when_capabilities_exist(self):
        """
        A mission that declares requirements but persists an empty list is BLOCKED: an empty
        list is a declaration failure, not a licence to skip evaluation.
        """
        gate_res = MissionCompletionGate.evaluate_mission_completion(
            mission_id="test-mission",
            required_capabilities=[],
            requirements_declared=True,
            critical_gaps=0,
            blocking_findings=0,
            capability_registry=self.capability_registry,
            state_db=self.db,
        )
        self.assertFalse(gate_res.can_complete)
        self.assertEqual(gate_res.mission_status, MissionStatus.BLOCKED)

    def test_03_resume_re_evaluates_and_does_not_complete_unverified_mission(self):
        """
        Resume must not confer authority. A mission requiring an unverified capability stays
        unterminated even when every task is VERIFIED.
        """
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.db.create_planner_task(
            task_id="T1", mission_id=mission_id, step_index=1,
            description="Paso 1", tool_name="COMMAND", tool_args={}, status="VERIFIED",
        )
        res_status, _task, _msg = self.resume_engine.evaluate_mission_for_resume(mission_id)
        self.assertEqual(res_status, MissionResumeStatus.ACTIVE_MISSION_COMPLETED)
        self.assertNotIn(self.db.get_mission(mission_id)["status"], ("COMPLETED",))

    def test_03b_resume_completes_only_after_real_capability_evidence(self):
        """The positive counterpart: with genuine evidence, Resume reaches COMPLETED."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        certify_state_engine(self.db, self.capability_registry, mission_id)
        self.db.create_planner_task(
            task_id="T1", mission_id=mission_id, step_index=1,
            description="Paso 1", tool_name="COMMAND", tool_args={}, status="VERIFIED",
        )
        self.resume_engine.evaluate_mission_for_resume(mission_id)
        self.assertEqual(self.db.get_mission(mission_id)["status"], "COMPLETED")

    def test_04_orchestrator_does_not_self_certify(self):
        """
        D-7/D-8: the orchestrator cannot manufacture evidence or name a capability status.

        Two structural properties are asserted, because a runtime fixture here would only
        prove one code path:
          1. the builder no longer exposes a caller-driven `create_evidence`;
          2. the orchestrator never constructs `CapabilityEvidence` directly, and never calls
             a capability-status setter — it can only offer facts to the verifier.
        """
        import inspect

        self.assertFalse(
            hasattr(AuthorizedEvidenceBuilder, "create_evidence"),
            "The caller-driven evidence constructor must be gone.",
        )

        import core.orchestrator as orchestrator_module
        source = inspect.getsource(orchestrator_module)
        self.assertNotIn("CapabilityEvidence(", source)
        self.assertNotIn("set_capability_status", source)
        self.assertNotIn("set_capability_limitation", source)

        # And a generic tool fact still certifies nothing.
        fact = PhysicalFactVerifier.verify_command(
            "echo test", "[Resultado PowerShell (ExitCode: 0)]: test"
        )
        self.assertNotEqual(
            self.capability_registry.get_capability_status("CAP_STATE_ENGINE"),
            CapabilityStatus.VERIFIED,
        )
        self.assertNotEqual(
            self.capability_registry.get_capability_status("CAP_STATE_ENGINE"),
            CapabilityStatus.VERIFIED,
        )

    def test_05_builder_refuses_generic_facts(self):
        """
        D-6: the builder is no longer a function of caller data. A COMMAND fact with exit
        code 0 cannot be turned into evidence for any capability.
        """
        fact = PhysicalFactVerifier.verify_command(
            "echo test", "[Resultado PowerShell (ExitCode: 0)]: test"
        )
        self.assertTrue(fact.verified)
        for capability_id in ("CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY"):
            with self.assertRaises(EvidenceRejected):
                AuthorizedEvidenceBuilder.build_for_capability(
                    capability_id=capability_id,
                    fact=fact,
                    mission_id="test-mission",
                    task_id="test-task",
                    execution_id="test-exec",
                )

    def test_05b_builder_produces_bound_evidence_from_real_verification(self):
        """The positive counterpart: the legitimate chain yields fully bound evidence."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.capability_registry, mission_id)
        self.assertTrue(evidence)
        ev = evidence[0]
        self.assertEqual(ev.mission_id, mission_id)
        self.assertEqual(ev.task_id, "T1")
        self.assertEqual(ev.execution_id, "exec-fixture")
        self.assertEqual(ev.origin, AUTHORIZED_ORIGIN)
        self.assertTrue(ev.is_authentic())
        self.assertEqual(ev.capability_id, "CAP_STATE_ENGINE")

    def test_06_unsigned_evidence_is_rejected(self):
        """
        CapabilityEvidence constructed directly, outside the builder, carries no valid
        signature and is refused. The capability remains unimplemented.
        """
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        ev = CapabilityEvidence(
            evidence_id="ev-unauthorized-001",
            capability_id="CAP_STATE_ENGINE",
            action="test",
            expected="exp",
            actual="act",
            evidence_type=EvidenceType.FILESYSTEM_EVIDENCE,
            physical_evidence=True,
            source="UnauthorizedCaller",
            timestamp="2026-09-27T00:00:00Z",
            verification_result=True,
            verifier="UnauthorizedCaller",
            mission_id=mission_id,
            task_id="test-task",
            execution_id="test-exec",
            verification_id="v1",
            observation_id="o1",
            physical_fact_reference="p1",
            capability_verification_token="t1",
            origin=AUTHORIZED_ORIGIN,
        )
        self.assertFalse(ev.is_authentic())
        status = self.capability_registry.register_evidence(
            "CAP_STATE_ENGINE", ev, mission_id=mission_id
        )
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)
        self.assertEqual(status, CapabilityStatus.NOT_IMPLEMENTED)


if __name__ == "__main__":
    unittest.main()
