"""
Capability evidence registry (D-4, D-7, D-8).

`register_evidence` is now a *validator*, not a decision maker. It accepts evidence only when
every one of the following holds, and otherwise records nothing and reports the capability as
unverified:

  1. the capability is a declared `CapabilityDefinition`;
  2. the evidence object carries a valid internal HMAC signature (it came from
     `AuthorizedEvidenceBuilder`, not from a hand-built dataclass);
  3. `evidence.origin` is the single authorized value;
  4. the evidence's `capability_id` matches the capability being certified;
  5. the evidence's `mission_id` matches the mission being certified (cross-mission reuse);
  6. mission/task/execution/observation/physical-fact references are all present;
  7. the `evidence_type` is one the capability actually requires;
  8. physical evidence is present when the capability demands it.

Status is then *derived* from complete coverage, scoped to a mission. It is never assigned.
`set_capability_status` no longer exists; `set_capability_limitation` can only demote a
capability to a non-verified state and refuses VERIFIED/PARTIAL outright.
"""
from __future__ import annotations

import datetime
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.cognitive import _authority
from core.cognitive.authorized_evidence_builder import (
    AUTHORIZED_ORIGIN,
    CapabilityEvidence,
)
from core.cognitive.capability_definitions import (
    EvidenceType,
    all_definitions,
    get_definition,
    is_known_capability,
)
from core.state_db import StateEngine


class CapabilityStatus:
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    IMPLEMENTED_NOT_INTEGRATED = "IMPLEMENTED_NOT_INTEGRATED"
    SIMULATED_ONLY = "SIMULATED_ONLY"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    BLOCKED_SECURITY = "BLOCKED_SECURITY"
    BLOCKED_INFRASTRUCTURE = "BLOCKED_INFRASTRUCTURE"


#: States a caller may impose on a capability. VERIFIED and PARTIAL are excluded on purpose:
#: they are derived from evidence coverage and must never be assignable.
CALLER_ASSIGNABLE_STATUSES = frozenset(
    {
        CapabilityStatus.NOT_IMPLEMENTED,
        CapabilityStatus.BLOCKED_EXTERNAL,
        CapabilityStatus.BLOCKED_SECURITY,
        CapabilityStatus.BLOCKED_INFRASTRUCTURE,
        CapabilityStatus.SIMULATED_ONLY,
        CapabilityStatus.IMPLEMENTED_NOT_INTEGRATED,
    }
)


class EvidenceRejection:
    NO_DEFINITION = "CAPABILITY_NOT_DEFINED"
    CAPABILITY_MISMATCH = "EVIDENCE_CAPABILITY_MISMATCH"
    MISSION_MISMATCH = "CROSS_MISSION_EVIDENCE_REJECTED"
    UNAUTHORIZED_ORIGIN = "UNAUTHORIZED_EVIDENCE_ORIGIN"
    INVALID_SIGNATURE = "EVIDENCE_SIGNATURE_INVALID"
    MISSING_BINDING = "EVIDENCE_BINDING_INCOMPLETE"
    MISSING_PHYSICAL_FACT = "EVIDENCE_NOT_LINKED_TO_PHYSICAL_FACT"
    EVIDENCE_TYPE_NOT_REQUIRED = "EVIDENCE_TYPE_NOT_REQUIRED_BY_CAPABILITY"
    NOT_PHYSICAL = "PHYSICAL_EVIDENCE_REQUIRED"


@dataclass
class CapabilityRecord:
    capability_id: str
    capability_name: str
    required_evidence: List[str]
    required_tests: List[str]
    physical_verification_required: bool
    verification_status: str = CapabilityStatus.NOT_IMPLEMENTED
    evidence_ids: List[Any] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    last_verified_at: Optional[str] = None


