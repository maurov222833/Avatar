"""
Act chokepoint — the single place where Avatar performs a side effect.

Why this exists
---------------
Before this module, the agent could reach a real external action (a WhatsApp message, a
PowerShell command, a file write) by calling a tool directly. Nothing recorded that it
happened, nothing could refuse it, and nothing distinguished "the tool said it worked" from
"we observed that it worked". The authority subsystem could not help, because it sat behind a
mission row that the execution path never created.

This module makes the following structural properties true:

  1. **One writer.** A side effect happens here or not at all. Adding a tool means registering
     an act type, not bypassing a check.
  2. **Request ≠ attempt ≠ execution ≠ observation.** A record carries all four separately, so
     a denied or failed act is representable and distinguishable from a successful one.
  3. **The tool's own success claim is never proof.** `observed` comes from the observer, which
     inspects the real post-state independently of what the executor reported.
  4. **Dry-run is the default for external effects.** Sending a real message requires the
     operator to opt in, not the agent to opt out.
  5. **Everything is recorded.** Every attempt produces an append-only row, so "what did Avatar
     actually do?" is a SQL query rather than an inference from logs.

Security note, stated precisely: this is an in-process control. It stops a *mistaken or
over-eager agent* and produces an auditable record. It does not stop arbitrary code executing
inside the agent's interpreter, which can call the underlying tools directly. Protection
against that requires an out-of-process boundary; see docs/AVATAR_FINAL_DELIVERY_REPORT.md.
"""
from __future__ import annotations

import datetime
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------
class ActStatus:
    REQUESTED = "REQUESTED"
    DENIED = "DENIED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    OBSERVED = "OBSERVED"
    OBSERVATION_FAILED = "OBSERVATION_FAILED"


class ActRisk:
    READ = "READ"              # no external consequence
    LOCAL_WRITE = "LOCAL_WRITE"  # writes to disk
    NETWORK = "NETWORK"          # outbound network request
    EXTERNAL_MESSAGE = "EXTERNAL_MESSAGE"  # a human being receives this
    EXEC = "EXEC"                # arbitrary code execution


#: Act types Avatar can perform, and the risk each carries. Anything not listed is refused,
#: so an unknown tool name cannot reach an executor.
ACT_TYPES: Dict[str, str] = {
    "READ_FILE": ActRisk.READ,
    "LIST_DIR": ActRisk.READ,
    "WEB_SEARCH": ActRisk.NETWORK,
    "FETCH_URL": ActRisk.NETWORK,
    "PLAY_AUDIO": ActRisk.LOCAL_WRITE,
    "AUDIO_CONTROL": ActRisk.LOCAL_WRITE,
    "SCREEN_CAPTURE": ActRisk.READ,
    "WRITE_FILE": ActRisk.LOCAL_WRITE,
    "COMMAND": ActRisk.EXEC,
    "SEND_WHATSAPP": ActRisk.EXTERNAL_MESSAGE,
    # WhatsApp por navegador dedicado (verificado por relectura), en vez de
    # improvisar con COMMAND+python. STATUS/READ son observación; SEND exige
    # consentimiento como todo mensaje externo.
    "WHATSAPP_STATUS": ActRisk.READ,
    "WHATSAPP_READ": ActRisk.READ,
    "WHATSAPP_SEND": ActRisk.EXTERNAL_MESSAGE,
}

#: Risk levels that require the operator to opt in before they may run.
RISKS_REQUIRING_CONSENT = {ActRisk.EXTERNAL_MESSAGE}

EXEC_APPROVAL_REASON = "EXEC_REQUIRES_OPERATOR_APPROVAL"

#: Characters that let one command line smuggle another (PowerShell and POSIX shells).
#: An allowlisted prefix followed by any of these is not the allowlisted command anymore.
#: PowerShell evaluates `(...)`, `{...}` and `$var` inside arguments, so they are excluded too.
_COMMAND_CHAINING_TOKENS = (";", "&", "|", "`", "$", "(", ")", "{", "}", ">", "<", "\n", "\r")


def command_matches_allowlist(command: str, allowlist: Tuple[str, ...]) -> bool:
    """
    True only if `command` is exactly one allowlisted command line.

    Matching is case-insensitive on whitespace-normalised text. Arguments are never implied:
    options such as `git diff --output=...`, `--ext-diff` or `Get-ChildItem Env:` change what
    a command does, so each permitted invocation must be listed in full. Chaining and
    evaluation tokens disqualify a command even if an entry contains them.
    """
    if any(tok in (command or "") for tok in _COMMAND_CHAINING_TOKENS):
        return False
    text = " ".join((command or "").split()).lower()
    if not text:
        return False
    return any(text == " ".join((entry or "").split()).lower() for entry in allowlist or ())


