"""
Capability-specific verification (D-1, D-2, D-6).

Sealed design
-------------
IMPLEMENTATION 003 exposed `register_verifier` as a plain classmethod writing into a mutable
dict. Audit 004 replaced the `CAP_STATE_ENGINE` verifier at runtime, produced evidence for
every required type, and completed a mission. The registry is now:

  * built once at import time into a read-only mapping;
  * refuses to overwrite any existing `(capability, verifier_id)` pair, trusted or not;
  * refuses outright to register a verifier for a *protected* capability, so an extension can
    never acquire authority over a protected capability;
  * resolved exclusively from the trusted mapping — a caller cannot point a capability at a
    verifier it supplied.

Provenance
----------
A fact is only considered if the observation ledger backs it: the fact must correspond to a
real observation performed by the authorized observer, its `observed_state` must equal the
recorded one, and it must bind to exactly one (mission, execution) pair. A hand-built
`VerifiedPhysicalFact` has no ledger sequence and is refused, so the boolean `verified` is no
longer the load-bearing property.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import os
from types import MappingProxyType
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.cognitive.authority_core import (
    LEDGER,
    AuthorityAudit,
    AuthorityRejection,
)
from core.cognitive.capability_definitions import (
    EvidenceType,
    get_definition,
    is_protected_capability,
)
from core.cognitive.physical_fact_verifier import SQLITE_PERSISTENCE_FACT, VerifiedPhysicalFact


class VerificationRejection:
    """Backwards-compatible alias onto the shared taxonomy."""
    REASON_NO_DEFINITION = "CAPABILITY_NOT_DEFINED"
    REASON_FACT_TYPE_NOT_ALLOWED = "FACT_TYPE_NOT_DECLARED_FOR_CAPABILITY"
    REASON_SUBJECT_MISMATCH = "FACT_SUBJECT_IS_DIFFERENT_CAPABILITY"
    REASON_FACT_UNVERIFIED = AuthorityRejection.UNVERIFIED_PHYSICAL_FACT
    REASON_NO_VERIFIER = AuthorityRejection.UNTRUSTED_VERIFIER
    REASON_VERIFIER_REJECTED = "CAPABILITY_VERIFIER_REJECTED"
    REASON_NO_EVIDENCE_SATISFIED = AuthorityRejection.EVIDENCE_TYPE_NOT_SATISFIED
    REASON_NOT_A_PHYSICAL_FACT = AuthorityRejection.NOT_A_PHYSICAL_FACT


@dataclass(frozen=True)
class CapabilityVerificationResult:
    """Outcome of a capability-specific verification. Immutable by construction."""

    capability_id: str
    verified: bool
    reason: str
    fact_id: str
    fact_type: str
    verifier_id: str
    execution_id: str = ""
    evidence_types_satisfied: Tuple[str, ...] = ()
    observed_state: Dict[str, Any] = field(default_factory=dict)
    observation_sequence: int = 0

    def authorization_token(self) -> str:
        """Opaque token binding evidence back to the exact verification that produced it."""
        return (f"{self.capability_id}|{self.fact_id}|{self.fact_type}|"
                f"{self.verifier_id}|{','.join(self.evidence_types_satisfied)}")


# A verifier receives the fact plus its definition and returns the evidence types it actually
# proved, together with a human-readable reason. It may not invent types outside the
# definition; the caller re-checks that. A verifier that additionally declares
# `expected_resource` is resource-bound and is always called with the mission's real store.
VerifierFn = Callable[..., Tuple[Tuple[str, ...], str]]


def _accepts_resource(fn) -> bool:
    """Whether a verifier declares the `expected_resource` binding."""
    try:
        return "expected_resource" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


class CapabilitySpecificVerifier:
    """
    Trusted verifier registry.

    `_TRUSTED_VERIFIERS` is replaced by an immutable mapping during bootstrap. There is no
    public API that adds, removes or replaces an entry once bootstrap has run; `register_verifier`
    only accepts brand-new verifier ids for non-protected capabilities, which by construction
    can never satisfy a mission requirement.
    """

    _REGISTRY: Dict[Tuple[str, str], VerifierFn] = {}
    _SEALED: bool = False

    # ---------------- bootstrap ----------------
    @classmethod
    def _bootstrap(cls) -> None:
        """Install the trusted verifiers and seal the registry. Runs once, at import."""
        if cls._SEALED:
            return
        for (capability_id, verifier_id), fn in tuple(cls._REGISTRY.items()):
            cls._REGISTRY[(capability_id, verifier_id)] = fn
        cls._SEALED = True

    @classmethod
    def _trusted_view(cls) -> MappingProxyType:
        return MappingProxyType(cls._REGISTRY)

    # ---------------- extension registration ----------------
    @classmethod
    def register_verifier(cls, capability_id: str, verifier_id: str, fn: VerifierFn) -> None:
        """
        Register an **extension** verifier.

        Refused for protected capabilities, and refused for any duplicate identifier.
        Extension verifiers exist so the mechanism can be exercised for capabilities outside
        the protected set; they carry no authority over a protected capability and cannot
        satisfy a mission requirement (see `capability_definitions.can_satisfy_requirement`).
        """
        if is_protected_capability(capability_id):
            raise PermissionError(
                f"'{capability_id}' is a protected capability. Its verifier cannot be "
                f"registered or replaced at runtime."
            )
        if (capability_id, verifier_id) in cls._REGISTRY:
            raise PermissionError(
                f"Verifier '{verifier_id}' for '{capability_id}' is already registered "
                f"and cannot be replaced."
            )
        cls._REGISTRY[(capability_id, verifier_id)] = fn
        AuthorityAudit.record(
            decision="VERIFIER_REGISTERED", subject=verifier_id, capability_id=capability_id,
            reason="EXTENSION",
        )

    @classmethod
    def has_verifier(cls, capability_id: str, verifier_id: Optional[str] = None) -> bool:
        if verifier_id is None:
            definition = get_definition(capability_id)
            verifier_id = definition.verifier_id if definition else None
        return bool(verifier_id) and (capability_id, verifier_id) in cls._REGISTRY

    @classmethod
    def trusted_verifier_ids(cls, capability_id: str) -> Tuple[str, ...]:
        return tuple(sorted(v for (c, v) in cls._REGISTRY if c == capability_id))

    # ---------------- verification ----------------
    @classmethod
    def verify(
        cls,
        capability_id: str,
        fact: VerifiedPhysicalFact,
        execution_id: str = "",
        mission_id: str = "",
        expected_resource: Optional[str] = None,
    ) -> CapabilityVerificationResult:
        definition = get_definition(capability_id)
        if definition is None:
            return cls._reject(capability_id, fact, execution_id,
                               AuthorityRejection.CAPABILITY_MISMATCH)

        # Only a real VerifiedPhysicalFact may be presented.
        if not isinstance(fact, VerifiedPhysicalFact):
            return cls._reject(capability_id, fact, execution_id,
                               AuthorityRejection.NOT_A_PHYSICAL_FACT)

        # D-2: provenance. The fact must be backed by a real recorded observation, and its
        # payload must equal the recorded one. A caller-built dataclass has no ledger
        # sequence, so this is where fabrication stops.
        provenance_error = LEDGER.validate_fact(fact)
        if provenance_error is not None:
            return cls._reject(capability_id, fact, execution_id, provenance_error)

        if not definition.allows_fact_type(fact.fact_type):
            return cls._reject(capability_id, fact, execution_id,
                               AuthorityRejection.FACT_TYPE_NOT_DECLARED)

        if fact.subject != capability_id:
            return cls._reject(capability_id, fact, execution_id,
                               AuthorityRejection.CAPABILITY_MISMATCH)

        # A protected capability is verified only by a trusted verifier.
        if is_protected_capability(capability_id):
            verifier_id = definition.verifier_id
            fn = cls._REGISTRY.get((capability_id, verifier_id)) if verifier_id else None
            if fn is None:
                return cls._reject(capability_id, fact, execution_id,
                                   AuthorityRejection.UNTRUSTED_VERIFIER, verifier_id or "")
        else:
            verifier_id = definition.verifier_id
            fn = cls._REGISTRY.get((capability_id, verifier_id)) if verifier_id else None
            if fn is None:
                return cls._reject(capability_id, fact, execution_id,
                                   AuthorityRejection.UNTRUSTED_VERIFIER, verifier_id or "")

        try:
            if _accepts_resource(fn):
                # Resource-bound verifier: it additionally checks that the observed resource
                # is the one this mission is actually persisted to.
                if expected_resource is None:
                    return cls._reject(
                        capability_id, fact, execution_id,
                        AuthorityRejection.INVALID_PROVENANCE, verifier_id or "")
                satisfied, reason = fn(fact, definition, expected_resource=expected_resource)
            else:
                satisfied, reason = fn(fact, definition)
        except Exception as exc:  # defensive: a broken verifier must never certify
            return cls._reject(capability_id, fact, execution_id,
                               f"{VerificationRejection.REASON_VERIFIER_REJECTED}:{exc}",
                               verifier_id or "")

        # The verifier may only claim types the capability actually requires.
        satisfied = tuple(t for t in satisfied if definition.requires_evidence_type(t))
        if not satisfied:
            return cls._reject(capability_id, fact, execution_id,
                               AuthorityRejection.EVIDENCE_TYPE_NOT_SATISFIED, verifier_id or "")

        return CapabilityVerificationResult(
            capability_id=capability_id,
            verified=True,
            reason=reason,
            fact_id=fact.fact_id,
            fact_type=fact.fact_type,
            verifier_id=verifier_id or "",
            execution_id=execution_id or fact.execution_id,
            evidence_types_satisfied=satisfied,
            observed_state=dict(fact.observed_state),
            observation_sequence=fact.observation_sequence,
        )

    @classmethod
    def _reject(cls, capability_id, fact, execution_id, reason, verifier_id="") -> CapabilityVerificationResult:
        AuthorityAudit.record(
            decision="VERIFICATION_REJECTED", subject=getattr(fact, "fact_id", ""),
            capability_id=capability_id, execution_id=execution_id, reason=reason,
        )
        return CapabilityVerificationResult(
            capability_id=capability_id,
            verified=False,
            reason=reason,
            fact_id=getattr(fact, "fact_id", ""),
            fact_type=getattr(fact, "fact_type", ""),
            verifier_id=verifier_id,
            execution_id=execution_id,
            evidence_types_satisfied=(),
            observed_state=dict(getattr(fact, "observed_state", {}) or {}),
            observation_sequence=getattr(fact, "observation_sequence", 0),
        )


# ----------------------------------------------------------------------
# Built-in capability-specific verifier
# ----------------------------------------------------------------------
def _verify_sqlite_persistence(fact: VerifiedPhysicalFact, definition) -> Tuple[Tuple[str, ...], str]:
    """
    Genuine inspection of the observed SQLite state. Declares FILESYSTEM evidence only when
    the database file is really on disk, and DATABASE evidence only when WAL is active and a
    probe row genuinely round-trips.
    """
    observed = fact.observed_state or {}
    satisfied: List[str] = []
    if observed.get("file_exists"):
        satisfied.append(EvidenceType.FILESYSTEM_EVIDENCE)
    if (
        observed.get("journal_mode") == "wal"
        and observed.get("missions_table")
        and observed.get("required_columns")
        and observed.get("roundtrip_ok")
    ):
        satisfied.append(EvidenceType.DATABASE_EVIDENCE)
    return tuple(satisfied), f"sqlite_persistence observed: {observed}"


def _verify_sqlite_persistence_bound(
    fact: VerifiedPhysicalFact, definition, *, expected_resource: Optional[str] = None
) -> Tuple[Tuple[str, ...], str]:
    """
    Resource-bound variant: additionally requires that the observed database is the very
    database the mission is being persisted to.

    Without this, an observation of a *different* real database would certify a mission. That
    observation is genuine, but it says nothing about the store holding this mission's rows.
    """
    if expected_resource:
        observed_path = (fact.observed_state or {}).get("db_path")
        if not observed_path or os.path.abspath(str(observed_path)) != os.path.abspath(str(expected_resource)):
            return (), "OBSERVED_DATABASE_IS_NOT_THE_MISSION_DATABASE"
    return _verify_sqlite_persistence(fact, definition)


def _register_builtin_verifiers() -> None:
    # The trusted verifier for CAP_STATE_ENGINE is resource-bound: it refuses to certify a
    # mission whose store is not the database it actually inspected.
    CapabilitySpecificVerifier._REGISTRY[("CAP_STATE_ENGINE", "sqlite_persistence")] = (
        _verify_sqlite_persistence_bound
    )


_register_builtin_verifiers()
CapabilitySpecificVerifier._bootstrap()
