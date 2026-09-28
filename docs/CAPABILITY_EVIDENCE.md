# Avatar AI — Capability Evidence & Epistemic Authority Model

## 1. Architectural Principles

Forensic Repair 002 eliminates LLM auto-certification by establishing strict epistemic boundary separation:

$$\text{MODEL\_CLAIM} \neq \text{VERIFIED\_FACT}$$
$$\text{TEST\_PASS} \neq \text{CAPABILITY\_VERIFIED}$$
$$\text{EXIT\_CODE\_0} \neq \text{OBJECTIVE\_COMPLETED}$$
$$\text{DOCUMENT\_CREATED} \neq \text{AUDIT\_COMPLETED}$$

```
   LLM (Generates Text / Claims)
          │
          ▼
   ClaimValidator (Extracts & Sanitizes Unverified Claims)
          │
          ▼
   CapabilityEvidenceRegistry (Validates Required Physical Evidence)
          │
          ▼
   MissionCompletionGate (Evaluates Hard Deterministic Closure Criteria)
          │
          ▼
   StateEngine (SQLite WAL Epistemic State Authority)
```

---

## 2. Capability Evidence Model

### Capability Record Structure
Every system capability is tracked in `CapabilityEvidenceRegistry` ([`core/cognitive/capability_registry.py`](file:///b:/PROYECTOS%20ANTIGRAVITY/Avatar/core/cognitive/capability_registry.py)) with the following fields:
- `capability_id`: Unique identifier (e.g. `CAP_WHATSAPP_AUTO_REPLY`, `CAP_PLAYWRIGHT_BROWSER`).
- `capability_name`: Human-readable title.
- `required_evidence`: List of mandatory `EvidenceType` values (e.g. `COMMUNICATION_EVIDENCE`, `BROWSER_EVIDENCE`).
- `required_tests`: Mandatory integration test suite files.
- `physical_verification_required`: Boolean flag indicating if live physical infrastructure proof is required.
- `verification_status`: Epistemic status in state engine.
- `evidence_ids`: List of registered `CapabilityEvidence` IDs.
- `limitations`: List of active technical limitations or missing infrastructure warnings.
- `dependencies`: Dependent capabilities.
- `last_verified_at`: Timestamp of last verified physical proof.

### Taxonomy of Permitted Statuses
- `VERIFIED`: Live physical operational evidence registered and validated.
- `PARTIAL`: Implementation exists and unit/mock tests pass, but live physical infrastructure proof is pending.
- `IMPLEMENTED_NOT_INTEGRATED`: Code modules written but not wired to runtime execution engine.
- `SIMULATED_ONLY`: Operates purely in simulated or mock environment.
- `NOT_IMPLEMENTED`: Feature does not exist in codebase.
- `BLOCKED_EXTERNAL`: Execution blocked by third-party external service unavailability.
- `BLOCKED_SECURITY`: Blocked by security constraints.
- `BLOCKED_INFRASTRUCTURE`: Blocked by missing hardware or network infrastructure.

---

## 3. Mission Completion Gate

`MissionCompletionGate` ([`core/cognitive/mission_completion_gate.py`](file:///b:/PROYECTOS%20ANTIGRAVITY/Avatar/core/cognitive/mission_completion_gate.py)) deterministically enforces completion rules before any mission can transition to `MISSION_COMPLETED`:

```python
can_complete = (
    unverified_required_capabilities == []
    and critical_gaps == 0
    and blocking_findings == 0
)
```

If `critical_gaps > 0` or `blocking_findings > 0`, the mission status is degraded to `COMPLETED_WITH_BLOCKING_FINDINGS` or `BLOCKED`.

---

## 4. Claim Interception (`ClaimValidator`)

`ClaimValidator` ([`core/cognitive/claim_validator.py`](file:///b:/PROYECTOS%20ANTIGRAVITY/Avatar/core/cognitive/claim_validator.py)) scans model text responses for text claims such as `CAPABILITY = VERIFIED` or `STATUS = COMPLETED`.

If no corresponding physical evidence exists in `CapabilityEvidenceRegistry` or if `MissionCompletionGate` rejects completion:
1. The claim is downgraded to `UNVERIFIED_CLAIM`.
2. A system audit annotation is automatically injected into the user-facing text:
   `> ⚠️ [AUDITORÍA DE AUTORIDAD EPISTÉMICA - AFIRMACIÓN DE CAPACIDAD DEGRADADA]: El sistema detectó la afirmación "...", pero se degradó a UNVERIFIED_CLAIM...`
