"""
Adversarial authority suite for IMPLEMENTATION 003.

Each test names the specific boundary it attacks (D-x) and asserts the *architectural
property*, not merely that some value differs. Where a previous suite asserted vulnerable
behaviour, that assertion is inverted here and the original intent is preserved as an
adversarial case rather than deleted.
"""
from __future__ import annotations

import copy
import os
import pickle
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.cognitive import _authority
from core.cognitive.capability_registry import (
    CapabilityEvidence,
    CapabilityEvidenceRegistry,
    CapabilityStatus,
    EvidenceType,
)
from core.cognitive.gate_authorization import GateAuthorization
from core.cognitive.gate_types import MissionGateResult, MissionStatus
from core.cognitive.mission_completion_gate import MissionCompletionGate
from core.cognitive.physical_fact_verifier import (
    PhysicalFactVerifier,
    VerifiedPhysicalFact,
)
from core.cognitive.authorized_evidence_builder import (
    AUTHORIZED_ORIGIN,
    AuthorizedEvidenceBuilder,
    EvidenceRejected,
)
from core.cognitive.capability_specific_verifier import (
    CapabilitySpecificVerifier,
    VerificationRejection,
)
from core.cognitive.claim_validator import ClaimValidator
from core.cognitive.adapter import CognitiveAdapter
from tests.authority_fixtures import (
    authorized_evidence_for,
    certify_state_engine,
    cleanup,
    make_mission,
    sqlite_fact,
    temp_db,
)

TERMINAL = ("COMPLETED",)


class AdversarialAuthorityBase(unittest.TestCase):
    def setUp(self):
        self.db, self.temp_dir = temp_db()
        self.registry = CapabilityEvidenceRegistry(state_db=self.db)

    def tearDown(self):
        cleanup(self.db, self.temp_dir)

    def status(self, mission_id):
        return self.db.get_mission(mission_id)["status"]


