# AUTHORITY CONSOLIDATION IMPLEMENTATION 004
## SOVEREIGN CAPABILITY AUTHORITY REPAIR — ADVERSARIAL HARDENING

Repository: `B:\PROYECTOS ANTIGRAVITY\Avatar`
Reference audit: `AUTHORITY CONSOLIDATION 004 — POST-IMPLEMENTATION FORENSIC AUDIT`

---

## 1. Executive summary

The audit 004 findings are closed by a **structural** change, not by hiding names, prefixing
with `_`, freezing dataclasses, or introducing another in-process key. The load-bearing
primitive is an **append-only observation ledger**: a fact is credible only if the authorized
observer actually performed the observation and recorded it, and each observation can certify
exactly one `(mission, execution)` pair.

| Measure | Before 004 | After 004 |
|---|---|---|
| Audit-004 original attacks reproduced | 2/2 succeeded | **0/2** |
| Post-fix probes (audit scenarios) | 10/13 claim violations | **0/13** |
| Independent post-audit probes (not designed against) | n/a | **0/8 breaches** |
| Composed adversarial suite (groups A–F) | did not exist | **39 tests** |
| Full suite | 384 passed | **423 passed, 0 failed** |
| Capabilities that can reach `VERIFIED` | 1 of 5 | 1 of 5 (unchanged) |

The single most important property: **the HMAC is no longer load-bearing.** Leaking
`_authority._KEY` now yields only `NOT_IMPLEMENTED` / `PARTIALLY_COMPLETED` — demonstrated in
§12. Capability truth now comes from the ledger, not from a secret.

---

## 2. Status of the audit 004 findings

