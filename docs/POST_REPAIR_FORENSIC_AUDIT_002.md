# POST-REPAIR FORENSIC AUDIT 002
## VERIFY — AUTHORITY CONSOLIDATION IMPLEMENTATION 002

**Mode:** READ-ONLY forensic audit. No source file was modified during this audit.
**Date:** 2026-09-28
**Verdict:** `AUTHORITY_INTEGRITY_FAILED`

---

## 1. Scope

Objective: determine whether the seven claimed authority boundaries are actually closed, and
whether the five closure claims of IMPLEMENTATION 002 hold.

The 331/331 test result was treated as a *starting observation only*, not as evidence. Every
boundary was attacked directly with executable adversarial scripts. The full test suite remains
green **while six independently reproducible completion/capability/requirements bypasses exist**,
which is itself the central finding of this audit.

Boundary targets:

| ID | Boundary |
|----|----------|
| A | CALLER ≠ GATE AUTHORITY |
| B | REQUIREMENTS ≠ EMPTY-REQUIREMENTS BYPASS |
| C | VERIFIED FACT ≠ PHYSICAL CAPABILITY EVIDENCE |
| D | CAPABILITY EVIDENCE ≠ CAPABILITY VERIFIED |
| E | GATE AUTHORIZATION ≠ FABRICATED OBJECT |
| F | PERSISTENCE ≠ COMPLETION AUTHORITY |
| G | RESUME ≠ NEW COMPLETION AUTHORITY |

---

## 2. Code inspected

- `core/cognitive/gate_authorization.py` (118 lines)
- `core/cognitive/mission_completion_gate.py` (101 lines)
- `core/state_db.py` (781 lines) — schema, `create_mission`, `update_mission_status`
- `core/cognitive/capability_registry.py` (245 lines)
- `core/cognitive/authorized_evidence_builder.py` (94 lines)
- `core/cognitive/physical_fact_verifier.py` (219 lines)
- `core/resume_engine.py` (268 lines)
- `core/checkpoint_engine.py` (134 lines)
- `core/orchestrator.py` (813 lines) — gate + evidence call sites
- `tests/test_authority_consolidation_001..004.py`, `test_browser_engine.py`,
  `test_forensic_repair_002.py`, `test_state_engine.py`, `test_checkpoint_resume.py`