# ======================================================================
# D-1 / D-2 : authorization cannot be fabricated, mutated or replayed
# ======================================================================
class TestD1NoPublicAuthorizationForgery(AdversarialAuthorityBase):

    def test_A1_public_create_authorization_api_does_not_exist(self):
        """A1: there is no public API that mints an authorization from a caller result."""
        self.assertFalse(
            hasattr(MissionCompletionGate, "create_authorization"),
            "MissionCompletionGate must not expose create_authorization().",
        )

    def test_A1_fabricated_gate_result_cannot_reach_completed(self):
        """A1: a fabricated MissionGateResult, even issued through the private path, is inert."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        fabricated = MissionGateResult(
            can_complete=True,
            mission_status=MissionStatus.MISSION_COMPLETED,
            blocking_reasons=[],
            unverified_required_capabilities=[],
        )
        forged = GateAuthorization._issue(
            mission_id=mission_id,
            required_capabilities=[],
            requirements_declared=True,
            evaluation_id="forged",
            verdict=fabricated,
            authorized_status=MissionStatus.MISSION_COMPLETED,
        )
        # Authentic signature, wrong content: re-derivation must reject it.
        self.assertTrue(forged.is_authentic())
        self.db.complete_mission_with_authorization(mission_id, gate_authorization=forged)
        self.assertNotIn(self.status(mission_id), TERMINAL)

    def test_A2_emitted_authorization_is_immutable(self):
        """A2: no field of an issued authorization can be reassigned."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        auth = MissionCompletionGate.evaluate_and_authorize(mission_id, state_db=self.db)
        with self.assertRaises(Exception):
            auth.mission_id = "other"
        with self.assertRaises(Exception):
            auth.authorized_status = "COMPLETED"

    def test_A3_mutation_plus_rehash_is_impossible(self):
        """A3: the signing key is not obtainable, so a valid signature cannot be recomputed."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        auth = MissionCompletionGate.evaluate_and_authorize(mission_id, state_db=self.db)
        # A caller cannot build a signature without the key.
        self.assertFalse(
            _authority.verify_signature(
                {"mission_id": "other", "can_complete": True}, "0" * 64
            )
        )
        self.assertFalse(auth.is_valid_for(
            mission_id="other", required_capabilities=[], requirements_declared=True,
            expected_verdict=auth.verdict,
        ))

    def test_A4_authorization_not_reusable_across_missions(self):
        """A4: Mission-A authorization cannot complete Mission-B."""
        a = make_mission(self.db, ["CAP_STATE_ENGINE"])
        b = make_mission(self.db, ["CAP_STATE_ENGINE"])
        certify_state_engine(self.db, self.registry, a)
        auth_a = MissionCompletionGate.evaluate_and_authorize(a, state_db=self.db)
        self.db.complete_mission_with_authorization(b, gate_authorization=auth_a)
        self.assertNotIn(self.status(b), TERMINAL)

    def test_A21_authorization_bound_to_execution_id(self):
        """A21: an authorization issued for one execution_id is invalid for another."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        certify_state_engine(self.db, self.registry, mission_id, execution_id="exec-A")
        auth = MissionCompletionGate.evaluate_and_authorize(
            mission_id, state_db=self.db, execution_id="exec-A"
        )
        self.assertTrue(auth.is_valid_for(
            mission_id=mission_id, required_capabilities=["CAP_STATE_ENGINE"],
            requirements_declared=True, expected_verdict=auth.verdict, execution_id="exec-A",
        ))
        self.assertFalse(auth.is_valid_for(
            mission_id=mission_id, required_capabilities=["CAP_STATE_ENGINE"],
            requirements_declared=True, expected_verdict=auth.verdict, execution_id="exec-B",
        ))

    def test_A19_restart_does_not_preserve_a_valid_authorization(self):
        """A19: a fresh process holds no valid authorization; mission stays unterminated."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        db2 = StateEngine(db_path=self.db.db_path)
        try:
            result = db2.update_mission_status(mission_id)
            self.assertNotIn(result, TERMINAL)
        finally:
            db2.close()

    def test_A20_copy_deepcopy_pickle_cannot_produce_usable_authority(self):
        """
        A20: structural duplication must not be a route to escalation.

        A byte-identical clone carries exactly the authority of the original, which is not an
        escalation. What must be impossible is obtaining a clone whose *content* differs
        while still verifying. Each clone is therefore tampered with and must be rejected.
        """
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        auth = MissionCompletionGate.evaluate_and_authorize(mission_id, state_db=self.db)
        clones = [copy.copy(auth), copy.deepcopy(auth), pickle.loads(pickle.dumps(auth))]
        for clone in clones:
            # Escalation attempt on a structurally duplicated object.
            for field, value in (
                ("mission_id", "msn_someone_else"),
                ("authorized_status", "COMPLETED"),
            ):
                tampered = copy.copy(clone)
                object.__setattr__(tampered, field, value)
                self.assertFalse(
                    tampered.is_authentic(),
                    f"a {field}-tampered clone must not verify",
                )
            # A pristine clone is equivalent to the original, and no more powerful.
            self.assertEqual(clone.verdict.verdict_signature(), auth.verdict.verdict_signature())


# ======================================================================
# D-3 : no direct creation of a terminal mission
# ======================================================================
class TestD3NoDirectCompletion(AdversarialAuthorityBase):

    def test_A5_create_mission_refuses_terminal_status(self):
        """A5: a mission cannot be born complete."""
        session_id = self.db.create_session()
        for terminal in ("COMPLETED", "VERIFIED", "BLOCKED", "PARTIALLY_COMPLETED"):
            with self.assertRaises(ValueError):
                self.db.create_mission(session_id=session_id, raw_prompt="x", status=terminal)

    def test_A22_completed_requires_a_gate_evaluation_that_agrees(self):
        """A22: a mission with unverified requirements never reaches COMPLETED."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        result = self.db.update_mission_status(mission_id)
        self.assertNotIn(result, TERMINAL)
        self.assertNotIn(self.status(mission_id), TERMINAL)

    def test_A26_completed_only_with_valid_authorization(self):
        """A26: persisted requirements X,Y plus real evidence for X,Y => COMPLETED."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        self.assertNotIn(self.db.update_mission_status(mission_id), TERMINAL)
        certify_state_engine(self.db, self.registry, mission_id)
        auth = MissionCompletionGate.evaluate_and_authorize(mission_id, state_db=self.db)
        result = self.db.complete_mission_with_authorization(mission_id, gate_authorization=auth)
        self.assertEqual(result, "COMPLETED")
        self.assertEqual(self.status(mission_id), "COMPLETED")


# ======================================================================
# D-4 : no public path to VERIFIED
# ======================================================================
class TestD4NoDirectVerified(AdversarialAuthorityBase):

    def test_A6_set_capability_status_cannot_assign_verified(self):
        """A6: VERIFIED/PARTIAL are derived and refuse assignment."""
        for derived in (CapabilityStatus.VERIFIED, CapabilityStatus.PARTIAL):
            with self.assertRaises(PermissionError):
                self.registry.set_capability_status("CAP_WHATSAPP_AUTO_REPLY", derived)

    def test_A6_set_capability_limitation_cannot_assign_verified(self):
        """A6: the replacement API is equally closed to derived states."""
        with self.assertRaises(PermissionError):
            self.registry.set_capability_limitation("CAP_STATE_ENGINE", CapabilityStatus.VERIFIED)

    def test_A6_limitation_may_still_demote(self):
        """A6: non-derived limitations remain expressible."""
        self.registry.set_capability_limitation(
            "CAP_WHATSAPP_AUTO_REPLY", CapabilityStatus.BLOCKED_EXTERNAL, "no verifier"
        )
        self.assertNotEqual(
            self.registry.get_capability_status("CAP_WHATSAPP_AUTO_REPLY"), CapabilityStatus.VERIFIED
        )


# ======================================================================
# D-5 : requirements are sovereign
# ======================================================================
class TestD5RequirementsAreSovereign(AdversarialAuthorityBase):

    def test_A7_caller_cannot_substitute_empty_requirements(self):
        """A7: update_mission_status exposes no requirements parameter at all."""
        import inspect
        params = list(inspect.signature(self.db.update_mission_status).parameters)
        self.assertNotIn("required_capabilities", params)
        self.assertNotIn("allow_empty_requirements", params)
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        self.assertNotIn(self.db.update_mission_status(mission_id), TERMINAL)

    def test_A7_authorization_contradicting_persisted_requirements_is_rejected(self):
        """A7: an authorization whose requirement set differs from the mission is refused."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        derived = MissionCompletionGate.evaluate_mission_completion(
            mission_id=mission_id, required_capabilities=[], requirements_declared=True,
            capability_registry=self.registry, state_db=self.db,
        )
        lying = GateAuthorization._issue(
            mission_id=mission_id, required_capabilities=[],
            requirements_declared=True, evaluation_id="lie",
            verdict=derived, authorized_status=derived.mission_status,
        )
        self.db.complete_mission_with_authorization(mission_id, gate_authorization=lying)
        self.assertNotIn(self.status(mission_id), TERMINAL)

    def test_declared_empty_requirements_is_a_persisted_property(self):
        """A mission with genuinely no requirements records that fact explicitly."""
        mission_id = make_mission(self.db, [], declare_no_requirements=True)
        row = self.db.get_mission(mission_id)
        self.assertEqual(row["requirements_declared"], 0)
        self.assertEqual(self.db.update_mission_status(mission_id), "NO_REQUIREMENTS_DECLARED")

    def test_undeclared_empty_requirements_is_blocked(self):
        """A mission that declares requirements but persists an empty list is BLOCKED."""
        mission_id = make_mission(self.db, [])
        self.assertEqual(self.db.get_mission(mission_id)["requirements_declared"], 1)
        self.assertEqual(self.db.update_mission_status(mission_id), "BLOCKED")

    def test_A25_partial_evidence_does_not_complete(self):
        """A25: requirements X,Y with evidence for only X => not COMPLETED."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY"])
        certify_state_engine(self.db, self.registry, mission_id)
        self.assertNotIn(self.db.update_mission_status(mission_id), TERMINAL)

    def test_unknown_requirement_is_not_complete(self):
        """A requirement naming an undeclared capability can never be satisfied."""
        mission_id = make_mission(self.db, ["CAP_DOES_NOT_EXIST"])
        self.assertNotIn(self.db.update_mission_status(mission_id), TERMINAL)


# ======================================================================
# D-6 : capability verification is specific
# ======================================================================
class TestD6CapabilitySpecificVerification(AdversarialAuthorityBase):

    def test_A9_pytest_success_cannot_verify_whatsapp(self):
        """A9: a green test run is not capability evidence for anything."""
        fact = PhysicalFactVerifier.verify_test_execution("pytest", "Ran 331 tests in 1s\nOK")
        result = CapabilitySpecificVerifier.verify("CAP_WHATSAPP_AUTO_REPLY", fact)
        self.assertFalse(result.verified)
        # No definition declares TEST among its verifiable fact types.
        self.assertIn(result.reason, (
            VerificationRejection.REASON_FACT_TYPE_NOT_ALLOWED,
            VerificationRejection.REASON_NO_VERIFIER,
        ))

    def test_A10_curl_success_cannot_verify_whatsapp(self):
        """A10: a zero exit code is not capability evidence for anything."""
        fact = PhysicalFactVerifier.verify_command(
            "curl https://wa.me", "[Resultado PowerShell (ExitCode: 0)]:"
        )
        result = CapabilitySpecificVerifier.verify("CAP_WHATSAPP_AUTO_REPLY", fact)
        self.assertFalse(result.verified)

    def test_A16_valid_fact_of_a_different_capability_is_rejected(self):
        """A16: a real CAP_STATE_ENGINE fact cannot demonstrate another capability."""
        fact = sqlite_fact(self.db)
        self.assertTrue(fact.verified)
        result = CapabilitySpecificVerifier.verify("CAP_WHATSAPP_AUTO_REPLY", fact)
        self.assertFalse(result.verified)
        # A re-pointed subject is caught by the ledger before the verifier is even reached.
        self.assertIn(result.reason, (
            VerificationRejection.REASON_FACT_TYPE_NOT_ALLOWED,
            VerificationRejection.REASON_SUBJECT_MISMATCH,
            "OBSERVATION_STATE_MISMATCH",
            "CAPABILITY_MISMATCH",
        ))

    def test_file_write_cannot_verify_any_capability(self):
        """A generic filesystem fact is not declared evidence for any capability."""
        path = os.path.join(self.temp_dir, "artifact.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("data")
        fact = PhysicalFactVerifier.verify_write_file(path, "data")
        self.assertTrue(fact.verified)
        for cap in ("CAP_STATE_ENGINE", "CAP_WHATSAPP_AUTO_REPLY", "CAP_PLAYWRIGHT_BROWSER"):
            self.assertFalse(CapabilitySpecificVerifier.verify(cap, fact).verified)

    def test_capability_without_verifier_can_never_be_verified(self):
        """A capability with no capability-specific verifier is permanently unverified."""
        for cap in ("CAP_WHATSAPP_AUTO_REPLY", "CAP_PLAYWRIGHT_BROWSER", "CAP_DESKTOP_VISION",
                    "CAP_CHECKPOINT_RESUME"):
            self.assertNotEqual(
                self.registry.get_capability_status(cap), CapabilityStatus.VERIFIED
            )
            self.assertFalse(CapabilitySpecificVerifier.has_verifier(cap))

    def test_unverified_fact_is_rejected_by_the_verifier(self):
        """A fact whose physical check failed cannot be certified."""
        bad = VerifiedPhysicalFact(
            fact_id="f1", fact_type="SQLITE_PERSISTENCE", subject="CAP_STATE_ENGINE",
            verified=False, observed_state={},
        )
        self.assertFalse(CapabilitySpecificVerifier.verify("CAP_STATE_ENGINE", bad).verified)

    def test_A23_partial_coverage_yields_partial(self):
        """
        A23: a capability with only some required evidence types is PARTIAL.

        Rewritten in 004. The previous version re-pointed a real fact's `subject` with
        `dataclasses.replace` to fit a synthetic capability — precisely the fabrication the
        observation ledger now refuses.

        The extension mechanism is instead exercised end-to-end with a genuine observation.
        `PhysicalFactVerifier` observes a real file and records the observation; the
        extension capability declares `WRITE_FILE` as an allowed fact type, and its verifier
        claims only FILESYSTEM coverage of a capability that also requires DATABASE. The
        result must be PARTIAL, never VERIFIED.
        """
        from core.cognitive.capability_definitions import (
            CapabilityDefinition,
            EvidenceType as ET,
            register_definition,
        )
        from core.cognitive.capability_specific_verifier import (
            CapabilitySpecificVerifier as CSV,
        )

        real_file = os.path.join(self.temp_dir, "composite_probe.txt")
        with open(real_file, "w", encoding="utf-8") as fh:
            fh.write("composite")
        fact = PhysicalFactVerifier.verify_write_file(real_file, "composite")
        self.assertTrue(fact.verified)

        # The extension capability is keyed on the real observed subject (the file path),
        # so no fact field has to be rewritten.
        subject = fact.subject
        register_definition(CapabilityDefinition(
            capability_id=subject,
            capability_name="Composite probe",
            required_evidence_types=(ET.FILESYSTEM_EVIDENCE, ET.DATABASE_EVIDENCE),
            required_tests=(),
            physical_verification_required=True,
            verifiable_by_fact_types=("WRITE_FILE",),
            verifier_id="probe_partial",
        ))
        CSV.register_verifier(
            subject, "probe_partial",
            lambda f, d: ((ET.FILESYSTEM_EVIDENCE,), "only filesystem observed"),
        )
        mission_id = make_mission(self.db, [])
        evidence = AuthorizedEvidenceBuilder.build_for_capability(
            subject, fact, mission_id, "T1", "exec-1"
        )
        status = self.registry.register_evidence(
            subject, evidence[0], mission_id=mission_id
        )
        self.assertEqual(status, CapabilityStatus.PARTIAL)

    def test_A24_full_coverage_yields_verified(self):
        """A24: all required types physically verified => VERIFIED, for that mission only."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        status = certify_state_engine(self.db, self.registry, mission_id)
        self.assertEqual(status, CapabilityStatus.VERIFIED)
        self.assertEqual(
            self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=mission_id),
            CapabilityStatus.VERIFIED,
        )
        # A24b: scoped to the mission. A different mission does not inherit it.
        other = make_mission(self.db, ["CAP_STATE_ENGINE"])
        self.assertNotEqual(
            self.registry.get_capability_status("CAP_STATE_ENGINE", mission_id=other),
            CapabilityStatus.VERIFIED,
        )


    def test_runtime_registered_capability_cannot_satisfy_a_requirement(self):
        """
        A caller may register an extension capability and a permissive verifier, and the
        registry will model and score it — but it must never be able to satisfy a mission
        requirement, otherwise a caller could complete a mission on self-issued evidence.
        """
        from core.cognitive.capability_definitions import (
            CapabilityDefinition,
            EvidenceType as ET,
            register_definition,
        )
        from core.cognitive.capability_specific_verifier import (
            CapabilitySpecificVerifier as CSV,
        )

        real_file = os.path.join(self.temp_dir, "invented_probe.txt")
        with open(real_file, "w", encoding="utf-8") as fh:
            fh.write("invented")
        fact = PhysicalFactVerifier.verify_write_file(real_file, "invented")
        subject = fact.subject

        register_definition(CapabilityDefinition(
            capability_id=subject,
            capability_name="Invented at runtime",
            required_evidence_types=(ET.FILESYSTEM_EVIDENCE,),
            required_tests=(),
            physical_verification_required=True,
            verifiable_by_fact_types=("WRITE_FILE",),
            verifier_id="always_passes",
        ))
        CSV.register_verifier(
            subject, "always_passes",
            lambda f, d: ((ET.FILESYSTEM_EVIDENCE,), "unconditionally satisfied"),
        )
        mission_id = make_mission(self.db, [subject])
        evidence = AuthorizedEvidenceBuilder.build_for_capability(
            subject, fact, mission_id, "T1", "exec-1"
        )
        status = self.registry.register_evidence(
            subject, evidence[0], mission_id=mission_id
        )
        # The registry scores it...
        self.assertEqual(status, CapabilityStatus.VERIFIED)
        # ...but the gate refuses to let an extension capability complete a mission.
        self.assertNotIn(self.db.update_mission_status(mission_id), TERMINAL)

    def test_existing_definition_cannot_be_overwritten(self):
        """Replacing a protected capability contract is refused."""
        from core.cognitive.capability_definitions import (
            CapabilityDefinition,
            EvidenceType as ET,
            register_definition,
        )
        with self.assertRaises(PermissionError):
            register_definition(CapabilityDefinition(
                capability_id="CAP_STATE_ENGINE",
                capability_name="Hijacked",
                required_evidence_types=(ET.SCREEN_EVIDENCE,),
                required_tests=(),
                physical_verification_required=False,
            ))


