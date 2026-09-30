"""Resolución y autorización de rutas (spec 003, U2).

La comparación usa la ruta canónica, no la cadena recibida. Ante duda, niega.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Optional, Sequence, Tuple

ALLOW = "ALLOW"
DENY = "DENY"
NEEDS_APPROVAL = "NEEDS_APPROVAL"

_RESERVED = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}
_SHORT = re.compile(r"^[a-z0-9]{1,6}~\d$", re.IGNORECASE)
_MASS_LIMIT = 10_000

_CRITICAL_SEGMENTS = (
    ("windows", "system32"),
    ("windows", "syswow64"),
    ("windows", "winsxs"),
    ("windows", "boot"),
    ("windows", "system volume information"),
    ("$recycle.bin",),
    ("recovery",),
    ("program files",),
    ("program files (x86)",),
    ("programdata",),
)

_PROFILE_DIRS = {
    "documents", "documentos", "pictures", "imágenes", "imagenes",
    "videos", "desktop", "escritorio", "downloads", "descargas", "onedrive",
}

_SECRET_PARTS = {".ssh", ".aws", ".gnupg", "appdata"}

_PROTECTED_REL = (
    "core/act_chokepoint.py",
    "core/halt.py",
    "core/path_guard.py",
    "core/command_risk.py",
    "core/containment.py",
    "core/grants.py",
)

_BACKUP_ROOTS: list = []


def register_backup_root(path: str) -> None:
    if path and path not in _BACKUP_ROOTS:
        _BACKUP_ROOTS.append(os.path.abspath(path))


def package_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _protected_files() -> set:
    root = package_root()
    return {os.path.normcase(os.path.abspath(os.path.join(root, rel))) for rel in _PROTECTED_REL}


def _parts(path: str) -> list:
    text = path.replace("\\", "/")
    if text.startswith("//?/") or text.lower().startswith("//?/"):
        text = text[4:]
    if text.lower().startswith("//./"):
        text = text[4:]
    parts = []
    for part in text.split("/"):
        if part.endswith(":"):
            parts.append(part)
            continue
        # Flujo NTFS: nombre:stream
        part = part.split(":", 1)[0]
        parts.append(part.rstrip(" .").casefold())
    return [p for p in parts if p not in ("", ".")]


def _has_ads(raw: str) -> bool:
    text = raw.replace("\\", "/")
    # Letra de unidad C: no es un flujo.
    if len(text) >= 2 and text[1] == ":":
        text = text[2:]
    return ":" in text


def _looks_windows_absolute(raw: str) -> bool:
    text = raw.strip().replace("/", "\\")
    if text.startswith("\\\\?\\") or text.startswith("\\\\.\\") or text.startswith("\\\\"):
        return True
    return len(text) >= 2 and text[1] == ":" and text[0].isalpha()


def _contains_critical(parts: Sequence[str]) -> Optional[str]:
    folded = tuple(parts)
    for needle in _CRITICAL_SEGMENTS:
        n = len(needle)
        for i in range(0, len(folded) - n + 1):
            if folded[i:i + n] == needle:
                return "/".join(needle)
    return None


def _within(target: str, root: str) -> bool:
    try:
        t = os.path.normcase(os.path.abspath(target))
        r = os.path.normcase(os.path.abspath(root))
        return os.path.commonpath([t, r]) == r
    except ValueError:
        return False


def authorize_path(
    path: str,
    operation: str,
    mission_scope: Optional[str] = None,
    *,
    extra_allow: Iterable[str] = (),
    affected_count: int = 1,
) -> Tuple[str, str]:
    """Allow, Deny(reason) o NeedsApproval(reason)."""
    raw = str(path or "").strip()
    if not raw or "\x00" in raw:
        return DENY, "PATH_EMPTY_OR_AMBIGUOUS"
    if _has_ads(raw):
        return DENY, "PATH_ALTERNATE_DATA_STREAM"
    parts = _parts(raw)
    if not parts:
        return DENY, "PATH_EMPTY_OR_AMBIGUOUS"
    leaf = parts[-1]
    if leaf in _RESERVED:
        return DENY, "PATH_RESERVED_DEVICE"
    if any(_SHORT.match(part) for part in parts if not part.endswith(":")):
        return DENY, "PATH_SHORT_NAME_8_3"
    critical = _contains_critical(parts)
    if critical:
        return DENY, f"PATH_DENYLIST:{critical}"
    if _looks_windows_absolute(raw):
        # Raíz de unidad: "C:" o "C:\" únicamente.
        body = raw.replace("/", "\\").rstrip("\\")
        if len(body) == 2 and body[1] == ":":
            return DENY, "PATH_DRIVE_ROOT"
    if any(part in _SECRET_PARTS for part in parts) and operation in ("read", "write", "delete"):
        return DENY, "PATH_SECRET_STORE"
    if any(part in _PROFILE_DIRS for part in parts):
        allowed_extra = [os.path.abspath(p) for p in extra_allow]
        lexical = os.path.abspath(raw) if not _looks_windows_absolute(raw) else raw
        if not any(str(lexical).casefold().startswith(p.casefold()) for p in allowed_extra):
            if operation != "read":
                return DENY, "PATH_PROFILE_NOT_IN_MISSION"

    if _looks_windows_absolute(raw) and os.name != "nt":
        # No se puede canonicalizar en este sistema. La denylist léxica ya pasó.
        if operation in ("write", "delete"):
            return DENY, "PATH_WINDOWS_UNRESOLVED"
        return DENY, "PATH_WINDOWS_UNRESOLVED"

    try:
        resolved = os.path.realpath(raw)
    except (OSError, ValueError):
        return DENY, "PATH_CANNOT_RESOLVE"

    protected = _protected_files()
    if os.path.normcase(resolved) in protected or os.path.normcase(os.path.abspath(raw)) in protected:
        return DENY, "PATH_SECURITY_COMPONENT"

    for root in _BACKUP_ROOTS:
        if _within(resolved, root) and operation in ("write", "delete"):
            return DENY, "PATH_BACKUP_IMMUTABLE"

    if mission_scope and operation in ("write", "delete"):
        scope = os.path.realpath(mission_scope)
        extras = [os.path.realpath(p) for p in extra_allow if p]
        if not _within(resolved, scope) and not any(_within(resolved, extra) for extra in extras):
            return DENY, "PATH_OUTSIDE_MISSION_SCOPE"
        # Enlace que sale del alcance: realpath ya está fuera.
        if os.path.islink(raw) and not _within(resolved, scope):
            return DENY, "PATH_SYMLINK_ESCAPE"

    if affected_count > _MASS_LIMIT:
        return NEEDS_APPROVAL, "PATH_MASS_OPERATION"

    return ALLOW, "PATH_ALLOWED"


def safe_delete(path: str, mission_id: str, mission_scope: str) -> Tuple[str, str]:
    """Mueve a la papelera de la misión. El borrado permanente no existe aquí."""
    decision, reason = authorize_path(path, "delete", mission_scope)
    if decision != ALLOW:
        return decision, reason
    trash = os.path.join(mission_scope, ".avatar_trash", mission_id or "mission")
    os.makedirs(trash, exist_ok=True)
    base = os.path.basename(os.path.realpath(path))
    dest = os.path.join(trash, base)
    manifest = os.path.join(trash, "manifest.txt")
    os.replace(path, dest)
    with open(manifest, "a", encoding="utf-8") as handle:
        handle.write(f"{path}\t{dest}\n")
    return ALLOW, dest
