"""
Deterministic physical fact verification.

A fact is an immutable observation of the machine. It records *what was observed*, never
*what it means*. Interpretation of a fact for a given capability is the job of
`CapabilitySpecificVerifier`, never of this module and never of a caller.

D-6/D-8 notes:
  * `VerifiedPhysicalFact` is frozen, so a fact cannot be edited after verification.
  * `subject` binds the fact to the thing it actually observed, which is what lets a
    capability-specific verifier reject a fact that belongs to a different capability.
  * `verify_capability_operation` has been removed. It accepted `bool(data)` as proof and
    therefore allowed a synthetic file, a mock dict, or any source file to "verify" an
    arbitrary capability. Capability truth now comes only from
    `CapabilitySpecificVerifier`.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.cognitive.authority_core import LEDGER, observer_token
from core.cognitive.capability_definitions import SQLITE_PERSISTENCE_FACT

VERIFIER_NAME = "PhysicalFactVerifier"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _issue(fact_id: str, fact_type: str, subject: str, verified: bool,
           observed_state: Dict[str, Any], execution_id: str, error: Optional[str]) -> VerifiedPhysicalFact:
    """
    Construct a fact AND record the underlying observation in the ledger.

    Every physical fact in the system is produced here. Recording the observation is what
    makes the fact credible downstream: `CapabilitySpecificVerifier` refuses any fact that is
    not backed by a matching ledger entry, so a hand-built dataclass cannot certify anything.
    """
    sequence = LEDGER.record(
        observer_token(),
        fact_type=fact_type,
        subject=subject,
        verified=verified,
        observed_state=observed_state,
        execution_id=execution_id,
        observer=VERIFIER_NAME,
    )
    return VerifiedPhysicalFact(
        fact_id=fact_id,
        fact_type=fact_type,
        subject=subject,
        verified=verified,
        observed_state=dict(observed_state),
        source=VERIFIER_NAME,
        execution_id=execution_id,
        verifier=VERIFIER_NAME,
        timestamp=_now(),
        error=error,
        observation_sequence=sequence,
    )


@dataclass(frozen=True)
class VerifiedPhysicalFact:
    """An immutable, machine-verified observation."""

    fact_id: str
    fact_type: str
    subject: str
    verified: bool
    observed_state: Dict[str, Any] = field(default_factory=dict)
    source: str = VERIFIER_NAME
    execution_id: str = ""
    verifier: str = VERIFIER_NAME
    timestamp: str = field(default_factory=_now)
    error: Optional[str] = None
    #: Ledger sequence proving a real observation backs this fact. A manually constructed
    #: fact has no sequence and is therefore not credible.
    observation_sequence: int = 0

    # Backwards-compatible aliases. `evidence_data` is read-only by construction because the
    # dataclass is frozen, so exposing it cannot re-open a mutation channel.
    @property
    def evidence_data(self) -> Dict[str, Any]:
        return self.observed_state

    @property
    def target(self) -> str:
        return self.subject


#: Retained name used across the codebase.
VerifiedFact = VerifiedPhysicalFact


class PhysicalFactVerifier:
    """
    Verificador de Evidencia Física Determinista para Avatar AI.
    Inspecciona físicamente el sistema operativo y el sistema de archivos para confirmar
    hechos incontrovertibles independientemente de las afirmaciones textuales del LLM.
    """

    @staticmethod
    def calculate_file_hash(file_path: str) -> Optional[str]:
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            return None
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    @staticmethod
    def verify_write_file(
        file_path: str,
        expected_content: Optional[str] = None,
        execution_id: str = "",
    ) -> VerifiedPhysicalFact:
        fact_id = f"fact-write-{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
        if not os.path.exists(file_path):
            return _issue(fact_id, "WRITE_FILE", file_path, False, {},
                          execution_id, f"File '{file_path}' does not exist on disk.")
        if os.path.isdir(file_path):
            return _issue(fact_id, "WRITE_FILE", file_path, False, {},
                          execution_id, f"Target path '{file_path}' is a directory.")

        size = os.path.getsize(file_path)
        content_hash = PhysicalFactVerifier.calculate_file_hash(file_path)
        hash_matches = True
        if expected_content is not None:
            exp_hash = hashlib.sha256(expected_content.encode("utf-8", errors="replace")).hexdigest()
            hash_matches = content_hash == exp_hash
        is_verified = (size >= 0) and hash_matches
        return _issue(
            fact_id, "WRITE_FILE", file_path, is_verified,
            {"size_bytes": size, "content_hash": content_hash, "hash_matches": hash_matches},
            execution_id,
            None if is_verified else "Content hash does not match expected content.",
        )

    @staticmethod
    def verify_modify_file(file_path: str, initial_hash: str, execution_id: str = "") -> VerifiedPhysicalFact:
        fact_id = f"fact-mod-{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
        if not os.path.exists(file_path):
            return _issue(fact_id, "MODIFY_FILE", file_path, False, {},
                          execution_id, f"File '{file_path}' does not exist on disk.")
        current_hash = PhysicalFactVerifier.calculate_file_hash(file_path)
        changed = current_hash != initial_hash
        return _issue(
            fact_id, "MODIFY_FILE", file_path, changed,
            {"initial_hash": initial_hash, "current_hash": current_hash, "file_changed": changed},
            execution_id,
            None if changed else f"File '{file_path}' content was not modified.",
        )

    @staticmethod
    def verify_delete_file(file_path: str, existed_before: bool, execution_id: str = "") -> VerifiedPhysicalFact:
        fact_id = f"fact-del-{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
        currently_exists = os.path.exists(file_path)
        verified = existed_before and (not currently_exists)
        return _issue(
            fact_id, "DELETE_FILE", file_path, verified,
            {"existed_before": existed_before, "currently_exists": currently_exists},
            execution_id,
            None if verified else f"File '{file_path}' still exists on disk.",
        )

    @staticmethod
    def verify_command(command: str, raw_output: str, expected_exit_code: int = 0,
                       execution_id: str = "") -> VerifiedPhysicalFact:
        fact_id = f"fact-cmd-{hashlib.md5(command.encode()).hexdigest()[:8]}"
        exit_code = 0
        match = re.search(r"\[Resultado PowerShell \(ExitCode:\s*(-?\d+)\)\]:", raw_output)
        if match:
            exit_code = int(match.group(1))
        verified = exit_code == expected_exit_code
        return _issue(
            fact_id, "COMMAND", command, verified,
            {"command": command, "exit_code": exit_code,
             "expected_exit_code": expected_exit_code, "output_length": len(raw_output)},
            execution_id,
            None if verified else f"Command exited with code {exit_code}, expected {expected_exit_code}.",
        )

    @staticmethod
    def verify_test_execution(command: str, raw_output: str, execution_id: str = "") -> VerifiedPhysicalFact:
        fact_id = f"fact-test-{hashlib.md5(command.encode()).hexdigest()[:8]}"
        exit_code = 0
        match_code = re.search(r"\[Resultado PowerShell \(ExitCode:\s*(-?\d+)\)\]:", raw_output)
        if match_code:
            exit_code = int(match_code.group(1))
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        errors = 0
        match_ran = re.search(r"Ran\s+(\d+)\s+tests?", raw_output)
        if match_ran:
            total_tests = int(match_ran.group(1))
        if "OK" in raw_output and exit_code == 0:
            passed_tests = total_tests
            verified = True
        else:
            verified = False
            match_fail = re.search(
                r"FAILED\s*\((?:failures=(\d+))?,?\s*(?:errors=(\d+))?\)", raw_output
            )
            if match_fail:
                failed_tests = int(match_fail.group(1) or 0)
                errors = int(match_fail.group(2) or 0)
        return _issue(
            fact_id, "TEST", command, verified,
            {"command": command, "exit_code": exit_code, "total_tests": total_tests,
             "passed_tests": passed_tests, "failed_tests": failed_tests, "errors": errors,
             "fact_subtype": "TEST_EXECUTION_VERIFIED", "is_unit_test": True,
             # D-7: a green test run never certifies a capability.
             "capability_verified": False},
            execution_id,
            None if verified else f"Test execution failed (exit {exit_code}, ran {total_tests}).",
        )

    # ------------------------------------------------------------------
    # Capability-specific physical observation
    # ------------------------------------------------------------------
    @staticmethod
    def verify_sqlite_persistence(db_path: str, execution_id: str = "") -> VerifiedPhysicalFact:
        """
        Real, deterministic inspection of a SQLite database file.

        Observes, on the actual filesystem and database:
          1. the database file exists and is a regular file  -> FILESYSTEM_EVIDENCE
          2. WAL journalling is active                          -> DATABASE_EVIDENCE
          3. the missions table exists with the authority columns
          4. a probe row round-trips (write then read back)     -> DATABASE_EVIDENCE

        `subject` is the capability id, which is what allows the capability-specific verifier
        to reject this fact when offered for a different capability.
        """
        fact_id = f"fact-sqlite-{hashlib.md5(str(db_path).encode()).hexdigest()[:8]}"
        subject = "CAP_STATE_ENGINE"
        observed: Dict[str, Any] = {
            "db_path": str(db_path),
            "file_exists": False,
            "journal_mode": None,
            "missions_table": False,
            "required_columns": False,
            "roundtrip_ok": False,
        }
        if not db_path or db_path == ":memory:":
            return _issue(
                fact_id, SQLITE_PERSISTENCE_FACT, subject, False, dict(observed), execution_id,
                "A real on-disk database path is required.",
            )
        if not (os.path.exists(db_path) and os.path.isfile(db_path)):
            return _issue(
                fact_id, SQLITE_PERSISTENCE_FACT, subject, False, dict(observed), execution_id,
                f"Database file does not exist: {db_path}",
            )

        observed["file_exists"] = True
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            observed["journal_mode"] = str(cur.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            names = {r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            observed["missions_table"] = "missions" in names
            if observed["missions_table"]:
                cols = {r[1] for r in cur.execute("PRAGMA table_info(missions)").fetchall()}
                observed["required_columns"] = {"mission_id", "status", "required_capabilities"} <= cols
                probe = f"__probe_{os.getpid()}_{id(db_path)}"
                cur.execute(
                    "INSERT INTO missions (mission_id, session_id, raw_prompt, classified_intent,"
                    " required_capabilities, status, created_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (probe, "__probe__", "probe", "PROBE", "[]", "IN_PROGRESS", _now(), _now()),
                )
                conn.commit()
                row = cur.execute("SELECT status FROM missions WHERE mission_id = ?", (probe,)).fetchone()
                observed["roundtrip_ok"] = bool(row) and row[0] == "IN_PROGRESS"
                cur.execute("DELETE FROM missions WHERE mission_id = ?", (probe,))
                conn.commit()
            cur.close()
            conn.close()
        except Exception as exc:  # pragma: no cover - defensive
            return _issue(
                fact_id, SQLITE_PERSISTENCE_FACT, subject, False, dict(observed), execution_id,
                f"SQLite inspection failed: {exc}",
            )

        verified = (
            observed["file_exists"]
            and observed["journal_mode"] == "wal"
            and observed["missions_table"]
            and observed["required_columns"]
            and observed["roundtrip_ok"]
        )
        return _issue(
            fact_id, SQLITE_PERSISTENCE_FACT, subject, verified, dict(observed), execution_id,
            None if verified else f"SQLite persistence checks incomplete: {observed}",
        )