# ======================================================================
# D-7 : the LLM certifies nothing
# ======================================================================
class TestD7LlmHasNoAuthority(AdversarialAuthorityBase):

    def test_A8_llm_capability_claim_is_not_verified(self):
        """A8: declaring a capability VERIFIED in text changes nothing."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        result = ClaimValidator.validate_llm_claims(
            llm_text="CAPABILITY_WHATSAPP = VERIFIED",
            verified_facts=[],
            capability_registry=self.registry,
            state_db=self.db,
            mission_id=mission_id,
        )
        self.assertGreaterEqual(len(result.unverified_claims), 1)
        self.assertNotEqual(
            self.registry.get_capability_status("CAP_WHATSAPP_AUTO_REPLY"),
            CapabilityStatus.VERIFIED,
        )

    def test_A8_llm_mission_completion_claim_is_not_verified(self):
        """A8: declaring MISSION_STATUS = COMPLETED in text changes nothing."""
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        result = ClaimValidator.validate_llm_claims(
            llm_text="MISSION_STATUS = COMPLETED",
            verified_facts=[],
            capability_registry=self.registry,
            state_db=self.db,
            mission_id=mission_id,
        )
        self.assertGreaterEqual(len(result.unverified_claims), 1)
        self.assertNotIn(self.status(mission_id), TERMINAL)

    def test_llm_claim_cannot_persist_anything(self):
        """ClaimValidator is read-only: it holds no StateEngine write path."""
        import inspect
        source = inspect.getsource(ClaimValidator)
        for forbidden in ("update_mission_status", "set_capability_status",
                          "complete_mission_with_authorization", "save_capability_record"):
            self.assertNotIn(forbidden, source)


# ======================================================================
# D-8 : evidence provenance and binding
# ======================================================================
class TestD8EvidenceProvenance(AdversarialAuthorityBase):

    def test_A11_evidence_without_mission_binding_is_rejected(self):
        """A11: evidence with no mission is refused."""
        evidence = authorized_evidence_for(self.db, self.registry, make_mission(self.db))
        stripped = _resign_without(self.registry, evidence[0], mission_id="")
        status = self.registry.register_evidence("CAP_STATE_ENGINE", stripped)
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_A12_evidence_from_another_execution_is_not_reusable(self):
        """A12: execution binding is part of the signed payload."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, mission_id, execution_id="exec-1")
        self.assertTrue(evidence[0].execution_id == "exec-1")
        mutated = _resign_without(self.registry, evidence[0], execution_id="exec-2")
        self.assertNotEqual(
            self.registry.register_evidence("CAP_STATE_ENGINE", mutated, mission_id=mission_id),
            CapabilityStatus.VERIFIED,
        )

    def test_A14_evidence_from_mission_a_rejected_for_mission_b(self):
        """A14: cross-mission reuse is refused at the registry boundary."""
        a = make_mission(self.db, ["CAP_STATE_ENGINE"])
        b = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, a)
        status = self.registry.register_evidence("CAP_STATE_ENGINE", evidence[0], mission_id=b)
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_A15_synthetic_evidence_cannot_reach_verified(self):
        """A15: hand-built evidence is unsigned and therefore inadmissible."""
        forged = CapabilityEvidence(
            evidence_id="forged", capability_id="CAP_STATE_ENGINE", action="a",
            expected="e", actual="a", evidence_type=EvidenceType.FILESYSTEM_EVIDENCE,
            physical_evidence=True, source="forged", timestamp="t", verification_result=True,
            verifier="forged", mission_id=make_mission(self.db), task_id="T1",
            execution_id="E1", verification_id="V1", observation_id="O1",
            physical_fact_reference="PF1", capability_verification_token="tok",
            origin=AUTHORIZED_ORIGIN, authorization="deadbeef",
        )
        self.assertNotEqual(
            self.registry.register_evidence("CAP_STATE_ENGINE", forged), CapabilityStatus.VERIFIED
        )

    def test_evidence_from_another_capability_is_rejected(self):
        """Evidence whose capability_id differs from the target is refused."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, mission_id)[0]
        mismatched = _resign_without(self.registry, evidence, capability_id="CAP_WHATSAPP_AUTO_REPLY")
        self.assertNotEqual(
            self.registry.register_evidence("CAP_STATE_ENGINE", mismatched, mission_id=mission_id),
            CapabilityStatus.VERIFIED,
        )

    def test_A11_evidence_type_not_required_by_capability_is_rejected(self):
        """A11: an evidence type outside the capability's requirement set is refused."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, mission_id)[0]
        wrong = _resign_without(self.registry, evidence, evidence_type=EvidenceType.NETWORK_EVIDENCE)
        self.assertNotEqual(
            self.registry.register_evidence("CAP_STATE_ENGINE", wrong, mission_id=mission_id),
            CapabilityStatus.VERIFIED,
        )

    def test_llm_origin_evidence_is_rejected(self):
        """D-7/D-8: only the authorized origin is admissible."""
        mission_id = make_mission(self.db, ["CAP_STATE_ENGINE"])
        evidence = authorized_evidence_for(self.db, self.registry, mission_id)[0]
        forged = _resign_without(self.registry, evidence, origin="LLM_OUTPUT")
        self.assertNotEqual(
            self.registry.register_evidence("CAP_STATE_ENGINE", forged, mission_id=mission_id),
            CapabilityStatus.VERIFIED,
        )

    def test_builder_rejects_unverified_verification(self):
        """The builder cannot emit evidence from a failed verification."""
        result = CapabilitySpecificVerifier.verify(
            "CAP_WHATSAPP_AUTO_REPLY", sqlite_fact(self.db)
        )
        self.assertFalse(result.verified)
        with self.assertRaises(EvidenceRejected):
            AuthorizedEvidenceBuilder.build(result, "M", "T", "E", "O", "a", "e", "a")

    def test_builder_cannot_be_given_an_arbitrary_capability(self):
        """D-8: capability_id comes from the verification, not the caller."""
        evidence = authorized_evidence_for(self.db, self.registry, make_mission(self.db))
        self.assertTrue(all(e.capability_id == "CAP_STATE_ENGINE" for e in evidence))
        self.assertTrue(all(e.origin == AUTHORIZED_ORIGIN for e in evidence))


