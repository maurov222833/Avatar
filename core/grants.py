"""Registro de autorización de una misión (spec 003, U3).

El modelo no escribe este archivo: path_guard lo trata como componente de
seguridad cuando vive bajo el árbol del paquete. Las pruebas usan un directorio
temporal fuera de ese árbol.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


def grant_path(root: Optional[str] = None) -> str:
    base = root or os.environ.get("AVATAR_GRANT_ROOT") or os.path.join(os.getcwd(), "memory")
    return os.path.join(base, "mission_grants.json")


def _load(root: Optional[str]) -> Dict[str, Any]:
    path = grant_path(root)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(root: Optional[str], data: Dict[str, Any]) -> None:
    path = grant_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def put_grant(mission_id: str, grant: Dict[str, Any], root: Optional[str] = None) -> Dict[str, Any]:
    record = {
        "mission_id": mission_id,
        "objective": grant.get("objective") or "",
        "workspace": grant.get("workspace") or "",
        "levels": list(grant.get("levels") or ["A", "B"]),
        "allow_level_c": bool(grant.get("allow_level_c", False)),
        "expires_at": grant.get("expires_at"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    data = _load(root)
    data[mission_id] = record
    _save(root, data)
    return record


def get_grant(mission_id: str, root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    record = _load(root).get(mission_id)
    if not record:
        return None
    expires = record.get("expires_at")
    if expires and str(expires) < time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()):
        return None
    return record
