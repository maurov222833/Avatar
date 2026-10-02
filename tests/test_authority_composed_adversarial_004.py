"""
COMPOSED ADVERSARIAL SUITE — AUTHORITY CONSOLIDATION 004 (D-10).

These tests attack the pipeline as a chain rather than one control at a time, which is how
the IMPLEMENTATION 003 suite was defeated: it proved each control worked in isolation while
never composing "replace the verifier" with "construct a fact".

Every test asserts the PERSISTED STATE, not merely a return value, and each must fail if the
attack succeeds. Group F contains real-observation positive tests; the synthetic-infrastructure
tests are confined to groups A–E and are labelled as such.
"""
from __future__ import annotations

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.cognitive import _authority, capability_definitions as capdefs
from core.cognitive.authority_core import LEDGER, AuthorityAudit
from core.cognitive.authorized_evidence_builder import (
    AUTHORIZED_ORIGIN,
    AuthorizedEvidenceBuilder,
    CapabilityEvidence,
    EvidenceRejected,
)
from core.cognitive.capability_definitions import (
    CapabilityDefinition,
    EvidenceType,
    SQLITE_PERSISTENCE_FACT,
)
from core.cognitive.capability_registry import (
    CapabilityEvidenceRegistry,
    CapabilityStatus,
)
from core.cognitive.capability_specific_verifier import CapabilitySpecificVerifier
from core.cognitive.physical_fact_verifier import (
    PhysicalFactVerifier,
    VerifiedPhysicalFact,
)
from core.cognitive.mission_completion_gate import MissionCompletionGate
from core.resume_engine import ResumeEngine

from tests.authority_fixtures import (
    authorized_evidence_for,
    certify_state_engine,
    cleanup,
    make_mission,
    sqlite_fact,
    temp_db,
)

TERMINAL_COMPLETE = ("COMPLETED",)
FABRICATED_SQLITE_STATE = {
    "file_exists": True, "journal_mode": "wal", "missions_table": True,
    "required_columns": True, "roundtrip_ok": True,
}


