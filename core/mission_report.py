"""Estado de misión calculado desde evidencia (spec 003, U6).

El modelo no elige el estado. Si falta evidencia, no hay COMPLETED_VERIFIED.
"""
from __future__ import annotations

from typing import Any, Dict, List

STATUSES = (
    "COMPLETED_VERIFIED",
    "COMPLETED_WITH_LIMITATIONS",
    "PARTIALLY_COMPLETED",
    "BLOCKED",
    "WAITING_FOR_AUTHORIZATION",
    "FAILED",
    "ABORTED",
    "UNVERIFIED",
)


def compute_status(evidence: Dict[str, Any]) -> str:
    """evidence: criteria -> bool, más claves de control opcionales."""
    if evidence.get("aborted"):
        return "ABORTED"
    if evidence.get("waiting_authorization"):
        return "WAITING_FOR_AUTHORIZATION"
    if evidence.get("blocked"):
        return "BLOCKED"
    if evidence.get("failed"):
        return "FAILED"
    criteria: Dict[str, bool] = dict(evidence.get("criteria") or {})
    if not criteria:
        return "UNVERIFIED"
    met = [ok for ok in criteria.values() if ok]
    missed = [name for name, ok in criteria.items() if not ok]
    if missed and met:
        return "PARTIALLY_COMPLETED"
    if missed and not met:
        return "FAILED"
    if evidence.get("limitations"):
        return "COMPLETED_WITH_LIMITATIONS"
    return "COMPLETED_VERIFIED"


def render_report(objective: str, evidence: Dict[str, Any], *,
                  actions: List[str], pending: List[str]) -> Dict[str, Any]:
    status = compute_status(evidence)
    claimed = evidence.get("model_claims_success")
    return {
        "objective": objective,
        "status": status,
        "actions": list(actions),
        "pending": list(pending),
        "limitations": list(evidence.get("limitations") or []),
        "model_claim_ignored": bool(claimed) and status != "COMPLETED_VERIFIED",
    }