def _normalized_parts(path: str) -> List[str]:
    parts = []
    for i, part in enumerate(path.replace("\\", "/").split("/")):
        if i > 0 or not (len(part) == 2 and part[1] == ":"):
            part = part.split(":", 1)[0]  # NTFS stream suffix: name::$DATA is the file itself
        # Win32 drops trailing dots and spaces, so ".git." and ".git " open ".git".
        parts.append(part.rstrip(" .").casefold())
    return parts


def _is_git_metadata(parts: List[str]) -> bool:
    if ".git" in parts or ".gitconfig" in parts or (parts and parts[-1] == "gitconfig"):
        return True
    return any(parts[i:i + 2] == [".config", "git"] for i in range(len(parts) - 1))


def _touches_git_dir(path: str) -> bool:
    """
    Defence in depth for WRITE_FILE: git config and hooks run code during later git commands.

    Checks the lexical path and the resolved one (symlinks, and 8.3 short names on Windows),
    and refuses to write through an existing hard link. The EXEC approval gate stays the
    primary control; this only narrows what an unattended write can prepare.
    """
    if not path:
        return False
    lexical = os.path.abspath(path)
    try:
        resolved = os.path.realpath(path)
    except (OSError, ValueError):
        return True
    if _is_git_metadata(_normalized_parts(lexical)) or _is_git_metadata(_normalized_parts(resolved)):
        return True
    try:
        return os.path.isfile(resolved) and os.stat(resolved).st_nlink > 1
    except OSError:
        return False