class ComposedBase(unittest.TestCase):
    def setUp(self):
        self.db, self.temp_dir = temp_db()
        self.registry = CapabilityEvidenceRegistry(state_db=self.db)
        AuthorityAudit.clear()

    def tearDown(self):
        cleanup(self.db, self.temp_dir)

    def persisted(self, mission_id):
        return self.db.get_mission(mission_id)["status"]

    def real_file_fact(self, name="artifact.txt", content="payload"):
        path = os.path.join(self.temp_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return PhysicalFactVerifier.verify_write_file(path, content)


# ======================================================================
# GROUP A — verifier registry
# ======================================================================
class TestGroupAVerifiers(ComposedBase):

    def test_A1_duplicate_trusted_verifier_id_is_refused(self):
        """A1: registering a verifier under a trusted id fails."""
        with self.assertRaises(PermissionError):
            CapabilitySpecificVerifier.register_verifier(
                "CAP_STATE_ENGINE", "sqlite_persistence",
                lambda f, d: (tuple(d.required_evidence_types), "attacker"))
        self.assertNotIn(
            ("CAP_STATE_ENGINE", "sqlite_persistence"),
            {k for k in CapabilitySpecificVerifier._REGISTRY
             if CapabilitySpecificVerifier._REGISTRY[k].__module__.startswith("__main__")},
        )

    def test_A2_trusted_verifier_cannot_be_replaced_after_bootstrap(self):
        """A2: the trusted verifier is still the built-in, resource-bound one."""
        builtin = CapabilitySpecificVerifier._REGISTRY[("CAP_STATE_ENGINE", "sqlite_persistence")]
        self.assertEqual(builtin.__name__, "_verify_sqlite_persistence_bound")
        # And it is resource-bound, so it cannot certify a foreign database.
        self.assertIn("expected_resource", str(__import__("inspect").signature(builtin)))

    def test_A3_extension_verifier_refused_for_protected_capability(self):
        """A3: an extension verifier cannot be attached to a protected capability."""
        for cap in ("CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY", "CAP_PLAYWRIGHT_BROWSER"):
            with self.assertRaises(PermissionError):
                CapabilitySpecificVerifier.register_verifier(
                    cap, "attacker_verifier", lambda f, d: (tuple(d.required_evidence_types), "x"))

    def test_A4_verifier_returning_all_types_without_inspection_cannot_certify(self):
        """
        A4: even if a verifier could be attached to an extension capability and claimed every
        required type, a fabricated fact still cannot reach it, because provenance is checked
        before the verifier runs.
        """
        subject = self.real_file_fact("a4.txt", "a4").subject
        capdefs.register_definition(CapabilityDefinition(
            capability_id=subject, capability_name="A4 probe",
            required_evidence_types=(EvidenceType.FILESYSTEM_EVIDENCE,),
            required_tests=(), physical_verification_required=True,
            verifiable_by_fact_types=("WRITE_FILE",), verifier_id="greedy"))
        CapabilitySpecificVerifier.register_verifier(
            subject, "greedy", lambda f, d: (tuple(d.required_evidence_types), "no inspection"))

        fabricated = VerifiedPhysicalFact(
            fact_id="a4", fact_type="WRITE_FILE", subject=subject, verified=True,
            observed_state={"size_bytes": 999}, execution_id="e")
        result = CapabilitySpecificVerifier.verify(subject, fabricated)
        self.assertFalse(result.verified)
        self.assertEqual(result.reason, "OBSERVATION_NOT_IN_LEDGER")

    def test_A6_verifier_configuration_is_stable_during_an_active_mission(self):
        """A6: repeated attempts during a live mission never change the trusted mapping."""
        before = dict(CapabilitySpecificVerifier._REGISTRY)
        mission = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        for _ in range(3):
            with self.assertRaises(PermissionError):
                CapabilitySpecificVerifier.register_verifier(
                    "CAP_STATE_ENGINE", "sqlite_persistence", lambda f, d: ((), "x"))
        self.assertEqual(dict(CapabilitySpecificVerifier._REGISTRY), before)
        self.assertNotEqual(self.persisted(mission), "COMPLETED")


# ======================================================================
# GROUP B — physical facts
# ======================================================================
class TestGroupBPhysicalFacts(ComposedBase):

    def test_B1_hand_built_fact_cannot_certify(self):
        """B1: a hand-built VerifiedPhysicalFact has no ledger sequence."""
        fact = VerifiedPhysicalFact(
            fact_id="b1", fact_type=SQLITE_PERSISTENCE_FACT, subject="CAP_STATE_ENGINE",
            verified=True, observed_state=dict(FABRICATED_SQLITE_STATE), execution_id="e")
        self.assertEqual(fact.observation_sequence, 0)
        self.assertFalse(CapabilitySpecificVerifier.verify("CAP_STATE_ENGINE", fact).verified)

    def test_B2_forged_observed_state_is_refused(self):
        """B2: a real observation whose payload is edited is refused."""
        real = sqlite_fact(self.db)
        self.assertTrue(real.verified)
        tampered = dataclasses.replace(real, observed_state=dict(FABRICATED_SQLITE_STATE))
        result = CapabilitySpecificVerifier.verify("CAP_STATE_ENGINE", tampered)
        self.assertFalse(result.verified)
        self.assertEqual(result.reason, "OBSERVATION_STATE_MISMATCH")

    def test_B3_real_fact_repointed_to_another_capability_is_refused(self):
        """B3: changing the subject of a real fact is caught by the ledger."""
        real = sqlite_fact(self.db)
        repointed = dataclasses.replace(real, subject="CAP_WHATSAPP_AUTO_REPLY")
        self.assertFalse(CapabilitySpecificVerifier.verify(
            "CAP_WHATSAPP_AUTO_REPLY", repointed).verified)

    def test_B5_fact_from_another_execution_cannot_be_reused(self):
        """B5: one observation binds to one (mission, execution) pair."""
        fact = sqlite_fact(self.db)
        m1 = make_mission(self.db, [])
        AuthorizedEvidenceBuilder.build_for_capability(
            "CAP_STATE_ENGINE", fact, m1, "T1", "exec-A",
            expected_resource=self.db.db_path)
        with self.assertRaises(EvidenceRejected):
            AuthorizedEvidenceBuilder.build_for_capability(
                "CAP_STATE_ENGINE", fact, m1, "T1", "exec-B",
                expected_resource=self.db.db_path)

    def test_B6_llm_text_cannot_become_a_physical_fact(self):
        """B6: there is no path from text to a ledger-backed fact."""
        fact = PhysicalFactVerifier.verify_command("echo verified", "[Resultado PowerShell (ExitCode: 0)]:")
        self.assertEqual(fact.fact_type, "COMMAND")
        for cap in ("CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY"):
            self.assertFalse(CapabilitySpecificVerifier.verify(cap, fact).verified)

    def test_B8_observation_ledger_cannot_be_appended_to_by_a_caller(self):
        """B8: the ledger rejects any append that does not carry the observer token."""
        with self.assertRaises(PermissionError):
            LEDGER.record(
                object(), fact_type="WRITE_FILE", subject="x", verified=True,
                observed_state={}, execution_id="e", observer="attacker")

    def test_every_real_fact_carries_a_ledger_sequence(self):
        """Positive: the authorized observer records what it observes."""
        for fact in (self.real_file_fact("p1.txt", "p1"),
                     PhysicalFactVerifier.verify_sqlite_persistence(self.db.db_path)):
            self.assertGreater(fact.observation_sequence, 0)
            self.assertIsNotNone(LEDGER.get(fact.observation_sequence))


# ======================================================================
# GROUP C — evidence
# ======================================================================
class TestGroupCEvidence(ComposedBase):

    def test_C1_builder_is_not_a_signing_oracle(self):
        """C1: the legitimate builder refuses a fabricated fact."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        fabricated = VerifiedPhysicalFact(
            fact_id="c1", fact_type=SQLITE_PERSISTENCE_FACT, subject="CAP_STATE_ENGINE",
            verified=True, observed_state=dict(FABRICATED_SQLITE_STATE), execution_id="e")
        with self.assertRaises(EvidenceRejected):
            AuthorizedEvidenceBuilder.build_for_capability(
                "CAP_STATE_ENGINE", fabricated, mission, "T1", "E1")
        self.assertNotEqual(self.persisted(mission), "COMPLETED")

    def test_C2_manually_built_evidence_is_not_registered(self):
        """C2: an unsigned evidence object is refused, even with a leaked key signature."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        for signature in ("0" * 64, _authority.sign({"forged": True})):
            ev = CapabilityEvidence(
                evidence_id="c2", capability_id="CAP_STATE_ENGINE", action="a",
                expected="e", actual="a", evidence_type=EvidenceType.FILESYSTEM_EVIDENCE,
                physical_evidence=True, source="x", timestamp="t", verification_result=True,
                verifier="x", mission_id=mission, task_id="T", execution_id="E",
                verification_id="V", observation_id="O", physical_fact_reference="P",
                capability_verification_token="K", origin=AUTHORIZED_ORIGIN,
                authorization=signature)
            status = self.registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=mission)
            self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_C3_authentic_evidence_reused_across_missions(self):
        """C3: real evidence admitted for mission A does not certify mission B."""
        a = make_mission(self.db, ["CAP_STATE_ENGINE"])
        b = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, a)
        self.assertEqual(certify_state_engine(self.db, self.registry, a), CapabilityStatus.VERIFIED)
        status = self.registry.register_evidence("CAP_STATE_ENGINE", evidence[0], mission_id=b)
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)
        self.assertNotEqual(
            self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=b),
            CapabilityStatus.VERIFIED,
        )

    def test_C5_capability_or_type_substitution_is_refused(self):
        """C5: editing capability_id or evidence_type invalidates the signature."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, mission)[0]
        for field, value in (("capability_id", "CAP_WHATSAPP_AUTO_REPLY"),
                             ("evidence_type", EvidenceType.NETWORK_EVIDENCE)):
            clone = dataclasses.replace(evidence, **{field: value})
            object.__setattr__(clone, "authorization", _authority.sign(clone.signature_payload()))
            status = self.registry.register_evidence("CAP_STATE_ENGINE", clone, mission_id=mission)
            self.assertNotEqual(status, CapabilityStatus.VERIFIED, f"substitution of {field}")

    def test_C8_one_observation_cannot_satisfy_a_composite_requirement(self):
        """C8: a single insufficient observation yields PARTIAL, never VERIFIED."""
        subject = self.real_file_fact("c8.txt", "c8").subject
        capdefs.register_definition(CapabilityDefinition(
            capability_id=subject, capability_name="C8 probe",
            required_evidence_types=(EvidenceType.FILESYSTEM_EVIDENCE, EvidenceType.DATABASE_EVIDENCE),
            required_tests=(), physical_verification_required=True,
            verifiable_by_fact_types=("WRITE_FILE",), verifier_id="partial"))
        CapabilitySpecificVerifier.register_verifier(
            subject, "partial", lambda f, d: ((EvidenceType.FILESYSTEM_EVIDENCE,), "one only"))
        mission = make_mission(self.db, [])
        evidence = AuthorizedEvidenceBuilder.build_for_capability(
            subject, self.real_file_fact("c8.txt", "c8"), mission, "T1", "exec")
        status = self.registry.register_evidence(subject, evidence[0], mission_id=mission)
        self.assertEqual(status, CapabilityStatus.PARTIAL)


# ======================================================================
# GROUP D — definitions
# ======================================================================
class TestGroupDDefinitions(ComposedBase):

    def test_D1_bootstrap_flag_grants_nothing(self):
        """D1: registering with bootstrap=True does not grant requirement authority."""
        capdefs.register_definition(CapabilityDefinition(
            capability_id="CAP_BOOTSTRAP_LIE", capability_name="lie",
            required_evidence_types=(), required_tests=(),
            physical_verification_required=False, bootstrap=True))
        self.assertFalse(capdefs.can_satisfy_requirement("CAP_BOOTSTRAP_LIE"))

    def test_D2_runtime_injected_definition_cannot_satisfy_a_requirement(self):
        """D2: an extension capability can be scored but never completes a mission."""
        subject = self.real_file_fact("d2.txt", "d2").subject
        capdefs.register_definition(CapabilityDefinition(
            capability_id=subject, capability_name="D2 probe",
            required_evidence_types=(EvidenceType.FILESYSTEM_EVIDENCE,),
            required_tests=(), physical_verification_required=True,
            verifiable_by_fact_types=("WRITE_FILE",), verifier_id="passes"))
        CapabilitySpecificVerifier.register_verifier(
            subject, "passes", lambda f, d: (tuple(d.required_evidence_types), "ok"))
        mission = make_mission(self.db, [subject])
        evidence = AuthorizedEvidenceBuilder.build_for_capability(
            subject, self.real_file_fact("d2.txt", "d2"), mission, "T1", "exec")
        self.assertEqual(
            self.registry.register_evidence(subject, evidence[0], mission_id=mission),
            CapabilityStatus.VERIFIED)
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_D3_protected_definition_cannot_be_replaced(self):
        """D3: the protected contract is immutable at runtime."""
        with self.assertRaises(PermissionError):
            capdefs.register_definition(CapabilityDefinition(
                capability_id="CAP_STATE_ENGINE", capability_name="hijack",
                required_evidence_types=(), required_tests=(),
                physical_verification_required=False))

    def test_D5_unknown_capability_cannot_satisfy_a_requirement(self):
        """D5: a requirement naming an unknown capability never completes."""
        mission = make_mission(self.db, ["CAP_DOES_NOT_EXIST"])
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)


# ======================================================================
# GROUP E — requirements and finalisation
# ======================================================================
class TestGroupERequirements(ComposedBase):

    def test_E1_empty_arguments_cannot_replace_persisted_requirements(self):
        """E1: the finalisation API exposes no requirements argument at all."""
        import inspect
        params = list(inspect.signature(self.db.update_mission_status).parameters)
        self.assertNotIn("required_capabilities", params)
        self.assertNotIn("allow_empty_requirements", params)
        mission = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_E3_requirements_tampering_is_detected_and_blocks(self):
        """E3: direct SQL erasure of requirements blocks and is never downgraded."""
        mission = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.assertTrue(self.db.verify_requirements_integrity(self.db.get_mission(mission)))
        with self.db._lock:
            conn = self.db._get_connection()
            conn.execute(
                "UPDATE missions SET required_capabilities='[]', requirements_declared=0"
                " WHERE mission_id=?", (mission,))
            conn.commit()
        self.assertFalse(self.db.verify_requirements_integrity(self.db.get_mission(mission)))
        self.assertEqual(self.db.update_mission_status(mission), "BLOCKED")
        self.assertEqual(self.persisted(mission), "BLOCKED")
        self.assertIn(
            "REQUIREMENTS_INTEGRITY_FAILURE",
            " ".join(e["reason"] for e in AuthorityAudit.events()),
        )

    def test_E4_authorization_cannot_cross_missions(self):
        """E4: mission A's authorization does not complete mission B."""
        a = make_mission(self.db, ["CAP_STATE_ENGINE"])
        b = make_mission(self.db, ["CAP_STATE_ENGINE"])
        certify_state_engine(self.db, self.registry, a)
        auth = MissionCompletionGate.evaluate_and_authorize(a, state_db=self.db)
        self.db.complete_mission_with_authorization(b, gate_authorization=auth)
        self.assertNotIn(self.persisted(b), TERMINAL_COMPLETE)

    def test_E5_authorization_is_stale_after_evidence_changes(self):
        """
        E5: an authorization issued before the evidence existed is rejected.

        Note the precise property being asserted. Presenting the stale authorization does not
        *itself* complete the mission — it is refused and the refusal is recorded. The mission
        may still reach COMPLETED afterwards, but only because the caller then performs a
        fresh evaluation against real evidence. A stale authorization can never be the cause
        of a completion; re-derivation is.
        """
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        stale = MissionCompletionGate.evaluate_and_authorize(mission, state_db=self.db)
        self.assertFalse(stale.verdict.can_complete)
        self.assertEqual(self.db.update_mission_status(mission), "PARTIALLY_COMPLETED")

        # Real evidence now exists; the stale authorization is still refused.
        certify_state_engine(self.db, self.registry, mission)
        self.db.complete_mission_with_authorization(mission, gate_authorization=stale)
        rejections = [g["description"] for g in self.db.get_evidence_gaps(mission)]
        self.assertTrue(
            any("GateAuthorization rejected" in d for d in rejections),
            "the stale authorization must be refused and recorded",
        )

        # Completion now happens only through a fresh, correctly-issued authorization.
        fresh = MissionCompletionGate.evaluate_and_authorize(mission, state_db=self.db)
        self.assertTrue(fresh.verdict.can_complete)
        self.assertEqual(self.db.complete_mission_with_authorization(
            mission, gate_authorization=fresh), "COMPLETED")

    def test_E6_fabricated_gate_result_is_inert(self):
        """E6: a fabricated verdict, even self-issued, does not complete a mission."""
        from core.cognitive.gate_authorization import GateAuthorization
        from core.cognitive.gate_types import MissionGateResult, MissionStatus
        mission = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        forged = GateAuthorization._issue(
            mission_id=mission, required_capabilities=[], requirements_declared=True,
            evaluation_id="forged",
            verdict=MissionGateResult(can_complete=True,
                                      mission_status=MissionStatus.MISSION_COMPLETED,
                                      blocking_reasons=[], unverified_required_capabilities=[]),
            authorized_status=MissionStatus.MISSION_COMPLETED)
        self.db.complete_mission_with_authorization(mission, gate_authorization=forged)
        self.assertNotIn(self.persisted(mission), TERMINAL_COMPLETE)

    def test_E7_partial_capability_cannot_complete(self):
        """E7: a mission requiring a capability with partial coverage stays incomplete."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY"])
        certify_state_engine(self.db, self.registry, mission)
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_E8_llm_output_evidence_cannot_complete(self):
        """E8: evidence whose origin is LLM_OUTPUT is refused at admission."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        fact = sqlite_fact(self.db)
        evidence = AuthorizedEvidenceBuilder.build_for_capability(
            "CAP_STATE_ENGINE", fact, mission, "T1", "exec",
            expected_resource=self.db.db_path)
        relabelled = []
        for ev in evidence:
            clone = dataclasses.replace(ev, origin="LLM_OUTPUT")
            object.__setattr__(clone, "authorization", _authority.sign(clone.signature_payload()))
            relabelled.append(clone)
        for ev in relabelled:
            status = self.registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=mission)
            self.assertNotEqual(status, CapabilityStatus.VERIFIED)
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_E9_synthetic_evidence_cannot_complete(self):
        """E9: TEST_SYNTHETIC evidence cannot certify."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        ev = CapabilityEvidence(
            evidence_id="e9", capability_id="CAP_STATE_ENGINE", action="a", expected="e",
            actual="a", evidence_type=EvidenceType.FILESYSTEM_EVIDENCE, physical_evidence=True,
            source="SyntheticTest", timestamp="t", verification_result=True, verifier="t",
            mission_id=mission, task_id="T", execution_id="E", verification_id="V",
            observation_id="O", physical_fact_reference="P",
            capability_verification_token="K", origin="TEST_SYNTHETIC",
            authorization=_authority.sign({"forged": "e9"}))
        self.assertNotEqual(
            self.registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=mission),
            CapabilityStatus.VERIFIED)
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_E11_no_requirements_declared_requires_an_explicit_persisted_property(self):
        """E11: NO_REQUIREMENTS_DECLARED is reachable only via declare_no_requirements."""
        declared_empty = make_mission(self.db, [])
        self.assertEqual(self.db.update_mission_status(declared_empty), "BLOCKED")
        explicit = make_mission(self.db, [], declare_no_requirements=True)
        self.assertEqual(self.db.update_mission_status(explicit), "NO_REQUIREMENTS_DECLARED")

    def test_E12_failure_between_evaluation_and_persistence_blocks(self):
        """
        E12: if persistence raises, the mission must not be left in a terminal state.
        """
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        certify_state_engine(self.db, self.registry, mission)
        original = self.db._persist_mission_status

        def exploding(mission_id, status, snapshot=None):
            raise RuntimeError("simulated storage failure")

        self.db._persist_mission_status = exploding
        try:
            with self.assertRaises(RuntimeError):
                self.db.update_mission_status(mission)
        finally:
            self.db._persist_mission_status = original
        self.assertNotIn(self.persisted(mission), TERMINAL_COMPLETE)


# ======================================================================
# GROUP F — integration, real observations and recovery
# ======================================================================
class TestGroupFIntegration(ComposedBase):
    """These use REAL observations produced by the authorized observer."""

    def test_F1_real_observation_completes_a_mission(self):
        """F1: a genuine SQLite inspection certifies CAP_STATE_ENGINE and completes."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        self.assertEqual(certify_state_engine(self.db, self.registry, mission),
                         CapabilityStatus.VERIFIED)
        self.assertEqual(self.db.complete_mission_with_authorization(mission), "COMPLETED")
        self.assertEqual(self.persisted(mission), "COMPLETED")

    def test_F2_insufficient_evidence_leaves_the_mission_incomplete(self):
        """F2: real but insufficient evidence does not complete."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE", "CAP_PLAYWRIGHT_BROWSER"])
        certify_state_engine(self.db, self.registry, mission)
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_F3_interrupted_and_resumed_mission_re_evaluates(self):
        """F3: after a resume, authority is re-derived rather than inherited."""
        mission = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.db.create_planner_task("T1", mission, 1, "step", "COMMAND", {}, "VERIFIED")
        self.db.close()
        reopened = StateEngine(db_path=self.db.db_path)
        try:
            engine = ResumeEngine(state_db=reopened)
            engine.evaluate_mission_for_resume(mission)
            self.assertNotIn(reopened.get_mission(mission)["status"], TERMINAL_COMPLETE)
        finally:
            reopened.close()

    def test_F4_recovery_does_not_grant_capability(self):
        """F4: entering recovery confers nothing."""
        mission = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.assertNotEqual(
            self.registry.get_capability_status("CAP_WHATSAPP_AUTO_REPLY"),
            CapabilityStatus.VERIFIED)
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)

    def test_F5_concurrent_certification_is_consistent(self):
        """F5: two threads certifying the same capability leave a consistent result."""
        import threading
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        results = []

        def worker():
            try:
                results.append(certify_state_engine(self.db, self.registry, mission))
            except Exception as exc:  # a refusal is an acceptable outcome
                results.append(f"refused:{type(exc).__name__}")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 4)
        self.assertEqual(
            self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=mission),
            CapabilityStatus.VERIFIED)
        self.assertEqual(self.db.complete_mission_with_authorization(mission), "COMPLETED")

    def test_F5_overlapping_admission_cannot_drop_evidence(self):
        """
        Hold the first admission between read and write. A second admission must not
        enter that window; otherwise the later save drops a required evidence type.
        """
        import threading
        import time

        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, mission)
        self.assertGreaterEqual(len(evidence), 2)
        started = threading.Event()
        release = threading.Event()
        ready = {"n": 0}
        ready_cv = threading.Condition()
        peak = {"n": 0}
        current = {"n": 0}
        peak_mu = threading.Lock()
        original = self.registry._load_record

        def load(capability_id):
            with peak_mu:
                current["n"] += 1
                peak["n"] = max(peak["n"], current["n"])
            started.set()
            self.assertTrue(release.wait(timeout=3), "la admisión retenida no se soltó")
            try:
                return original(capability_id)
            finally:
                with peak_mu:
                    current["n"] -= 1

        errors = []

        def worker(item):
            with ready_cv:
                ready["n"] += 1
                ready_cv.notify_all()
            try:
                self.registry.register_evidence(
                    "CAP_STATE_ENGINE", item, mission_id=mission)
            except Exception as exc:
                errors.append(repr(exc))

        self.registry._load_record = load
        threads = [threading.Thread(target=worker, args=(item,)) for item in evidence[:2]]
        try:
            for thread in threads:
                thread.start()
            with ready_cv:
                while ready["n"] < 2:
                    self.assertTrue(ready_cv.wait(timeout=3), "las dos admisiones no arrancaron")
            self.assertTrue(started.wait(timeout=3), "ninguna admisión llegó a leer el expediente")
            time.sleep(0.3)
            self.assertEqual(peak["n"], 1)
            release.set()
            for thread in threads:
                thread.join(timeout=5)
        finally:
            release.set()
            self.registry._load_record = original
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        record = self.db.get_capability_record("CAP_STATE_ENGINE")
        types = {
            item.get("type")
            for item in (record.get("evidence_ids") or [])
            if isinstance(item, dict) and item.get("mission_id") == mission
        }
        self.assertGreaterEqual(len(types), 2)
        self.assertEqual(
            self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=mission),
            CapabilityStatus.VERIFIED)

    def test_F5_repeated_concurrent_rounds_stay_verified(self):
        """Eight fresh missions, four threads each. Every one must end VERIFIED."""
        import threading

        for _round in range(8):
            mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
            results = []

            def worker(mission_id=mission):
                try:
                    results.append(certify_state_engine(self.db, self.registry, mission_id))
                except Exception as exc:
                    results.append(f"refused:{type(exc).__name__}")

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(results), 4, results)
            self.assertEqual(
                self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=mission),
                CapabilityStatus.VERIFIED)

    def test_F5_concurrent_sqlite_probe_uses_a_unique_key(self):
        """Four inspections of the same file must all verify. A shared probe id does not."""
        import threading

        for _round in range(10):
            facts = []
            barrier = threading.Barrier(4)

            def worker():
                barrier.wait()
                facts.append(PhysicalFactVerifier.verify_sqlite_persistence(
                    self.db.db_path, execution_id="concurrent-probe"))

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(facts), 4)
            self.assertTrue(
                all(fact.verified for fact in facts),
                [fact.error for fact in facts if not fact.verified],
            )

    def test_F6_completion_racing_evidence_change_stays_consistent(self):
        """
        F6: a mission whose evidence is withdrawn mid-flight must not complete.
        """
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        certify_state_engine(self.db, self.registry, mission)
        with self.db._lock:
            conn = self.db._get_connection()
            conn.execute("UPDATE missions SET requirements_declared=0 WHERE mission_id=?",
                         (mission,))
            conn.commit()
        self.assertNotIn(self.db.update_mission_status(mission), TERMINAL_COMPLETE)


    def test_F7_observation_of_a_foreign_database_cannot_certify(self):
        """
        F7 (added in 004 post-audit): a genuine observation of a *different* real database
        must not certify this mission.

        Found by an independent post-audit probe. The observation was real, but it described
        a different store than the one holding the mission's rows, so it proves nothing about
        this mission. The trusted verifier is resource-bound to prevent exactly this.
        """
        other_db, _ = temp_db()
        try:
            fact = PhysicalFactVerifier.verify_sqlite_persistence(
                other_db.db_path, execution_id="foreign")
            self.assertTrue(fact.verified, "the foreign observation is itself genuine")
            with self.assertRaises(EvidenceRejected):
                AuthorizedEvidenceBuilder.build_for_capability(
                    "CAP_STATE_ENGINE", fact, make_mission(self.db, ["CAP_STATE_ENGINE"]),
                    "T1", "foreign", expected_resource=self.db.db_path)
        finally:
            other_db.close()

    def test_F8_own_database_observation_still_certifies(self):
        """F8: the positive counterpart — the mission's own database certifies normally."""
        mission = make_mission(self.db, ["CAP_STATE_ENGINE"])
        self.assertEqual(certify_state_engine(self.db, self.registry, mission),
                         CapabilityStatus.VERIFIED)
        self.assertEqual(self.db.complete_mission_with_authorization(mission), "COMPLETED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
