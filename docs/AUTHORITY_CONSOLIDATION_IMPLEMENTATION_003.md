# AUTHORITY CONSOLIDATION IMPLEMENTATION 003
## TRUE AUTHORITY BOUNDARY REPAIR

---

## 1. Executive Result

All eight defects from FORENSIC AUDIT 002 (D-1 … D-8) are closed, and each closure was
verified by **re-running the original attack scripts** — not by the test count.

| Evidence | Result |
|----------|--------|
| Forensic AUDIT 002 attack reproductions re-run | **24 / 24 now rejected** (was 6 successful bypasses) |
| New adversarial suite `test_authority_adversarial_003.py` | **45 passed** |
| Full suite | **384 passed, 0 failed, 0 skipped, 0 errors** (95s) |
| Live capabilities that can reach VERIFIED | **1 of 5** (`CAP_STATE_ENGINE`, real SQLite inspection) |

The previous state was 331 passing with six reproducible bypasses. The suite grew by 53 tests
and every one of the vulnerabilities the audit found is now closed by construction rather
than by test expectation.

**No new capability was added.** Four of the five pre-existing capabilities
(`CAP_CHECKPOINT_RESUME`, `CAP_DESKTOP_VISION`, `CAP_PLAYWRIGHT_BROWSER`,
`CAP_WHATSAPP_AUTO_REPLY`) now have *no* capability-specific verifier and therefore can never
reach VERIFIED. That is the honest state: they are not operationally implemented.

---

## 2. D-1 … D-8 Closure Matrix

| Finding | Before | Repair | Verification | Status |
|---|---|---|---|---|
| **D-1** Public `create_authorization(result)` | `MissionCompletionGate.create_authorization` accepted any `MissionGateResult`; `verify=True, persisted=COMPLETED` | API deleted. Only `evaluate_and_authorize` issues, and it computes the verdict itself. **Plus** `update_mission_status` re-derives the verdict independently and discards any authorization that disagrees | A1 (API absent), A1b (forged result → `PARTIALLY_COMPLETED`), audit script | **CLOSED** |
| **D-2** Mutable / re-hashable authorization | Plain attrs; `_compute_authorization_id` was a public re-hash oracle; mutation + rehash → `COMPLETED` | `@dataclass(frozen=True)`; HMAC-SHA256 under a process-local key in private module `_authority`; bound to mission, requirements, requirements_declared, evaluation_id, verdict, authorized_status, execution_id | A2, A3, A4, A20, A21, audit script | **CLOSED** |
| **D-3** `create_mission(status="COMPLETED")` | Persisted COMPLETED with zero authority | `create_mission` rejects every terminal state (`INITIAL_MISSION_STATUSES`); sole terminal transition is `complete_mission_with_authorization` | A5, A22, `test_18c`, audit script | **CLOSED** |
| **D-4** `set_capability_status(VERIFIED)` | One call falsified any capability; `evidence_ids == []` | Replaced by `set_capability_limitation`, which refuses `VERIFIED`/`PARTIAL` (`CALLER_ASSIGNABLE_STATUSES`). VERIFIED/PARTIAL are derived only from coverage | A6, A6b, A6c, audit script | **CLOSED** |
| **D-5** Caller-supplied requirements | `update_mission_status(requirements=[], allow_empty=True)` completed a mission whose row required `CAP_X` | `allow_empty_requirements` **removed**. Requirements read from the persisted row. Empty-with-no-override is a persisted property (`requirements_declared`); declared-but-empty is `BLOCKED` | A7, A7b, A25, audit script | **CLOSED** |
| **D-6** No capability-specific verification | `capability_id`/`evidence_type` caller-chosen; `bool(data)` accepted; pytest+curl drove `CAP_WHATSAPP_AUTO_REPLY` → VERIFIED | `CapabilityDefinition.verifiable_by_fact_types` declares what may prove what; `CapabilitySpecificVerifier` enforces fact-type, subject binding, `isinstance`, and a registered verifier. `verify_capability_operation` deleted | A9, A10, A16, A23, A24, audit script | **CLOSED** |
| **D-7** LLM could influence verdicts | `MISSION_COMPLETED` claim accepted on `critical_gaps==0`, no gate call; `origin="LLM_OUTPUT"` reached VERIFIED | Claim validated through the gate using **persisted** requirements; `ClaimValidator` holds no write path; origin allowlist has exactly one value | A8, A8b, "claim validator is read-only" test, audit script | **CLOSED** |
| **D-8** Weak evidence binding | Non-emptiness only; no origin allowlist; no cross-mission/execution; `observation_id` dropped; records global | Eight admission checks incl. HMAC authenticity, single origin, capability match, mission match, execution binding, persisted `observation_id`; status computed **per mission** | A11, A12, A14, A15, A11b, A11c, origin test, audit script | **CLOSED** |
| **SQLite** No migration | Legacy DB kept 5-value CHECK; every non-COMPLETED verdict raised `IntegrityError` | `PRAGMA user_version` + transactional table rebuild with row-count verification | Migration test, audit script, manual legacy test | **CLOSED** |

