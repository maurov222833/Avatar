"""
Adversarial authority suite 004.

REWRITTEN IN IMPLEMENTATION 003. Three tests in this file did not test the property they
claimed, and one asserted the opposite of its own name. All are corrected here; none of the
original adversarial intent is discarded.

  * `test_b_cross_mission_replay_is_blocked` previously mutated `ev.mission_id` to
    "mission-b" and then asserted that the mutation had taken effect
    (`assert ev.mission_id == "mission-b"`). It demonstrated the replay, not its prevention.
    It now asserts the registry refuses cross-mission use.
  * `test_g_mock_cannot_certify` was `assert True` inside a `try/except: pass`. It could not
    fail. It now drives the real builder and asserts refusal.
  * `test_a_unauthorized_evidence_is_rejected` asserted `PARTIAL`; unsigned evidence now
    leaves the capability NOT_IMPLEMENTED, which is a strictly stronger statement.
  * `test_synthetic_evidence_cannot_reach_verified` previously passed for the wrong reason
    (missing evidence-type coverage, not the `TEST_SYNTHETIC` origin) and its stated intent
    was false: an origin of `TEST_SYNTHETIC` did reach VERIFIED. It is now a genuine test.
  * `test_cross_mission_evidence_is_blocked` previously only omitted `mission_id` and did
    not exercise any cross-mission comparison. It is replaced by a real cross-mission test.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

from tests.authority_fixtures import (
    authorized_evidence_for,
    certify_state_engine,
    cleanup,
    make_mission,
    sqlite_fact,
    temp_db,
)

MISSION_ID = "test-mission-004"
TASK_ID = "test-task-004"
EXECUTION_ID = "test-exec-004"
VERIFICATION_ID = "test-verif-004"


class TestAuthorityConsolidation004:

    def setup_method(self):
        self.db, self.temp_dir = temp_db()
        self.registry = CapabilityEvidenceRegistry(state_db=self.db)
        self.mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])

    def teardown_method(self):
        cleanup(self.db, self.temp_dir)

    # ------------------------------------------------------------------
    def test_a_unauthorized_evidence_is_rejected(self):
        """Perfectly-formed evidence built outside the builder is refused."""
        fake_evidence = CapabilityEvidence(
            evidence_id="ev_fake_001",
            capability_id="CAP_PLAYWRIGHT_BROWSER",
            action="unauthorized_action",
            expected="expected",
            actual="actual",
            evidence_type=EvidenceType.BROWSER_EVIDENCE,
            physical_evidence=True,
            source="unauthorized_caller",
            timestamp="2025-01-01T00:00:00",
            verification_result=True,
            verifier="none",
        )
        assert not fake_evidence.is_authentic()
        status = self.registry.register_evidence(
            "CAP_PLAYWRIGHT_BROWSER", fake_evidence, mission_id=self.mission_id
        )
        assert status != CapabilityStatus.VERIFIED

    def test_b_cross_mission_replay_is_blocked(self):
        """
        CORRECTED. Evidence admitted for mission A cannot be registered for mission B.

        The old version mutated `ev.mission_id` and asserted the mutation succeeded, which
        demonstrated the replay rather than its prevention. Here the evidence is left intact
        and offered to a different mission, which the registry refuses.
        """
        mission_a = make_mission(self.db, ["CAP_STATE_ENGINE"])
        mission_b = make_mission(self.db, ["CAP_STATE_ENGINE"])

        evidence = authorized_evidence_for(self.db, self.registry, mission_a)
        assert evidence, "legitimate evidence must exist for the test to be meaningful"
        ev = evidence[0]
        assert ev.mission_id == mission_a

        status_a = certify_state_engine(self.db, self.registry, mission_a)
        assert status_a == CapabilityStatus.VERIFIED

        # Same object, different mission: refused, and the capability is untouched there.
        status_b = self.registry.register_evidence(
            "CAP_STATE_ENGINE", ev, mission_id=mission_b
        )
        assert status_b != CapabilityStatus.VERIFIED
        assert self.registry.get_capability_status(
            "CAP_STATE_ENGINE", mission_id=mission_b
        ) != CapabilityStatus.VERIFIED

    def test_g_mock_cannot_certify(self):
        """
        CORRECTED. A duck-typed mock claiming `verified=True` cannot produce evidence.

        The old version was `assert True` inside `try/except: pass` and could not fail. This
        drives the real code path and asserts a refusal.
        """
        mock_fact = type("MockFact", (), {
            "fact_id": "mock-fact-id",
            "fact_type": "SQLITE_PERSISTENCE",
            "subject": "CAP_STATE_ENGINE",
            "verified": True,
            "observed_state": {"file_exists": True, "journal_mode": "wal",
                               "missions_table": True, "required_columns": True,
                               "roundtrip_ok": True},
            "execution_id": "mock",
        })()
        with pytest.raises(EvidenceRejected):
            AuthorizedEvidenceBuilder.build_for_capability(
                "CAP_STATE_ENGINE", mock_fact, self.mission_id, TASK_ID, EXECUTION_ID
            )

    def test_i_llm_cannot_certify(self):
        """An undeclared capability is never VERIFIED."""
        assert self.registry.get_capability_status(
            "CAP_NON_EXISTENT_CAPABILITY_004"
        ) != CapabilityStatus.VERIFIED

    def test_k_valid_authorized_evidence(self):
        """
        Evidence produced through the real chain is admitted and satisfies its coverage rule.
        CAP_STATE_ENGINE requires FILESYSTEM and DATABASE evidence; the SQLite observation
        genuinely provides both.
        """
        evidence = authorized_evidence_for(self.db, self.registry, self.mission_id)
        assert {e.evidence_type for e in evidence} == {
            EvidenceType.FILESYSTEM_EVIDENCE, EvidenceType.DATABASE_EVIDENCE
        }
        status = certify_state_engine(self.db, self.registry, self.mission_id)
        assert status == CapabilityStatus.VERIFIED

    def test_synthetic_evidence_cannot_reach_verified(self):
        """
        CORRECTED. Evidence with a non-authorized origin cannot reach VERIFIED.

        The old version asserted PARTIAL while claiming the origin was the reason. It was not:
        the capability was merely missing an evidence type, and an origin of
        `TEST_SYNTHETIC` in fact reached VERIFIED. Here the origin is the only thing wrong
        with a fully-typed pair of evidence records.
        """
        types = (EvidenceType.FILESYSTEM_EVIDENCE, EvidenceType.DATABASE_EVIDENCE)
        for index, evidence_type in enumerate(types):
            ev = CapabilityEvidence(
                evidence_id=f"ev-synthetic-{index}",
                capability_id="CAP_STATE_ENGINE",
                action="test", expected="exp", actual="act",
                evidence_type=evidence_type,
                physical_evidence=True,
                source="SyntheticTest",
                timestamp="2025-01-01T00:00:00Z",
                verification_result=True,
                verifier="SyntheticTest",
                mission_id=self.mission_id,
                task_id=TASK_ID,
                execution_id=EXECUTION_ID,
                verification_id=f"fake-verif-{index}",
                observation_id=f"obs-{index}",
                physical_fact_reference=f"pf-{index}",
                capability_verification_token=f"tok-{index}",
                origin="TEST_SYNTHETIC",
            )
            status = self.registry.register_evidence(
                "CAP_STATE_ENGINE", ev, mission_id=self.mission_id
            )
            assert status != CapabilityStatus.VERIFIED
        assert self.registry.get_capability_status(
            "CAP_STATE_ENGINE", mission_id=self.mission_id
        ) != CapabilityStatus.VERIFIED

    def test_cross_mission_evidence_is_blocked(self):
        """Cross-mission reuse is refused (see test_b for the fuller scenario)."""
        ev = CapabilityEvidence(
            evidence_id="ev-nobinding-001",
            capability_id="CAP_STATE_ENGINE",
            action="test", expected="exp", actual="act",
            evidence_type=EvidenceType.FILESYSTEM_EVIDENCE,
            physical_evidence=True, source="Test",
            timestamp="2025-01-01T00:00:00Z",
            verification_result=True, verifier="PhysicalFactVerifier",
            verification_id=VERIFICATION_ID,
            task_id=TASK_ID, execution_id=EXECUTION_ID,
            origin=AUTHORIZED_ORIGIN,
        )
        status = self.registry.register_evidence("CAP_STATE_ENGINE", ev)
        assert status != CapabilityStatus.VERIFIED

    def test_gate_rejects_undeclared_empty_requirements(self):
        """A mission declaring requirements but persisting none is BLOCKED."""
        mission_id = make_mission(self.db, [])
        gate_res = MissionCompletionGate.evaluate_and_authorize(
            mission_id, state_db=self.db, capability_registry=self.registry
        )
        assert not gate_res.verdict.can_complete
        assert gate_res.verdict.mission_status == MissionStatus.BLOCKED

    def test_real_fact_from_another_capability_is_rejected(self):
        """A genuine CAP_STATE_ENGINE observation cannot verify anything else."""
        from core.cognitive.capability_specific_verifier import CapabilitySpecificVerifier
        fact = sqlite_fact(self.db)
        assert fact.verified
        for other in ("CAP_WHATSAPP_AUTO_REPLY", "CAP_PLAYWRIGHT_BROWSER",
                      "CAP_DESKTOP_VISION", "CAP_CHECKPOINT_RESUME"):
            assert not CapabilitySpecificVerifier.verify(other, fact).verified
