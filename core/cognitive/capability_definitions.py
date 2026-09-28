"""
Capability definitions: the declarative half of the authority chain.

A capability is not a label. It is a contract stating:

  * which evidence types must all be present (complete coverage), and
  * which physical fact types are *allowed* to demonstrate it at all.

`verifiable_by_fact_types` is the D-6 control. A capability with an empty tuple can never
reach VERIFIED, because there is no fact type that the evidence builder will accept for it.
Generic facts (a file write, a test run, an exit code) are deliberately absent from every
definition, so no amount of unrelated successful activity can certify a capability.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple


class EvidenceType:
    """Evidence vocabulary. Retained verbatim for compatibility with existing callers."""

    TOOL_RESULT = "TOOL_RESULT"
    TEST_RESULT = "TEST_RESULT"
    FILESYSTEM_EVIDENCE = "FILESYSTEM_EVIDENCE"
    PROCESS_EVIDENCE = "PROCESS_EVIDENCE"
    WINDOW_EVIDENCE = "WINDOW_EVIDENCE"
    SCREEN_EVIDENCE = "SCREEN_EVIDENCE"
    NETWORK_EVIDENCE = "NETWORK_EVIDENCE"
    BROWSER_EVIDENCE = "BROWSER_EVIDENCE"
    COMMUNICATION_EVIDENCE = "COMMUNICATION_EVIDENCE"
    DATABASE_EVIDENCE = "DATABASE_EVIDENCE"
    OTHER_PHYSICAL_EVIDENCE = "OTHER_PHYSICAL_EVIDENCE"


#: Fact type produced only by a real, deterministic SQLite persistence inspection.
SQLITE_PERSISTENCE_FACT = "SQLITE_PERSISTENCE"


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    capability_name: str
    required_evidence_types: Tuple[str, ...]
    required_tests: Tuple[str, ...]
    physical_verification_required: bool
    # D-6: fact types permitted to demonstrate this capability. Empty => NOT IMPLEMENTED.
    verifiable_by_fact_types: Tuple[str, ...] = ()
    verifier_id: Optional[str] = None
    operational_state: str = "NOT_IMPLEMENTED"
    limitations: Tuple[str, ...] = ()
    #: Only bootstrap-approved capabilities may satisfy a mission requirement. Capabilities
    #: registered at runtime are modelled by the registry but can never unblock completion,
    #: so a caller cannot invent a capability plus a permissive verifier and then declare a
    #: mission that requires it.
    bootstrap: bool = True

    def allows_fact_type(self, fact_type: str) -> bool:
        return fact_type in self.verifiable_by_fact_types

    def requires_evidence_type(self, evidence_type: str) -> bool:
        return evidence_type in self.required_evidence_types


# The five pre-existing capabilities. None of them gains new behaviour here: four are
# declared NOT operationally verifiable because no capability-specific verifier exists in
# this codebase, and they therefore cannot reach VERIFIED by any route.
_DEFS: Tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id="CAP_STATE_ENGINE",
        capability_name="StateEngine Persistence",
        required_evidence_types=(EvidenceType.FILESYSTEM_EVIDENCE, EvidenceType.DATABASE_EVIDENCE),
        required_tests=("test_state_engine.py",),
        physical_verification_required=True,
        verifiable_by_fact_types=(SQLITE_PERSISTENCE_FACT,),
        verifier_id="sqlite_persistence",
        operational_state="IMPLEMENTED",
    ),
    CapabilityDefinition(
        capability_id="CAP_CHECKPOINT_RESUME",
        capability_name="Checkpoint and Resume Engine",
        required_evidence_types=(EvidenceType.FILESYSTEM_EVIDENCE, EvidenceType.DATABASE_EVIDENCE),
        required_tests=("test_checkpoint_resume.py",),
        physical_verification_required=True,
        verifiable_by_fact_types=(),
        verifier_id=None,
        operational_state="NOT_IMPLEMENTED",
        limitations=("No capability-specific physical verifier is implemented.",),
    ),
    CapabilityDefinition(
        capability_id="CAP_DESKTOP_VISION",
        capability_name="Desktop Control & Local Vision OCR",
        required_evidence_types=(EvidenceType.SCREEN_EVIDENCE, EvidenceType.WINDOW_EVIDENCE),
        required_tests=("test_desktop_vision.py",),
        physical_verification_required=True,
        verifiable_by_fact_types=(),
        verifier_id=None,
        operational_state="NOT_IMPLEMENTED",
        limitations=("No capability-specific physical verifier is implemented.",),
    ),
    CapabilityDefinition(
        capability_id="CAP_PLAYWRIGHT_BROWSER",
        capability_name="Playwright Browser Automation",
        required_evidence_types=(EvidenceType.BROWSER_EVIDENCE, EvidenceType.SCREEN_EVIDENCE),
        required_tests=("test_browser_live.py",),
        physical_verification_required=True,
        verifiable_by_fact_types=(),
        verifier_id=None,
        operational_state="NOT_IMPLEMENTED",
        limitations=("No capability-specific physical verifier is implemented.",),
    ),
    CapabilityDefinition(
        capability_id="CAP_WHATSAPP_AUTO_REPLY",
        capability_name="WhatsApp Integration & Auto-Reply",
        required_evidence_types=(EvidenceType.COMMUNICATION_EVIDENCE, EvidenceType.NETWORK_EVIDENCE),
        required_tests=("test_whatsapp_live.py",),
        physical_verification_required=True,
        verifiable_by_fact_types=(),
        verifier_id=None,
        operational_state="NOT_IMPLEMENTED",
        limitations=("No capability-specific physical verifier is implemented.",),
    ),
)

_DEFINITIONS: Dict[str, CapabilityDefinition] = {d.capability_id: d for d in _DEFS}

#: Capabilities whose contracts are fixed at bootstrap. A definition registered later can
#: never enter this set, so it can never satisfy a mission requirement.
_PROTECTED_CAPABILITY_IDS: frozenset = frozenset(_DEFINITIONS.keys())

#: Extension definitions live in a separate store and are exposed read-only. They exist so
#: the mechanism can be exercised for capabilities outside the protected set.
_EXTENSION_DEFINITIONS: Dict[str, CapabilityDefinition] = {}


def get_definition(capability_id: str) -> Optional[CapabilityDefinition]:
    definition = _DEFINITIONS.get(capability_id)
    if definition is not None:
        return definition
    return _EXTENSION_DEFINITIONS.get(capability_id)


def is_known_capability(capability_id: str) -> bool:
    return capability_id in _DEFINITIONS or capability_id in _EXTENSION_DEFINITIONS


def all_definitions() -> List[CapabilityDefinition]:
    return list(_DEFINITIONS.values()) + list(_EXTENSION_DEFINITIONS.values())


def is_protected_capability(capability_id: str) -> bool:
    """Whether this capability's contract is fixed at bootstrap."""
    return capability_id in _PROTECTED_CAPABILITY_IDS