All attacks were executed from throwaway scripts under `%TEMP%\opencode\`, against temporary
SQLite databases. The repository was not written to.

---

## 3. GateAuthorization audit

### 3.1 Structure

- **Who can create:** `GateAuthorization.__init__` (line 23) is a *public* constructor.
  `GateAuthorization._issue` (line 36) is the only path that registers into
  `_ISSUED_AUTHORIZATIONS` (`weakref.WeakSet`, line 9). `MissionCompletionGate.create_authorization`
  (`mission_completion_gate.py:88`) is the sole production caller of `_issue`.
- **Who can verify:** `GateAuthorization.verify_authorization` (line 107) — checks
  `isinstance`, `mission_id` equality, and `verify()`.
- **Fields:** `mission_id`, `gate_result`, `required_capabilities`, `evaluated_at`,
  `_authorization_id`.
- **Integrity:** SHA-256 over `{mission_id, can_complete, mission_status,
  sorted(required_capabilities), evaluated_at}` (`_compute_authorization_id`, line 54).
- **Proof of gate issuance:** membership in `_ISSUED_AUTHORIZATIONS` (`verify`, line 102).
- **Link to gate result:** **none.** The gate result is not hashed, not compared against a
  re-evaluation, and carries no provenance of its own.

### 3.2 Attack matrix

| # | Attack | Result |
|---|--------|--------|
| 1 | `object()` as authorization | **PASS (blocked)** — `isinstance` check, line 112 |
| 2 | Raw `MissionGateResult` | **PASS (blocked)** — not a `GateAuthorization` |
| 3 | Direct `GateAuthorization(...)` constructor | **PASS (blocked)** — not in WeakSet |
| 4 | `from_dict()` | **PASS (blocked)** — unregistered by design |
| 5 | `copy.deepcopy()` of a valid auth | **PASS (blocked)** — copy not registered |
| 6 | `pickle` round-trip | **PASS (blocked)** — unpickled copy not registered |
| 7 | Mutate `gate_result.can_complete=True` then recompute hash | **FAIL — BYPASS** |
| 8 | Retarget `mission_id` after issuance | **PASS (blocked)** |
| 11 | Reuse Mission-A authorization on Mission-B | **PASS (blocked)** |
| 13 | Use an authorization minted before any gate evaluation | **FAIL — BYPASS** |

### 3.3 CRITICAL-1 — public `create_authorization` mints authority from a fabricated result

`mission_completion_gate.py:88-101` is a **public static method that accepts any
`MissionGateResult` the caller supplies.** It performs no check that the result came from
`evaluate_mission_completion`. Observed:

```
fabricated[can_complete=True/MISSION_COMPLETED] verify=True persisted=COMPLETED  BYPASS!!
fabricated[can_complete=True/COMPLETED (raw)]  verify=True persisted=COMPLETED  BYPASS!!
```

A caller with no evidence, no verified capability and an unverified mission requirement writes
`COMPLETED` through the *fully legitimate* authorization path. The WeakSet is satisfied because
`create_authorization` really did call `_issue`. This voids boundary **A** and **E**, and
invalidates AUTH-01, AUTH-04 and AUTH-17.

**This is the root cause of the whole authority model.** The WeakSet proves *"an object was
constructed"*; it does not prove *"the gate evaluated this mission"*.

### 3.4 CRITICAL-2 — post-issuance mutation is accepted

`_compute_authorization_id` is a public method on the same object, so any holder of a legitimate
authorization can set `gate_result.can_complete = True`, set `mission_status =
"MISSION_COMPLETED"`, recompute `_authorization_id`, and be accepted (attack 7 → `COMPLETED`).
The hash provides tamper-*evidence* only against naive mutation; it is not tamper-*proof*,
because the recomputation oracle is public and co-located.

### 3.5 Is the WeakSet sufficient authority for Avatar's current lifecycle?

**It is adequate for the lifecycle as it actually exists, and that is the precise reason
CRITICAL-1 is exploitable.** Demonstrated:

- Authorization is never persisted, reconstructed, or serialized in production code. `to_dict`
  and `from_dict` have **zero production call sites** (only unrelated `evidence_gap_obj.to_dict()`).
- Every consumer (`state_db`, `resume_engine`, `orchestrator`) mints the authorization in-process
  and passes it immediately to `update_mission_status`.
- After a fresh process the registry is empty: `ISSUED_AFTER_RESTART_LEN 0`.

Therefore persistence of `GateAuthorization` is **not required**, and there is **no contradiction**
between "WeakSet is process-only" and "resume/recovery must work". The lifecycle is
single-process, immediate-use. The weakness is not the storage medium — it is that the issuing
function is public and trusts its input.

---

## 4. Requirements audit

### 4.1 Where `required_capabilities` lives

- Persisted: `missions.required_capabilities` (JSON text), written by `create_mission`
  (`state_db.py:281`, column added by `ALTER TABLE`, `state_db.py:98-101`).
- Read at gate time from the DB by **only** `resume_engine.py:52` and `:246`.
- `update_mission_status` **never reads the column.** It uses the caller-supplied
  `required_capabilities` argument, or the authorization's copy.

**The database is not the source of truth at the point of decision.** The caller is.

### 4.2 Attacks

| Attack | Expected | Observed | Verdict |
|--------|----------|----------|---------|
| Mission has `["CAP_WHATSAPP_AUTO_REPLY"]`; resume with `[]` | CAP_X cannot be dropped | DB row still holds `["CAP_WHATSAPP_AUTO_REPLY"]`, mission `COMPLETED` | **FAIL — BYPASS** |
| `allow_empty_requirements=True` on a mission holding CAP_X | cannot hide CAP_X | `COMPLETED` | **FAIL — BYPASS** |
| Authorization carrying `required_capabilities=[]` vs DB `["CAP_X"]` | rejected | `COMPLETED` | **FAIL — BYPASS** |
| Unknown requirement `CAP_DOES_NOT_EXIST` | no COMPLETED | `PARTIALLY_COMPLETED` | PASS |
| Legit empty + `allow_empty_requirements=True` | may complete | `COMPLETED` | PASS |

**CRITICAL-3 — requirements erasure.** The persisted requirement survives in the row but is
silently ignored at decision time, because `update_mission_status` does not reconcile
`required_capabilities` against the stored mission. `verify_authorization` checks `mission_id`
but **not** `required_capabilities`, so an authorization minted over an empty list is accepted for
a mission the database says requires `CAP_X`. Boundary **B** is not closed. AUTH-05 and AUTH-06
both fail. The `allow_empty_requirements` docstring (`state_db.py:324-327`) asserts the knob is
"not an authority bypass"; against a mission with real stored requirements it functions as one.

### 4.3 `NO_REQUIREMENTS_DECLARED` vs `REQUIREMENTS_UNKNOWN`

- `NO_REQUIREMENTS_DECLARED` is a legal `MissionStatus` and is accepted by the SQLite CHECK on a
  fresh schema, but the gate **never returns it** — `mission_completion_gate.py:66-77` has no
  branch producing it. The legitimate "no requirements declared" case is therefore **unreachable**;
  in practice it is expressed as `COMPLETED` via `allow_empty_requirements=True`.
- `REQUIREMENTS_UNKNOWN` (a capability id absent from the registry) resolves to
  `NOT_IMPLEMENTED` (`capability_registry.py:238-242`), is reported in
  `unverified_required_capabilities`, and correctly yields `PARTIALLY_COMPLETED`. These two cases
  must not be conflated, and in the current code they are not — but the distinction is carried
  only by a status string, not by a distinct persisted state.

---

## 5. Resume / Recovery / Checkpoint audit

`GateAuthorization` lifecycle across restart: **discarded and re-evaluated.** Confirmed
`ISSUED_AFTER_RESTART_LEN 0` in a fresh interpreter.

Restart scenario, mission with real requirement `CAP_WHATSAPP_AUTO_REPLY` (`NOT_IMPLEMENTED`) and
all tasks `VERIFIED`:

```
phase1 resume=ACTIVE_MISSION_COMPLETED status=PARTIALLY_COMPLETED
after restart, persisted requirements = ["CAP_WHATSAPP_AUTO_REPLY"]
phase2 resume=ACTIVE_MISSION_COMPLETED status=PARTIALLY_COMPLETED
restart did NOT create authority: True
```

**AUTH-14, AUTH-15, AUTH-16 PASS.** Resume, recovery and restart do not manufacture authority;
each re-runs the gate. The `CRITICAL-3` requirements-erasure path *is* reachable after restart
(same script erases requirements post-restart and reaches `COMPLETED`), but the erasure itself is
the defect, not the restart.

Checkpoint status writes (`PRE_TOOL_EXECUTION`, `POST_TOOL_EXECUTION`, `VERIFIED`,
`UNCERTAIN_EXECUTION`) are task-scoped and never touch mission completion authority.

---

## 6. AuthorizedEvidenceBuilder audit

### 6.1 The real chain

```
VerifiedFact (any object with .verified=True, .fact_id, .fact_type, .evidence_data)
   ↓  create_evidence()  — checks ONLY: verified, mission_id, task_id, execution_id, fact_id
   ↓  _derive_physical_evidence(fact, evidence_type)  — branches on fact_type, ignores capability