---

## 3. Authority Model

```
                     LLM
                      │  plan / hypothesis / prose
                      ▼
                 NO AUTHORITY HERE  ── text is data, never evidence
                      │
                      ▼
                  Executor
                      │  tool invocation
                      ▼
             Physical Observation          (file, exit code, DB page)
                      │
                      ▼
          PhysicalFactVerifier            → VerifiedPhysicalFact (frozen)
                                             fact_type, subject, observed_state,
                                             execution_id
                      │
                      ▼
       CapabilitySpecificVerifier          ← AUTHORITY IS BORN HERE
                 three gates:                 (only component that may say
                   1. fact_type declared?     "this fact proves THIS capability")
                   2. subject == capability?
                   3. registered verifier ran?
                      │
                      ▼
        CapabilityVerificationResult       (frozen, immutable)
                      │
                      ▼
        AuthorizedEvidenceBuilder          capability_id and evidence_type are
                      │                   TAKEN FROM the result, not the caller
                      ▼
          CapabilityEvidence (HMAC-signed)
                      │
                      ▼
      CapabilityEvidenceRegistry          admission checks + per-mission
                      │                   coverage derivation
                      ▼
         MissionCompletionGate             reads PERSISTED requirements
                      │
                      ▼
          GateAuthorization                frozen + HMAC + bound
                      │
                      ▼
              StateEngine                  RE-DERIVES the verdict itself and
                      │                    discards any disagreeing authorization
                      ▼
                 COMPLETED
```

Authority is **born** at `CapabilitySpecificVerifier.verify`. It is **validated** at
`register_evidence` and again at `StateEngine.update_mission_status`. It is **consumed** at
`complete_mission_with_authorization`. It is **persisted** in `missions.status`.

---

## 4. Capability Verification Model

A capability reaches VERIFIED only through this conjunction:

1. **Declaration** — the capability exists in `CapabilityDefinition` with a
   `required_evidence_types` set and is `bootstrap=True`.
2. **Fact admissibility** — a real `VerifiedPhysicalFact` (checked with `isinstance`, so mocks
   and duck-typed objects are refused) whose `fact_type` appears in that capability's
   `verifiable_by_fact_types`, whose `subject` equals the capability, and whose `verified` is
   True.
3. **Capability-specific verification** — a verifier registered for `(capability, verifier_id)`
   inspects `observed_state` and returns the evidence types it *actually* proved. The verifier
   cannot claim a type the capability does not require; the result is filtered.
4. **Authorized construction** — `AuthorizedEvidenceBuilder` projects the result into one
   HMAC-signed `CapabilityEvidence` per satisfied type. `capability_id` and `evidence_type`
   come from the result.
5. **Registry admission** — eight checks including signature authenticity, single authorized
   origin, capability match, mission match, and evidence-type membership.
6. **Complete coverage, scoped to the mission** — status is
   `VERIFIED` only when every required type is present among evidence bound to *that mission*.

Consequences, all deliberate:

