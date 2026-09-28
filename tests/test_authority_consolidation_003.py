import unittest
import os
import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cognitive.capability_registry import (
    CapabilityEvidenceRegistry,
    CapabilityEvidence,
    EvidenceType,
    CapabilityStatus,
)
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.cognitive.capability_specific_verifier import (
    CapabilitySpecificVerifier,
    VerificationRejection,
)
from core.cognitive.authorized_evidence_builder import (
    AUTHORIZED_ORIGIN,
    AuthorizedEvidenceBuilder,
    EvidenceRejected,
)
from core.cognitive.claim_validator import ClaimValidator

from tests.authority_fixtures import (
    authorized_evidence_for,
    certify_state_engine,
    cleanup,
    make_mission,
    sqlite_fact,
    temp_db,
)

MISSION_ID = "test-mission-003"
TASK_ID = "test-task-003"
EXECUTION_ID = "test-exec-003"
VERIFICATION_ID = "test-verif-003"


class TestAuthorityConsolidation003(unittest.TestCase):
    """
    Adversarial authority suite.

    REWRITTEN IN IMPLEMENTATION 003 — four tests previously asserted behaviour that the
    forensic audit identified as the D-6 defect, and are now inverted (the adversarial case
    is kept, the vulnerable expectation is gone):

      * test_B / test_C / test_F asserted that a synthetic file, a mock dict and an
        unrelated source file all produced `verified=True` via `verify_capability_operation`.
        That function accepted `bool(data)` as proof. It no longer exists, and each of those
        artifacts is now asserted to verify nothing.
      * test_J asserted that two hand-built evidence objects promoted
        CAP_DESKTOP_VISION to VERIFIED. Unsigned evidence is inadmissible, so the capability
        stays unimplemented; the positive case moves to a capability with a real
        capability-specific verifier.

    Hand-building `CapabilityEvidence` and expecting admission is no longer a valid test
    pattern anywhere in this file: such evidence is unsigned and always refused.
    """

    def setUp(self):
        self.db, self.temp_dir = temp_db()
        self.registry = CapabilityEvidenceRegistry(state_db=self.db)
        self.mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])

    def tearDown(self):
        cleanup(self.db, self.temp_dir)

    # ------------------------------------------------------------------
    def test_A_fake_physical_flag_rejected(self):
        """Self-declared physical_evidence=True without binding is refused."""
        ev = CapabilityEvidence(
            evidence_id="ev-fake-001",
            capability_id="CAP_WHATSAPP_AUTO_REPLY",
            action="fake_send", expected="sent", actual="fake_sent",
            evidence_type=EvidenceType.COMMUNICATION_EVIDENCE,
            physical_evidence=True, source="AdversarialTest",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True, verifier="SelfDeclaredCaller",
        )
        status = self.registry.register_evidence(
            "CAP_WHATSAPP_AUTO_REPLY", ev, mission_id=self.mission_id
        )
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_B_synthetic_file_verifies_nothing(self):
        """
        INVERTED. A synthetic file on disk is not capability evidence. Previously this test
        asserted `verify_capability_operation(...)` returned verified=True for it.
        """
        syn_file = os.path.join(self.temp_dir, "synthetic_screen.png")
        with open(syn_file, "wb") as f:
            f.write(b"SYNTHETIC_IMAGE_BYTES")
        fact = PhysicalFactVerifier.verify_write_file(syn_file)
        self.assertTrue(fact.verified, "the file genuinely exists; that is all that is proven")
        for cap in ("CAP_DESKTOP_VISION", "CAP_WHATSAPP_AUTO_REPLY", "CAP_STATE_ENGINE"):
            self.assertFalse(CapabilitySpecificVerifier.verify(cap, fact).verified)
        with self.assertRaises(EvidenceRejected):
            AuthorizedEvidenceBuilder.build_for_capability(
                "CAP_DESKTOP_VISION", fact, self.mission_id, TASK_ID, EXECUTION_ID
            )

    def test_C_mock_observation_verifies_nothing(self):
        """
        INVERTED. A mock dict is not an observation at all; there is no longer a code path
        that treats `bool(data)` as proof of a capability operation.
        """
        self.assertFalse(
            hasattr(PhysicalFactVerifier, "verify_capability_operation"),
            "The bool(data)-based capability verifier must be gone.",
        )
        mock_observation = {"window_title": "Fake Window", "ocr_text": "Fake Content"}
        self.assertTrue(bool(mock_observation), "the dict is truthy, which proves nothing")

    def test_D_llm_claim(self):
        """An LLM declaring a capability VERIFIED and the mission COMPLETED changes nothing."""
        res = ClaimValidator.validate_llm_claims(
            llm_text="CAPABILITY_WHATSAPP = VERIFIED. MISSION_STATUS = COMPLETED",
            verified_facts=[],
            capability_registry=self.registry,
            critical_gaps=1,
            state_db=self.db,
            mission_id=self.mission_id,
        )
        self.assertGreaterEqual(len(res.unverified_claims), 2)
        self.assertIn("AFIRMACIÓN DE CAPACIDAD DEGRADADA", res.sanitized_text)

    def test_E_tool_success(self):
        """A successful tool result with no physical evidence does not certify anything."""
        self.assertEqual(
            self.registry.get_capability_status("CAP_PLAYWRIGHT_BROWSER"),
            CapabilityStatus.NOT_IMPLEMENTED,
        )

    def test_F_existing_irrelevant_artifact_verifies_nothing(self):
        """
        INVERTED. An unrelated pre-existing source file is not evidence for any capability.
        Previously this test asserted it produced verified=True.
        """
        fact = PhysicalFactVerifier.verify_write_file(__file__)
        self.assertTrue(fact.verified)
        result = CapabilitySpecificVerifier.verify("CAP_WHATSAPP_AUTO_REPLY", fact)
        self.assertFalse(result.verified)
        self.assertIn(result.reason, (
            VerificationRejection.REASON_FACT_TYPE_NOT_ALLOWED,
            VerificationRejection.REASON_SUBJECT_MISMATCH,
            VerificationRejection.REASON_NO_VERIFIER,
        ))

    def test_G_wrong_capability(self):
        """Evidence for CAP_STATE_ENGINE must not certify CAP_WHATSAPP_AUTO_REPLY."""
        fact = sqlite_fact(self.db)
        self.assertTrue(fact.verified)
        for ev in authorized_evidence_for(self.db, self.registry, self.mission_id):
            self.registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=self.mission_id)
        self.assertEqual(
            self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=self.mission_id),
            CapabilityStatus.VERIFIED,
        )
        self.assertEqual(
            self.registry.get_capability_status("CAP_WHATSAPP_AUTO_REPLY"),
            CapabilityStatus.NOT_IMPLEMENTED,
        )

    def test_H_wrong_evidence_type(self):
        """An evidence type the capability does not require is refused."""
        ev = CapabilityEvidence(
            evidence_id="ev-wrong-type-001", capability_id="CAP_DESKTOP_VISION",
            action="file_save", expected="file_exists", actual="file_exists",
            evidence_type=EvidenceType.FILESYSTEM_EVIDENCE, physical_evidence=True,
            source="FileTool", timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True, verifier="PhysicalFactVerifier",
            mission_id=self.mission_id, task_id=TASK_ID, execution_id=EXECUTION_ID,
            verification_id=VERIFICATION_ID, origin=AUTHORIZED_ORIGIN,
        )
        status = self.registry.register_evidence(
            "CAP_DESKTOP_VISION", ev, mission_id=self.mission_id
        )
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_I_missing_required_evidence(self):
        """One of two required evidence types yields PARTIAL, not VERIFIED."""
        ev = CapabilityEvidence(
            evidence_id="ev-scr-001", capability_id="CAP_DESKTOP_VISION",
            action="screen_shot", expected="shot", actual="shot",
            evidence_type=EvidenceType.SCREEN_EVIDENCE, physical_evidence=True,
            source="ScreenTool", timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True, verifier="PhysicalFactVerifier",
            mission_id=self.mission_id, task_id=TASK_ID, execution_id=EXECUTION_ID,
            verification_id=VERIFICATION_ID, origin=AUTHORIZED_ORIGIN,
        )
        status = self.registry.register_evidence(
            "CAP_DESKTOP_VISION", ev, mission_id=self.mission_id
        )
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_J_complete_required_evidence_still_cannot_verify(self):
        """
        INVERTED. Complete, correctly-typed, correctly-bound evidence still cannot promote a
        capability, because it is unsigned and the capability has no capability-specific
        verifier. Previously this test asserted VERIFIED.
        """
        for evidence_id, evidence_type in (
            ("ev-scr-002", EvidenceType.SCREEN_EVIDENCE),
            ("ev-win-002", EvidenceType.WINDOW_EVIDENCE),
        ):
            ev = CapabilityEvidence(
                evidence_id=evidence_id, capability_id="CAP_DESKTOP_VISION",
                action="observe", expected="exp", actual="act",
                evidence_type=evidence_type, physical_evidence=True,
                source="VisionTool",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                verification_result=True, verifier="PhysicalFactVerifier",
                mission_id=self.mission_id, task_id=TASK_ID, execution_id=EXECUTION_ID,
                verification_id=VERIFICATION_ID, observation_id=f"obs-{evidence_id}",
                physical_fact_reference=f"pf-{evidence_id}",
                capability_verification_token=f"tok-{evidence_id}",
                origin=AUTHORIZED_ORIGIN,
            )
            self.assertFalse(ev.is_authentic())
            status = self.registry.register_evidence(
                "CAP_DESKTOP_VISION", ev, mission_id=self.mission_id
            )
            self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_J2_real_complete_evidence_verifies(self):
        """The positive counterpart, over the genuine verification chain."""
        self.assertEqual(
            certify_state_engine(self.db, self.registry, self.mission_id),
            CapabilityStatus.VERIFIED,
        )

    def test_K_evidence_replay(self):
        """Re-registering the same evidence_id must not duplicate the entry."""
        evidence = authorized_evidence_for(self.db, self.registry, self.mission_id)
        ev = evidence[0]
        self.registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=self.mission_id)
        self.registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=self.mission_id)
        rec = self.db.get_capability_record("CAP_STATE_ENGINE")
        ids = [item.get("id") for item in rec["evidence_ids"] if isinstance(item, dict)]
        self.assertEqual(ids.count(ev.evidence_id), 1)

    def test_L_evidence_substitution_fixed(self):
        """CapabilityEvidence carries mission and task binding."""
        ev = CapabilityEvidence(
            evidence_id="ev-sub-001", capability_id="CAP_STATE_ENGINE",
            action="action", expected="exp", actual="act",
            evidence_type=EvidenceType.DATABASE_EVIDENCE, physical_evidence=True,
            source="Src", timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True, verifier="PhysicalFactVerifier",
            mission_id=MISSION_ID, task_id=TASK_ID, execution_id=EXECUTION_ID,
            verification_id=VERIFICATION_ID,
        )
        self.assertEqual(ev.mission_id, MISSION_ID)
        self.assertEqual(ev.task_id, TASK_ID)

    def test_M_origin_loss(self):
        """Provenance metadata is preserved on the evidence object."""
        ev = CapabilityEvidence(
            evidence_id="ev-origin-001", capability_id="CAP_STATE_ENGINE",
            action="test_action", expected="exp", actual="act",
            evidence_type=EvidenceType.FILESYSTEM_EVIDENCE, physical_evidence=True,
            source="OriginTool", timestamp="2026-09-27T21:00:00Z",
            verification_result=True, verifier="VerifierX",
            mission_id=MISSION_ID, task_id=TASK_ID, execution_id=EXECUTION_ID,
            verification_id=VERIFICATION_ID, origin=AUTHORIZED_ORIGIN,
        )
        self.assertEqual(ev.source, "OriginTool")
        self.assertEqual(ev.verifier, "VerifierX")
        self.assertEqual(ev.timestamp, "2026-09-27T21:00:00Z")
        self.assertEqual(ev.origin, AUTHORIZED_ORIGIN)

    def test_N_unauthorized_evidence_without_origin_is_rejected(self):
        """Evidence with the default UNKNOWN origin is refused."""
        ev = CapabilityEvidence(
            evidence_id="ev-no-origin-001", capability_id="CAP_STATE_ENGINE",
            action="test", expected="exp", actual="act",
            evidence_type=EvidenceType.DATABASE_EVIDENCE, physical_evidence=True,
            source="UnknownSource",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True, verifier="UnknownVerifier",
            mission_id=self.mission_id,
        )
        status = self.registry.register_evidence(
            "CAP_STATE_ENGINE", ev, mission_id=self.mission_id
        )
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_O_evidence_without_mission_id_is_rejected(self):
        """Evidence with no mission binding is refused."""
        ev = CapabilityEvidence(
            evidence_id="ev-no-mission-001", capability_id="CAP_STATE_ENGINE",
            action="test", expected="exp", actual="act",
            evidence_type=EvidenceType.DATABASE_EVIDENCE, physical_evidence=True,
            source="Test", timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True, verifier="PhysicalFactVerifier",
            task_id=TASK_ID, execution_id=EXECUTION_ID, verification_id=VERIFICATION_ID,
            origin=AUTHORIZED_ORIGIN,
        )
        status = self.registry.register_evidence("CAP_STATE_ENGINE", ev)
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)


if __name__ == "__main__":
    unittest.main()