CapabilityEvidence(capability_id=<CALLER SUPPLIED>, evidence_type=<CALLER SUPPLIED>)
   ↓  register_evidence()  — checks field NON-EMPTINESS only
capability status recomputed from coverage of caller-chosen types
```

### 6.2 No capability-specific evaluation exists

**There is no step anywhere that decides "this VerifiedFact proves CAP_X".** `capability_id` is a
free parameter of `create_evidence` (`authorized_evidence_builder.py:22`). No comparison is made
against `verified_fact.target` or `evidence_data["capability_id"]`. Boundary **C** is not closed.

### 6.3 Attacks

| # | Attack | Observed `physical_evidence` | Verdict |
|---|--------|------------------------------|---------|
| A | Fully synthetic `VerifiedFact(verified=True)` | `True` | **REJECTED? no — accepted** |
| B | `verified=True`, no physical artifact | `True` | accepted |
| C | `evidence_data={"physical_evidence": False}` | `False` | correctly rejected |
| D | `COMMAND` exit 0 → `COMMUNICATION_EVIDENCE` | `True` | accepted |
| G | `CAP_STATE_ENGINE` fact reused for `CAP_WHATSAPP_AUTO_REPLY` | `True`, `verification_id=fact-cap-07e3e7b8` | accepted |
| H | Real but insufficient fact | degrades to PARTIAL | PASS |
| I | Tool `exit_code=0`, no capability evaluation | `True` | accepted |
| J | `pytest` OK, no capability evaluation | `True` | accepted |

**CRITICAL-4 — end-to-end capability forgery.** `_derive_physical_evidence` (line 73) returns
`True` unconditionally for `WRITE_FILE`/`MODIFY_FILE`/`DELETE_FILE`/`TEST`, and for any `COMMAND`
with `exit_code == 0`, regardless of which capability is being certified. Combined with
caller-chosen `evidence_type`, a capability is certifiable from unrelated evidence:

```
after COMMUNICATION(pytest)   : PARTIAL
after NETWORK(curl exit 0)    : VERIFIED
-> VERIFIED without touching WhatsApp: True
```

`CAP_WHATSAPP_AUTO_REPLY` reached `VERIFIED` using a pytest summary and a `curl` exit code.
**AUTH-07 and AUTH-08 FAIL.** Boundary **C** not closed. Note the asymmetry: only
`fact_type == "CAPABILITY"` consults `capability_verified`, and even
`verify_capability_operation(cap, <any truthy non-path>)` sets `verified=True`
(`physical_fact_verifier.py:203-205`).

---

## 7. Registry audit

`register_evidence` (`capability_registry.py:142-151`) enforces **non-emptiness** of
`mission_id`, `task_id`, `execution_id`, `verification_id`, and rejects `origin` only when empty
or literally `"UNKNOWN"`. Observed:

| Check | Result |
|-------|--------|
| provenance fields present (AUTH-10) | **PASS** |
| `origin` allowlist | **FAIL** — `TEST_SYNTHETIC`, `LLM_OUTPUT`, `TOTALLY_MADE_UP` all reach `VERIFIED` |
| cross-mission binding (AUTH-11) | **FAIL** — evidence minted for `MISSION_A` certifies `MISSION_B`; no comparison exists |
| cross-execution binding (AUTH-12) | **FAIL** — `execution_id` is stored but never compared |
| `observation_id` binding | **FAIL** — empty `observation_id` accepted, not even stored in `ev_entry` |
| composite coverage ⊆ verified physical types (AUTH-13) | **PASS in isolation** — but voided by CRITICAL-5 |

`CapabilityRecord` has **no mission dimension**: capability status is global. A capability
verified while serving Mission-A is `VERIFIED` for every later mission, so per-mission
requirements inherit other missions' evidence. Boundary **D** is not closed.

**CRITICAL-5 — direct status write.** `set_capability_status(capability_id, status, reason)`
(`capability_registry.py:222-236`) is public and writes any status with no evidence:

```
CAP_WHATSAPP status before: NOT_IMPLEMENTED
after set_capability_status(VERIFIED): VERIFIED   <- NO EVIDENCE REGISTERED
evidence_ids = []
```

A single call falsifies a capability and thereby satisfies any mission requiring it.
**AUTH-13 FAILS**; this is the cheapest complete bypass found.

**Dead code:** `AuthorizedEvidenceBuilder.is_authorized_evidence` is never called by
`register_evidence` and returns `True` for `origin="LLM_OUTPUT"`. It provides no protection.

---

## 8. SQLite migration audit

`CREATE TABLE IF NOT EXISTS` does **not** alter an existing table. `_create_tables`
(`state_db.py:55-105`) only issues `ALTER TABLE missions ADD COLUMN required_capabilities`, which
adds a column but **cannot widen an existing CHECK constraint**.

Legacy DB built with the pre-002 schema, then opened by current `StateEngine`:

```
StateEngine init on legacy DB: OK (no exception)
required_capabilities present: True
status CHECK accepts BLOCKED/PARTIALLY_COMPLETED: False
legacy row readable: status='IN_PROGRESS' req_caps='[]'   data preserved
```

Gate verdicts written into the legacy DB:

| Gate status | Legacy DB result |
|-------------|------------------|
| `BLOCKED` | `IntegrityError: CHECK constraint failed` |
| `PARTIALLY_COMPLETED` | `IntegrityError` |
| `COMPLETED_WITH_FINDINGS` | `IntegrityError` |
| `COMPLETED` | persisted |
| `MISSION_COMPLETED` | persisted as `COMPLETED` |

**HIGH-1 — no real migration.** The deployment initializes without error, silently retains an
incompatible constraint, and then fails closed on every non-`COMPLETED` verdict. Because
`update_mission_status` rolls back and re-raises (`state_db.py:369-371`), such missions are
permanently stuck in `IN_PROGRESS` while the exception surfaces at the call site. Data is
preserved; **AUTH-18 FAILS**. The audit explicitly does not assume `IF NOT EXISTS` upgrades.

---

## 9. Status compatibility

Fresh-schema CHECK accepts: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `VERIFIED`,
`COMPLETED_WITH_BLOCKING_FINDINGS`, `COMPLETED_WITH_FINDINGS`, `PARTIALLY_COMPLETED`, `BLOCKED`,
`NO_REQUIREMENTS_DECLARED`. `MISSION_COMPLETED` is correctly remapped to `COMPLETED` at
`state_db.py:355-356` before the write, so no `IntegrityError` occurs on a fresh DB.

**`except: pass` inventory (27 sites) — classified:**

| Site | Class | Note |
|------|-------|------|
| `state_db.py:450, 499, 549` | benign | JSON decode fallback on read |
| `state_db.py:779` | benign | connection close |
| `state_db.py:101` | benign, load-bearing | `ALTER TABLE` duplicate-column guard |
| `orchestrator.py:450` | **authority-adjacent** | swallows evidence-registration failure; fails closed, but hides capability-certification errors |
| `orchestrator.py:13, 180, 242, 271, 296, 641, 747` | benign / telemetry | stdout reconfigure, UI, iteration |
| `resume_engine.py:187` | benign | evidence-gap parse fallback |
| `autoloop.py:10`, `llm_provider.py:485, 586`, `rag_memory.py:73, 107`, `ui_inspector.py:58, 107, 159, 183, 203`, `structured_action_recovery.py:27, 37` | benign | I/O, parsing, logging |

No `except: pass` converts a gate rejection into a completion. The `Gate result → SQLite
IntegrityError → swallowed` chain does **not** occur on fresh schemas; it occurs on **legacy**
schemas and is *not* swallowed (it propagates), which is the safer failure but leaves missions
wedged.

---

## 10. Test forensics

**Disclosure:** during IMPLEMENTATION 002 the auditor (this session) modified four test files.
These edits are part of the system under audit and are graded here accordingly:
`test_state_engine.py::test_18` (now passes `allow_empty_requirements=True`),
`test_browser_engine.py::test_09` and `test_forensic_repair_002.py::test_09` (provenance binding
fields added to fixtures), plus API-shape edits in `test_authority_consolidation_001/002/004` and
`test_checkpoint_resume.py::test_17`. No test assertion was weakened to hide a failure, but
`test_18` in particular now *asserts the behaviour of the very knob under dispute*.

| Test | Class | Assessment |
|------|-------|------------|
| `001::test_01` | **WEAK** | `assertNotEqual(status,"COMPLETED")` on the real gate path. Would fail if the bypass returned, but asserts only a negative; never attempts to write `COMPLETED` directly. |
| `001::test_02` | **VALID** | Real gate, strict default, asserts `BLOCKED`. |
| `001::test_03` | **WEAK** | Asserts `COMPLETED` after resume. Passes *because* `allow_empty_requirements=True`; contributes no protection evidence and normalizes the very behaviour CRITICAL-3 exploits. |
| `001::test_04` | **WEAK** | Asserts orchestrator did not auto-create evidence; checks a side effect, not authority. |
| `004::test_synthetic_evidence_cannot_reach_verified` | **TAUTOLOGICAL** | Asserts `PARTIAL`, but the cause is missing `FILESYSTEM`/`DATABASE` type coverage, **not** the `TEST_SYNTHETIC` origin. Directly contradicted: `origin="TEST_SYNTHETIC"` reaches `VERIFIED` when coverage is complete. Its stated intent is false. |
| `004::test_cross_mission_evidence_is_blocked` | **WEAK / MISLABELLED** | Merely omits `mission_id`. No cross-mission comparison exists in the code; the test would pass unchanged if cross-mission protection were deleted. |
| `004::test_k_valid_authorized_evidence` | WEAK | Fixtures use synthetic `VerifiedFact`s; proves builder plumbing, not physical capability. |
| `browser/forensic test_09` | **SYNTHETIC** | Evidence objects hand-constructed with `physical_evidence=True`; auditor-added binding made them pass. They assert the registry's arithmetic, not real physical capability. |

**No test in the suite attacks the `create_authorization`-with-fabricated-result path, the
post-issuance mutation path, `create_mission(status=...)`, `set_capability_status`, or
requirements erasure.** Those five paths are where every confirmed bypass lives. This is why
331/331 is consistent with `AUTHORITY_INTEGRITY_FAILED`.

---

## 11. Authority graph

### Mission `COMPLETED` write paths

```
[1] Caller → create_mission(status="COMPLETED")
      → INSERT INTO missions(status)          ✗ NO GATE            ← BYPASS (CRITICAL-3/F)