def _is_within_root(target: str, root: str) -> bool:
    target_abs = os.path.normcase(os.path.abspath(target))
    root_abs = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([target_abs, root_abs]) == root_abs
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
@dataclass
class ActPolicy:
    """
    Decides whether an act may proceed.

    Defaults are deliberately conservative for anything that reaches a human: external
    messages require explicit consent and, by default, run in dry-run. Arbitrary command
    execution requires operator approval unless the exact command is allowlisted; dry-run
    does not cover it, because a command's effects are not external messages.
    """

    dry_run: bool = True
    allow_external_messages: bool = False
    allowed_workspace_root: Optional[str] = None
    denied_act_types: Tuple[str, ...] = ()
    max_acts_per_mission: Optional[int] = None
    exec_requires_approval: bool = True
    exec_allowlist: Tuple[str, ...] = ()

    def decide(self, act_type: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """Return `(allowed, reason)`. `reason` is always populated so refusals are explainable."""
        risk = ACT_TYPES.get(act_type)
        if risk is None:
            return False, f"UNKNOWN_ACT_TYPE:{act_type}"
        if act_type in self.denied_act_types:
            return False, "ACT_TYPE_DENIED_BY_POLICY"
        if risk in RISKS_REQUIRING_CONSENT and not self.allow_external_messages:
            return False, "EXTERNAL_EFFECT_REQUIRES_OPERATOR_CONSENT"
        if risk == ActRisk.EXEC and self.exec_requires_approval:
            command = args.get("command") or args.get("params") or ""
            if command_matches_allowlist(command, self.exec_allowlist):
                return True, "ALLOWED_BY_EXEC_ALLOWLIST"
            return False, EXEC_APPROVAL_REASON
        if act_type == "WRITE_FILE" and _touches_git_dir(args.get("file_path") or ""):
            return False, "WRITE_TO_PROTECTED_PATH_DENIED"
        if risk == ActRisk.LOCAL_WRITE and self.allowed_workspace_root:
            root = os.path.abspath(self.allowed_workspace_root)
            target = args.get("file_path") or args.get("audio_source") or ""
            if target and not _is_within_root(target, root):
                return False, f"WRITE_OUTSIDE_ALLOWED_ROOT:{root}"
        return True, "ALLOWED"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
@dataclass
class ActRecord:
    """One attempt at one side effect. Append-only."""

    act_id: str
    mission_id: str
    task_id: str
    execution_id: str
    act_type: str
    risk: str
    request: Dict[str, Any]
    status: str
    policy_reason: str
    dry_run: bool
    executor_result: Optional[str] = None
    observed: Optional[Dict[str, Any]] = None
    observation_verified: Optional[bool] = None
    created_at: str = ""

    def to_row(self) -> Tuple:
        return (
            self.act_id, self.mission_id or "", self.task_id or "", self.execution_id or "",
            self.act_type, self.risk, json.dumps(self.request, ensure_ascii=False)[:2000],
            self.status, self.policy_reason, 1 if self.dry_run else 0,
            (self.executor_result or "")[:4000],
            json.dumps(self.observed, ensure_ascii=False)[:2000] if self.observed else None,
            None if self.observation_verified is None else (1 if self.observation_verified else 0),
            self.created_at,
        )


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Observers
# ---------------------------------------------------------------------------
def _observe_write_file(args: Dict[str, Any], result: str) -> Dict[str, Any]:
    """Independently check the file really exists afterwards, rather than trusting the writer."""
    path = args.get("file_path", "")
    exists = bool(path) and os.path.isfile(path)
    return {"file_path": path, "exists": exists,
            "size": os.path.getsize(path) if exists else 0,
            "verified": exists}


def _observe_command(args: Dict[str, Any], result: str) -> Dict[str, Any]:
    """
    Read the exit code out of the raw tool output.

    Every observer returns an explicit `verified` key. Without it the chokepoint had no way to
    decide, and a successful command was recorded as OBSERVATION_FAILED.
    """
    import re
    match = re.search(r"\[Resultado PowerShell \(ExitCode:\s*(-?\d+)\)\]:", result or "")
    exit_code = int(match.group(1)) if match else None
    return {"exit_code": exit_code,
            "output_length": len(result or ""),
            "verified": exit_code == 0}


def _observe_screen_capture(args: Dict[str, Any], result: str) -> Dict[str, Any]:
    """The executor returns the image path; verified means a non-empty file really exists."""
    path = (result or "").strip()
    exists = bool(path) and os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    return {"file_path": path, "exists": exists, "size": size, "verified": size > 0}


def _observe_whatsapp_report(args: Dict[str, Any], result: str) -> Dict[str, Any]:
    """
    Los ejecutores WHATSAPP_STATUS/READ reportan 'RESULT:OK ...' o 'RESULT:ERROR ...'.
    Verificado = el ejecutor afirma OK sin marcas de error. Determinista y testeable.
    """
    text = result or ""
    lowered = text.lower()
    looks_like_error = text.startswith("RESULT:ERROR") or any(
        t in lowered for t in ("error", "denegad", "no se pudo", "fall"))
    ok = text.startswith("RESULT:OK") and not looks_like_error
    return {"report": text[:300], "looks_like_error": looks_like_error,
            "verified": ok}


def _observe_external_message(args: Dict[str, Any], result: str) -> Dict[str, Any]:
    """
    For external messages there is no system-side signal of delivery, so the observer
    records what is actually knowable and says so, rather than manufacturing a success
    claim. EXCEPTION: an executor that verified by read-back (e.g. the WhatsApp DOM
    reader re-reading the outgoing bubble) marks its report with [READBACK_VERIFIED];
    that independent observation is honored as verification.
    """
    lowered = (result or "").lower()
    looks_like_error = any(t in lowered for t in ("error", "denegad", "no se pudo", "fall"))
    readback = "[READBACK_VERIFIED]" in (result or "")
    return {
        "delivery_confirmed": readback and not looks_like_error,
        "executor_report": (result or "")[:200],
        "note": ("Verified by read-back of the outgoing message."
                 if readback else
                 "No system-side delivery receipt; success is NOT independently confirmed."),
        "looks_like_error": looks_like_error,
        "verified": readback and not looks_like_error,
    }


# ---------------------------------------------------------------------------
# Chokepoint
# ---------------------------------------------------------------------------
class ActChokepoint:
    """
    The only sanctioned path to a side effect.

    The orchestrator calls `perform(...)`; it never touches a tool module directly. That is the
    whole point: it makes "what can Avatar do" a single readable function.
    """

    def __init__(self, state_db=None, policy: Optional[ActPolicy] = None,
                 executors: Optional[Dict[str, Callable[[Dict[str, Any]], str]]] = None,
                 observers: Optional[Dict[str, Callable]] = None,
                 approver: Optional[Callable[[str, Dict[str, Any]], bool]] = None):
        self.state_db = state_db
        self.policy = policy or ActPolicy()
        self.executors: Dict[str, Callable[[Dict[str, Any]], str]] = dict(executors or {})
        self.observers: Dict[str, Callable] = dict(observers or {})
        # Only set by a surface with a human present (the interactive CLI). Remote channels
        # and the GUI server never set it, so approval-gated acts are refused there.
        self.approver = approver
        self._ensure_schema()
        self._register_default_observers()

    # ---------------- persistence ----------------
    def _ensure_schema(self):
        if not self.state_db:
            return
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            conn.execute("""
            CREATE TABLE IF NOT EXISTS acts (
                act_id TEXT PRIMARY KEY,
                mission_id TEXT,
                task_id TEXT,
                execution_id TEXT,
                act_type TEXT NOT NULL,
                risk TEXT NOT NULL,
                request TEXT NOT NULL,
                status TEXT NOT NULL,
                policy_reason TEXT NOT NULL,
                dry_run INTEGER NOT NULL,
                executor_result TEXT,
                observed TEXT,
                observation_verified INTEGER,
                created_at TEXT NOT NULL
            );
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_acts_mission ON acts(mission_id)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_acts_created ON acts(created_at)")
            conn.commit()

    def _register_default_observers(self):
        self.observers.setdefault("WRITE_FILE", _observe_write_file)
        self.observers.setdefault("COMMAND", _observe_command)
        self.observers.setdefault("SCREEN_CAPTURE", _observe_screen_capture)
        self.observers.setdefault("SEND_WHATSAPP", _observe_external_message)
        self.observers.setdefault("WHATSAPP_STATUS", _observe_whatsapp_report)
        self.observers.setdefault("WHATSAPP_READ", _observe_whatsapp_report)
        self.observers.setdefault("WHATSAPP_SEND", _observe_external_message)

    def list_acts(self, mission_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.state_db:
            return []
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            if mission_id:
                cur = conn.execute(
                    "SELECT * FROM acts WHERE mission_id = ? ORDER BY created_at", (mission_id,))
            else:
                cur = conn.execute("SELECT * FROM acts ORDER BY created_at")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _persist(self, record: ActRecord):
        if not self.state_db:
            return
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            conn.execute(
                "INSERT OR REPLACE INTO acts (act_id, mission_id, task_id, execution_id, act_type,"
                " risk, request, status, policy_reason, dry_run, executor_result, observed,"
                " observation_verified, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                record.to_row())
            conn.commit()

    # ---------------- the single entry point ----------------
    def perform(
        self,
        act_type: str,
        args: Dict[str, Any],
        mission_id: str = "",
        task_id: str = "",
        execution_id: str = "",
    ) -> str:
        """
        Request, authorise, execute and observe one act.

        Returns a human-readable string in the tool-result shape the orchestrator already
        expects, so integrating the chokepoint does not require rewriting the planning layer.
        """
        risk = ACT_TYPES.get(act_type, "UNKNOWN")
        record = ActRecord(
            act_id=f"act_{uuid.uuid4().hex[:12]}",
            mission_id=mission_id or "",
            task_id=task_id or "",
            execution_id=execution_id or "",
            act_type=act_type,
            risk=risk,
            request=dict(args or {}),
            status=ActStatus.REQUESTED,
            policy_reason="",
            dry_run=self.policy.dry_run,
            created_at=_now(),
        )

        allowed, reason = self.policy.decide(act_type, args or {})
        if not allowed and reason == EXEC_APPROVAL_REASON and self.approver is not None:
            try:
                approved = bool(self.approver(act_type, dict(args or {})))
            except Exception:
                approved = False
            allowed = approved
            reason = "APPROVED_BY_OPERATOR" if approved else "REJECTED_BY_OPERATOR"
        record.policy_reason = reason
        if not allowed:
            record.status = ActStatus.DENIED
            self._persist(record)
            return (f"[Bloqueado por política: {reason}] No se ejecutó '{act_type}'. "
                    f"Solicitud: {json.dumps(args or {}, ensure_ascii=False)[:200]}")

        if self.policy.dry_run and risk in RISKS_REQUIRING_CONSENT:
            record.status = ActStatus.DENIED
            record.policy_reason = "DRY_RUN_NO_EXTERNAL_EFFECT"
            self._persist(record)
            return (f"[DRY-RUN] No se envió ningún mensaje real. "
                    f"Solicitud registrada: {json.dumps(args or {}, ensure_ascii=False)[:200]}")

        executor = self.executors.get(act_type)
        if executor is None:
            record.status = ActStatus.DENIED
            record.policy_reason = "NO_EXECUTOR_REGISTERED"
            self._persist(record)
            return f"[Error]: no hay ejecutor registrado para '{act_type}'."

        try:
            result = executor(args or {})
            record.executor_result = result
            record.status = ActStatus.EXECUTED
        except Exception as exc:
            record.status = ActStatus.FAILED
            record.policy_reason = f"EXECUTOR_ERROR:{type(exc).__name__}"
            self._persist(record)
            return f"[Error de ejecución en {act_type}]: {exc}"

        observer = self.observers.get(act_type)
        if observer is not None:
            try:
                observed = observer(args or {}, result)
                record.observed = observed
                record.observation_verified = bool(observed.get("verified", False))
                record.status = (ActStatus.OBSERVED if record.observation_verified
                                 else ActStatus.OBSERVATION_FAILED)
            except Exception as exc:
                record.observed = {"observer_error": f"{type(exc).__name__}: {exc}"}
                record.observation_verified = False
                record.status = ActStatus.OBSERVATION_FAILED

        self._persist(record)
        return result
