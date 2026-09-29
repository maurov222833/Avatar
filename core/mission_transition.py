"""Mission state transition with acceptance criteria (F-10 / Fase 4).

Replaces the production meaning of "misión completada":

* Acceptance criteria are **data** on the mission row.
* Without criteria the mission may only finish as ``REPORTED`` (turn finished,
  goal not proven) — never ``COMPLETED``.
* A ``DENIED`` / ``FAILED`` act never satisfies a success criterion.
* HMAC / capability-registry machinery stays available for legacy tests, but
  the live orchestrator settles missions through this module.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


#: Criterion kinds the transition function understands.
CRITERION_ACT_OBSERVED = "act_observed"      # need an OBSERVED/EXECUTED act of this type
CRITERION_ACT_NOT_DENIED = "act_not_denied"  # no DENIED/FAILED of this type
CRITERION_FILE_EXISTS = "file_exists"        # path exists on disk


@dataclass(frozen=True)
class TransitionVerdict:
    status: str
    reasons: List[str] = field(default_factory=list)
    satisfied: List[str] = field(default_factory=list)
    unmet: List[str] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.status == "COMPLETED"


def parse_acceptance_criteria(raw: Any) -> List[Dict[str, Any]]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if isinstance(raw, dict):
        # Allow {"all_of": [...]} or a single criterion object.
        if "all_of" in raw and isinstance(raw["all_of"], list):
            return [c for c in raw["all_of"] if isinstance(c, dict)]
        if "type" in raw or "kind" in raw:
            return [raw]
        return []
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    return []


def derive_acceptance_criteria(user_input: str, tool_summary: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Best-effort criteria from what the turn actually did.

    If the agent ran side-effect tools, require those acts to be OBSERVED.
    Pure conversation / empty turns yield no criteria → REPORTED.
    """
    criteria: List[Dict[str, Any]] = []
    seen = set()
    for entry in tool_summary or []:
        name = (entry.get("tool_name") or entry.get("act_type") or "").upper()
        if not name or name in seen:
            continue
        # Reads alone do not prove a goal was completed.
        if name in ("READ_FILE", "LIST_DIR", "WEB_SEARCH", "FETCH_URL",
                    "WHATSAPP_STATUS", "WHATSAPP_READ", "SCREEN_CAPTURE"):
            continue
        seen.add(name)
        criteria.append({"type": CRITERION_ACT_OBSERVED, "act_type": name})
        criteria.append({"type": CRITERION_ACT_NOT_DENIED, "act_type": name})
    return criteria


def _acts_by_type(acts: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for act in acts or []:
        out.setdefault(str(act.get("act_type") or ""), []).append(act)
    return out


def criterion_satisfied(criterion: Dict[str, Any], acts: Sequence[Dict[str, Any]]) -> bool:
    kind = (criterion.get("type") or criterion.get("kind") or "").lower()
    by_type = _acts_by_type(acts)
    if kind == CRITERION_ACT_OBSERVED:
        act_type = str(criterion.get("act_type") or "")
        for act in by_type.get(act_type, []):
            status = act.get("status")
            if status in ("OBSERVED", "EXECUTED") and status not in ("DENIED", "FAILED"):
                return True
        return False
    if kind == CRITERION_ACT_NOT_DENIED:
        act_type = str(criterion.get("act_type") or "")
        for act in by_type.get(act_type, []):
            if act.get("status") in ("DENIED", "FAILED", "PENDING_APPROVAL"):
                return False
        # Vacuous truth only if at least one successful attempt exists, or none attempted.
        # If none attempted, the paired act_observed criterion fails separately.
        return True
    if kind == CRITERION_FILE_EXISTS:
        path = criterion.get("path") or criterion.get("file_path") or ""
        return bool(path) and os.path.isfile(str(path))
    return False


def evaluate_transition(
    *,
    acceptance_criteria: Any,
    acts: Sequence[Dict[str, Any]],
) -> TransitionVerdict:
    """
    Single transition function (F-10 invariants).

    * No criteria → REPORTED (never COMPLETED).
    * All criteria satisfied → COMPLETED.
    * Otherwise → BLOCKED with unmet list.
    """
    criteria = parse_acceptance_criteria(acceptance_criteria)
    if not criteria:
        return TransitionVerdict(
            status="REPORTED",
            reasons=["NO_ACCEPTANCE_CRITERIA: el turno terminó sin criterios de aceptación; "
                     "no se puede afirmar COMPLETED."],
        )

    satisfied: List[str] = []
    unmet: List[str] = []
    for crit in criteria:
        label = json.dumps(crit, ensure_ascii=False, sort_keys=True)
        if criterion_satisfied(crit, acts):
            satisfied.append(label)
        else:
            unmet.append(label)

    if unmet:
        return TransitionVerdict(
            status="BLOCKED",
            reasons=["ACCEPTANCE_CRITERIA_UNMET"],
            satisfied=satisfied,
            unmet=unmet,
        )
    return TransitionVerdict(
        status="COMPLETED",
        reasons=["ALL_ACCEPTANCE_CRITERIA_MET"],
        satisfied=satisfied,
        unmet=[],
    )


def settle_mission(
    state_db,
    mission_id: str,
    *,
    acts: Optional[Sequence[Dict[str, Any]]] = None,
    chokepoint=None,
) -> TransitionVerdict:
    """Persist the transition verdict onto the mission row (bypasses HMAC gate)."""
    mission = state_db.get_mission(mission_id) if state_db else None
    if not mission:
        return TransitionVerdict(status="BLOCKED", reasons=["MISSION_NOT_FOUND"])

    if acts is None:
        acts = []
        if chokepoint is not None:
            try:
                acts = chokepoint.list_acts(mission_id=mission_id)
            except Exception:
                acts = []

    criteria = mission.get("acceptance_criteria")
    verdict = evaluate_transition(acceptance_criteria=criteria, acts=acts)
    try:
        state_db.set_mission_terminal_status(mission_id, verdict.status)
    except Exception:
        # Fallback for older DBs mid-migration: update_mission_status path may refuse.
        try:
            state_db._force_mission_status(mission_id, verdict.status)
        except Exception:
            pass
    return verdict