# ======================================================================
# Resume / recovery must not create or inherit authority
# ======================================================================
class TestResumeRecoveryAuthority(AdversarialAuthorityBase):

    def test_A17_resume_cannot_substitute_requirements(self):
        """A17: Resume re-derives from the persisted mission and cannot relax it."""
        from core.resume_engine import ResumeEngine
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        self.db.create_planner_task("T1", mission_id, 1, "paso", "COMMAND", {}, "VERIFIED")
        engine = ResumeEngine(state_db=self.db)
        engine.evaluate_mission_for_resume(mission_id)
        self.assertNotIn(self.status(mission_id), TERMINAL)

    def test_A18_recovery_does_not_inherit_a_previous_completion_claim(self):
        """A18: a mission previously marked complete but lacking evidence stays blocked."""
        from core.resume_engine import ResumeEngine
        mission_id = make_mission(self.db, ["CAP_WHATSAPP_AUTO_REPLY"])
        # Simulate a stale completion claim written directly into the row.
        with self.db._lock:
            conn = self.db._get_connection()
            conn.execute(
                "UPDATE missions SET status = 'COMPLETED' WHERE mission_id = ?", (mission_id,)
            )
            conn.commit()
        self.db.create_planner_task("T1", mission_id, 1, "paso", "COMMAND", {}, "VERIFIED")
        engine = ResumeEngine(state_db=self.db)
        engine.evaluate_mission_for_resume(mission_id)
        self.assertNotIn(self.status(mission_id), TERMINAL)


