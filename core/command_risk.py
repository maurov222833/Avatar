"""Clasificación de riesgo de comandos (spec 003, U3).

C entendido (git push, curl, un install sin fijar) puede entrar en un grant
con allow_level_c. Lo no entendido no entra en ningún grant: pide el comando
completo. Lo ofuscado es PROHIBITED. Esto no apaga exec_requires_approval.
"""
from __future__ import annotations

import os
import re
import shlex
from typing import List, Optional, Sequence, Tuple

PROHIBITED = "PROHIBITED"
UNUNDERSTOOD = "UNUNDERSTOOD"
LEVELS = ("A", "B", "C", UNUNDERSTOOD, "D", PROHIBITED)

_PROHIBITED_RE = re.compile(
    r"(?i)(\bformat\b|\bdiskpart\b|\bbcdedit\b|\breg(\.exe)?\s+delete\b|"
    r"\bset-executionpolicy\b|\brunas\b|\bstart-process\b.*\brunas\b|"
    r"\binvoke-expression\b|\biex\b|"
    r"\bset-mppreference\b|\bnetsh\b.*\badvfirewall\b|"
    r"irm\s*\|\s*iex|invoke-webrequest\s*\|\s*iex)"
)
# -EncodedCommand, concatenación de cadenas, sustitución e iex partido con `.
_OBFUSCATED_RE = re.compile(
    r"(?i)(-encodedcommand|`|\$\(|\$\{|\+[\"']|[\"']\s*\+)"
)

# Componentes de ruta que un comando de lectura no puede tratar como A.
# Credenciales, perfiles de navegador y claves. AppData cubre el perfil de
# Chrome en Windows; el resto son los nombres en otros sistemas.
_PROTECTED_PATH_PARTS = frozenset({
    ".ssh", ".aws", ".gnupg", "appdata",
    ".mozilla", ".chrome", ".chromium", "google-chrome",
    "user data",
    "credentials", "cookies", ".netrc",
    "id_rsa", "id_ed25519", "id_ecdsa",
})


def _tokens(command: str) -> Optional[List[str]]:
    text = (command or "").strip()
    if not text:
        return None
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return None


_RANK = {"A": 0, "B": 1, "C": 2, UNUNDERSTOOD: 3, "D": 4, PROHIBITED: 5}
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


def _path_parts(token: str) -> List[str]:
    text = token.replace("\\", "/").strip("\"'")
    if text.startswith("~/"):
        text = text[2:]
    parts = []
    for part in text.split("/"):
        name = part.strip().casefold().rstrip(" .")
        if name and name not in (".", ".."):
            parts.append(name)
    return parts


def _protected_part(part: str) -> bool:
    if part in _PROTECTED_PATH_PARTS:
        return True
    return part.startswith(("id_rsa", "id_ed25519", "id_ecdsa"))


def _args_name_protected(args: Sequence[str]) -> bool:
    for token in args:
        if any(_protected_part(part) for part in _path_parts(token)):
            return True
    return False


def _as_read(tokens: Sequence[str], why: str) -> Tuple[str, str]:
    """Una lectura cuyo argumento nombra una ruta protegida deja de ser A."""
    if _args_name_protected(tokens[1:]):
        return "D", "PROTECTED_PATH"
    return "A", why


def _has_requirement_file(tail: Sequence[str]) -> bool:
    for index, token in enumerate(tail):
        if token in ("-r", "--requirement") and index + 1 < len(tail):
            return True
        if token.startswith("--requirement="):
            return True
    return False


def _global_install(tail: Sequence[str]) -> bool:
    return any(flag in tail for flag in ("-g", "--global", "--user", "--prefix"))


def _pip_args(head: str, tail: Sequence[str]) -> Optional[Sequence[str]]:
    if head in ("pip", "pip3"):
        return tail
    if head in ("python", "python3") and list(tail[:2]) == ["-m", "pip"]:
        return tail[2:]
    return None


