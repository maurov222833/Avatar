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


def classify_command(command: str) -> Tuple[str, str]:
    """Devuelve (nivel, motivo). Ante duda, C o PROHIBITED."""
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
        if sub in ("add", "commit", "checkout", "switch"):
            return "B", "GIT_LOCAL"
        if sub == "push":
            return "C", "GIT_PUSH"
        if sub == "reset" and "--hard" in tail:
            return "D", "GIT_RESET_HARD"
        if sub == "clean" and ("-fd" in tail or "-df" in tail or "-xfd" in tail):
            return "D", "GIT_CLEAN"
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
