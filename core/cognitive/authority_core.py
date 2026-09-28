"""
Authority core: observation ledger, rejection taxonomy and authority audit.

WHY THIS EXISTS
---------------
IMPLEMENTATION 003 tried to make capability authority depend on a cryptographic key held in
this process. Audit 004 demonstrated that a key stored as a module attribute is readable by
any in-process caller, so the signature proved nothing. A key cannot be a security boundary
inside a single address space.

The primitive used instead is *structural*: a fact is credible only if the authorized
observer actually performed the observation and recorded it here. The caller cannot append to
this ledger, cannot alter a recorded observation, and cannot re-use one observation to certify
two different missions or executions. Fabrication now requires performing the real
observation, which is precisely the thing the boundary is meant to force.

THREAT MODEL (see docs/AUTHORITY_CONSOLIDATION_IMPLEMENTATION_004.md §7)
------------------------------------------------------------------------
* **Model A — ordinary caller.** Uses documented public APIs, does not reach into private
  attributes, does not monkey-patch. The system resists this model: the ledger is only
  appendable by the observation layer, trusted verifiers cannot be replaced, and observations
  are single-use.
* **Model B — arbitrary code with full control of the interpreter.** Can read module
  attributes, mutate the ledger, patch functions, and run SQL. No in-process Python design
  resists this. Guarantees here are explicitly NOT claimed against Model B. Real protection
  would require an out-of-process boundary (separate process + validated IPC, or OS-level
  privilege separation), which is out of scope here and is documented as a recommendation.
"""
from __future__ import annotations

import datetime
import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Rejection taxonomy
# ---------------------------------------------------------------------------
class AuthorityRejection:
    """Stable, machine-readable reasons an authority elevation was refused."""

    UNTRUSTED_VERIFIER = "UNTRUSTED_VERIFIER"
    VERIFIER_ALREADY_REGISTERED = "VERIFIER_ALREADY_REGISTERED"
    PROTECTED_CAPABILITY = "PROTECTED_CAPABILITY"
    UNVERIFIED_PHYSICAL_FACT = "UNVERIFIED_PHYSICAL_FACT"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    OBSERVATION_NOT_IN_LEDGER = "OBSERVATION_NOT_IN_LEDGER"
    OBSERVATION_ALREADY_CONSUMED = "OBSERVATION_ALREADY_CONSUMED"
    OBSERVATION_STATE_MISMATCH = "OBSERVATION_STATE_MISMATCH"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    MISSION_MISMATCH = "MISSION_MISMATCH"
    EXECUTION_MISMATCH = "EXECUTION_MISMATCH"
    EVIDENCE_TYPE_NOT_SATISFIED = "EVIDENCE_TYPE_NOT_SATISFIED"
    FACT_TYPE_NOT_DECLARED = "FACT_TYPE_NOT_DECLARED_FOR_CAPABILITY"
    REQUIREMENTS_INTEGRITY_FAILURE = "REQUIREMENTS_INTEGRITY_FAILURE"
    AUTHORIZATION_INVALID = "AUTHORIZATION_INVALID"
    AUTHORIZATION_STALE = "AUTHORIZATION_STALE"
    LLM_NOT_AUTHORITY = "LLM_NOT_AUTHORITY"
    SYNTHETIC_EVIDENCE_REJECTED = "SYNTHETIC_EVIDENCE_REJECTED"
    UNSUPPORTED_FACT_TYPE = "UNSUPPORTED_FACT_TYPE"
    NOT_A_PHYSICAL_FACT = "NOT_A_VERIFIED_PHYSICAL_FACT"
    DERIVED_STATE_NOT_ASSIGNABLE = "DERIVED_STATE_NOT_ASSIGNABLE"


class AuthorityAudit:
    """
    Append-only, in-memory authority decision log.

    Deliberately does not record secrets, key material, or the content of inspected
    resources — only identifiers, the decision, and the reason. Persisted audit rows are
    written by `StateEngine.record_authority_event`.
    """

    _events = None
    _lock = threading.Lock()

    @classmethod
    def _store(cls):
        if cls._events is None:
            cls._events = []
        return cls._events

    @classmethod
    def record(cls, *, decision: str, subject: str, mission_id: str = "",
               capability_id: str = "", execution_id: str = "", reason: str = "",
               detail: str = "") -> Dict[str, Any]:
        event = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "decision": decision,
            "subject": subject,
            "mission_id": mission_id,
            "capability_id": capability_id,
            "execution_id": execution_id,
            "reason": reason,
            "detail": detail[:200],
        }
        with cls._lock:
            store = cls._store()
            store.append(event)
            if len(store) > 2000:
                del store[:1000]
        return event

    @classmethod
    def events(cls) -> Tuple[Dict[str, Any], ...]:
        with cls._lock:
            return tuple(cls._store())

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._store().clear()


# ---------------------------------------------------------------------------
# Observation ledger
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VerifiedObservation:
    """The observation an authorization token refers to, as seen by the evidence registry."""

    sequence: int
    capability_id: str
    execution_id: str
    fact_type: str
    verified: bool


