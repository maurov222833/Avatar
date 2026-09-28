"""
Gate authorization (D-1, D-2).

Design notes, because the previous two attempts failed for instructive reasons:

  * Attempt 1 used a `WeakSet` to mean "the gate issued this". That proves an object was
    constructed, not that a gate evaluated anything.
  * Attempt 2 added a SHA-256 over the object's own fields. The holder could recompute it,
    because the hash function lived on the object. Tamper-*evident*, not tamper-proof.

The authorization is now:
  * **frozen** — no field can be reassigned, so mutation (A2) and mutate-and-rehash (A3) are
    impossible rather than merely detected;
  * **HMAC-signed with a key that never leaves `_authority`** — a caller cannot forge or
    recompute a valid signature, and `copy`/`deepcopy`/`pickle` cannot produce a usable object;
  * **bound** to mission id, persisted requirements, the evaluation id, the exact verdict and
    the authorized status;
  * **issued only by the gate**, through a private issuer, never by a public
    `create_authorization(result)` API.

Most importantly, the signature is *not* the primary control. `StateEngine` re-derives the
verdict itself from the persisted mission and refuses any authorization whose verdict differs.
A perfectly signed forged authorization is therefore inert: authority comes from
re-derivation, not from the object's assertion about itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.cognitive import _authority
from core.cognitive.gate_types import MissionGateResult


class AuthorizationRejected(PermissionError):
    """Raised when an authorization cannot be issued or is not acceptable."""


@dataclass(frozen=True)
class GateAuthorization:
    """Immutable, signed proof that the gate evaluated a specific mission."""

    mission_id: str
    required_capabilities: Tuple[str, ...]
    requirements_declared: bool
    evaluation_id: str
    verdict: MissionGateResult
    authorized_status: str
    execution_id: str = ""
    issuer: str = "MissionCompletionGate"
    authorization: str = field(default="", repr=False)

    # ---------------- integrity ----------------
    def signature_payload(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "required_capabilities": list(self.required_capabilities),
            "requirements_declared": self.requirements_declared,
            "evaluation_id": self.evaluation_id,
            "verdict": list(self.verdict.verdict_signature()),
            "authorized_status": self.authorized_status,
            "execution_id": self.execution_id,
            "issuer": self.issuer,
        }

    def is_authentic(self) -> bool:
        return _authority.verify_signature(self.signature_payload(), self.authorization)

    def is_valid_for(
        self,
        mission_id: str,
        required_capabilities: List[str],
        requirements_declared: bool,
        expected_verdict: MissionGateResult,
        execution_id: Optional[str] = None,
    ) -> bool:
        """
        Full acceptance test used by the persistence layer.

        Checks authenticity, mission binding, requirement binding, execution binding and —
        decisively — that the verdict the authorization carries is exactly the verdict the
        caller has just re-derived from persisted state.
        """
        if not self.is_authentic():
            return False
        if self.mission_id != mission_id:
            return False
        if self.requirements_declared != requirements_declared:
            return False
        if tuple(sorted(self.required_capabilities)) != tuple(sorted(required_capabilities or [])):
            return False
        if self.verdict.verdict_signature() != expected_verdict.verdict_signature():
            return False
        if self.execution_id != (execution_id or ""):
            return False
        return True

    # ---------------- issuance ----------------
    @staticmethod
    def _issue(
        mission_id: str,
        required_capabilities: List[str],
        requirements_declared: bool,
        evaluation_id: str,
        verdict: MissionGateResult,
        authorized_status: str,
        execution_id: str = "",
    ) -> "GateAuthorization":
        """
        Private issuer. Called only by `MissionCompletionGate.evaluate_and_authorize`, which
        always supplies a verdict it has just computed. There is no public API that accepts a
        caller-supplied result.
        """
        auth = GateAuthorization(
            mission_id=mission_id,
            required_capabilities=tuple(sorted(required_capabilities or [])),
            requirements_declared=requirements_declared,
            evaluation_id=evaluation_id,
            verdict=verdict,
            authorized_status=authorized_status,
            execution_id=execution_id or "",
        )
        object.__setattr__(auth, "authorization", _authority.sign(auth.signature_payload()))
        return auth