def register_definition(definition: CapabilityDefinition) -> CapabilityDefinition:
    """
    Register an **extension** capability contract.

    Three properties matter, and all three are enforced here rather than by convention:
      * an identifier that already exists — protected or extension — is refused, so an
        extension can never displace a protected contract;
      * the definition is stored in the extension store and is forcibly marked
        non-bootstrap, so declaring `bootstrap=True` grants nothing;
      * it can never enter `_PROTECTED_CAPABILITY_IDS`, and `can_satisfy_requirement`
        consults only that set, so an extension cannot satisfy a mission requirement.
    """
    if definition.capability_id in _DEFINITIONS:
        raise PermissionError(
            f"'{definition.capability_id}' is a protected capability and its definition "
            f"cannot be replaced at runtime."
        )
    if definition.capability_id in _EXTENSION_DEFINITIONS:
        raise PermissionError(
            f"Extension capability '{definition.capability_id}' is already defined."
        )
    stored = replace(definition, bootstrap=False)
    _EXTENSION_DEFINITIONS[definition.capability_id] = stored
    return stored


def can_satisfy_requirement(capability_id: str) -> bool:
    """
    Whether this capability may ever satisfy a mission requirement.

    Membership of the bootstrap-protected set is the only route. Extension and unknown
    capabilities are excluded regardless of any field they carry.
    """
    return capability_id in _PROTECTED_CAPABILITY_IDS