- `CAP_WHATSAPP_AUTO_REPLY` cannot be verified by pytest, curl, a file write, or a zero exit
  code, because no definition declares any of those fact types for it and no verifier exists.
- A capability registered at runtime is modelled and scored by the registry but is **not
  bootstrap**, so `can_satisfy_requirement()` is False and it can never unblock a mission.
  This closes the "invent a capability plus a permissive verifier" path.
- `CAP_STATE_ENGINE` is genuinely verifiable: a real on-disk SQLite inspection (file exists,
  WAL active, `missions` table and columns present, probe row round-trips) yields
  FILESYSTEM + DATABASE evidence. This is the one honest positive path, and A24 exercises it.

---

## 5. Mission Completion Model

1. A mission is created in `PENDING` or `IN_PROGRESS` only. Terminal creation raises.
2. Requirements are persisted once at creation and are thereafter **sovereign**.
   `requirements_declared=0` records "this mission genuinely requires no capabilities";
   `requirements_declared=1` with an empty list is a declaration failure and yields `BLOCKED`.
3. `complete_mission_with_authorization` reads the persisted requirements, re-evaluates the
   gate itself, and compares any supplied authorization against that fresh verdict.
4. A disagreeing, unsigned, cross-mission, or wrong-execution authorization is **discarded**
   and an `evidence_gaps` row records the rejection. The re-derived verdict is applied either
   way — which is why a forged authorization is inert even if perfectly signed.
5. `MISSION_COMPLETED` is remapped to `COMPLETED`; `NO_REQUIREMENTS_DECLARED` is preserved as
   a distinct terminal state so "no requirements were declared" is never conflated with
   "requirements were met" or "requirements are unknown".

---

## 6. State Transition Authority

| Transition | Who may produce it | Enforced by |
|---|---|---|
| mission → `COMPLETED` | `StateEngine.update_mission_status` after re-deriving the gate verdict | no public status parameter; re-derivation |
| mission → `NO_REQUIREMENTS_DECLARED` | same, when `requirements_declared=0` and no blocking findings | same |
| mission → `BLOCKED` / `PARTIALLY_COMPLETED` / `COMPLETED_WITH_*` | same, derived only | same |
| mission → `PENDING` / `IN_PROGRESS` | `create_mission` only | `INITIAL_MISSION_STATUSES` |
| capability → `VERIFIED` | `register_evidence` coverage derivation, per mission | `CALLER_ASSIGNABLE_STATUSES` excludes it |
| capability → `PARTIAL` | same derivation | same |
| capability → `NOT_IMPLEMENTED` | derivation with no admitted evidence | same |
| capability → `BLOCKED_*` / `SIMULATED_ONLY` | `set_capability_limitation` | explicit allowlist |
| task → `VERIFIED` | `CheckpointEngine.mark_verified` | task-scoped, no mission authority |
| task → `*_TOOL_EXECUTION` | `CheckpointEngine` | task-scoped |

---

## 7. Evidence Provenance

| Field | Source | In signature | Checked at admission |
|---|---|---|---|
| `mission_id` | caller of the builder | yes | must equal the mission being certified |
| `task_id` | caller | yes | non-empty |
| `execution_id` | caller | yes | non-empty; bound to the authorization |
| `observation_id` | caller | yes | non-empty and now **persisted** in the evidence entry |
| `capability_id` | **verification result** | yes | must equal target capability |
| `evidence_type` | **verification result** | yes | must be in the capability's required set |
| `physical_evidence` | **verification result** | yes | must be True when physical verification is required |
| `physical_fact_reference` | verification result (`fact_id`) | yes | non-empty |
| `capability_verification_token` | verification result | yes | non-empty |
| `verifier` | registered verifier id | yes | — |
| `origin` | fixed constant | yes | must equal `CAPABILITY_SPECIFIC_VERIFIER` |
| `authorization` | `_authority.sign(payload)` | — | verified with `compare_digest` |

Cross-mission reuse fails at two independent points: the registry compares
`evidence.mission_id` to the mission being certified, and status is computed per mission, so
even admitted evidence cannot certify a second mission.