def _named_requirement(tail: Sequence[str]) -> Optional[str]:
    for index, token in enumerate(tail):
        if token in ("-r", "--requirement") and index + 1 < len(tail):
            return tail[index + 1]
        if token.startswith("--requirement="):
            return token.split("=", 1)[1]
    return None


def _pinned_files(head: str, tail: Sequence[str]) -> Optional[List[str]]:
    """Archivos que la forma canónica da por fijados. None si no es un install con hashes."""
    pip_args = _pip_args(head, tail)
    if pip_args is not None:
        if not pip_args or pip_args[0] != "install":
            return None
        if "--require-hashes" in pip_args and _has_requirement_file(pip_args):
            named = _named_requirement(pip_args)
            return [named] if named else []
        return None
    if head == "npm" and tail[:1] == ["ci"]:
        return ["package-lock.json"]
    if head == "pnpm" and tail[:1] == ["install"] and "--frozen-lockfile" in tail:
        return ["pnpm-lock.yaml"]
    if head == "yarn" and tail[:1] == ["install"] and "--frozen-lockfile" in tail:
        return ["yarn.lock"]
    return None


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _reviewed_install_files() -> set:
    path = os.path.join(_repo_root(), "config", "avatar", "reviewed_install_files.yaml")
    try:
        from core.avatar_config import parse_simple_yaml
        with open(path, "r", encoding="utf-8") as handle:
            parsed = parse_simple_yaml(handle.read()) or {}
    except (OSError, ValueError):
        return set()
    files = parsed.get("files") if isinstance(parsed, dict) else None
    if not isinstance(files, list):
        return set()
    return {str(item).replace("\\", "/").lstrip("./") for item in files}


