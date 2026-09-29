from __future__ import annotations
import sqlite3
import os
import json
import uuid
import datetime
import hashlib
import hmac
import secrets
import threading
from typing import Dict, Any, List, Optional, TYPE_CHECKING


def _is_hex(value: str, size: int) -> bool:
    return len(value) == size and all(c in "0123456789abcdef" for c in value)


def _is_legacy_requirements_seal(seal: str) -> bool:
    """Hex HMAC from before the seal carried a database key id."""
    return _is_hex(seal, 64)


# Turns returned by a default load. A no-id resend of this window plus a short
# tail is treated as new turns; a longer identical resend can still be ambiguous.
_HISTORY_WINDOW = 50
_HISTORY_TAIL_SLACK = 20

if TYPE_CHECKING:  # pragma: no cover - typing only
    from core.cognitive.gate_authorization import GateAuthorization
    from core.cognitive.gate_types import INITIAL_MISSION_STATUSES
else:
    # Imported eagerly: gate_types has no dependency on StateEngine, so this cannot cycle.
    from core.cognitive.gate_types import INITIAL_MISSION_STATUSES

class StateEngine:
    """
    State Engine / Operational Memory para Avatar AI (Fase 1).
    Persistencia relacional autoritativa basada en SQLite en modo WAL.
    Garantiza integridad transaccional, tolerancia a caídas y trazabilidad.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            memory_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
            os.makedirs(memory_dir, exist_ok=True)
            db_path = os.path.join(memory_dir, "state_engine.db")
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = None
        self._init_connection()
        self._create_tables()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_connection()
        return self._conn

    def _init_connection(self):
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        # Activar SQLite WAL mode, Foreign Keys y Busy Timeout
        cursor = self._conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.close()

    def get_journal_mode(self) -> str:
        """Devuelve el modo journal activo (debe ser 'wal')."""
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("PRAGMA journal_mode;")
            row = cursor.fetchone()
            cursor.close()
            return str(row[0]).lower() if row else "unknown"

    #: Bumped whenever the on-disk schema changes in a way SQLite cannot apply in place.
    SCHEMA_VERSION = 2

    def _create_tables(self):
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            self._migrate_schema(conn, cursor)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'FAILED'))
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                raw_prompt TEXT NOT NULL,
                classified_intent TEXT NOT NULL,
                required_capabilities TEXT NOT NULL DEFAULT '[]',
                requirements_declared INTEGER NOT NULL DEFAULT 1,
                requirements_seal TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'VERIFIED', 'COMPLETED_WITH_BLOCKING_FINDINGS', 'COMPLETED_WITH_FINDINGS', 'PARTIALLY_COMPLETED', 'BLOCKED', 'NO_REQUIREMENTS_DECLARED')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS planner_tasks (
                task_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                description TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                tool_args TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'IN_PROGRESS', 'PRE_TOOL_EXECUTION', 'POST_TOOL_EXECUTION', 'UNCERTAIN_EXECUTION', 'VERIFIED', 'COMPLETED', 'FAILED')),
                execution_output TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE
            );
            """)
            cursor.execute("PRAGMA foreign_keys = ON;")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_records (
                fact_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                task_id TEXT,
                claim TEXT NOT NULL,
                verified_status TEXT NOT NULL,
                evidence_data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES planner_tasks(task_id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS recovery_states (
                recovery_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                task_id TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                failure_context TEXT NOT NULL,
                hypotheses_history TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES planner_tasks(task_id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidences (
                evidence_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                task_id TEXT,
                source TEXT NOT NULL,
                data_reference TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES planner_tasks(task_id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS evidence_gaps (
                gap_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL,
                task_id TEXT,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(mission_id) REFERENCES missions(mission_id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES planner_tasks(task_id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS history_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE SET NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_context (
                context_key TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                progress_percent INTEGER NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS capability_records (
                capability_id TEXT PRIMARY KEY,
                capability_name TEXT NOT NULL,
                required_evidence TEXT NOT NULL,
                required_tests TEXT NOT NULL,
                physical_verification_required INTEGER NOT NULL,
                verification_status TEXT NOT NULL,
                evidence_ids TEXT NOT NULL,
                limitations TEXT NOT NULL,
                dependencies TEXT NOT NULL,
                last_verified_at TEXT NOT NULL
            );
            """)

            conn.commit()
            cursor.close()

    def _timestamp(self) -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ==========================================
    # REQUIREMENTS INTEGRITY (D-5)
    # ==========================================
    def _requirements_seal(self, mission_id: str, caps_json: str, declared: int) -> str:
        """
        Tamper-evident seal over a mission's declared requirements.

        A mission's requirement set is part of its logical identity. This seal binds
        `mission_id`, `required_capabilities` and `requirements_declared` together, so a
        direct SQL edit that empties the requirement list is detectable on the next read.

        LIMITATION, stated precisely: this detects *inconsistency*, it does not stop an
        adversary who can read the seal-key file beside the database and rewrite the row.
        A SQL edit that only changes the requirement columns, or that plants another
        key id, fails the check and blocks completion. A legacy 64-hex seal cannot be
        checked: the mission stays open and is not marked complete.
        """
        mac = self._seal_mac({
            "mission_id": mission_id,
            "required_capabilities": caps_json,
            "requirements_declared": int(declared),
        })
        return f"v2:{self._seal_key_id()}:{mac}"

    def _requirements_payload(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "mission_id": mission["mission_id"],
            "required_capabilities": mission.get("required_capabilities") or "[]",
            "requirements_declared": int(mission.get("requirements_declared") or 0),
        }

    def _seal_key_path(self) -> str:
        return self.db_path + ".seal_key"

    def _load_seal_key(self) -> bytes:
        """
        Key for the requirements seal, stored beside the database.

        It survives a restart, so a real seal still verifies. It is not in the mission
        row: an UPDATE of the requirement columns cannot mint a new valid seal.
        """
        cached = getattr(self, "_seal_key_cache", None)
        if isinstance(cached, bytes) and len(cached) == 32:
            return cached
        path = self._seal_key_path()
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            data = b""
        if len(data) == 32:
            self._seal_key_cache = data
            return data
        if data:
            raise ValueError(f"requirements seal key at {path} is not 32 bytes")
        key = secrets.token_bytes(32)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            with open(path, "rb") as handle:
                data = handle.read()
            if len(data) != 32:
                raise ValueError(f"requirements seal key at {path} is not 32 bytes")
            self._seal_key_cache = data
            return data
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        self._seal_key_cache = key
        return key

    def _seal_key_id(self) -> str:
        return hashlib.sha256(self._load_seal_key()).hexdigest()[:16]

    def _seal_mac(self, payload: Dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hmac.new(self._load_seal_key(), body, hashlib.sha256).hexdigest()

    def requirements_seal_state(self, mission: Dict[str, Any]) -> str:
        """
        ``intact`` when the seal names this database's key and the HMAC matches.

        ``tampered`` when that key's HMAC fails, the seal was wiped, or the seal
        names some other key. That blocks completion.

        ``unverified`` only for a legacy 64-hex seal from before this key existed.
        Resume may continue. The mission is not marked complete.
        """
        seal = mission.get("requirements_seal") or ""
        prefix = f"v2:{self._seal_key_id()}:"
        if seal.startswith(prefix):
            mac = seal[len(prefix):]
            expected = self._seal_mac(self._requirements_payload(mission))
            try:
                matches = hmac.compare_digest(expected, mac)
            except Exception:
                return "tampered"
            return "intact" if matches else "tampered"
        if _is_legacy_requirements_seal(seal):
            return "unverified"
        return "tampered"

    def verify_requirements_integrity(self, mission: Dict[str, Any]) -> bool:
        """True only when this process can still vouch for the requirement seal."""
        return self.requirements_seal_state(mission) == "intact"

    # ==========================================
    # SCHEMA MIGRATION
    # ==========================================
    def _migrate_schema(self, conn, cursor):
        """
        Bring an existing database up to `SCHEMA_VERSION`.

        `CREATE TABLE IF NOT EXISTS` does not modify an existing table, and SQLite cannot
        widen a CHECK constraint in place, so a pre-consolidation database would otherwise
        keep the narrow five-value status constraint and reject every gate verdict that is not
        `COMPLETED`. The missions table is therefore rebuilt inside a single transaction when
        its shape is outdated. Data is copied, never dropped; the transaction rolls back on
        any error, so a failed migration leaves the original database untouched.
        """
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='missions'"
        ).fetchone()

        if row is None:
            # Fresh database: nothing to migrate.
            conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
            conn.commit()
            return

        columns = {r[1] for r in cursor.execute("PRAGMA table_info(missions)").fetchall()}
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='missions'"
        ).fetchone()[0] or ""
        needs_rebuild = "BLOCKED" not in ddl.upper()
        needs_columns = (
            "required_capabilities" not in columns
            or "requirements_declared" not in columns
            or "requirements_seal" not in columns
        )

        if not needs_rebuild and not needs_columns and version >= self.SCHEMA_VERSION:
            return

        self._rebuild_missions_table(conn, cursor, columns)
        conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        conn.commit()

    def _rebuild_missions_table(self, conn, cursor, existing_columns):
        """
        Rebuild `missions` with the current definition, preserving every existing row.

        Foreign keys are disabled for the duration because `planner_tasks` references
        `missions`; the table is swapped rather than altered, which is the only way SQLite
        permits a CHECK constraint to be widened.
        """
        shared = [
            "mission_id", "session_id", "raw_prompt", "classified_intent",
            "status", "created_at", "updated_at",
        ]
        available = [c for c in shared if c in existing_columns]
        select_list = ", ".join(available)
        insert_list = ", ".join(available)

        conn.execute("PRAGMA foreign_keys = OFF;")
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute("DROP TABLE IF EXISTS missions_migrated;")
            conn.execute("""
            CREATE TABLE missions_migrated (
                mission_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                raw_prompt TEXT NOT NULL,
                classified_intent TEXT NOT NULL,
                required_capabilities TEXT NOT NULL DEFAULT '[]',
                requirements_declared INTEGER NOT NULL DEFAULT 1,
                requirements_seal TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'VERIFIED', 'COMPLETED_WITH_BLOCKING_FINDINGS', 'COMPLETED_WITH_FINDINGS', 'PARTIALLY_COMPLETED', 'BLOCKED', 'NO_REQUIREMENTS_DECLARED')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
            """)
            conn.execute(
                f"INSERT INTO missions_migrated ({insert_list}, required_capabilities, "
                f"requirements_declared, requirements_seal) "
                f"SELECT {select_list}, '[]', 1, '' FROM missions;"
            )
            before = conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
            conn.execute("DROP TABLE missions;")
            conn.execute("ALTER TABLE missions_migrated RENAME TO missions;")
            after = conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
            if before != after:  # pragma: no cover - defensive
                raise RuntimeError(
                    f"Migration lost rows: {before} -> {after}. Rolling back."
                )
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON;")

    # ==========================================
    # SESSION MANAGEMENT
    # ==========================================
    def create_session(self, session_id: Optional[str] = None, status: str = "ACTIVE") -> str:
        if not session_id:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (session_id, started_at, updated_at, status) VALUES (?, ?, ?, ?)",
                    (session_id, now, now, status)
                )
                conn.commit()
                cursor.close()
                return session_id
            except Exception as e:
                conn.rollback()
                raise e

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None

    def update_session_status(self, session_id: str, status: str):
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                    (status, now, session_id)
                )
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e

    # ==========================================
    # MISSION MANAGEMENT
    # ==========================================
    def create_mission(
        self,
        mission_id: Optional[str] = None,
        session_id: Optional[str] = None,
        raw_prompt: str = "",
        classified_intent: str = "DIRECT_ACTION",
        status: str = "IN_PROGRESS",
        required_capabilities: Optional[List[str]] = None,
        declare_no_requirements: bool = False
    ) -> str:
        """
        Create a mission in a non-terminal state (D-3).

        Terminal states are refused outright. A mission cannot be *born* complete: reaching a
        terminal state requires a GateAuthorization produced by `complete_mission_with_authorization`
        (or `update_mission_status`), which re-derives the verdict from this row.

        `declare_no_requirements` is the explicit, persisted way to record that a mission
        genuinely requires no capabilities (D-5). It is a property of the mission, not an
        argument that relaxes a later evaluation.
        """
        if status not in INITIAL_MISSION_STATUSES:
            raise ValueError(
                f"Cannot create a mission in terminal state '{status}'. "
                f"Initial states are {sorted(INITIAL_MISSION_STATUSES)}. "
                "Use complete_mission_with_authorization() to reach a terminal state."
            )
        if not mission_id:
            mission_id = f"msn_{uuid.uuid4().hex[:12]}"
        if not session_id:
            session_id = self.create_session()

        now = self._timestamp()
        caps_json = json.dumps(list(required_capabilities or []))
        declared = 0 if (declare_no_requirements and not required_capabilities) else 1
        seal = self._requirements_seal(mission_id, caps_json, declared)
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO missions
                       (mission_id, session_id, raw_prompt, classified_intent,
                        required_capabilities, requirements_declared, requirements_seal,
                        status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (mission_id, session_id, raw_prompt, classified_intent, caps_json,
                     declared, seal, status, now, now)
                )
                conn.commit()
                cursor.close()
                return mission_id
            except Exception as e:
                conn.rollback()
                raise e

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None

    def update_mission_status(
        self,
        mission_id: str,
        gate_authorization: Optional["GateAuthorization"] = None,
        execution_id: str = "",
        critical_gaps: int = 0,
        blocking_findings: int = 0,
        open_findings: int = 0
    ) -> str:
        """
        Persist a mission status derived from a fresh gate evaluation.

        AUTHORITY MODEL
        ----------------
        The verdict is **re-derived here** from the mission's own persisted requirements and
        the current physical evidence. An authorization, when supplied, is only accepted if it
        agrees with that independent re-derivation. This is deliberate: it means the signature
        is defence in depth rather than the primary control, and a perfectly signed forged
        authorization is inert.

        Note the absence of `required_capabilities` and `allow_empty_requirements` parameters
        (D-5). Requirements are read from the mission row; a caller cannot supply or relax them.
        """
        from core.cognitive.gate_authorization import GateAuthorization
        from core.cognitive.mission_completion_gate import (
            MissionCompletionGate,
            requirements_from_row,
        )
        from core.cognitive.capability_registry import CapabilityEvidenceRegistry

        mission = self.get_mission(mission_id)
        if not mission:
            raise KeyError(f"Mission not found: {mission_id}")

        required_capabilities, requirements_declared = requirements_from_row(mission)
        registry = CapabilityEvidenceRegistry(state_db=self)

        # D-5: a bad seal must not be completed and must not be reinterpreted as
        # declaring no requirements. A legacy seal stays at its current open status.
        # Checked here as well as in the gate because this method is the sovereign writer.
        seal_state = self.requirements_seal_state(mission)
        if seal_state == "unverified":
            return mission.get("status") or "IN_PROGRESS"
        if seal_state == "tampered":
            from core.cognitive.gate_types import MissionGateResult, MissionStatus
            from core.cognitive.authority_core import (
                AuthorityAudit,
                AuthorityRejection,
            )
            derived = MissionGateResult(
                can_complete=False,
                mission_status=MissionStatus.BLOCKED,
                blocking_reasons=[
                    "REQUIREMENTS_INTEGRITY_FAILURE: los requisitos persistidos no coinciden "
                    f"con su sello (persistidos={required_capabilities})."
                ],
                unverified_required_capabilities=list(required_capabilities),
            )
            AuthorityAudit.record(
                decision="MISSION_TRANSITION", subject="requirements_integrity",
                mission_id=mission_id,
                reason=AuthorityRejection.REQUIREMENTS_INTEGRITY_FAILURE,
            )
            return self._persist_mission_status(mission_id, MissionStatus.BLOCKED)

        # Independent re-derivation: the source of truth for this decision.
        derived = MissionCompletionGate.evaluate_mission_completion(
            mission_id=mission_id,
            required_capabilities=required_capabilities,
            critical_gaps=critical_gaps,
            blocking_findings=blocking_findings,
            open_findings=open_findings,
            capability_registry=registry,
            state_db=self,
            requirements_declared=requirements_declared,
        )

        if gate_authorization is not None:
            if not gate_authorization.is_valid_for(
                mission_id=mission_id,
                required_capabilities=required_capabilities,
                requirements_declared=requirements_declared,
                expected_verdict=derived,
                execution_id=execution_id,
            ):
                # A rejected authorization leaves the mission untouched. It is not an error
                # condition for the caller: the derived verdict below is still authoritative.
                self._record_authorization_rejection(mission_id, gate_authorization)
                gate_authorization = None

        verdict = derived
        final_status = verdict.mission_status
        if final_status == "MISSION_COMPLETED":
            final_status = "COMPLETED"
        return self._persist_mission_status(mission_id, final_status, snapshot=mission)

    def _persist_mission_status(
        self,
        mission_id: str,
        final_status: str,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Single write path for a mission's persisted status (D-6).

        When `snapshot` is given, the write lands only if the requirement columns and
        the seal are still the ones that were evaluated. A concurrent edit does not
        inherit that verdict.
        """
        now = self._timestamp()
        applied = False
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                if snapshot is None:
                    cursor.execute(
                        "UPDATE missions SET status = ?, updated_at = ? WHERE mission_id = ?",
                        (final_status, now, mission_id)
                    )
                    applied = True
                else:
                    cursor.execute(
                        """UPDATE missions SET status = ?, updated_at = ?
                           WHERE mission_id = ?
                             AND required_capabilities = ?
                             AND requirements_declared = ?
                             AND requirements_seal = ?""",
                        (final_status, now, mission_id,
                         snapshot.get("required_capabilities") or "[]",
                         int(snapshot.get("requirements_declared") or 0),
                         snapshot.get("requirements_seal") or "")
                    )
                    applied = cursor.rowcount == 1
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e
        if applied:
            return final_status
        fresh = self.get_mission(mission_id)
        if fresh and self.requirements_seal_state(fresh) == "tampered":
            return self._persist_mission_status(mission_id, "BLOCKED")
        return (fresh or {}).get("status") or "IN_PROGRESS"

    def complete_mission_with_authorization(
        self,
        mission_id: str,
        gate_authorization: Optional["GateAuthorization"] = None,
        execution_id: str = "",
    ) -> str:
        """
        The single, auditable transition into a terminal mission state (D-3).

        Identical in effect to `update_mission_status`, provided as an explicitly named entry
        point so the intent to finalise a mission is visible at the call site.
        """
        return self.update_mission_status(
            mission_id,
            gate_authorization=gate_authorization,
            execution_id=execution_id,
        )

    def _record_authorization_rejection(self, mission_id: str, authorization) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO evidence_gaps (gap_id, mission_id, task_id, description, status, timestamp)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (f"gap_auth_{uuid.uuid4().hex[:10]}", mission_id, None,
                     "GateAuthorization rejected: signature, binding or verdict mismatch.", "UNRESOLVED",
                     self._timestamp())
                )
                conn.commit()
                cursor.close()
            except Exception:
                conn.rollback()

    # ==========================================
    # PLANNER TASKS MANAGEMENT
    # ==========================================
    def create_planner_task(
        self,
        task_id: str,
        mission_id: str,
        step_index: int,
        description: str,
        tool_name: str,
        tool_args: Any,
        status: str = "PENDING"
    ) -> str:
        now = self._timestamp()
        args_json = json.dumps(tool_args, ensure_ascii=False) if not isinstance(tool_args, str) else tool_args
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO planner_tasks 
                       (task_id, mission_id, step_index, description, tool_name, tool_args, status, execution_output, created_at, updated_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
                    (task_id, mission_id, step_index, description, tool_name, args_json, status, now, now)
                )
                conn.commit()
                cursor.close()
                return task_id
            except Exception as e:
                conn.rollback()
                raise e

    def update_planner_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        execution_output: Optional[str] = None
    ):
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                if status is not None and execution_output is not None:
                    cursor.execute(
                        "UPDATE planner_tasks SET status = ?, execution_output = ?, updated_at = ? WHERE task_id = ?",
                        (status, execution_output, now, task_id)
                    )
                elif status is not None:
                    cursor.execute(
                        "UPDATE planner_tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                        (status, now, task_id)
                    )
                elif execution_output is not None:
                    cursor.execute(
                        "UPDATE planner_tasks SET execution_output = ?, updated_at = ? WHERE task_id = ?",
                        (execution_output, now, task_id)
                    )
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e

    def get_planner_tasks(self, mission_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM planner_tasks WHERE mission_id = ? ORDER BY step_index ASC", (mission_id,))
            rows = cursor.fetchall()
            cursor.close()
            res = []
            for row in rows:
                d = dict(row)
                try:
                    d["tool_args"] = json.loads(d["tool_args"])
                except Exception:
                    pass
                res.append(d)
            return res

    # ==========================================
    # VERIFICATION RECORDS
    # ==========================================
    def add_verification_record(
        self,
        fact_id: Optional[str],
        mission_id: str,
        claim: str,
        verified_status: str,
        evidence_data: Any,
        task_id: Optional[str] = None
    ) -> str:
        if not fact_id:
            fact_id = f"fact_{uuid.uuid4().hex[:12]}"
        now = self._timestamp()
        ev_json = json.dumps(evidence_data, ensure_ascii=False) if not isinstance(evidence_data, str) else evidence_data
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO verification_records 
                       (fact_id, mission_id, task_id, claim, verified_status, evidence_data, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (fact_id, mission_id, task_id, claim, verified_status, ev_json, now)
                )
                conn.commit()
                cursor.close()
                return fact_id
            except Exception as e:
                conn.rollback()
                raise e

    def get_verification_records(self, mission_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM verification_records WHERE mission_id = ? ORDER BY timestamp ASC", (mission_id,))
            rows = cursor.fetchall()
            cursor.close()
            res = []
            for row in rows:
                d = dict(row)
                try:
                    d["evidence_data"] = json.loads(d["evidence_data"])
                except Exception:
                    pass
                res.append(d)
            return res

    # ==========================================
    # RECOVERY STATES
    # ==========================================
    def add_recovery_state(
        self,
        recovery_id: Optional[str],
        mission_id: str,
        failure_context: str,
        hypotheses_history: Any,
        retry_count: int = 0,
        status: str = "ACTIVE",
        task_id: Optional[str] = None
    ) -> str:
        if not recovery_id:
            recovery_id = f"rec_{uuid.uuid4().hex[:12]}"
        now = self._timestamp()
        hyp_json = json.dumps(hypotheses_history, ensure_ascii=False) if not isinstance(hypotheses_history, str) else hypotheses_history
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO recovery_states 
                       (recovery_id, mission_id, task_id, retry_count, failure_context, hypotheses_history, status, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (recovery_id, mission_id, task_id, retry_count, failure_context, hyp_json, status, now)
                )
                conn.commit()
                cursor.close()
                return recovery_id
            except Exception as e:
                conn.rollback()
                raise e

    def get_recovery_states(self, mission_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM recovery_states WHERE mission_id = ? ORDER BY timestamp ASC", (mission_id,))
            rows = cursor.fetchall()
            cursor.close()
            res = []
            for row in rows:
                d = dict(row)
                try:
                    d["hypotheses_history"] = json.loads(d["hypotheses_history"])
                except Exception:
                    pass
                res.append(d)
            return res

    # ==========================================
    # EVIDENCE & EVIDENCE GAPS
    # ==========================================
    def add_evidence(
        self,
        evidence_id: Optional[str],
        mission_id: str,
        source: str,
        data_reference: str,
        task_id: Optional[str] = None
    ) -> str:
        if not evidence_id:
            evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO evidences 
                       (evidence_id, mission_id, task_id, source, data_reference, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (evidence_id, mission_id, task_id, source, data_reference, now)
                )
                conn.commit()
                cursor.close()
                return evidence_id
            except Exception as e:
                conn.rollback()
                raise e

    def get_evidences(self, mission_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM evidences WHERE mission_id = ? ORDER BY timestamp ASC", (mission_id,))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]

    def add_evidence_gap(
        self,
        gap_id: Optional[str],
        mission_id: str,
        description: str,
        status: str = "UNRESOLVED",
        task_id: Optional[str] = None
    ) -> str:
        if not gap_id:
            gap_id = f"gap_{uuid.uuid4().hex[:12]}"
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO evidence_gaps 
                       (gap_id, mission_id, task_id, description, status, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (gap_id, mission_id, task_id, description, status, now)
                )
                conn.commit()
                cursor.close()
                return gap_id
            except Exception as e:
                conn.rollback()
                raise e

    def get_evidence_gaps(self, mission_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM evidence_gaps WHERE mission_id = ? ORDER BY timestamp ASC", (mission_id,))
            rows = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in rows]

    # ==========================================
    # CONVERSATION HISTORY & ACTIVE CONTEXT
    # ==========================================
    def save_history_entry(self, role: str, content: str, session_id: Optional[str] = None):
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO history_entries (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (session_id, role, content, now)
                )
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e

    def _history_rows(self, cursor, session_id: Optional[str], newest_first: bool, limit: Optional[int]):
        order = "DESC" if newest_first else "ASC"
        params: List[Any] = []
        if session_id:
            where = "WHERE session_id = ?"
            params.append(session_id)
        else:
            where = ""
        sql = f"SELECT id, role, content FROM history_entries {where} ORDER BY id {order}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        cursor.execute(sql, params)
        return [
            {"id": row["id"], "role": row["role"], "content": row["content"]}
            for row in cursor.fetchall()
        ]

    @staticmethod
    def _history_entry_id(entry: Dict[str, Any]) -> Optional[int]:
        value = entry.get("id")
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if value > 0 else None

    def sync_history(self, history: List[Dict[str, str]], session_id: Optional[str] = None):
        """
        Append turns that are not already stored.

        The in-memory list is a window, often the last 50 turns. Replacing the table
        with that window deletes everything older. Entries that already carry a stored
        id stay. A list with no ids appends only the suffix that is not already the tail,
        so a repeated save of the same window does not duplicate it. A no-id list of a
        different length than the log, at most 20 turns past the default window, whose
        first 50 turns are exactly the end of the log, appends that tail even when the
        text repeats. The same length is an exact resend and does not grow.
        """
        incoming = [
            entry for entry in history
            if isinstance(entry, dict) and "role" in entry and "content" in entry
        ]
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                stored = self._history_rows(cursor, session_id, newest_first=False, limit=None)
                stored_ids = {row["id"] for row in stored}
                known = [
                    self._history_entry_id(entry) in stored_ids
                    for entry in incoming
                ]
                if any(known):
                    if all(known):
                        suffix_at = len(incoming)
                    else:
                        suffix_at = next(i for i, is_known in enumerate(known) if not is_known)
                    to_insert = [
                        entry for entry in incoming[suffix_at:]
                        if self._history_entry_id(entry) not in stored_ids
                    ]
                else:
                    stored_pairs = [(row["role"], row["content"]) for row in stored]
                    incoming_pairs = [(entry["role"], entry["content"]) for entry in incoming]
                    overlap = 0
                    for size in range(min(len(stored_pairs), len(incoming_pairs)), 0, -1):
                        if stored_pairs[-size:] == incoming_pairs[:size]:
                            overlap = size
                            break
                    to_insert = incoming[overlap:]
                    # Repeated text lets a long suffix match swallow new copies.
                    # If this list is not the same length as the log, and its first
                    # 50 turns are exactly the end of the log, those 50 are the
                    # default window and everything after them is new.
                    window = _HISTORY_WINDOW
                    if (
                        len(incoming_pairs) != len(stored_pairs)
                        and window < len(incoming_pairs) <= window + _HISTORY_TAIL_SLACK
                        and len(stored_pairs) >= window
                        and stored_pairs[-window:] == incoming_pairs[:window]
                    ):
                        to_insert = incoming[window:]
                for entry in to_insert:
                    cursor.execute(
                        "INSERT INTO history_entries (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                        (session_id, entry["role"], entry["content"], now)
                    )
                    entry["id"] = cursor.lastrowid
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e

    def load_history(self, session_id: Optional[str] = None, limit: Optional[int] = _HISTORY_WINDOW) -> List[Dict[str, str]]:
        """The most recent `limit` turns, oldest of that window first. None returns the full log."""
        if limit is not None and int(limit) < 1:
            return []
        with self._lock:
            cursor = self._get_connection().cursor()
            rows = self._history_rows(cursor, session_id, newest_first=True, limit=limit)
            cursor.close()
            rows.reverse()
            return rows

    def save_active_task(self, task_description: str, progress: int, status: str):
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO active_context (context_key, task_description, progress_percent, status, updated_at) 
                       VALUES ('main', ?, ?, ?, ?)""",
                    (task_description, progress, status, now)
                )
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e

    def get_active_task(self) -> Dict[str, Any]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT task_description as task, progress_percent, status, updated_at FROM active_context WHERE context_key = 'main'")
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else {}

    # ==========================================
    # CAPABILITY RECORD MANAGEMENT
    # ==========================================
    def save_capability_record(self, record_data: Dict[str, Any]):
        now = self._timestamp()
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT OR REPLACE INTO capability_records 
                       (capability_id, capability_name, required_evidence, required_tests, physical_verification_required, verification_status, evidence_ids, limitations, dependencies, last_verified_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_data["capability_id"],
                        record_data.get("capability_name", record_data["capability_id"]),
                        json.dumps(record_data.get("required_evidence", [])),
                        json.dumps(record_data.get("required_tests", [])),
                        1 if record_data.get("physical_verification_required", True) else 0,
                        record_data.get("verification_status", "NOT_IMPLEMENTED"),
                        json.dumps(record_data.get("evidence_ids", [])),
                        json.dumps(record_data.get("limitations", [])),
                        json.dumps(record_data.get("dependencies", [])),
                        record_data.get("last_verified_at", now)
                    )
                )
                conn.commit()
                cursor.close()
            except Exception as e:
                conn.rollback()
                raise e

    def get_capability_record(self, capability_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM capability_records WHERE capability_id = ?", (capability_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return None
            res = dict(row)
            res["required_evidence"] = json.loads(res["required_evidence"]) if res["required_evidence"] else []
            res["required_tests"] = json.loads(res["required_tests"]) if res["required_tests"] else []
            res["evidence_ids"] = json.loads(res["evidence_ids"]) if res["evidence_ids"] else []
            res["limitations"] = json.loads(res["limitations"]) if res["limitations"] else []
            res["dependencies"] = json.loads(res["dependencies"]) if res["dependencies"] else []
            res["physical_verification_required"] = bool(res["physical_verification_required"])
            return res

    def get_all_capability_records(self) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._get_connection().cursor()
            cursor.execute("SELECT * FROM capability_records")
            rows = cursor.fetchall()
            cursor.close()
            results = []
            for row in rows:
                res = dict(row)
                res["required_evidence"] = json.loads(res["required_evidence"]) if res["required_evidence"] else []
                res["required_tests"] = json.loads(res["required_tests"]) if res["required_tests"] else []
                res["evidence_ids"] = json.loads(res["evidence_ids"]) if res["evidence_ids"] else []
                res["limitations"] = json.loads(res["limitations"]) if res["limitations"] else []
                res["dependencies"] = json.loads(res["dependencies"]) if res["dependencies"] else []
                res["physical_verification_required"] = bool(res["physical_verification_required"])
                results.append(res)
            return results

    def close(self):
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