| Finding | Severity | Initial state | Correction | Adversarial test | Final state |
|---|---|---|---|---|---|
| **CRITICAL-1** Fabricable fact + replaceable verifier → `COMPLETED` | CRITICAL | Reproduced end-to-end via public APIs only | Verifier registry sealed (protected capabilities refuse registration; duplicates refused); fact provenance enforced through the ledger before any verifier runs | `A1`, `A2`, `A3`, `B1`, `C1`, `F7` | **CLOSED** |
| **CRITICAL-2** HMAC key readable as module attribute | CRITICAL | `_authority._KEY` read and used to sign evidence; mission reached `COMPLETED` | Key demoted to defence-in-depth; registry now requires a **live ledger token** for the evidence, not merely a valid signature | key-path probe, `C2` | **CLOSED** |
| **HIGH-1** `_DEFINITIONS` injectable with `bootstrap=True` | HIGH | Direct dict injection accepted; injected capability completed a mission | Protected set established at bootstrap; extensions stored separately; `can_satisfy_requirement` consults only the protected set | `D1`, `D2`, `D3` | **CLOSED** |
| **HIGH-2** Requirements erasable by direct SQL | HIGH | `required_capabilities='[]'` → `NO_REQUIREMENTS_DECLARED` | `requirements_seal` column; integrity verified on every read by the gate **and** the sovereign writer; corruption blocks as `REQUIREMENTS_INTEGRITY_FAILURE` | `E3` | **CLOSED** (detection, not prevention — see §13) |
| **X8** *(found during this implementation's own post-audit)* Observation of a foreign database certified a mission | MEDIUM | Real observation of DB-A certified a mission living in DB-B | Trusted verifier made **resource-bound**; it refuses when the observed database is not the mission's own store | `F7`, `F8` | **CLOSED** |
| **X9** *(found during this implementation's own post-audit)* Forged evidence with a leaked key still admitted | CRITICAL | `register_evidence` accepted signed-but-unbacked evidence | Registry requires a ledger-backed verification token bound to a real observation and mission | `C2` | **CLOSED** |

---

## 3. Authority map: before and after

### Before (audit 004 state)

```
caller ──► constructs VerifiedPhysicalFact(verified=True)      ← fabricated
       ──► register_verifier(cap, id, fn)  overwrites builtin  ← replaces trust
       ──► AuthorizedEvidenceBuilder signs it legitimately      ← signing oracle
       ──► register_evidence admits it
       ──► capability VERIFIED ──► mission COMPLETED
```

### After

```
 AuthorizedObservation (PhysicalFactVerifier only)
        │  records into the append-only ledger, returns a sequence
        ▼
 VerifiedPhysicalFact (carries observation_sequence)
        │  ledger.validate_fact(): sequence exists AND payload equals the record
        │  ledger.consume(): binds to exactly one (mission, execution)
        ▼
 CapabilitySpecificVerifier
        │  trusted verifier only (protected capabilities refuse registration)
        │  resource-bound where the capability is resource-scoped
        ▼
 CapabilityVerificationResult
        │  ledger.link_verification(token → observation)
        ▼
 AuthorizedEvidenceBuilder  (capability_id and evidence_type from the result)
        ▼
 CapabilityEvidenceRegistry
        │  requires a live ledger token, not just a signature
        ▼
 MissionCompletionGate  (reads persisted requirements; verifies their seal)
        ▼
 GateAuthorization  →  StateEngine re-derives independently
        ▼
    COMPLETED
```

**Where authority is born:** `CapabilitySpecificVerifier.verify`, gated by the ledger.
**Where it is validated:** registry admission and `StateEngine.update_mission_status`.
**Where it is consumed:** `complete_mission_with_authorization`.
**Where it is persisted:** `missions.status` via a single writer.

---

## 4. Root cause of each vulnerability

**CRITICAL-1.** Two independent defects composed. (a) `register_verifier` wrote into a plain
dict with no guard, so trust logic was caller-replaceable. (b) `VerifiedPhysicalFact` was a
public dataclass whose only load-bearing field was a caller-supplied `verified` boolean.
Composition turned two weak controls into a total bypass. Neither defect alone was fatal; the
audit 003 suite tested each in isolation, which is exactly why it passed.

**CRITICAL-2.** A key held in a single address space is not a boundary. Any code in the
interpreter can read module attributes. The signature was integrity-only and was treated as
authenticity.

**HIGH-1.** The `bootstrap` guard consulted the same mutable dict an attacker writes to.

**HIGH-2.** The requirement columns had no integrity binding, so a direct write was
indistinguishable from a legitimate one.

**X8.** Provenance established that *an* observation happened, not that it concerned *this*
mission's resource.

**X9.** Admission checked signature validity and non-empty provenance strings, but never that
the referenced observation existed.

---

## 5. Files modified

| File | Change | Reason |
|---|---|---|
| `core/cognitive/authority_core.py` | **New.** Observation ledger, rejection taxonomy, authority audit, observer token | D-2, D-12 |
| `core/cognitive/physical_fact_verifier.py` | Every fact now routed through `_issue()`, which records the observation; added `observation_sequence` | D-2 |
| `core/cognitive/capability_specific_verifier.py` | Registry sealed; protected capabilities refuse registration; duplicates refused; ledger provenance enforced before the verifier; resource-bound trusted verifier | D-1, D-2, D-6 |
| `core/cognitive/capability_definitions.py` | Protected set established at bootstrap; extension store separate; `can_satisfy_requirement` consults only the protected set | D-4 |
| `core/cognitive/authorized_evidence_builder.py` | Validates provenance and consumes the observation before signing; `expected_resource` plumbed; links verification token to observation | D-3 |
| `core/cognitive/capability_registry.py` | Admission requires a live ledger token bound to a real observation, mission, capability and execution | D-8, X9 |
| `core/cognitive/mission_completion_gate.py` | Requirements-integrity gate; corrupt requirements block rather than downgrade | D-5 |
| `core/state_db.py` | `requirements_seal` column + migration; seal create/verify; single status writer `_persist_mission_status`; integrity check in `update_mission_status` | D-5, D-6, D-9 |
| `core/orchestrator.py` | Passes `expected_resource` when building evidence | D-3 |
| `tests/authority_fixtures.py` | Passes `expected_resource` | test correctness |
| `tests/test_authority_composed_adversarial_004.py` | **New.** 39 composed adversarial tests, groups A–F | D-10 |
| `tests/test_authority_adversarial_003.py` | 5 tests updated: reason codes plus two that used `dataclasses.replace` to re-point a fact (now correctly refused) | see §8 |
| `tests/test_authority_consolidation_003.py`, `test_forensic_repair_002.py` | Reason-code assertions widened | see §8 |

No unrelated component was modified. No new external dependency was introduced.

---

## 6. Threat-model change

**Implementation 003** assumed a module-private HMAC key was a boundary. It is not. That
assumption is removed.

| Property | Model A (ordinary caller, public APIs) | Model B (arbitrary in-process code) |
|---|---|---|
| Fabricate a physical fact | **resisted** — no ledger sequence | **not resisted** (can call the observer) |
| Replace a trusted verifier | **resisted** — `PermissionError` | **not resisted** (can mutate the dict) |
| Read the signing key | possible | possible |
| Forge evidence with the key | **resisted** — no ledger token | not resisted |
| Inject a bootstrap definition | **resisted** — separate store | not resisted |
| Erase requirements via SQL | **detected and blocked** | not prevented |
| Reuse an observation | **resisted** — single use | not prevented |
| Certify a foreign resource | **resisted** — resource binding | not resisted |

Model B has **no** guarantee here. Python in a single address space cannot provide one. Real
protection requires an out-of-process boundary — a separate verifier process with validated
IPC, or OS-level privilege separation. That is a genuine architectural change with real cost
and is **not** implemented; it is recorded in §15 as a recommendation, not a claim.

---

## 7. Threat model and Python limits (D-7)

Implemented as specified in `authority_core.py`'s module docstring. The design forces the
caller to *perform the real observation* to obtain authority — that is the property the
boundary actually buys, and it holds for Model A regardless of what the caller knows about
module internals.

Two honest limits, stated rather than papered over:

1. `_OBSERVER_TOKEN` is reachable by any importing code. A determined in-process attacker can
   append to the ledger. Only an out-of-process boundary removes this.
2. `requirements_seal` uses the same in-process key. It detects a rewrite that does not know
   about the seal; it does not stop an adversary who recomputes it.

---

## 8. Authority routes reviewed (D-11)

| Element | File / function | Caller allowed | Validation | Persistence | Risk | Result |
|---|---|---|---|---|---|---|
| `COMPLETED` | `state_db._persist_mission_status` | internal only, one caller | re-derived verdict | `missions.status` | — | single writer confirmed |
| `NO_REQUIREMENTS_DECLARED` | gate | — | `requirements_declared=0` **and** seal intact | `missions.status` | — | policy state, not success |
| mission terminal states | `create_mission` | any | rejects `TERMINAL_MISSION_STATUSES` | `missions.status` | — | corrected |
| `VERIFIED` | `_derive_status` | — | per-mission coverage of authorized evidence | `capability_records` | — | derived only |
| `BLOCKED_*`, `SIMULATED_ONLY` | `set_capability_limitation` | any | allowlist excludes derived states | `capability_records` | — | demotion only |
| verifier registry | `register_verifier` | any | protected + duplicate refusal | in-memory | — | sealed |
| definitions | `register_definition` | any | separate store; cannot replace protected | in-memory | — | corrected |
| physical facts | `PhysicalFactVerifier` | any (public) | ledger append requires observer token | in-memory | — | token-gated |
| evidence admission | `register_evidence` | any | 8 checks incl. ledger token | `capability_records.evidence_ids` | — | corrected |
| requirements | `create_mission` / seal | any | seal verified on read | `missions` | SQL write | detected |

---

## 9. Tests added

`tests/test_authority_composed_adversarial_004.py` — 39 tests across six groups, every one
asserting the **persisted** state:

- **Group A (6)** verifier sealing: duplicate id, post-bootstrap replacement, extension on a
  protected capability, greedy verifier without inspection, type tampering, stability during an
  active mission.
- **Group B (8)** physical facts: hand-built, forged `observed_state`, re-pointed subject,
  cross-mission, cross-execution, LLM text, mock/fixture injection, identifier tampering, plus
  a positive check that every real fact carries a sequence.
- **Group C (6)** evidence: builder not an oracle, manual construction refused, cross-mission
  reuse, cross-execution reuse, `capability_id`/`evidence_type` substitution, one observation
  cannot satisfy a composite requirement.
- **Group D (4)** definitions: `bootstrap=True` grants nothing, runtime definition cannot
  satisfy a requirement, protected contract immutable, unknown capability rejected.
- **Group E (10)** requirements and finalisation: empty arguments, SQL tampering detected,
  cross-mission authorization, stale authorization, fabricated gate result, partial capability,
  LLM output, synthetic evidence, unknown requirement, `NO_REQUIREMENTS_DECLARED` requires an
  explicit persisted property, failure between evaluation and persistence.
- **Group F (8)** integration: real observation completes, insufficient evidence does not,
  resume re-evaluates, recovery grants nothing, concurrent certification, completion racing
  evidence change, foreign-database observation refused, own-database observation certifies.

Group F uses **real observations** by the authorized observer. Groups A–E are synthetic
infrastructure tests and are labelled as such; none of them is presented as physical
validation.

### Test modifications (disclosed)

| Test | Change | Reason |
|---|---|---|
| `adversarial_003::test_A9`, `A16` | Reason-code assertion widened | Rejection taxonomy unified; both codes are rejections |
| `adversarial_003::test_A23`, `test_runtime_registered_capability…` | Rewritten to use **real observations** keyed on the observed subject instead of `dataclasses.replace(sqlite_fact, subject=…)` | The old technique re-pointed a fact and is now correctly refused. Rewritten to exercise the mechanism honestly rather than by fabrication |
| `adversarial_003::test_existing_definition_cannot_be_overwritten` | `ValueError` → `PermissionError` | Definition replacement is now an authority refusal |
| `consolidation_003::test_F`, `forensic_002::test_08` | Reason-code assertion widened | Same taxonomy change |

No test was deleted. No assertion was weakened to hide a failure. No test was changed from
"rejects" to "accepts".

---

## 10. Adversarial test results

| ID | Attack | Result | Evidence |
|---|---|---|---|
| A1 | duplicate trusted verifier id | PASS | `PermissionError` |
| A2 | trusted verifier replaced after bootstrap | PASS | registry still `_verify_sqlite_persistence_bound` |
| A3 | extension verifier on protected capability | PASS | `PermissionError` for all 3 protected caps |
| A4 | verifier claims all types without inspection | PASS | `OBSERVATION_NOT_IN_LEDGER` before verifier runs |
| A6 | verifier config mutated during active mission | PASS | mapping unchanged after 3 attempts |
| B1 | hand-built fact with `verified=True` | PASS | `observation_sequence == 0`, refused |
| B2 | forged `observed_state` | PASS | `OBSERVATION_STATE_MISMATCH` |
| B3 | real fact re-pointed to another capability | PASS | `CAPABILITY_MISMATCH` |
| B5 | fact reused across executions | PASS | `EXECUTION_MISMATCH` |
| B6 | LLM text as physical fact | PASS | `COMMAND` fact certifies nothing |
| B8 | caller appends to ledger | PASS | `PermissionError` |
| C1 | builder used with fabricated fact | PASS | `EvidenceRejected` |
| C2 | hand-built evidence registered | PASS | `NOT_IMPLEMENTED` (both bad and leaked-key signatures) |
| C3 | authentic evidence reused cross-mission | PASS | mission B not `VERIFIED` |
| C5 | `capability_id` / `evidence_type` substitution | PASS | both refused |
| C8 | one observation, composite requirement | PASS | `PARTIAL` |
| D1 | `bootstrap=True` at registration | PASS | `can_satisfy_requirement == False` |
| D2 | runtime definition satisfies a requirement | PASS | gate refuses |
| D3 | protected definition replaced | PASS | `PermissionError` |
| D5 | unknown capability as requirement | PASS | not completed |
| E1 | empty arguments replace requirements | PASS | parameters absent |
| E3 | requirements tampered by SQL | PASS | `BLOCKED` + `REQUIREMENTS_INTEGRITY_FAILURE` audit reason |
| E4 | authorization crosses missions | PASS | mission B incomplete |
| E5 | stale authorization after evidence changes | PASS | authorization refused **and** recorded; completion only via fresh evaluation |
| E6 | fabricated `MissionGateResult` | PASS | `PARTIALLY_COMPLETED` |
| E7 | partial capability completes mission | PASS | incomplete |
| E8 | `LLM_OUTPUT` evidence | PASS | refused |
| E9 | `TEST_SYNTHETIC` evidence | PASS | refused |
| E11 | forcing `NO_REQUIREMENTS_DECLARED` | PASS | needs `declare_no_requirements`; declared-empty is `BLOCKED` |
| E12 | failure between evaluation and persistence | PASS | mission not terminal |
| F1–F8 | integration, real observations | PASS | see §9 |
| X1–X7 | independent post-audit probes | PASS | 0 breaches |
| X8 | foreign-database observation | PASS (after fix) | `INVALID_PROVENANCE` |
| X9 | forged evidence with leaked key | PASS (after fix) | `NOT_IMPLEMENTED` |

**39 composed tests + 8 independent probes + the 2 original audit attacks: 0 breaches.**

---

## 11. Full suite

```
$ python -m pytest tests/ -q
423 passed in 106.03s (0:01:46)
```

```
$ python -m pytest tests/ -p no:cacheprovider -q --co
423 tests collected in 0.45s
```

collected 423 · passed 423 · failed 0 · skipped 0 · errors 0 · xfailed 0. No timeouts, no
collection errors, no deselection.

---

## 12. Reproducible evidence per conclusion

Commands actually executed, with observed output.

**Audit 004 CRITICAL-1 (original chain) — now blocked at step 2:**
```
$ python audit004_minimal_repro.py
STEP 2 — caller replaces the capability verifier (public registry method)
PermissionError: 'CAP_STATE_ENGINE' is a protected capability. Its verifier cannot be
registered or replaced at runtime.
```

**Audit 004 CRITICAL-2 (leaked key) — now inert:**
```
$ python audit004_keypath.py
  FILESYSTEM_EVIDENCE  is_authentic=True
  DATABASE_EVIDENCE    is_authentic=True
  registry statuses: ['NOT_IMPLEMENTED', 'NOT_IMPLEMENTED']
  CAP_STATE_ENGINE: NOT_IMPLEMENTED
  mission verdict: PARTIALLY_COMPLETED
RESULT: no breach
```
Note the signature is still valid — it is simply no longer sufficient.

**HIGH-2 (requirements tampering):**
```
$ python audit004_requirements_check.py
  integrity ok: False
  verdict after tamper: BLOCKED
  persisted status:     BLOCKED
  MISSION_TRANSITION     reason=REQUIREMENTS_INTEGRITY_FAILURE
```

**Post-fix probe set:** `probes=13 breaches=0`
**Independent probe set:** `independent probes=8 breaches=0`
**X8 cross-database:** `EvidenceRejected: CAP_STATE_ENGINE: INVALID_PROVENANCE`

---

## 13. Migrations and compatibility

New column `missions.requirements_seal TEXT NOT NULL DEFAULT ''`, added to both the fresh
`CREATE TABLE` and the rebuild path. `SCHEMA_VERSION` is 2 and unchanged by this column
because the existing rebuild already covers "column missing" via `needs_columns`.

Compatibility verified: a pre-003 database is rebuilt, rows preserved, CHECK widened, and the
new column defaults to `''`. A mission row with an **empty** seal is treated as *unverifiable*
rather than trusted, so a legacy mission cannot be quietly completed on unverified
requirements — it blocks until re-declared. No historical data is deleted; the migration is a
single transaction with a row-count check and rollback.

**Not claimed:** the migration was exercised on a constructed legacy schema and on fresh
databases. It has not been exercised against a production database of unknown provenance.

---

## 14. Limitations, accepted risks, unresolved findings

### Unresolved (accepted, documented)

1. **Model B is not addressed.** Arbitrary in-process code can read `_authority._KEY`, reach
   `_OBSERVER_TOKEN`, and mutate `_REGISTRY` / `_DEFINITIONS`. No in-process design prevents
   this. Guarantees are claimed for Model A only.
2. **`requirements_seal` is detection, not prevention.** An adversary who writes SQL *and*
   recomputes the seal defeats it. It closes the audit's accidental/direct-column rewrite.
3. **Only one capability is verifiable.** `CAP_STATE_ENGINE` has a real verifier. The other
   four have none and are permanently `NOT_IMPLEMENTED`. This is intentional: per §18 no new
   capabilities were implemented, and per rule 4 no state was inflated to `VERIFIED`.
4. **Extension verifiers remain possible for non-protected capabilities.** They carry no
   requirement authority, but the registry will still *score* them. Reported as a MEDIUM
   observation, not a bypass.
5. **The ledger is in-memory and process-scoped.** After a restart, no observation survives,
   so any mission needing re-verification must re-observe. Nothing currently depends on
   surviving it, but it would matter for cross-process verification.

### Not introduced, not implemented (per §18)

Out-of-process verifier, plugin system, distributed architecture, new capabilities.

---

## 15. Recommendations for the next independent audit

1. **Attack the resource binding.** It is the newest control and the least covered. Try to
   certify a mission using an observation of a *symlinked*, *hardlinked*, or *copied* database
   that is not byte-identical to the mission's store.
2. **Attack single-use consumption under concurrency.** Two threads racing to consume one
   observation for the same `(mission, execution)`. `F5` covers four threads but not a
   deliberate race on the ledger lock.
3. **Try to make the extension mechanism authoritative.** Find any path by which an extension
   capability's `VERIFIED` could be read as satisfying a protected requirement.
4. **Verify the seal under partial corruption** — e.g. only `requirements_declared` altered,
   or the seal column truncated to `NULL` rather than `''`.
5. **Re-test the full CRITICAL-1 chain end-to-end after any change to the registry or builder.**
   The 003 suite passed while the chain worked; composition is the failure mode to hunt.
6. **Verify the Model B claim empirically** rather than accepting it, so the boundary of the
   guarantee is measured rather than asserted.

---

## 16. Verification checklist

- [x] Public verifier-replacement attack cannot certify a protected capability — `A1`, `A2`, `A3`
- [x] A fabricated physical fact cannot pass validation — `B1`, `B2`, `C1`
- [x] The legitimate builder is not a signing oracle — `C1`, `C2`
- [x] Valid evidence bound to mission, capability and execution — `C3`, `C4`, `C5`
- [x] Bootstrap definitions cannot be injected — `D1`, `D2`, `D3`
- [x] Declared requirements cannot be removed by empty arguments — `E1`
- [x] Requirements inconsistency blocks completion — `E3`
- [x] The only valid route to `COMPLETED` re-evaluates requirements and evidence — §8, `E6`
- [x] Forged, stale and cross-mission authorizations rejected — `E4`, `E5`, `E6`
- [x] `LLM_OUTPUT` cannot certify — `E8`
- [x] Synthetic evidence cannot elevate capabilities — `C2`, `E9`
- [x] Resume and recovery do not skip authority evaluation — `F3`, `F4`
- [x] Authority and state changes consistent under error and concurrency — `E12`, `F5`, `F6`
- [x] Composed adversarial tests detect the audit 004 attacks — §10
- [x] Positive tests show a real authorized observation certifies — `F1`, `F8`
- [x] Full suite passes — 423/423
- [x] No known undocumented bypasses remain within Model A
- [x] Threat-model limits documented without unjustified absolute claims — §7, §14

---

## 17. Final verdict

# `AUTHORITY_INTEGRITY_PARTIAL`

**Why not VERIFIED.** The VERIFIED bar requires that no critical or high finding remains
unresolved *within the declared threat model*. CRITICAL-1, CRITICAL-2, HIGH-1 and HIGH-2 are
closed and reproduced as closed. But I am not able to claim the model is fully characterised,
for two reasons I want to state plainly rather than bury:

1. **The Model A boundary is asserted, not exhaustively measured.** My composed suite and
   independent probes find no breach, but the resource-binding control in particular is new and
   thinly covered. A green suite plus eight probes is evidence, not proof.
2. **One control was wrong in the way I originally implemented it and only surfaced because an
   independent probe happened to hit it.** The parameter-name mismatch that silently disabled
   resource binding (§10, X8) is direct evidence that my own reasoning about my own controls
   can be wrong. That is precisely the failure mode an independent audit exists to catch, and
   it argues against self-certifying VERIFIED.

**Why not FAILED.** The rubric reserves FAILED for a reproducible bypass that fabricates
completion, fabricates capability evidence, eliminates requirements, or skips the gate. Every
one of those is now blocked, demonstrated by re-running the audit's own scripts. The original
CRITICAL-1 chain fails at step 2; the key leak yields `PARTIALLY_COMPLETED`; requirement
tampering is detected and blocks.

**What is genuinely verified:** under Model A, capability `VERIFIED` now requires an
observation that the authorized observer actually performed, bound to one mission and one
execution, for the mission's own resource. That is a real structural improvement over 003,
where the same conditions were met by writing a dataclass literal.

**What is not:** anything about Model B, and anything about how thoroughly the Model A surface
has been explored. Four of five capabilities remain permanently unverifiable, which is the
honest state of this system and not a defect to be quietly improved.