---

## 8. API Exposure Review

| API | Before | Now |
|---|---|---|
| `MissionCompletionGate.create_authorization` | public, took arbitrary result | **removed** |
| `StateEngine.update_mission_status(required_capabilities=…)` | caller could supply | **removed** |
| `StateEngine.update_mission_status(allow_empty_requirements=…)` | evasion lever | **removed** |
| `StateEngine.create_mission(status="COMPLETED")` | bypass | **rejected** (`ValueError`) |
| `StateEngine.set_capability_status(VERIFIED)` | falsified any capability | **raises** `PermissionError` for derived states |
| `PhysicalFactVerifier.verify_capability_operation` | `bool(data)` as proof | **removed** |
| `AuthorizedEvidenceBuilder.create_evidence` | caller chose capability + type | **removed** |
| `AuthorizedEvidenceBuilder._derive_physical_evidence` | True for any file/test/exit-0 | **removed** |
| `GateAuthorization.__init__` | public, verifiable after `_issue` | still public but **inert** — not in any registry and cannot be signed |
| `CapabilityEvidenceRegistry.register_evidence` | accepted on non-emptiness | eight admission checks |
| `register_definition` / `register_verifier` | n/a | may add capabilities, but non-`bootstrap`, so they cannot satisfy a requirement |

AST-level verification confirms `allow_empty_requirements` and `verify_capability_operation`
survive only inside docstrings — they are not parameters, keywords or attributes anywhere in
`core/`.

---

## 9. Bypass Search

Write sites for mission/capability status in `core/`:

| Site | Classification |
|---|---|
| `state_db.py:393` INSERT INTO missions | AUTHORIZED — `create_mission`, terminal states refused |
| `state_db.py:488` UPDATE missions SET status | AUTHORIZED — re-derived verdict only |
| `state_db.py:286` INSERT INTO missions_migrated | AUTHORIZED — migration, values copied |
| `capability_registry.py:215` `record["verification_status"] = self._derive_status(...)` | AUTHORIZED — derived |
| `capability_registry.py:284` read-path recompute | AUTHORIZED — derived |
| `capability_registry.py:312` `record["verification_status"] = status` | AUTHORIZED — `set_capability_limitation`, non-derived states only |
| `physical_fact_verifier.py:261` INSERT probe row | AUTHORIZED — transient probe, deleted immediately, status hard-coded `IN_PROGRESS` |

Term search: `authorized_by_gate` → **0 hits** in `core/`. `create_authorization` → 2 hits,
both prose. `set_capability_status` → 2 hits: one docstring, one thin alias that delegates to
the refusing `set_capability_limitation`. `MISSION_COMPLETED` → 9 hits, all constants,
comparisons, or the gate's own assignment.

`except: pass` inside the authority chain: **0**. The four in `state_db.py` are JSON-decode
fallbacks on read paths and connection close, none of which can convert a rejection into a
completion.

**No bypass path was found.** I am not claiming zero bypass paths as a proof; I am reporting
that the exhaustive search over write sites, removed APIs, and error handling produced no
route to `VERIFIED` or `COMPLETED` outside the modelled chain.

---

## 10. SQLite Migration

**Old schema** (pre-003): `missions` with no `required_capabilities`, no
`requirements_declared`, and a five-value status CHECK. No schema version.

**New schema** (version 2): adds `required_capabilities`, adds
`requirements_declared INTEGER NOT NULL DEFAULT 1`, and widens the status CHECK to the ten
authoritative values. `PRAGMA user_version = 2`.

**Migration path** (`StateEngine._migrate_schema` / `_rebuild_missions_table`):
1. Read `PRAGMA user_version` and `sqlite_master` for `missions`.
2. Rebuild required if the CHECK lacks `BLOCKED` **or** a column is missing **or**
   `user_version < 2`.
