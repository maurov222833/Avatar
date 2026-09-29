"""
Mission completion gate (D-1, D-5, D-7).

Two changes of substance:

  * **D-1** — there is no longer a public `create_authorization(result)`. The only way to
    obtain a `GateAuthorization` is `evaluate_and_authorize`, which reads the mission's
    persisted requirements, evaluates them, and issues the authorization itself. A caller can
    ask a question; it cannot hand the gate an answer.

  * **D-5** — requirements are sovereign and come from the persisted mission row. The gate
    does not accept requirements from a caller, and `allow_empty_requirements` is gone. A
    mission that genuinely requires no capabilities must say so as a persisted, verifiable
    property of the mission (`requirements_declared = 0`), not via an argument that evades
    evaluation. A mission that declares requirements and supplies an empty list is BLOCKED,
    because that is a declaration failure rather than a legitimate empty requirement set.

Capability status is evaluated per mission, so evidence gathered while serving one mission
cannot certify another.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from core.cognitive import _authority
from core.cognitive.capability_registry import CapabilityEvidenceRegistry, CapabilityStatus
from core.cognitive.capability_definitions import can_satisfy_requirement
from core.cognitive.gate_authorization import GateAuthorization
from core.cognitive.gate_types import MissionGateResult, MissionStatus
from core.state_db import StateEngine


def requirements_from_row(row: Optional[Dict[str, Any]]) -> Tuple[List[str], bool]:
    """Requirements as stored on one mission row. A missing row is not a declared empty set."""
    if not row:
        return [], False
    raw = row.get("required_capabilities")
    if isinstance(raw, str):
        try:
            caps = json.loads(raw)
        except Exception:
            caps = []
    elif isinstance(raw, (list, tuple)):
        caps = list(raw)
    else:
        caps = []
    declared = bool(row.get("requirements_declared", 1))
    return [str(c) for c in caps], declared


def read_mission_requirements(state_db: StateEngine, mission_id: str) -> Tuple[List[str], bool]:
    """
    Read the sovereign requirement set for a mission.

    Returns `(required_capabilities, requirements_declared)`. When the mission row is absent
    an empty, *declared* requirement set is not assumed: the caller must handle the missing
    mission explicitly.
    """
    return requirements_from_row(state_db.get_mission(mission_id))


def requirements_are_intact(state_db: StateEngine, mission_id: str) -> bool:
    """
    D-5: True only when this process sealed the requirements and the HMAC still matches.

    A same-process mismatch blocks completion. It is explicitly *not* downgraded to
    `NO_REQUIREMENTS_DECLARED`. A seal from another process is unverified, not intact,
    and is not by itself a corruption.
    """
    row = state_db.get_mission(mission_id)
    if not row:
        return False
    try:
        return state_db.requirements_seal_state(row) == "intact"
    except Exception:
        return False


class MissionCompletionGate:
    @staticmethod
    def evaluate_mission_completion(
        mission_id: str,
        required_capabilities: List[str],
        critical_gaps: int = 0,
        blocking_findings: int = 0,
        open_findings: int = 0,
        capability_registry: Optional[CapabilityEvidenceRegistry] = None,
        state_db: Optional[StateEngine] = None,
        requirements_declared: bool = True,
    ) -> MissionGateResult:
        """
        Deterministic evaluation of a mission's completion.

        Read-only: this returns a verdict and confers no authority. Authority is issued
        exclusively by `evaluate_and_authorize`.
        """
        registry = capability_registry or CapabilityEvidenceRegistry(state_db=state_db)
        blocking_reasons: List[str] = []
        unverified_caps: List[str] = []

        if not requirements_declared:
            # The mission explicitly declares that it requires no capabilities.
            pass
        elif not required_capabilities:
            all_caps = registry.get_all_capabilities()
            if all_caps:
                blocking_reasons.append(
                    "La misión declara requirements pero la lista persistida está vacía. "
                    "Una lista vacía no puede usarse para evadir la evaluación."
                )
        else:
            for cap_id in required_capabilities:
                # A capability registered at runtime can be modelled and scored by the
                # registry, but it may never satisfy a mission requirement. Without this,
                # a caller could register a capability plus a permissive verifier, declare
                # a mission that requires it, and complete that mission on self-issued
                # evidence.
                if not can_satisfy_requirement(cap_id):
                    unverified_caps.append(f"{cap_id} (NOT_APPROVED_FOR_REQUIREMENTS)")
                    continue
                status = registry.get_capability_status(cap_id, mission_id=mission_id)
                if status != CapabilityStatus.VERIFIED:
                    unverified_caps.append(f"{cap_id} ({status})")

        if unverified_caps:
            blocking_reasons.append(
                "Capacidades requeridas no verificadas físicamente: " + ", ".join(unverified_caps)
            )
        if critical_gaps > 0:
            blocking_reasons.append(f"Existen {critical_gaps} brecha(s) crítica(s) no resuelta(s).")
        if blocking_findings > 0:
            blocking_reasons.append(
                f"Existen {blocking_findings} hallazgo(s) bloqueante(s) pendiente(s)."
            )

        can_complete = len(blocking_reasons) == 0

        if can_complete:
            if open_findings > 0:
                final_status = MissionStatus.COMPLETED_WITH_FINDINGS
            elif not requirements_declared:
                final_status = MissionStatus.NO_REQUIREMENTS_DECLARED
            else:
                final_status = MissionStatus.MISSION_COMPLETED
        else:
            if critical_gaps > 0 or blocking_findings > 0:
                final_status = MissionStatus.COMPLETED_WITH_BLOCKING_FINDINGS
            elif unverified_caps:
                final_status = MissionStatus.PARTIALLY_COMPLETED
            elif not requirements_declared or required_capabilities:
                final_status = MissionStatus.BLOCKED
            else:
                final_status = MissionStatus.BLOCKED

        return MissionGateResult(
            can_complete=can_complete,
            mission_status=final_status,
            blocking_reasons=blocking_reasons,
            unverified_required_capabilities=unverified_caps,
            critical_gaps_count=critical_gaps,
            blocking_findings_count=blocking_findings,
            open_findings_count=open_findings,
            evaluation_id=_authority.new_nonce(),
        )

    @staticmethod
    def _reject_corrupt_requirements(
        mission_id: str, required_capabilities: List[str]
    ) -> GateAuthorization:
        """
        Issue a BLOCKED authorization for a mission whose requirement set is not intact.

        The mission is blocked rather than completed or downgraded. The persisted requirement
        list is reported in the blocking reason so the corruption is diagnosable.
        """
        from core.cognitive.authority_core import AuthorityAudit, AuthorityRejection
        verdict = MissionGateResult(
            can_complete=False,
            mission_status=MissionStatus.BLOCKED,
            blocking_reasons=[
                "REQUIREMENTS_INTEGRITY_FAILURE: los requisitos persistidos de la misión no "
                f"coinciden con su sello (persistidos={required_capabilities}). "
                "La finalización está bloqueada."
            ],
            unverified_required_capabilities=list(required_capabilities),
            evaluation_id=_authority.new_nonce(),
        )
        AuthorityAudit.record(
            decision="AUTHORIZATION_ISSUED", subject="requirements_integrity",
            mission_id=mission_id, reason=AuthorityRejection.REQUIREMENTS_INTEGRITY_FAILURE,
        )
        return GateAuthorization._issue(
            mission_id=mission_id,
            required_capabilities=required_capabilities,
            requirements_declared=False,
            evaluation_id=verdict.evaluation_id,
            verdict=verdict,
            authorized_status=MissionStatus.BLOCKED,
        )

    @staticmethod
    def _defer_unverified_requirements(
        mission_id: str, required_capabilities: List[str]
    ) -> GateAuthorization:
        """
        Keep a legacy-sealed mission open.

        The seal cannot be checked, so the mission is not completed and it is not
        rewritten as having no requirements. Resume of pending work still sees an
        open mission.
        """
        verdict = MissionGateResult(
            can_complete=False,
            mission_status="IN_PROGRESS",
            blocking_reasons=[
                "REQUIREMENTS_SEAL_UNVERIFIED: el sello de requisitos es de un formato "
                "anterior y no se puede comprobar. La misión sigue abierta."
            ],
            unverified_required_capabilities=list(required_capabilities),
            evaluation_id=_authority.new_nonce(),
        )
        return GateAuthorization._issue(
            mission_id=mission_id,
            required_capabilities=required_capabilities,
            requirements_declared=True,
            evaluation_id=verdict.evaluation_id,
            verdict=verdict,
            authorized_status="IN_PROGRESS",
        )

    @staticmethod
    def evaluate_and_authorize(
        mission_id: str,
        state_db: StateEngine,
        capability_registry: Optional[CapabilityEvidenceRegistry] = None,
        critical_gaps: int = 0,
        blocking_findings: int = 0,
        open_findings: int = 0,
        execution_id: str = "",
    ) -> GateAuthorization:
        """
        The single authority-issuing path.

        Reads the mission's persisted requirements, evaluates them against current evidence,
        and issues a signed authorization describing the verdict it just computed. There is no
        parameter through which a caller can supply a result.
        """
        required_capabilities, requirements_declared = read_mission_requirements(state_db, mission_id)
        row = state_db.get_mission(mission_id)

        # D-5: a mismatch, a wiped seal, or a seal under some other key blocks completion
        # and is never silently reinterpreted as "no requirements declared". A legacy
        # hex seal is unverified: the mission stays open and is not marked complete.
        seal_state = "tampered" if row is None else state_db.requirements_seal_state(row)
        if seal_state == "tampered":
            return MissionCompletionGate._reject_corrupt_requirements(
                mission_id, required_capabilities
            )
        if seal_state == "unverified":
            return MissionCompletionGate._defer_unverified_requirements(
                mission_id, required_capabilities
            )

        verdict = MissionCompletionGate.evaluate_mission_completion(
            mission_id=mission_id,
            required_capabilities=required_capabilities,
            critical_gaps=critical_gaps,
            blocking_findings=blocking_findings,
            open_findings=open_findings,
            capability_registry=capability_registry or CapabilityEvidenceRegistry(state_db=state_db),
            state_db=state_db,
            requirements_declared=requirements_declared,
        )
        return GateAuthorization._issue(
            mission_id=mission_id,
            required_capabilities=required_capabilities,
            requirements_declared=requirements_declared,
            evaluation_id=verdict.evaluation_id or _authority.new_nonce(),
            verdict=verdict,
            authorized_status=verdict.mission_status,
            execution_id=execution_id,
        )
