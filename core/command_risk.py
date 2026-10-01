"""Clasificación de riesgo de comandos (spec 003, U3).

Si el texto no se puede analizar con confianza, el nivel es C. Los comandos
prohibidos no tienen aprobación posible. Esto no apaga exec_requires_approval:
solo un grant de misión deja pasar A o B.
"""
from __future__ import annotations

import re
import shlex
from typing import List, Optional, Tuple

PROHIBITED = "PROHIBITED"
LEVELS = ("A", "B", "C", "D", PROHIBITED)

_PROHIBITED_RE = re.compile(
    r"(?i)(\bformat\b|\bdiskpart\b|\bbcdedit\b|\breg(\.exe)?\s+delete\b|"
    r"\bset-executionpolicy\b|\brunas\b|\bstart-process\b.*\brunas\b|"
    r"\binvoke-expression\b|\biex\b|"
    r"\bset-mppreference\b|\bnetsh\b.*\badvfirewall\b|"
    r"irm\s*\|\s*iex|invoke-webrequest\s*\|\s*iex)"
)
_OBFUSCATED_RE = re.compile(
    r"(?i)(-encodedcommand|`|\$\(|\$\{|iex\b|invoke-expression|\+[\"']\s*\+)"
)


def _tokens(command: str) -> Optional[List[str]]:
    text = (command or "").strip()
    if not text:
        return None
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return None


_RANK = {"A": 0, "B": 1, "C": 2, "D": 3, PROHIBITED: 4}
_WRAPPERS = {
    "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
    "bash", "sh", "sudo", "doas",
}
_WRAPPER_FLAGS = {"-c", "/c", "-command", "/command"}


def _stricter(left: Tuple[str, str], right: Tuple[str, str]) -> Tuple[str, str]:
    if _RANK[right[0]] > _RANK[left[0]]:
        return right
    return left


def _inner_command(tokens: Optional[List[str]]) -> Optional[str]:
    """Texto que un envoltorio va a ejecutar. No baja el nivel del envoltorio."""
    if not tokens or len(tokens) < 2:
        return None
    head = tokens[0].lower()
    if head not in _WRAPPERS:
        return None
    tail = tokens[1:]
    if head in ("sudo", "doas"):
        return " ".join(tail)
    for index, token in enumerate(tail):
        if token.lower() in _WRAPPER_FLAGS and index + 1 < len(tail):
            return " ".join(tail[index + 1:])
    return None


def classify_command(command: str, _depth: int = 0) -> Tuple[str, str]:
    """Devuelve (nivel, motivo). Ante duda, C o PROHIBITED."""
    level, why = _classify_surface(command)
    if _depth < 2:
        inner = _inner_command(_tokens(command or ""))
        if inner and inner.strip() and inner.strip() != (command or "").strip():
            level, why = _stricter((level, why), classify_command(inner, _depth + 1))
    return level, why


def _classify_surface(command: str) -> Tuple[str, str]:
    raw = command or ""
    if not raw.strip():
        return "C", "EMPTY_COMMAND"
    if _PROHIBITED_RE.search(raw):
        return PROHIBITED, "PROHIBITED_COMMAND"
    if _OBFUSCATED_RE.search(raw):
        return "C", "OBFUSCATED"
    if any(tok in raw for tok in (";", "|", "&", "\n", "`")):
        return "C", "COMPOSITION"
    tokens = _tokens(raw)
    if tokens is None:
        return "C", "UNPARSEABLE"
    head = tokens[0].lower()
    tail = [t.lower() for t in tokens[1:]]
    joined = " ".join(tokens).lower()

    if head in ("format", "diskpart", "bcdedit"):
        return PROHIBITED, "PROHIBITED_COMMAND"
    if head == "git":
        if not tail:
            return "C", "GIT_BARE"
        sub = tail[0]
        if sub == "diff" and any(token.startswith("--output") for token in tail):
            return "C", "GIT_DIFF_OUTPUT"
        if sub in ("status", "diff", "log", "show"):
            return "A", "GIT_READ"
        if sub in ("checkout", "switch", "restore"):
            discards = "--" in tail or "-f" in tail or "--force" in tail or sub == "restore"
            if discards:
                return "D", "GIT_DISCARD"
            return "B", "GIT_LOCAL"
        if sub in ("add", "commit"):
            return "B", "GIT_LOCAL"
        if sub == "push":
            if "--force" in tail or "--force-with-lease" in tail or "-f" in tail:
                return "D", "GIT_FORCE_PUSH"
            return "C", "GIT_PUSH"
        if sub == "reset" and "--hard" in tail:
            return "D", "GIT_RESET_HARD"
        if sub == "clean":
            blob = "".join(token.lstrip("-") for token in tail[1:] if token.startswith("-"))
            if "f" in blob and "d" in blob:
                return "D", "GIT_CLEAN"
            return "C", "GIT_CLEAN_PARTIAL"
        if sub == "branch" and "-d" in tail:
            return "D", "GIT_BRANCH_DELETE"
        if sub == "reset":
            return "C", "GIT_RESET"
        return "C", "GIT_OTHER"
    if joined in ("pytest", "npm test") or joined.startswith("python -m pytest"):
        return "A", "TEST_COMMAND"
    if head in ("ls", "dir", "pwd", "whoami", "cat", "type"):
        return "A", "READ_DIAGNOSTIC"
    if "env:" in joined:
        return "C", "ENV_READ"
    if head in ("get-childitem", "get-content", "get-location"):
        return "A", "READ_DIAGNOSTIC"
    if head in ("npm", "pnpm", "yarn") and tail[:1] == ["install"] and "-g" not in tail and "--global" not in tail:
        return "B", "LOCAL_INSTALL"
    if head == "pip" or (head == "python" and tail[:2] == ["-m", "pip"]):
        if any(flag in tail for flag in ("-g", "--user", "--prefix")):
            return "C", "GLOBAL_INSTALL"
        return "B", "LOCAL_INSTALL"
    if head in ("rm", "del", "erase", "remove-item", "rmdir"):
        return "D", "DELETE_COMMAND"
    if head in ("shutdown", "restart-computer", "stop-computer"):
        return "D", "POWER_COMMAND"
    if head in ("sc", "net") and any(word in tail for word in ("start", "stop", "delete")):
        return "C", "SERVICE_COMMAND"
    if head in ("curl", "wget", "irm", "invoke-webrequest"):
        return "C", "DOWNLOAD"
    return "C", "UNCLASSIFIED_DEFAULT_C"


def grant_allows(level: str, grant: Optional[dict]) -> bool:
    """Un grant nulo no autoriza nada. El planificador no edita este dict."""
    if not grant or level in (PROHIBITED, "D"):
        return False
    allowed = set(grant.get("levels") or [])
    if level == "C":
        return "C" in allowed and bool(grant.get("allow_level_c"))
    return level in allowed