3. `PRAGMA foreign_keys=OFF` → `BEGIN IMMEDIATE` → create `missions_migrated` with the new
   definition → `INSERT … SELECT` the shared columns plus defaults `'[]'` and `1` →
   `DROP TABLE missions` → `ALTER TABLE missions_migrated RENAME TO missions`.
4. Verify row counts before/after; **raise and `ROLLBACK`** if they differ.
5. `COMMIT`, restore `foreign_keys=ON`, set `user_version`.

A table swap is the only way SQLite permits widening a CHECK, so `CREATE TABLE IF NOT EXISTS`
alone was provably insufficient (demonstrated in audit 002).

**Verified on a legacy database**: `user_version` 0 → 2, legacy row and its child
`planner_tasks` row preserved, `raw_prompt` intact, and a `BLOCKED` verdict persisted without
`IntegrityError` where it previously failed.

**Backward compatibility**: existing columns are preserved by name; only the two new columns
and the CHECK change. A pre-existing `COMPLETED` row keeps its value until the gate re-derives
a verdict for it.

**Rollback**: the migration is one transaction. Any failure rolls back and re-raises, leaving
the original database untouched. A pre-migration backup remains the operator's responsibility
and is not automated.

---

## 11. Test Forensics

Nothing is hidden. Every modification is listed.

### New files
| File | Purpose |
|---|---|
| `tests/authority_fixtures.py` | helpers that route through the **real** chain; no hand-built evidence |
| `tests/test_authority_adversarial_003.py` | 45 adversarial tests, A1–A26 plus migration |

### Rewritten — assertions that encoded a vulnerability
| File / test | Was | Now | Reason |
|---|---|---|---|
| `003::test_B_synthetic_file` | asserted a synthetic file `verified=True` | asserts it verifies nothing | `verify_capability_operation` accepted `bool(data)` |
| `003::test_C_mock_observation` | asserted a mock dict `verified=True` | asserts the function is gone and truthiness proves nothing | same |
| `003::test_F_existing_irrelevant_artifact` | asserted an unrelated source file `verified=True` | asserts rejection | same |
| `003::test_J_complete_required_evidence` | asserted VERIFIED from two hand-built records | asserts NOT VERIFIED; positive case moved to `test_J2` over the real chain | D-6/D-8 |
| `004::test_b_cross_mission_replay_is_blocked` | **mutated `ev.mission_id` and asserted the mutation took** | registers mission-A evidence against mission-B and asserts refusal | the test demonstrated the bypass instead of preventing it |
| `004::test_g_mock_cannot_certify` | `assert True` inside `try/except: pass` | drives the builder and asserts `EvidenceRejected` | could not fail |
| `004::test_synthetic_evidence_cannot_reach_verified` | asserted PARTIAL for the wrong reason; `TEST_SYNTHETIC` origin in fact reached VERIFIED | origin is the only defect; asserts never VERIFIED | its stated intent was false |
| `004::test_cross_mission_evidence_is_blocked` | only omitted `mission_id`; no cross-mission check existed | replaced by a real cross-mission test | mislabelled |
| `002::test_03_full_required_evidence_promotes_to_verified` | asserted VERIFIED from hand-built evidence | becomes `test_03b` (refusal) + `test_03c` (real positive) | D-6 |
| `browser::test_09` | asserted VERIFIED from two literals | asserts refusal and NOT_IMPLEMENTED | D-6 |
| `forensic_002::test_08` | `verify_capability_operation(<file>)` → `capability_verified: True` | asserts a TEST fact is inadmissible for any capability | `bool(data)` as proof |
| `forensic_002::test_09` | a text file with a PNG signature "verified" CAP_DESKTOP_VISION | the fake screenshot is rejected; the real cycle runs against CAP_STATE_ENGINE | purest form of D-6 |