[2] Caller → MissionCompletionGate.create_authorization(FABRICATED MissionGateResult)
      → GateAuthorization._issue              ✗ NO EVALUATION       ← BYPASS (CRITICAL-1/A,E)
[3] Caller → GateAuthorization._issue(...) directly
      → update_mission_status                ✗ NO EVALUATION       ← BYPASS (CRITICAL-1)
[4] Caller → valid auth, then mutate gate_result + recompute hash
      → update_mission_status                ✗ HASH ORACLE PUBLIC  ← BYPASS (CRITICAL-2)
[5] Caller → update_mission_status(required_capabilities=[], allow_empty_requirements=True)
      → real gate over [] → COMPLETED        ✗ DB REQUIREMENTS IGNORED ← BYPASS (CRITICAL-4/B)
[6] resume_engine:52/246 → reads DB requirements → real gate → _issue
      → update_mission_status                ✓ GENUINE AUTHORITY
[7] orchestrator → real gate over goal.metadata → _issue
      → update_mission_status                ✓ GENUINE AUTHORITY
      (but requirements come from goal.metadata, never persisted back)
```

Paths [1]–[5] bypass the gate entirely. Only [6] and [7] traverse a real evaluation.

### Capability `VERIFIED` paths

```
[1] Caller → set_capability_status(cap, VERIFIED)
      → save_capability_record                ✗ NO EVIDENCE         ← BYPASS (CRITICAL-5/D)