class CapabilityEvidenceRegistry:
    """
    Registro Estructurado de Evidencia de Capacidades.
    Mantiene la autoridad epistemológica determinista sobre el estado de cada capacidad,
    impidiendo que el LLM —o cualquier caller— auto-certifique características.
    """

    #: Retained shape for callers that introspect the default set.
    DEFAULT_CAPABILITIES: Dict[str, Dict[str, Any]] = {
        d.capability_id: {
            "capability_name": d.capability_name,
            "required_evidence": list(d.required_evidence_types),
            "required_tests": list(d.required_tests),
            "physical_verification_required": d.physical_verification_required,
        }
        for d in all_definitions()
    }

    def __init__(self, state_db: Optional[StateEngine] = None):
        self.state_db = state_db or StateEngine()
        # register_evidence lee el expediente, lo muta y lo guarda. El candado de
        # StateEngine se suelta entre esas dos llamadas, así que dos hilos pueden
        # guardar cada uno una copia vieja y borrar la evidencia del otro.
        self._evidence_lock = threading.Lock()
        self._init_default_capabilities()

    # ------------------------------------------------------------------
    # initialisation
    # ------------------------------------------------------------------
    def _init_default_capabilities(self):
        for definition in all_definitions():
            if self.state_db.get_capability_record(definition.capability_id):
                continue
            self.state_db.save_capability_record(
                {
                    "capability_id": definition.capability_id,
                    "capability_name": definition.capability_name,
                    "required_evidence": list(definition.required_evidence_types),
                    "required_tests": list(definition.required_tests),
                    "physical_verification_required": definition.physical_verification_required,
                    "verification_status": CapabilityStatus.NOT_IMPLEMENTED,
                    "evidence_ids": [],
                    "limitations": list(definition.limitations),
                    "dependencies": [],
                    "last_verified_at": "",
                }
            )

    # ------------------------------------------------------------------
    # evidence admission
    # ------------------------------------------------------------------
    def _validate(self, capability_id: str, evidence, mission_id: Optional[str]) -> Optional[str]:
        """Return a rejection reason, or None when the evidence is admissible."""
        definition = get_definition(capability_id)
        if definition is None:
            return EvidenceRejection.NO_DEFINITION
        if not isinstance(evidence, CapabilityEvidence):
            return EvidenceRejection.INVALID_SIGNATURE
        if evidence.origin != AUTHORIZED_ORIGIN:
            return EvidenceRejection.UNAUTHORIZED_ORIGIN
        if not evidence.is_authentic():
            return EvidenceRejection.INVALID_SIGNATURE
        if evidence.capability_id != capability_id:
            return EvidenceRejection.CAPABILITY_MISMATCH

        target_mission = mission_id or evidence.mission_id
        if not target_mission or not evidence.mission_id:
            return EvidenceRejection.MISSING_BINDING
        if evidence.mission_id != target_mission:
            return EvidenceRejection.MISSION_MISMATCH

        for binding in ("task_id", "execution_id", "observation_id"):
            if not getattr(evidence, binding):
                return EvidenceRejection.MISSING_BINDING
        if not evidence.physical_fact_reference or not evidence.capability_verification_token:
            return EvidenceRejection.MISSING_PHYSICAL_FACT

        # D-8: provenance must be *real*, not merely present. The referenced physical fact and
        # the capability-verification token must both correspond to an observation the
        # authorized observer actually recorded, and that observation must be bound to this
        # mission. A caller who leaks the signing key can produce a valid signature, but
        # cannot produce a matching ledger entry, so fabricated evidence is still refused.
        from core.cognitive.authority_core import LEDGER, AuthorityRejection as _AR
        if not LEDGER.has_verification_token(evidence.capability_verification_token):
            return _AR.OBSERVATION_NOT_IN_LEDGER
        observation = LEDGER.observation_for_token(evidence.capability_verification_token)
        if observation is None:
            return _AR.OBSERVATION_NOT_IN_LEDGER
        bound = LEDGER.consumption_of(observation.sequence)
        if bound is not None and bound[0] != target_mission:
            return _AR.MISSION_MISMATCH
        if observation.capability_id and observation.capability_id != capability_id:
            return _AR.CAPABILITY_MISMATCH
        if observation.execution_id and evidence.execution_id and observation.execution_id != evidence.execution_id:
            return _AR.EXECUTION_MISMATCH

        if not evidence.physical_evidence:
            return EvidenceRejection.NOT_PHYSICAL
        if not definition.requires_evidence_type(evidence.evidence_type):
            return EvidenceRejection.EVIDENCE_TYPE_NOT_REQUIRED
        return None

    def register_evidence(
        self,
        capability_id: str,
        evidence,
        mission_id: Optional[str] = None,
    ) -> str:
        """
        Admit evidence for `capability_id` and return the resulting derived status.

        `mission_id` is the mission being certified. Passing a mission different from the one
        the evidence was bound to is rejected, which is what prevents cross-mission reuse.
        """
        with self._evidence_lock:
            return self._register_evidence_locked(capability_id, evidence, mission_id)

    def _register_evidence_locked(
        self,
        capability_id: str,
        evidence,
        mission_id: Optional[str] = None,
    ) -> str:
        rejection = self._validate(capability_id, evidence, mission_id)
        record = self._load_record(capability_id)
        if rejection is not None:
            self._record_rejection(record, rejection, capability_id)
            self.state_db.save_capability_record(record)
            return self._derive_status(record, mission_id or getattr(evidence, "mission_id", None))

        entry = {
            "id": evidence.evidence_id,
            "type": evidence.evidence_type,
            "physical": True,
            "verified": True,
            "mission_id": evidence.mission_id,
            "task_id": evidence.task_id,
            "execution_id": evidence.execution_id,
            "observation_id": evidence.observation_id,
            "verification_id": evidence.verification_id,
            "physical_fact_reference": evidence.physical_fact_reference,
            "verifier": evidence.verifier,
            "origin": evidence.origin,
        }
        entries = [e for e in (record.get("evidence_ids") or [])
                   if not (isinstance(e, dict) and e.get("id") == evidence.evidence_id)]
        entries.append(entry)
        record["evidence_ids"] = entries
        record["last_verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record["limitations"] = [
            l for l in record.get("limitations", [])
            if not l.startswith("Falta evidencia física requerida")
        ]
        status = self._derive_status(record, mission_id or evidence.mission_id)
        record["verification_status"] = self._derive_status(record, None)
        self.state_db.save_capability_record(record)
        return status

    def _record_rejection(self, record: Dict[str, Any], reason: str, capability_id: str) -> None:
        message = f"Evidencia rechazada ({reason}) para {capability_id}"
        if message not in record.get("limitations", []):
            record.setdefault("limitations", []).append(message)

    def _load_record(self, capability_id: str) -> Dict[str, Any]:
        record = self.state_db.get_capability_record(capability_id)
        if record:
            return record
        definition = get_definition(capability_id)
        return {
            "capability_id": capability_id,
            "capability_name": definition.capability_name if definition else capability_id,
            "required_evidence": list(definition.required_evidence_types) if definition else [],
            "required_tests": list(definition.required_tests) if definition else [],
            "physical_verification_required": bool(definition.physical_verification_required) if definition else True,
            "verification_status": CapabilityStatus.NOT_IMPLEMENTED,
            "evidence_ids": [],
            "limitations": [],
            "dependencies": [],
            "last_verified_at": "",
        }

    # ------------------------------------------------------------------
    # derived status
    # ------------------------------------------------------------------
    def _derive_status(self, record: Dict[str, Any], mission_id: Optional[str]) -> str:
        """
        Derive a capability's status from complete coverage of its required evidence types.

        When `mission_id` is given the computation is scoped to evidence bound to that
        mission, so a capability verified while serving one mission does not certify another.
        """
        required = set(record.get("required_evidence") or [])
        if not required:
            return CapabilityStatus.NOT_IMPLEMENTED
        present = set()
        for item in record.get("evidence_ids") or []:
            if not isinstance(item, dict):
                continue
            if mission_id is not None and item.get("mission_id") != mission_id:
                continue
            if item.get("verified") and item.get("physical") and item.get("type") in required:
                present.add(item["type"])
        if not present:
            return CapabilityStatus.NOT_IMPLEMENTED
        if required.issubset(present):
            return CapabilityStatus.VERIFIED
        return CapabilityStatus.PARTIAL

    def get_capability_status(self, capability_id: str, mission_id: Optional[str] = None) -> str:
        """
        Return the *derived* status. The persisted `verification_status` column is never
        trusted for this decision; it is recomputed from admitted evidence every time.
        """
        record = self.state_db.get_capability_record(capability_id)
        if record is None:
            return CapabilityStatus.NOT_IMPLEMENTED
        return self._derive_status(record, mission_id)

    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        records = self.state_db.get_all_capability_records()
        out = []
        for record in records:
            copy = dict(record)
            copy["verification_status"] = self._derive_status(record, None)
            out.append(copy)
        return out

    # ------------------------------------------------------------------
    # limitations
    # ------------------------------------------------------------------
    def set_capability_limitation(
        self,
        capability_id: str,
        status: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Impose a non-verified limitation on a capability.

        D-4: there is no longer any API that can set VERIFIED. Attempting to set VERIFIED or
        PARTIAL raises, because those states are derived from evidence coverage only.
        """
        if status not in CALLER_ASSIGNABLE_STATUSES:
            raise PermissionError(
                f"'{status}' is a derived state and cannot be assigned. "
                "It may only result from capability-specific verification with complete "
                "evidence coverage."
            )
        record = self.state_db.get_capability_record(capability_id)
        if record is None:
            return
        record["verification_status"] = status
        if reason and reason not in record.get("limitations", []):
            record.setdefault("limitations", []).append(reason)
        self.state_db.save_capability_record(record)

    # Backwards-compatible alias that now refuses derived states loudly.
    def set_capability_status(self, capability_id: str, status: str, reason: Optional[str] = None) -> None:
        self.set_capability_limitation(capability_id, status, reason)