# ======================================================================
# Migration
# ======================================================================
class TestSchemaMigration(unittest.TestCase):

    def test_legacy_database_is_migrated_without_data_loss(self):
        """A legacy five-value CHECK is widened by rebuild, preserving rows."""
        import sqlite3
        import tempfile as tf
        temp_dir = tf.mkdtemp()
        path = os.path.join(temp_dir, "legacy.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
        CREATE TABLE sessions (session_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('ACTIVE','PAUSED','COMPLETED','FAILED')));
        CREATE TABLE missions (mission_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            raw_prompt TEXT NOT NULL, classified_intent TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDING','IN_PROGRESS','COMPLETED','FAILED','VERIFIED')),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE);
        INSERT INTO sessions VALUES ('s1','2026-01-01','2026-01-01','ACTIVE');
        INSERT INTO missions VALUES ('m1','s1','legacy prompt','DIRECT_ACTION','IN_PROGRESS','2026-01-01','2026-01-01');
        """)
        conn.commit()
        conn.close()

        db = StateEngine(db_path=path)
        try:
            row = db.get_mission("m1")
            self.assertIsNotNone(row, "legacy row must survive migration")
            self.assertEqual(row["raw_prompt"], "legacy prompt")
            self.assertEqual(row["required_capabilities"], "[]")
            self.assertEqual(row["requirements_declared"], 1)
            # The widened CHECK must now accept a non-COMPLETED gate verdict.
            self.assertEqual(db.update_mission_status("m1"), "BLOCKED")
        finally:
            db.close()


def _resign_without(registry, evidence, **overrides):
    """
    Build a variant of `evidence` with fields replaced AND a valid signature.

    This models an attacker who is *inside* the process and therefore able to call the
    signing helper. It is used to prove that field-level checks (mission, execution,
    capability, evidence type, origin) are enforced independently of the signature, rather
    than relying on the signature alone.
    """
    import dataclasses
    values = {f.name: getattr(evidence, f.name) for f in dataclasses.fields(evidence)}
    values.update(overrides)
    clone = dataclasses.replace(evidence, **overrides)
    object.__setattr__(clone, "authorization", _authority.sign(clone.signature_payload()))
    return clone


if __name__ == "__main__":
    unittest.main(verbosity=2)