### Modified
| File | Change | Reason |
|---|---|---|
| `001` | fully rewritten; `test_05` inverted, `test_06` now expects `NOT_IMPLEMENTED`, `test_03` inverted with a positive `test_03b`, `test_04` became a structural property | removed API; new architecture |
| `002` | fully rewritten | removed API |
| `004` | fully rewritten | tautologies and mislabelled cases |
| `state_engine::test_18` | **removed `allow_empty_requirements=True`** — I introduced that in 002 — and now expects `NO_REQUIREMENTS_DECLARED`; added `test_18b`, `test_18c` | that argument was the D-5 evasion |
| `checkpoint_resume::test_07/17/20` | missions now created with `declare_no_requirements=True`; expect `NO_REQUIREMENTS_DECLARED` | these test resume mechanics; the missions need to declare no requirements rather than relax evaluation |
| `f02_adaptive_investigation` | `VerifiedFact(target=…)` → `subject=…` | field renamed for clarity |
| `f03`, `browser` | no change needed; diagnostic fields restored in production | — |

**Tests deleted: none.** Every adversarial case was preserved and inverted. **No test was
weakened to hide a failure**, and no bypass was converted into expected behaviour: in every
inverted case the vulnerable assertion became a *rejection* assertion, which is strictly
harder to pass.

---

## 12. Adversarial Test Results

| ID | Attack | Result | Evidence |
|----|--------|--------|----------|
| A1 | `create_authorization` with fabricated result | **PASS** | `hasattr == False`; forged object → `PARTIALLY_COMPLETED` |
| A2 | mutate emitted authorization | **PASS** | `FrozenInstanceError` |
| A3 | mutate + rehash | **PASS** | key unobtainable; tampered clone `is_authentic() == False` |
| A4 | reuse authorization across missions | **PASS** | mission B stays unterminated |
| A5 | `create_mission(status="COMPLETED")` | **PASS** | `ValueError` |
| A6 | `set_capability_status(VERIFIED)` | **PASS** | `PermissionError` |
| A7 | caller substitutes `[]` for `CAP_X` | **PASS** | parameter absent; mission → `PARTIALLY_COMPLETED` |
| A8 | LLM declares capability / mission VERIFIED | **PASS** | claims unverified; status unchanged |
| A9 | pytest success verifies WhatsApp | **PASS** | `FACT_TYPE_NOT_DECLARED_FOR_CAPABILITY` |
| A10 | curl exit 0 verifies WhatsApp | **PASS** | same |
| A11 | arbitrary / unrequired `evidence_type` | **PASS** | `EVIDENCE_TYPE_NOT_REQUIRED_BY_CAPABILITY` |
| A12 | arbitrary `capability_id` | **PASS** | `EVIDENCE_CAPABILITY_MISMATCH` |
| A13 | evidence without mission binding | **PASS** | `EVIDENCE_BINDING_INCOMPLETE` |
| A14 | Mission-A evidence reused in Mission-B | **PASS** | `CROSS_MISSION_EVIDENCE_REJECTED` |
| A15 | synthetic evidence reaches VERIFIED | **PASS** | signature invalid → refused |
| A16 | valid fact of a different capability | **PASS** | `FACT_SUBJECT_IS_DIFFERENT_CAPABILITY` |
| A17 | Resume substitutes requirements | **PASS** | mission stays unterminated |
| A18 | Recovery reuses a previous completion claim | **PASS** | stale `COMPLETED` re-derived to non-terminal |
| A19 | restart preserves a valid authorization | **PASS** | fresh process → non-terminal |
| A20 | deepcopy / pickle → usable authority | **PASS** | tampered clones all rejected |
| A21 | authorization reused for another execution_id | **PASS** | `is_valid_for(..., execution_id="exec-B")` False |
| A22 | COMPLETED without passing the Gate | **PASS** | unverified requirement → non-terminal |
| A23 | partial coverage | **PASS** | `PARTIAL` |
| A24 | full physically-verified coverage | **PASS** | `VERIFIED`, and **not** inherited by another mission |
| A25 | requirements X,Y with evidence only X | **PASS** | `PARTIALLY_COMPLETED` |
| A26 | requirements X,Y with valid evidence for both | **PASS** | `COMPLETED` only via a valid authorization |

---

## 13. Full Test Suite

```
collected   384
passed      384
failed        0
skipped       0
errors        0
xfailed       0
duration    ~96s
```

