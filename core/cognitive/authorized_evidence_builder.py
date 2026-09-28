"""
Authorized evidence construction (D-8).

This module is no longer a function of caller-supplied data. It is a pure projection of a
`CapabilityVerificationResult`, which only `CapabilitySpecificVerifier` can produce.

Consequences, all intentional:
  * the caller cannot choose `capability_id`   -> it comes from the verification result;
  * the caller cannot choose `evidence_type`   -> it comes from the verified satisfied set;
  * the caller cannot assert `physical_evidence` -> it is True only because a capability-
    specific verifier inspected a real observation and said so;
  * every emitted object carries an HMAC signature that the registry verifies, so evidence
    cannot be fabricated by constructing the dataclass directly.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.cognitive import _authority
from core.cognitive.authority_core import LEDGER
from core.cognitive.capability_specific_verifier import CapabilityVerificationResult

#: The only origin the registry will accept. There is deliberately no LLM/test/synthetic value.
AUTHORIZED_ORIGIN = "CAPABILITY_SPECIFIC_VERIFIER"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass(frozen=True)
class CapabilityEvidence:
    """
    Immutable, signed evidence of a capability-specific verification.

    The dataclass is frozen and every field participates in the signature, so any mutation,
    reconstruction or substitution invalidates `authorization`.
    """

    evidence_id: str
    capability_id: str
    action: str
    expected: str
    actual: str
    evidence_type: str
    physical_evidence: bool
    source: str
    timestamp: str
    verification_result: bool
    verifier: str
    mission_id: str = ""
    task_id: str = ""
    execution_id: str = ""
    verification_id: str = ""
    observation_id: str = ""
    physical_fact_reference: str = ""
    capability_verification_token: str = ""
    origin: str = "UNKNOWN"
    authorization: str = ""

    def signature_payload(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "capability_id": self.capability_id,
            "action": self.action,
            "expected": self.expected,
            "actual": self.actual,
            "evidence_type": self.evidence_type,
            "physical_evidence": self.physical_evidence,
            "source": self.source,
            "verification_result": self.verification_result,
            "verifier": self.verifier,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "verification_id": self.verification_id,
            "observation_id": self.observation_id,
            "physical_fact_reference": self.physical_fact_reference,
            "capability_verification_token": self.capability_verification_token,
            "origin": self.origin,
        }

    def is_authentic(self) -> bool:
        return _authority.verify_signature(self.signature_payload(), self.authorization)


class EvidenceRejected(ValueError):
    """Raised when evidence cannot be constructed from the supplied verification."""


class AuthorizedEvidenceBuilder:
    """
    Único componente autorizado para crear CapabilityEvidence válidos.

    La evidencia es una proyección de una verificación específica de capability. No decide
    qué capability fue demostrada ni qué tipo de evidencia produjo.
    """

    @staticmethod
    def build(
        verification: CapabilityVerificationResult,
        mission_id: str,
        task_id: str,
        execution_id: str,
        observation_id: str,
        action: str,
        expected: str,
        actual: str,
    ) -> List[CapabilityEvidence]:
        """
        Project a successful capability verification into one signed evidence record per
        required evidence type the verification actually satisfied.
        """
        if not isinstance(verification, CapabilityVerificationResult):
            raise EvidenceRejected("A CapabilityVerificationResult is required.")
        if not verification.verified:
            raise EvidenceRejected(f"Verification did not succeed: {verification.reason}")
        if not verification.evidence_types_satisfied:
            raise EvidenceRejected("Verification satisfied no required evidence type.")
        for field_name in ("mission_id", "task_id", "execution_id", "observation_id"):
            if not locals()[field_name]:
                raise EvidenceRejected(f"{field_name} is required for authorized evidence.")

        out: List[CapabilityEvidence] = []
        for evidence_type in verification.evidence_types_satisfied:
            ev = CapabilityEvidence(
                evidence_id=f"ev-{verification.fact_id}-{evidence_type}",
                capability_id=verification.capability_id,
                action=action,
                expected=expected,
                actual=actual,
                evidence_type=evidence_type,
                physical_evidence=True,
                source=f"{verification.verifier_id}:{verification.fact_id}",
                timestamp=_now(),
                verification_result=True,
                verifier=verification.verifier_id,
                mission_id=mission_id,
                task_id=task_id,
                execution_id=execution_id,
                verification_id=verification.authorization_token(),
                observation_id=observation_id,
                physical_fact_reference=verification.fact_id,
                capability_verification_token=verification.authorization_token(),
                origin=AUTHORIZED_ORIGIN,
            )
            # Bind the token to the observation that actually produced it. Evidence that does
            # not carry a live token-to-observation link is refused at registry admission.
            LEDGER.link_verification(verification.authorization_token(),
                                     verification.observation_sequence)
            object.__setattr__(ev, "authorization", _authority.sign(ev.signature_payload()))
            out.append(ev)
        return out

    @staticmethod
    def build_for_capability(
        capability_id: str,
        fact,
        mission_id: str,
        task_id: str,
        execution_id: str,
        observation_id: Optional[str] = None,
        action: str = "capability_operation",
        expected: str = "capability-specific verification",
        actual: str = "observed",
        expected_resource: Optional[str] = None,
    ) -> List[CapabilityEvidence]:
        """
        Verify the fact for `capability_id`, then build signed evidence from it.

        Three independent controls apply, so this cannot be used as a signing oracle:

        1. `capability_id` is a *question*, not an answer — the verifier independently rejects
           a fact whose subject or type does not match.
        2. The fact must be backed by a real recorded observation (ledger provenance), so a
           hand-built `VerifiedPhysicalFact` cannot get this far.
        3. The observation is **consumed** and bound to this (mission, execution). Re-using
           one observation to certify a second mission, or a second execution, is refused.
        """
        from core.cognitive.authority_core import LEDGER, AuthorityRejection
        from core.cognitive.capability_specific_verifier import CapabilitySpecificVerifier

        if not mission_id or not task_id or not execution_id:
            raise EvidenceRejected("mission_id, task_id and execution_id are required.")

        # (2) provenance, before anything is signed
        provenance_error = LEDGER.validate_fact(fact)
        if provenance_error is not None:
            raise EvidenceRejected(f"{capability_id}: {provenance_error}")

        verification = CapabilitySpecificVerifier.verify(
            capability_id, fact, execution_id=execution_id, mission_id=mission_id,
            expected_resource=expected_resource,
        )
        if not verification.verified:
            raise EvidenceRejected(f"{capability_id}: {verification.reason}")

        # (3) single-use consumption bound to this mission and execution
        consumption_error = LEDGER.consume(fact, mission_id, execution_id)
        if consumption_error is not None:
            raise EvidenceRejected(f"{capability_id}: {consumption_error}")

        return AuthorizedEvidenceBuilder.build(
            verification=verification,
            mission_id=mission_id,
            task_id=task_id,
            execution_id=execution_id,
            observation_id=observation_id or verification.fact_id,
            action=action,
            expected=expected,
            actual=actual,
        )