def _git_unchanged(relative: str) -> bool:
    """Verdadero solo si git tiene el archivo y el trabajo coincide con HEAD."""
    import subprocess
    root = _repo_root()
    relative = relative.replace("\\", "/").lstrip("./")
    listed = subprocess.run(
        ["git", "-C", root, "ls-files", "--error-unmatch", "--", relative],
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        return False
    diff = subprocess.run(
        ["git", "-C", root, "diff", "--quiet", "HEAD", "--", relative],
        capture_output=True,
        check=False,
    )
    return diff.returncode == 0


def _reviewed_and_clean(paths: Sequence[str]) -> bool:
    if not paths:
        return False
    reviewed = _reviewed_install_files()
    for path in paths:
        relative = str(path).replace("\\", "/").lstrip("./")
        if relative not in reviewed or not _git_unchanged(relative):
            return False
    return True


def _install_from_pinned_file(head: str, tail: Sequence[str]) -> Optional[Tuple[str, str]]:
    """B solo si el archivo está revisado y no cambió respecto a git. Si no, C."""
    pip_args = _pip_args(head, tail)
    if pip_args is not None:
        if not pip_args or pip_args[0] != "install":
            return None
        if _global_install(pip_args):
            return "C", "GLOBAL_INSTALL"
        if "--require-hashes" in pip_args and _has_requirement_file(pip_args):
            if _reviewed_and_clean(_pinned_files(head, tail) or []):
                return "B", "INSTALL_PINNED_FILE"
            return "C", "INSTALL_UNREVIEWED"
        return "C", "INSTALL_UNPINNED"
    pinned = _pinned_files(head, tail)
    if pinned is not None:
        if _reviewed_and_clean(pinned):
            return "B", "INSTALL_PINNED_FILE"
        return "C", "INSTALL_UNREVIEWED"
    if head in ("npm", "pnpm", "yarn") and tail[:1] == ["install"]:
        return "C", "INSTALL_UNPINNED"
    return None


def classify_command(command: str, _depth: int = 0) -> Tuple[str, str]:
    """Devuelve (nivel, motivo). Lo no entendido no es C."""
    level, why = _classify_surface(command)
    if _depth < 2:
        inner = _inner_command(_tokens(command or ""))
        if inner and inner.strip() and inner.strip() != (command or "").strip():
            level, why = _stricter((level, why), classify_command(inner, _depth + 1))
    return level, why


def _classify_surface(command: str) -> Tuple[str, str]:
    raw = command or ""
    if not raw.strip():
        return UNUNDERSTOOD, "EMPTY_COMMAND"
    if _PROHIBITED_RE.search(raw):
        return PROHIBITED, "PROHIBITED_COMMAND"
    if _OBFUSCATED_RE.search(raw):
        return PROHIBITED, "OBFUSCATED"
    if ">" in raw:
        return UNUNDERSTOOD, "REDIRECT"
    if any(tok in raw for tok in (";", "|", "&", "\n")):
        return UNUNDERSTOOD, "COMPOSITION"
    tokens = _tokens(raw)
    if tokens is None:
        return UNUNDERSTOOD, "UNPARSEABLE"
    head = tokens[0].lower()
    tail = [t.lower() for t in tokens[1:]]
    joined = " ".join(tokens).lower()

    if head in ("format", "diskpart", "bcdedit"):
        return PROHIBITED, "PROHIBITED_COMMAND"
    if head in _WRAPPERS:
        return "C", "WRAPPER"
    if head == "git":
        if not tail:
            return UNUNDERSTOOD, "GIT_BARE"
        sub = tail[0]
        if sub == "diff" and any(token.startswith("--output") for token in tail):
            return "C", "GIT_DIFF_OUTPUT"
        if sub in ("status", "diff", "log", "show"):
            return _as_read(tokens, "GIT_READ")
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
        return UNUNDERSTOOD, "GIT_OTHER"
    pinned = _install_from_pinned_file(head, tail)
    if pinned is not None:
        return pinned
    if joined in ("pytest", "npm test") or joined.startswith("python -m pytest") or joined.startswith("python3 -m pytest"):
        return _as_read(tokens, "TEST_COMMAND")
    if "env:" in joined:
        return "C", "ENV_READ"
    if head in ("ls", "dir", "pwd", "whoami", "cat", "type"):
        return _as_read(tokens, "READ_DIAGNOSTIC")
    if head in ("get-childitem", "get-content", "get-location"):
        return _as_read(tokens, "READ_DIAGNOSTIC")
    if head in ("rm", "del", "erase", "remove-item", "rmdir"):
        return "D", "DELETE_COMMAND"
    if head in ("shutdown", "restart-computer", "stop-computer"):
        return "D", "POWER_COMMAND"
    if head in ("sc", "net") and any(word in tail for word in ("start", "stop", "delete")):
        return "C", "SERVICE_COMMAND"
    if head in ("out-file", "set-content", "tee", "tee-object"):
        return UNUNDERSTOOD, "OUTPUT_SINK"
    if head in ("curl", "wget", "irm", "invoke-webrequest"):
        return "C", "DOWNLOAD"
    # Imprime. No lee una ruta. La redirección `>` no se ve aquí: es un hueco
    # del análisis estructural, anotado en el ADR, no un parser nuevo.
    if head == "echo":
        return "C", "ECHO"
    return UNUNDERSTOOD, "UNCLASSIFIED_DEFAULT_C"


def grant_allows(level: str, grant: Optional[dict], *, reason: str = "") -> bool:
    """Un grant nulo no autoriza nada. Lo no entendido no lo cubre allow_level_c."""
    if not grant or level in (PROHIBITED, "D", UNUNDERSTOOD):
        return False
    if reason in ("COMPOSITION", "UNPARSEABLE", "EMPTY_COMMAND", "UNCLASSIFIED_DEFAULT_C", "GIT_BARE", "GIT_OTHER"):
        return False
    allowed = set(grant.get("levels") or [])
    if level == "C":
        return "C" in allowed and bool(grant.get("allow_level_c"))
    return level in allowed
