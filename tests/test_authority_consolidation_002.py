import unittest
import os
import shutil
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.checkpoint_engine import CheckpointEngine
from core.cognitive.capability_registry import (
    CapabilityEvidenceRegistry,
    CapabilityEvidence,
    EvidenceType,
    CapabilityStatus,
)
from core.cognitive.mission_completion_gate import MissionCompletionGate, MissionStatus
from core.cognitive.authorized_evidence_builder import AUTHORIZED_ORIGIN

from tests.authority_fixtures import (
    authorized_evidence_for,
    certify_state_engine,
    cleanup,
    make_mission,
    temp_db,
)

MISSION_ID = "test-mission-001"
TASK_ID = "test-task-001"
EXECUTION_ID = "test-exec-001"
VERIFICATION_ID = "test-verif-001"


class TestAuthorityConsolidation002(unittest.TestCase):
    """
    Suite that demonstrates, quantitatively:

        TOOL SUCCESS != PHYSICAL EVIDENCE != CAPABILITY VERIFIED != MISSION COMPLETED

    Rewritten in IMPLEMENTATION 003. `test_03` previously hand-built two
    `CapabilityEvidence` objects and asserted they promoted CAP_WHATSAPP_AUTO_REPLY to
    VERIFIED. That is precisely the D-6/D-8 defect: a caller could name the capability and
    the evidence types. The capability has no capability-specific verifier, so it can no
    longer be verified at all, and the adversarial case is preserved as `test_03b`.
    """

    def setUp(self):
        self.db, self.temp_dir = temp_db()
        self.registry = CapabilityEvidenceRegistry(state_db=self.db)

    def tearDown(self):
        cleanup(self.db, self.temp_dir)

    def test_01_evidence_without_binding_is_rejected(self):
        """Evidence with no binding is refused and cannot produce VERIFIED."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        ev = CapabilityEvidence(
            evidence_id="ev-wa-comm-01",
            capability_id="CAP_WHATSAPP_AUTO_REPLY",
            action="send_reply",
            expected="Message sent",
            actual="Message sent successfully",
            evidence_type=EvidenceType.COMMUNICATION_EVIDENCE,
            physical_evidence=True,
            source="WhatsAppAutoReply",
            timestamp="2026-09-27T00:00:00Z",
            verification_result=True,
            verifier="PhysicalFactVerifier",
        )
        status = self.registry.register_evidence("CAP_WHATSAPP_AUTO_REPLY", ev, mission_id=mission_id)
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_02_non_physical_evidence_yields_not_verified(self):
        """A test stub with physical_evidence=False is refused."""
        mission_id = make_mission(self.db, ["CAP_PLAYWRIGHT_BROWSER"])
        ev = CapabilityEvidence(
            evidence_id="ev-stub-01",
            capability_id="CAP_PLAYWRIGHT_BROWSER",
            action="launch_mock",
            expected="Mock OK",
            actual="Mock OK",
            evidence_type=EvidenceType.BROWSER_EVIDENCE,
            physical_evidence=False,
            source="UnitTest",
            timestamp="2026-09-27T00:00:00Z",
            verification_result=True,
            verifier="UnitTest",
            mission_id=mission_id,
            task_id=TASK_ID,
            execution_id=EXECUTION_ID,
            verification_id=VERIFICATION_ID,
            origin="TEST_SYNTHETIC",
        )
        status = self.registry.register_evidence("CAP_PLAYWRIGHT_BROWSER", ev, mission_id=mission_id)
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_03b_hand_built_evidence_cannot_promote_to_verified(self):
        """
        The inverted form of the old test_03. Complete, correctly-bound-looking evidence
        still cannot promote a capability, because it is unsigned and the capability has no
        capability-specific verifier.
        """
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        for suffix, evidence_type in (
            ("comm", EvidenceType.COMMUNICATION_EVIDENCE),
            ("net", EvidenceType.NETWORK_EVIDENCE),
        ):
            ev = CapabilityEvidence(
                evidence_id=f"ev-wa-{suffix}-02",
                capability_id="CAP_WHATSAPP_AUTO_REPLY",
                action="send_reply",
                expected="Message sent",
                actual="Message sent successfully",
                evidence_type=evidence_type,
                physical_evidence=True,
                source="WhatsAppAutoReply",
                timestamp="2026-09-27T00:00:00Z",
                verification_result=True,
                verifier="PhysicalFactVerifier",
                mission_id=mission_id,
                task_id=TASK_ID,
                execution_id=EXECUTION_ID,
                verification_id=VERIFICATION_ID,
                observation_id=f"obs-{suffix}",
                physical_fact_reference=f"pf-{suffix}",
                capability_verification_token=f"tok-{suffix}",
                origin=AUTHORIZED_ORIGIN,
            )
            self.assertFalse(ev.is_authentic())
            status = self.registry.register_evidence(
                "CAP_WHATSAPP_AUTO_REPLY", ev, mission_id=mission_id
            )
            self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_03c_real_evidence_promotes_to_verified(self):
        """
        The positive counterpart. Complete coverage of genuinely verified, capability-scoped
        evidence does produce VERIFIED — for that mission.
        """
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        self.assertEqual(certify_state_engine(self.db, self.registry, mission_id),
                         CapabilityStatus.VERIFIED)

    def test_04_mission_completion_gate_blocks_when_capability_is_unverified(self):
        """The gate denies completion while a required capability is not VERIFIED."""
        mission_id = make_mission(self.db, ["CAP_PLAYWRIGHT_BROWSER"])
        gate_res = MissionCompletionGate.evaluate_and_authorize(
            mission_id, state_db=self.db, capability_registry=self.registry
        )
        self.assertFalse(gate_res.verdict.can_complete)
        self.assertIn(
            "CAP_PLAYWRIGHT_BROWSER",
            gate_res.verdict.unverified_required_capabilities[0]
            if gate_res.verdict.unverified_required_capabilities else "",
        )

    def test_04b_mission_cannot_complete_while_a_required_capability_is_partial(self):
        """A25: requirements X,Y with evidence only for X must not complete."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY"])
        certify_state_engine(self.db, self.registry, mission_id)
        result = self.db.update_mission_status(mission_id)
        self.assertNotEqual(result, "COMPLETED")
        self.assertEqual(result, "PARTIALLY_COMPLETED")


if __name__ == "__main__":
    unittest.main()
