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
    PENDING_APPROVAL = "PENDING_APPROVAL"
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
    "UPDATE_CONFIG": ActRisk.LOCAL_WRITE,
    "COMMAND": ActRisk.EXEC,
    "SEND_WHATSAPP": ActRisk.EXTERNAL_MESSAGE,
    # WhatsApp por navegador dedicado (verificado por relectura), en vez de
    # improvisar con COMMAND+python. STATUS/READ son observación; SEND exige
    # consentimiento como todo mensaje externo.
    "WHATSAPP_STATUS": ActRisk.READ,
    "WHATSAPP_READ": ActRisk.READ,
    "WHATSAPP_SEND": ActRisk.EXTERNAL_MESSAGE,
    # Telegram (owner personal channel): status/test are READ; send is EXTERNAL but
    # allowlisted chat_ids skip dry-run/consent (same personal-channel decision).
    "TELEGRAM_STATUS": ActRisk.READ,
    "TELEGRAM_SEND": ActRisk.EXTERNAL_MESSAGE,
    "TELEGRAM_TEST": ActRisk.EXTERNAL_MESSAGE,
    # Browser (F-20): navigate/interact are NETWORK; observe is READ but untrusted.
    "BROWSER_NAVIGATE": ActRisk.NETWORK,
    "BROWSER_OBSERVE": ActRisk.READ,
    "BROWSER_CLICK": ActRisk.NETWORK,
    "BROWSER_FILL": ActRisk.NETWORK,
    "BROWSER_CLOSE": ActRisk.READ,
    # Desktop GUI (F-20): click/type are EXEC (operator approval); observe is READ.
    # DESKTOP_HOTKEY: allowlisted Win/Alt combos (minimize, show desktop…) — LOCAL_WRITE
    # so the owner can do common window actions from Telegram without EXEC bureaucracy.
    "DESKTOP_CLICK": ActRisk.EXEC,
    "DESKTOP_TYPE": ActRisk.EXEC,
    "DESKTOP_OBSERVE": ActRisk.READ,
    "DESKTOP_HOTKEY": ActRisk.LOCAL_WRITE,
}

#: Risk levels that require the operator to opt in before they may run.
RISKS_REQUIRING_CONSENT = {ActRisk.EXTERNAL_MESSAGE}

EXEC_APPROVAL_REASON = "EXEC_REQUIRES_OPERATOR_APPROVAL"
CONTAMINATED_APPROVAL_REASON = "CONTAMINATED_CONTEXT_REQUIRES_APPROVAL"
PATH_MASS_APPROVAL_REASON = "PATH_MASS_OPERATION"
APPROVAL_GATE_REASONS = frozenset({
    EXEC_APPROVAL_REASON, CONTAMINATED_APPROVAL_REASON, PATH_MASS_APPROVAL_REASON,
})

#: Tools whose outputs are untrusted instruction sources (F-06 / D4).
#: Personal messaging (WhatsApp / Telegram) is trusted by owner decision (2026-09-29):
#: those channels are private and allowlisted; contaminating them forced extra approvals
#: and slowed day-to-day talk with Avatar. Web / browser content stays untrusted.
UNTRUSTED_INPUT_ACTS = frozenset({
    "FETCH_URL",
    "WEB_SEARCH",
    "BROWSER_OBSERVE",
})

#: Policy reason when a mission hits its act budget (R4).
MISSION_ACT_BUDGET_EXCEEDED = "MISSION_ACT_BUDGET_EXCEEDED"

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


def _xdg_git_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.abspath(os.path.join(base, "git"))


def _is_git_metadata(parts: List[str]) -> bool:
    if ".git" in parts or ".gitconfig" in parts:
        return True
    if parts[-2:] == ["etc", "gitconfig"]:
        return True
    xdg = _normalized_parts(_xdg_git_dir())
    return parts[:len(xdg)] == xdg