[2] Caller → VerifiedFact(any, verified=True) → create_evidence(capability_id=caller-chosen,
                                                          evidence_type=caller-chosen)
      → register_evidence → coverage satisfied  ✗ NO CAPABILITY EVAL  ← BYPASS (CRITICAL-4/C)
[3] Genuine PhysicalFactVerifier + correct evidence_type + full coverage
      → register_evidence                      ✓ GENUINE
```

---

## 12. AUTH-01 … AUTH-18

| ID | Invariant | Verdict | Evidence |
|----|-----------|---------|----------|
| AUTH-01 | Caller cannot fabricate `GateAuthorization` | **FAIL** | `create_authorization` public + accepts fabricated result (§3.3) |
| AUTH-02 | Authorization bound to `mission_id` | **PASS** | `verify_authorization:114`; attack 8/11 blocked |
| AUTH-03 | Cannot be reused across missions | **PASS** | attack 11 blocked |
| AUTH-04 | `COMPLETED` requires valid authorization | **FAIL** | `create_mission(status=…)` writes `COMPLETED` with no authorization (§4.2) |
| AUTH-05 | Persisted requirements cannot be replaced by `[]` | **FAIL** | DB requirements ignored at decision time (§4.2) |
| AUTH-06 | `allow_empty_requirements` cannot erase real requirements | **FAIL** | completes a mission whose row holds `CAP_X` (§4.2) |
| AUTH-07 | `VerifiedFact` ≠ capability verified | **FAIL** | no capability-specific evaluation exists (§6.2) |
| AUTH-08 | Tool success ≠ capability verified | **FAIL** | `pytest`+`curl` certify WhatsApp capability (§6.3) |
| AUTH-09 | LLM claim ≠ mission completed | **PASS** (not directly attacked) | `ClaimValidator` only reports; no status write path found |
| AUTH-10 | Evidence requires provenance | **PASS** | binding fields enforced, `capability_registry.py:142-149` |
| AUTH-11 | Evidence from another mission rejected | **FAIL** | no cross-mission comparison; records are global (§7) |
| AUTH-12 | Evidence from another execution rejected | **FAIL** | `execution_id` stored, never compared (§7) |
| AUTH-13 | Composite capability requires full coverage | **FAIL** | rule correct in isolation, voided by `set_capability_status` (§7) |
| AUTH-14 | Resume creates no authority | **PASS** | re-evaluates via gate (§5) |
| AUTH-15 | Recovery creates no authority | **PASS** | re-evaluates via gate (§5) |
| AUTH-16 | Restart cannot complete without a valid gate | **PASS** | WeakSet empty after restart; re-evaluation required (§5) |
| AUTH-17 | StateEngine rejects forged authorization | **FAIL** | forged + mutated authorizations accepted (§3.3, §3.4) |
| AUTH-18 | SQLite cannot be silently inconsistent | **FAIL** | no migration; legacy DB rejects all non-`COMPLETED` verdicts (§8) |

**9 FAIL · 9 PASS · 0 UNKNOWN**

---

## 13. Full test suite

```
collected   331
passed      331
failed        0
skipped       0
errors        0
xfailed       0
duration    77.38s (0:01:17)
```

No timeouts, no collection errors, no silent deselection, no hidden failures — and no skips
without explanation (there are none). **The suite is genuinely green. It is simply not a
sufficient oracle for the boundaries it is claimed to protect**, for the reasons in §10.

---

## 14. Defect register

| ID | File:line | Cause | Impact | Repro | Recommended repair |
|----|-----------|-------|--------|-------|--------------------|
| D-1 | `core/cognitive/mission_completion_gate.py:88-101` | `create_authorization` is public and trusts a caller-supplied `MissionGateResult` | **CRITICAL** — arbitrary `COMPLETED` | fabricate result → `create_authorization` → `update_mission_status` | Make issuance non-forgeable: have `evaluate_mission_completion` itself return the authorization, and issue via a module-private token/`classmethod` not exposed for external use. Re-derive the verdict inside `update_mission_status` and compare. |
| D-2 | `core/cognitive/gate_authorization.py:54-63, 100-105` | Integrity hash recomputable by the holder; no MAC | **CRITICAL** — mutate-then-rehash escalation to `COMPLETED` | issue valid auth → set `can_complete` → recompute hash | Sign with a process-private key (HMAC) held outside the object, or make the fields immutable after issuance. |
| D-3 | `core/state_db.py:266-297` | `create_mission` accepts an arbitrary `status`, bypassing the gate | **HIGH** — `COMPLETED` with zero authority | `create_mission(status="COMPLETED")` | Restrict `status` to non-terminal values at creation; force all terminal transitions through `update_mission_status`. Add a DB-level guard. |
| D-4 | `core/cognitive/capability_registry.py:222-236` | `set_capability_status` writes any status with no evidence | **CRITICAL** — falsifies any capability in one call | `set_capability_status(cap, "VERIFIED")` | Restrict to explicitly non-`VERIFIED` states; require evidence for `VERIFIED`; audit-log transitions. |
| D-5 | `core/state_db.py:307-345` | `update_mission_status` never reconciles caller requirements with the persisted mission | **CRITICAL** — erases real requirements | mission with `CAP_X` → `update_mission_status(required_capabilities=[], allow_empty_requirements=True)` | Read requirements from the DB inside `update_mission_status`; treat the argument as an assertion that must match, and have `verify_authorization` compare `required_capabilities` against the stored value. |
| D-6 | `core/cognitive/authorized_evidence_builder.py:22, 73-84` | `capability_id` caller-supplied; `physical_evidence` derived from `fact_type` alone | **CRITICAL** — certifies any capability from unrelated evidence | pytest + curl → `CAP_WHATSAPP_AUTO_REPLY` = `VERIFIED` | Require a capability-specific verdict: derive `capability_id` from the fact, or require `fact_type == "CAPABILITY"` with a capability-scoped evaluation before any evidence is emitted. |
| D-7 | `core/cognitive/capability_registry.py:142-151` | Provenance checked for non-emptiness only; no `origin` allowlist, no cross-mission/execution comparison | **HIGH** — `origin="LLM_OUTPUT"` reaches `VERIFIED`; cross-mission reuse accepted | register `LLM_OUTPUT`-origin evidence covering all required types | Allowlist `origin`; compare `mission_id`/`execution_id` against the mission being certified; scope capability records per mission. |
| D-8 | `core/state_db.py:55-105` | `IF NOT EXISTS` + column-only `ALTER`; no `CHECK` widening | **HIGH** — legacy DBs reject every non-`COMPLETED` verdict | open legacy DB, write `BLOCKED` → `IntegrityError` | Implement a real versioned migration: detect the old `CHECK`, rebuild the `missions` table inside a transaction, copy rows, verify counts. |
| D-9 | `core/cognitive/authorized_evidence_builder.py:86-94` | `is_authorized_evidence` never called; returns `True` for `LLM_OUTPUT` | **MEDIUM** — false assurance | — | Call it from `register_evidence`, or delete it. |
| D-10 | `core/cognitive/capability_registry.py:167-176` | `observation_id` not persisted in `ev_entry`, not validated | **MEDIUM** — observation binding unenforced | empty `observation_id` accepted | Persist and validate `observation_id`. |
| D-11 | `core/orchestrator.py:450-451` | `except: pass` hides evidence-registration failure | **LOW** — silent loss of certification | — | Log and surface; count as a degraded condition. |
| D-12 | `core/cognitive/mission_completion_gate.py:66-77` | `NO_REQUIREMENTS_DECLARED` never produced | **LOW** — legitimate state unreachable | — | Return it when `allow_empty_requirements=True` and no requirements are declared. |

---

## 15. Residual risks

1. **The WeakSet is a liveness check, not an authority check.** It answers "was this object
   constructed in-process" — never "did the gate evaluate this mission". Every bypass in D-1,
   D-2 and D-4 passes it.
2. **Boundary D has no per-mission dimension.** `CapabilityRecord` is global, so evidence from any
   mission permanently upgrades a capability for all future missions. Requirements are per-mission;
   capability truth is not. This is an architectural mismatch, not a bug.
3. **Green-suite risk.** The suite validates arithmetic and plumbing, not adversarial authority.
   Adding tests that exercise D-1…D-8 is the highest-value next step; they will fail initially,
   which is the point.
4. **Orchestrator requirements are never persisted.** `orchestrator.py` derives
   `required_capabilities` from `goal.metadata` and never writes it back to the mission row, so the
   persisted column is `[]` for orchestrator-driven missions — the exact state CRITICAL-3 exploits.
5. **Legacy databases in the field are unversioned.** There is no `user_version`/schema-version
   table, so D-8 cannot even be detected at runtime, let alone repaired.

---

## 16. Final verdict

# `AUTHORITY_INTEGRITY_FAILED`

The rule for `FAILED` is *"at least one reproducible bypass allowing falsified completion,
falsified capability, eliminated requirements, or a skipped gate."* **All four are present and
reproduced.**

- **Falsified completion** — D-1, D-2, D-3.
- **Falsified capability** — D-4 (one call), D-6 (unrelated evidence).
- **Eliminated requirements** — D-5.
- **Skipped gate** — D-1, D-4.

The three claims that survive scrutiny are genuine and worth crediting: resume/recovery/restart
re-evaluate rather than inherit authority (AUTH-14/15/16), the `GateAuthorization` is at least
bound to `mission_id` and resists the nine naive forgeries in §3.2, and provenance non-emptiness
is enforced (AUTH-10). Those are real. They are also insufficient, because the gate's own issuing
function is public and the registry's status writer is unrestricted.

`AUTHORITY_INTEGRITY_PARTIAL` was considered and rejected: it requires that *no critical bypass be
reproducible*, and D-1 alone — a public method that mints completion authority from a fabricated
verdict — is reproducible in three lines.

**The 331/331 result is accurate and is not evidence of the closures claimed.** Of the five
closure claims: CRITICAL-01 is not closed (D-1, D-2, D-3), CRITICAL-02 is not closed (D-5),
HIGH-01 is not closed (D-6, D-7), and the SQLite/StateEngine claim is not closed (D-8).

**No code was modified in this audit.** All five bypasses remain reproducible.