@dataclass(frozen=True)
class ObservationRecord:
    """An immutable record of one real observation performed by the observer layer."""

    sequence: int
    fact_type: str
    subject: str
    verified: bool
    observed_state: Dict[str, Any]
    execution_id: str
    observer: str
    observed_at: str
    capability_id: str = ""


#: Identity token proving the caller is the authorized observation layer.
#: Model A: not part of the public API. Model B: readable — see the module docstring.
_OBSERVER_TOKEN: object = object()


class ObservationLedger:
    """
    Append-only ledger of real observations, with single-use consumption.

    * Only the authorized observer can append (identity token).
    * A recorded observation's payload is immutable; a fact whose fields disagree with the
      ledger entry is refused, so `observed_state` cannot be edited after the fact.
    * Each observation may certify exactly one (mission, execution) pair. Re-using one
      observation to satisfy a second mission, or a second execution, is refused.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[int, ObservationRecord] = {}
        self._consumed: Dict[int, Tuple[str, str]] = {}
        self._by_token: Dict[str, int] = {}
        self._counter = itertools.count(1)

    # -- write side (observer only) ------------------------------------
    def record(self, token: object, *, fact_type: str, subject: str, verified: bool,
               observed_state: Dict[str, Any], execution_id: str,
               observer: str, capability_id: str = "") -> int:
        if token is not _OBSERVER_TOKEN:
            raise PermissionError("Only the authorized observation layer may record observations.")
        with self._lock:
            sequence = next(self._counter)
            self._records[sequence] = ObservationRecord(
                sequence=sequence,
                fact_type=fact_type,
                subject=subject,
                verified=verified,
                observed_state=dict(observed_state),
                execution_id=execution_id,
                observer=observer,
                observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                capability_id=capability_id or subject,
            )
        return sequence

    # -- read side -----------------------------------------------------
    def get(self, sequence: Any) -> Optional[ObservationRecord]:
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            return None
        with self._lock:
            return self._records.get(sequence)

    def validate_fact(self, fact) -> Optional[str]:
        """
        Return a rejection code when `fact` is not backed by a matching ledger entry.
        Returns None when the fact is provenance-consistent.
        """
        record = self.get(getattr(fact, "observation_sequence", None))
        if record is None:
            return AuthorityRejection.OBSERVATION_NOT_IN_LEDGER
        if record.verified is not True or getattr(fact, "verified", None) is not True:
            return AuthorityRejection.UNVERIFIED_PHYSICAL_FACT
        if record.fact_type != getattr(fact, "fact_type", None):
            return AuthorityRejection.INVALID_PROVENANCE
        if record.subject != getattr(fact, "subject", None):
            return AuthorityRejection.CAPABILITY_MISMATCH
        if dict(record.observed_state) != dict(getattr(fact, "observed_state", {}) or {}):
            return AuthorityRejection.OBSERVATION_STATE_MISMATCH
        return None

    def consume(self, fact, mission_id: str, execution_id: str) -> Optional[str]:
        """
        Bind an observation to one (mission, execution) pair.

        Returns None on success (including a repeat call with the same binding, so a single
        observation can yield several evidence records), or a rejection code.
        """
        sequence = getattr(fact, "observation_sequence", None)
        record = self.get(sequence)
        if record is None:
            return AuthorityRejection.OBSERVATION_NOT_IN_LEDGER
        with self._lock:
            bound = self._consumed.get(sequence)
            if bound is None:
                self._consumed[sequence] = (mission_id, execution_id)
                return None
            if bound == (mission_id, execution_id):
                return None
            if bound[0] != mission_id:
                return AuthorityRejection.MISSION_MISMATCH
            return AuthorityRejection.EXECUTION_MISMATCH

    def consumption_of(self, sequence: Any) -> Optional[Tuple[str, str]]:
        with self._lock:
            return self._consumed.get(sequence)

    def link_verification(self, token: str, sequence: int) -> None:
        """
        Bind a capability-verification token to the observation that produced it.

        The token is what evidence carries, so this is the join between "an observation
        happened" and "this evidence claims to come from it". Only the verifier/builder path
        calls it; a caller who merely knows the signing key still cannot create this link.
        """
        with self._lock:
            self._by_token[str(token)] = sequence

    def observation_for_token(self, token: Any) -> Optional["VerifiedObservation"]:
        if not isinstance(token, str) or not token:
            return None
        with self._lock:
            sequence = self._by_token.get(token)
            record = self._records.get(sequence) if sequence is not None else None
        if record is None:
            return None
        return VerifiedObservation(
            sequence=record.sequence,
            capability_id=record.capability_id,
            execution_id=record.execution_id,
            fact_type=record.fact_type,
            verified=record.verified,
        )

    def has_verification_token(self, token: Any) -> bool:
        if not isinstance(token, str) or not token:
            return False
        with self._lock:
            return token in self._by_token

    def reset(self) -> None:
        """Test-support only. Does not weaken the boundary: the ledger stays append-only."""
        with self._lock:
            self._records.clear()
            self._consumed.clear()
            self._by_token.clear()
            self._counter = itertools.count(1)


#: Process-wide ledger. The observation layer holds `_OBSERVER_TOKEN`; nothing else does.
LEDGER = ObservationLedger()


def observer_token() -> object:
    """Internal accessor used by `physical_fact_verifier` only."""
    return _OBSERVER_TOKEN