def _git_metadata_inodes(path: str) -> set:
    """(st_dev, st_ino) of git config and hook files a hard link could alias."""
    candidates = [os.path.join(os.path.expanduser("~"), ".gitconfig"),
                  os.path.join(_xdg_git_dir(), "config")]
    current = os.path.dirname(os.path.abspath(path))
    while True:
        git_dir = os.path.join(current, ".git")
        if os.path.isdir(git_dir):
            candidates.append(os.path.join(git_dir, "config"))
            hooks = os.path.join(git_dir, "hooks")
            if os.path.isdir(hooks):
                candidates.extend(os.path.join(hooks, n) for n in os.listdir(hooks))
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    inodes = set()
    for candidate in candidates:
        try:
            st = os.stat(candidate)
            inodes.add((st.st_dev, st.st_ino))
        except OSError:
            continue
    return inodes


def _touches_git_dir(path: str) -> bool:
    """
    Defence in depth for WRITE_FILE: git config and hooks run code during later git commands.

    Checks the lexical path and the resolved one (symlinks, and 8.3 short names on Windows),
    and refuses to write through a hard link to a git config or hook file. The EXEC approval
    gate stays the primary control; this only narrows what an unattended write can prepare.
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
        st = os.stat(resolved)
    except OSError:
        return False
    if st.st_nlink <= 1:
        return False
    return (st.st_dev, st.st_ino) in _git_metadata_inodes(resolved)


def _is_within_root(target: str, root: str) -> bool:
    raw = str(target or "").strip()
    if os.name != "nt":
        if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
            return False
        norm = raw.replace("\\", "/")
        if norm.startswith("//") or norm.startswith("\\\\"):
            return False
    target_abs = os.path.normcase(os.path.abspath(target))
    root_abs = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([target_abs, root_abs]) == root_abs
    except ValueError:
        return False


def _names_trade(args: Dict[str, Any]) -> bool:
    """Una orden, un retiro o una transferencia nombrados no se ejecutan."""
    from core.market_signals import TRADE_ENDPOINTS
    blob = " ".join(
        str(args.get(key) or "")
        for key in ("url", "command", "params", "path", "endpoint")
    ).lower()
    return any(piece in blob for piece in TRADE_ENDPOINTS)


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
    #: Numeric Telegram chat/user ids of the owner — sends there are personal, not "broadcast".
    trusted_telegram_chat_ids: Tuple[str, ...] = ()
    #: Set when the mission has ingested untrusted text (web, WhatsApp, off-workspace files).
    #: While True, EXEC / LOCAL_WRITE / EXTERNAL_MESSAGE need operator approval (F-06).
    context_contaminated: bool = False
    #: Grant de misión (U3). None conserva la política anterior: EXEC pide aprobación.
    mission_grant: Optional[Dict[str, Any]] = None
    #: Contadores de contención (U4). Apagado por defecto para no frenar la suite.
    containment_enabled: bool = False
    #: Sesión de Windows bloqueada: no hay escritorio que mirar ni que tocar.
    session_locked: bool = False
    #: Sobre de noche (U13). Apagado: de día la captura y el audio siguen igual.
    night_mode: bool = False

    def is_trusted_personal_send(self, act_type: str, args: Dict[str, Any]) -> bool:
        """Telegram send/test to the owner skips external consent/dry-run."""
        if act_type == "TELEGRAM_TEST":
            # Owner-initiated connection probe; the executor refuses to send without a chat.
            return True
        if act_type != "TELEGRAM_SEND":
            return False
        chat = str((args or {}).get("chat_id") or "").strip()
        return bool(chat) and chat in set(self.trusted_telegram_chat_ids)

    def decide(self, act_type: str, args: Dict[str, Any],
               *, acts_already: Optional[int] = None) -> Tuple[bool, str]:
        """Return `(allowed, reason)`. `reason` is always populated so refusals are explainable."""
        risk = ACT_TYPES.get(act_type)
        if risk is None:
            return False, f"UNKNOWN_ACT_TYPE:{act_type}"
        if self.session_locked and act_type in (
            "SCREEN_CAPTURE", "DESKTOP_CLICK", "DESKTOP_TYPE",
            "DESKTOP_HOTKEY", "DESKTOP_OBSERVE",
        ):
            return False, "SESSION_LOCKED"
        if _names_trade(args or {}):
            return False, "TRADE_ENDPOINT_BLOCKED"
        access_mode = str((args or {}).get("access_mode") or "")
        if access_mode:
            from core.marketplace import authorize_access_mode
            allowed_mode, mode_reason = authorize_access_mode(access_mode)
            if not allowed_mode:
                return False, mode_reason
        if (args or {}).get("invented") and "review" in (args or {}):
            from core.marketing import reject_fake_review
            if reject_fake_review(str(args.get("review") or ""), invented=True):
                return False, "FAKE_REVIEW_REJECTED"
        if act_type in self.denied_act_types:
            return False, "ACT_TYPE_DENIED_BY_POLICY"
        if (
            self.max_acts_per_mission is not None
            and acts_already is not None
            and acts_already >= int(self.max_acts_per_mission)
        ):
            return False, MISSION_ACT_BUDGET_EXCEEDED
        trusted_personal = self.is_trusted_personal_send(act_type, args or {})
        if risk in RISKS_REQUIRING_CONSENT and not self.allow_external_messages and not trusted_personal:
            return False, "EXTERNAL_EFFECT_REQUIRES_OPERATOR_CONSENT"
        if self.context_contaminated and risk in (
            ActRisk.EXEC, ActRisk.LOCAL_WRITE, ActRisk.EXTERNAL_MESSAGE,
        ):
            # Contaminated missions never trust the allowlist alone: the model may have been
            # steered by untrusted text into asking for a "safe-looking" command.
            # Personal Telegram to the owner still needs approval when contaminated by web.
            return False, CONTAMINATED_APPROVAL_REASON
        if risk == ActRisk.EXEC and act_type == "COMMAND":
            from core.command_risk import PROHIBITED, classify_command, grant_allows
            command_text = args.get("command") or args.get("params") or ""
            level, why = classify_command(str(command_text))
            if level == PROHIBITED:
                return False, f"COMMAND_PROHIBITED:{why}"
            from core.path_guard import ALLOW, authorize_path, paths_in_command
            hard_deny = (
                "PATH_DENYLIST", "PATH_SECRET", "PATH_RESERVED",
                "PATH_ALTERNATE", "PATH_SHORT", "PATH_DRIVE_ROOT", "PATH_DRIVE_RELATIVE",
                "PATH_SECURITY", "PATH_BACKUP", "PATH_TRAILING",
            )
            for candidate in paths_in_command(str(command_text)):
                decision, why = authorize_path(
                    candidate, "write", self.allowed_workspace_root,
                )
                if decision != ALLOW and why.startswith(hard_deny):
                    return False, why
            if self.night_mode:
                from core.night_mode import queued_at_night
                if queued_at_night(act_type, level):
                    return False, "NIGHT_QUEUED"
            if grant_allows(level, self.mission_grant):
                return True, f"ALLOWED_MISSION_LEVEL_{level}"
        if self.night_mode:
            from core.night_mode import queued_at_night
            if queued_at_night(act_type):
                return False, "NIGHT_QUEUED"
        if risk == ActRisk.EXEC and self.exec_requires_approval:
            # Desktop GUI acts have no shell command line to allowlist — always ask.
            if act_type in ("DESKTOP_CLICK", "DESKTOP_TYPE"):
                return False, EXEC_APPROVAL_REASON
            command = args.get("command") or args.get("params") or ""
            if command_matches_allowlist(command, self.exec_allowlist):
                return True, "ALLOWED_BY_EXEC_ALLOWLIST"
            return False, EXEC_APPROVAL_REASON
        if act_type == "WRITE_FILE" and _touches_git_dir(args.get("file_path") or ""):
            return False, "WRITE_TO_PROTECTED_PATH_DENIED"
        if risk == ActRisk.LOCAL_WRITE and self.allowed_workspace_root:
            root = os.path.abspath(self.allowed_workspace_root)
            # Solo rutas reales de archivo: el audio_source de PLAY_AUDIO suele ser
            # un título de canción ("bonito bonito"), no un path.
            path_candidates = []
            fp = args.get("file_path") or ""
            if fp:
                path_candidates.append(fp)
            audio = args.get("audio_source") or ""
            if audio and (os.path.isabs(audio) or os.path.exists(audio) or "\\" in audio or "/" in audio):
                # Heurística: parece ruta, no título de canción.
                if any(sep in audio for sep in ("/", "\\")) or os.path.exists(audio):
                    path_candidates.append(audio)
            for target in path_candidates:
                if target and not _is_within_root(target, root):
                    return False, f"WRITE_OUTSIDE_ALLOWED_ROOT:{root}"
        if act_type == "WRITE_FILE":
            from core.path_guard import ALLOW, authorize_path
            target = args.get("file_path") or ""
            if target:
                try:
                    affected = int(args.get("affected_count") or 1)
                except (TypeError, ValueError):
                    return False, "PATH_EMPTY_OR_AMBIGUOUS"
                decision, why = authorize_path(
                    target, "write", self.allowed_workspace_root, affected_count=affected,
                )
                if decision != ALLOW:
                    return False, why
        if trusted_personal:
            return True, "ALLOWED_PERSONAL_TELEGRAM"
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


# Una escritura a medias no se corta. Se nombra, se deja terminar y no se abre otro acto.
_NON_INTERRUPTIBLE = frozenset({"WRITE_FILE"})


def _halt_block_message(act_type: str, args: Dict[str, Any], reason: str) -> str:
    from core.halt import in_flight_critical
    names = in_flight_critical()
    course = f" En curso: {', '.join(names)}." if names else ""
    return (
        f"[Bloqueado por política: {reason}] No se ejecutó '{act_type}'.{course} "
        f"Solicitud: {json.dumps(args or {}, ensure_ascii=False)[:200]}"
    )


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


def _observe_json_success(args: Dict[str, Any], result: str) -> Dict[str, Any]:
    """
    Browser/desktop executors return JSON with a success/verified flag.
    Prefer an explicit verified key; otherwise treat success=True as verified.
    """
    try:
        data = json.loads(result or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    verified = bool(data.get("verified", data.get("success", False)))
    return {
        "report": (result or "")[:300],
        "success": bool(data.get("success", False)),
        "verified": verified,
    }


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

def _clog(message: str, level: str = "INFO") -> None:
    try:
        from core.logging_util import log
        log(level, message, component="ActChokepoint")
    except Exception:
        pass

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
            conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                act_id TEXT NOT NULL,
                mission_id TEXT,
                task_id TEXT,
                execution_id TEXT,
                act_type TEXT NOT NULL,
                risk TEXT NOT NULL,
                request TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolver TEXT,
                result TEXT
            );
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)")
            conn.commit()

    def _register_default_observers(self):
        self.observers.setdefault("WRITE_FILE", _observe_write_file)
        self.observers.setdefault("COMMAND", _observe_command)
        self.observers.setdefault("SCREEN_CAPTURE", _observe_screen_capture)
        self.observers.setdefault("SEND_WHATSAPP", _observe_external_message)
        self.observers.setdefault("WHATSAPP_STATUS", _observe_whatsapp_report)
        self.observers.setdefault("WHATSAPP_READ", _observe_whatsapp_report)
        self.observers.setdefault("WHATSAPP_SEND", _observe_external_message)
        for browser_act in (
            "BROWSER_NAVIGATE", "BROWSER_OBSERVE", "BROWSER_CLICK",
            "BROWSER_FILL", "BROWSER_CLOSE",
        ):
            self.observers.setdefault(browser_act, _observe_json_success)
        for desktop_act in ("DESKTOP_CLICK", "DESKTOP_TYPE", "DESKTOP_OBSERVE"):
            self.observers.setdefault(desktop_act, _observe_json_success)
        self.observers.setdefault("TELEGRAM_STATUS", _observe_json_success)
        self.observers.setdefault("TELEGRAM_SEND", _observe_json_success)
        self.observers.setdefault("TELEGRAM_TEST", _observe_json_success)

    def mark_contaminated(self, reason: str = "") -> None:
        """Mark the active context as having ingested untrusted text (F-06)."""
        self.policy.context_contaminated = True
        if reason:
            _clog(f"[ActChokepoint]: contexto contaminado -> {reason}")

    def clear_contamination(self) -> None:
        """Reset provenance for a new user turn."""
        self.policy.context_contaminated = False

    def note_tool_provenance(self, act_type: str, args: Optional[Dict[str, Any]] = None) -> str:
        """
        After a tool returns into the model context, classify its provenance.

        Untrusted sources are web/internet (FETCH_URL, WEB_SEARCH, BROWSER_OBSERVE)
        and files outside the workspace. Personal messaging reads (WhatsApp) do not
        contaminate: the owner treat those as trusted personal channels.
        While contaminated, later EXEC/WRITE/EXTERNAL acts need approval.
        """
        args = args or {}
        if act_type in UNTRUSTED_INPUT_ACTS:
            self.mark_contaminated(act_type)
            return "untrusted"
        if act_type == "READ_FILE":
            path = args.get("file_path") or args.get("params") or ""
            root = self.policy.allowed_workspace_root or os.getcwd()
            if path and not _is_within_root(path, root):
                self.mark_contaminated(f"READ_FILE:{path}")
                return "untrusted"
            return "workspace"
        if act_type in ("WHATSAPP_READ", "WHATSAPP_STATUS", "WHATSAPP_SEND", "SEND_WHATSAPP",
                        "TELEGRAM_STATUS", "TELEGRAM_SEND", "TELEGRAM_TEST"):
            return "personal_channel"
        return "trusted"

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

    def _persist_approval(
        self,
        *,
        approval_id: str,
        act_id: str,
        mission_id: str,
        task_id: str,
        execution_id: str,
        act_type: str,
        risk: str,
        request: Dict[str, Any],
        reason: str,
        status: str,
        resolved_at: Optional[str] = None,
        resolver: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        if not self.state_db:
            return
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            conn.execute(
                "INSERT OR REPLACE INTO approvals ("
                "approval_id, act_id, mission_id, task_id, execution_id, act_type, risk,"
                " request, reason, status, created_at, resolved_at, resolver, result"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    approval_id,
                    act_id,
                    mission_id or "",
                    task_id or "",
                    execution_id or "",
                    act_type,
                    risk,
                    json.dumps(request, ensure_ascii=False)[:2000],
                    reason,
                    status,
                    _now(),
                    resolved_at,
                    resolver,
                    (result or "")[:4000] if result is not None else None,
                ),
            )
            conn.commit()

    def list_pending_approvals(self) -> List[Dict[str, Any]]:
        return self.list_approvals(status="PENDING")

    def list_approvals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.state_db:
            return []
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            if status:
                cur = conn.execute(
                    "SELECT * FROM approvals WHERE status = ? ORDER BY created_at",
                    (status,),
                )
            else:
                cur = conn.execute("SELECT * FROM approvals ORDER BY created_at")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        if not self.state_db or not approval_id:
            return None
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            cur = conn.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    def resolve_approval(
        self,
        approval_id: str,
        approved: bool,
        resolver: str = "operator",
    ) -> Dict[str, Any]:
        """
        Approve or reject a queued act (F-18).

        On approve, runs the original request through the registered executor and updates
        both the approval row and the linked act record. On reject, marks both as denied.
        """
        from core.halt import current_block_reason
        halted = current_block_reason()
        if halted:
            return {"ok": False, "error": halted, "approval_id": approval_id}
        row = self.get_approval(approval_id)
        if row is None:
            return {"ok": False, "error": "APPROVAL_NOT_FOUND", "approval_id": approval_id}
        if row["status"] != "PENDING":
            return {
                "ok": False,
                "error": "APPROVAL_NOT_PENDING",
                "approval_id": approval_id,
                "status": row["status"],
            }

        try:
            request = json.loads(row["request"] or "{}")
        except Exception:
            request = {}

        resolved_at = _now()
        if not approved:
            self._update_approval(
                approval_id,
                status="REJECTED",
                resolved_at=resolved_at,
                resolver=resolver,
                result=None,
            )
            self._update_act_status(
                row["act_id"],
                status=ActStatus.DENIED,
                policy_reason="REJECTED_BY_OPERATOR",
            )
            return {
                "ok": True,
                "approval_id": approval_id,
                "status": "REJECTED",
                "act_type": row["act_type"],
                "result": None,
            }

        # Temporarily clear contamination / approval gates for this one resolved act:
        # the operator already decided. Restore afterwards.
        saved_contaminated = self.policy.context_contaminated
        saved_exec = self.policy.exec_requires_approval
        self.policy.context_contaminated = False
        self.policy.exec_requires_approval = False
        try:
            output = self.perform(
                act_type=row["act_type"],
                args=request,
                mission_id=row.get("mission_id") or "",
                task_id=row.get("task_id") or "",
                execution_id=row.get("execution_id") or "",
            )
        finally:
            self.policy.context_contaminated = saved_contaminated
            self.policy.exec_requires_approval = saved_exec

        # The fresh perform() created a new act; keep the original pending act linked.
        self._update_approval(
            approval_id,
            status="EXECUTED",
            resolved_at=resolved_at,
            resolver=resolver,
            result=output,
        )
        self._update_act_status(
            row["act_id"],
            status=ActStatus.EXECUTED,
            policy_reason="APPROVED_BY_OPERATOR",
            executor_result=output,
        )
        return {
            "ok": True,
            "approval_id": approval_id,
            "status": "EXECUTED",
            "act_type": row["act_type"],
            "result": output,
        }

    def _update_approval(
        self,
        approval_id: str,
        *,
        status: str,
        resolved_at: str,
        resolver: str,
        result: Optional[str],
    ) -> None:
        if not self.state_db:
            return
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            conn.execute(
                "UPDATE approvals SET status = ?, resolved_at = ?, resolver = ?, result = ? "
                "WHERE approval_id = ?",
                (status, resolved_at, resolver, (result or "")[:4000] if result is not None else None,
                 approval_id),
            )
            conn.commit()

    def _update_act_status(
        self,
        act_id: str,
        *,
        status: str,
        policy_reason: str,
        executor_result: Optional[str] = None,
    ) -> None:
        if not self.state_db or not act_id:
            return
        with self.state_db._lock:
            conn = self.state_db._get_connection()
            if executor_result is not None:
                conn.execute(
                    "UPDATE acts SET status = ?, policy_reason = ?, executor_result = ? "
                    "WHERE act_id = ?",
                    (status, policy_reason, executor_result[:4000], act_id),
                )
            else:
                conn.execute(
                    "UPDATE acts SET status = ?, policy_reason = ? WHERE act_id = ?",
                    (status, policy_reason, act_id),
                )
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

        from core.halt import current_block_reason
        halted = current_block_reason()
        if halted:
            record.policy_reason = halted
            record.status = ActStatus.DENIED
            self._persist(record)
            return _halt_block_message(act_type, args or {}, halted)

        acts_already = None
        if mission_id and self.policy.max_acts_per_mission is not None:
            try:
                acts_already = len(self.list_acts(mission_id=mission_id))
            except Exception:
                acts_already = None

        allowed, reason = self.policy.decide(
            act_type, args or {}, acts_already=acts_already)
        if not allowed and reason in APPROVAL_GATE_REASONS:
            if self.approver is not None:
                try:
                    approved = bool(self.approver(act_type, dict(args or {})))
                except Exception:
                    approved = False
                allowed = approved
                reason = "APPROVED_BY_OPERATOR" if approved else "REJECTED_BY_OPERATOR"
            else:
                # No live operator on this surface: queue for later approval (F-18).
                # Without a state DB there is nowhere to park the request — fail closed.
                if self.state_db is None:
                    record.policy_reason = reason
                    record.status = ActStatus.DENIED
                    return (
                        f"[Bloqueado por política: {reason}] No se ejecutó '{act_type}'. "
                        f"Solicitud: {json.dumps(args or {}, ensure_ascii=False)[:200]}"
                    )
                approval_id = f"apr_{uuid.uuid4().hex[:12]}"
                record.policy_reason = reason
                record.status = ActStatus.PENDING_APPROVAL
                self._persist(record)
                self._persist_approval(
                    approval_id=approval_id,
                    act_id=record.act_id,
                    mission_id=record.mission_id,
                    task_id=record.task_id,
                    execution_id=record.execution_id,
                    act_type=act_type,
                    risk=risk,
                    request=dict(args or {}),
                    reason=reason,
                    status="PENDING",
                )
                return (
                    f"[PENDING_APPROVAL:{approval_id}] Motivo: {reason}. "
                    f"No se ejecutó '{act_type}' aún. "
                    f"Aprueba con /approve {approval_id} o POST /api/approvals/{approval_id}/resolve. "
                    f"Solicitud: {json.dumps(args or {}, ensure_ascii=False)[:200]}"
                )
        record.policy_reason = reason
        if not allowed:
            record.status = ActStatus.DENIED
            self._persist(record)
            return (f"[Bloqueado por política: {reason}] No se ejecutó '{act_type}'. "
                    f"Solicitud: {json.dumps(args or {}, ensure_ascii=False)[:200]}")

        if self.policy.dry_run and risk in RISKS_REQUIRING_CONSENT:
            if not self.policy.is_trusted_personal_send(act_type, args or {}):
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

        from core.halt import clear_critical, current_block_reason, note_critical
        halted_now = current_block_reason()
        if halted_now:
            record.policy_reason = halted_now
            record.status = ActStatus.DENIED
            self._persist(record)
            return _halt_block_message(act_type, args or {}, halted_now)

        critical = act_type in _NON_INTERRUPTIBLE
        if critical:
            note_critical(record.act_id)
        try:
            result = executor(args or {})
        except Exception as exc:
            record.status = ActStatus.FAILED
            record.policy_reason = f"EXECUTOR_ERROR:{type(exc).__name__}"
            self._persist(record)
            return f"[Error de ejecución en {act_type}]: {exc}"
        finally:
            if critical:
                clear_critical(record.act_id)
        record.executor_result = result
        record.status = ActStatus.EXECUTED

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
        if self.policy.containment_enabled and record.status in (
            ActStatus.EXECUTED, ActStatus.OBSERVED, ActStatus.OBSERVATION_FAILED,
        ):
            trip = self._containment_monitor().observe(
                act_type, args or {}, mission_status="ACTIVE",
            )
            if trip:
                from core.halt import engage
                engage("PAUSE", source="containment", actor="containment")
        return result

    def _containment_monitor(self):
        monitor = getattr(self, "_containment", None)
        if monitor is None:
            from core.containment import ContainmentMonitor
            monitor = ContainmentMonitor()
            self._containment = monitor
        return monitor