No timeouts, no collection errors, no deselection, no hidden failures.

---

## 14. Remaining Findings

### CRITICAL
None. Every bypass reproducible in audit 002 is closed and re-verified.

### HIGH
None.

### MEDIUM
1. **`GateAuthorization._issue` is reachable from Python.** In-process privacy is a convention,
   not a guarantee. This is *not* an exploitable bypass: `update_mission_status` re-derives the
   verdict from persisted state and discards any authorization that disagrees, so a
   self-issued authorization cannot produce `COMPLETED` unless the gate independently agrees.
   Recommended hardening: move issuance behind a closure-captured token rather than a
   classmethod.
2. **`evaluate_mission_completion` remains a public read-only function** that accepts
   arbitrary `required_capabilities`. It confers no authority — nothing persists its result —
   but it is a second evaluation entry point and could be mistaken for one.
3. **`register_definition` + `register_verifier` let a caller model a capability the registry
   will score as VERIFIED.** Completion is blocked by `can_satisfy_requirement()`, so this
   cannot complete a mission, but the registry will report `VERIFIED` for such a capability to
   a caller reading it directly. Recommended: gate registration behind bootstrap, or have
   `get_capability_status` report non-bootstrap capabilities as `NOT_IMPLEMENTED`.
4. **`physical_fact_verifier.verify_sqlite_persistence` writes a probe row** into the
   production database during verification. It is deleted in the same call and the mission
   used is a synthetic `__probe_*` id, but it is a write on a read-path-style operation.

### LOW
5. `orchestrator.py:296` and `:450` still swallow exceptions with `except: pass`. They fail
   *closed* (no evidence registered, no completion), but they hide certification errors.
6. The `evidence_gaps` row written on authorization rejection is not surfaced anywhere.
7. `_authority` regenerates its key per process, so authorizations do not survive a restart by
   design. Nothing requires them to, but a future cross-process flow would need real signing.

---

## 15. Final Verdict

# `AUTHORITY_INTEGRITY_VERIFIED`

The bar set for this verdict is: no critical bypass is reproducible. That bar is met, and the
claim rests on re-running the audit's own attack scripts (24/24 rejected) rather than on the
suite size.

Specifically demonstrated:

- **No public API forges a `GateAuthorization`.** `create_authorization` is deleted; issuance
  happens only inside the gate, and persistence independently re-derives the verdict, so even
  a validly-signed forgery is inert.
- **No setter can declare `VERIFIED`.** Derived states raise `PermissionError`.
- **No direct creation of `COMPLETED`.** Terminal states are refused at creation.
- **Requirements come from the persisted mission.** No caller parameter can supply or relax
  them; empty-without-declaration is `BLOCKED`.
- **The LLM certifies nothing.** Claim validation routes through the gate and holds no write
  path.
- **Evidence is bound to real physical facts**, with HMAC authenticity, single authorized
  origin, and mission/task/execution/observation binding.
- **Capability verification is specific.** No fact type is declared for any capability except
  `SQLITE_PERSISTENCE` for `CAP_STATE_ENGINE`.
- **Coverage is deterministic and mission-scoped.**
- **Cross-mission reuse is rejected** at admission and again at evaluation.
- **Resume and recovery re-evaluate** and never inherit or confer authority.
- **SQLite schema and migration are coherent**, versioned, transactional, and non-destructive.
- **Adversarial tests pass (A1–A26)** and the **tautological tests are corrected** — the two
  worst offenders (`assert True` in a bare `try/except`, and a cross-mission test that
  asserted the mutation succeeded) are now real tests.

I want to be explicit about one thing rather than let the verdict imply more than it does:
this is a **boundary repair, not a capability expansion**. Four of the five capabilities can no
longer be verified, because they have no capability-specific verifier. That is the correct
posture under the new model, but it means the system is honest about being less capable than
it appeared — and that is the intended outcome, not a regression to be papered over.

The four MEDIUM findings above are documented, not concealed, and none of them is a route to
`VERIFIED` or `COMPLETED`.
