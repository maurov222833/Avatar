"""
Shared gate vocabulary.

Separated from `mission_completion_gate` so that `gate_authorization` can depend on the
result type without creating a circular import, and so that no module can reach the
authorization issuer by importing a side-effectful gate module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class MissionStatus:
    """Terminal and non-terminal mission states produced by the gate."""

    MISSION_COMPLETED = "MISSION_COMPLETED"
    COMPLETED_WITH_BLOCKING_FINDINGS = "COMPLETED_WITH_BLOCKING_FINDINGS"
    COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"
    BLOCKED = "BLOCKED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    NO_REQUIREMENTS_DECLARED = "NO_REQUIREMENTS_DECLARED"


#: States a mission may hold. Mirrors the SQLite CHECK constraint and is the single
#: source of truth for both the gate and the persistence layer.
MISSION_STATUS_VALUES = (
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    "VERIFIED",
    "COMPLETED_WITH_BLOCKING_FINDINGS",
    "COMPLETED_WITH_FINDINGS",
    "PARTIALLY_COMPLETED",
    "BLOCKED",
    "NO_REQUIREMENTS_DECLARED",
)

#: States in which a mission is considered finished. `create_mission` must refuse these:
#: reaching a terminal state requires a GateAuthorization.
TERMINAL_MISSION_STATUSES = frozenset(
    {
        "COMPLETED",
        "VERIFIED",
        "COMPLETED_WITH_BLOCKING_FINDINGS",
        "COMPLETED_WITH_FINDINGS",
        "PARTIALLY_COMPLETED",
        "BLOCKED",
        "FAILED",
    }
)

#: Legal initial states for a newly created mission.
INITIAL_MISSION_STATUSES = frozenset({"PENDING", "IN_PROGRESS"})


@dataclass(frozen=True)
class MissionGateResult:
    """Immutable verdict of a deterministic gate evaluation."""

    can_complete: bool
    mission_status: str
    blocking_reasons: List[str] = field(default_factory=list)
    unverified_required_capabilities: List[str] = field(default_factory=list)
    critical_gaps_count: int = 0
    blocking_findings_count: int = 0
    open_findings_count: int = 0
    evaluation_id: Optional[str] = None

    def verdict_signature(self) -> tuple:
        """Fields that a GateAuthorization must reproduce exactly."""
        return (
            self.can_complete,
            self.mission_status,
            tuple(self.blocking_reasons),
            tuple(self.unverified_required_capabilities),
            self.critical_gaps_count,
            self.blocking_findings_count,
            self.open_findings_count,
        )
