"""Parada de emergencia (spec 003, U1).

Un hilo o un archivo pueden activarla sin pasar por el modelo. El chokepoint
la consulta antes de cada efecto. Reanudar exige una llamada explícita.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

LEVELS = ("PAUSE", "STOP", "KILL_SWITCH")
DEFAULT_HOTKEY = "ctrl+alt+shift+x"
_LOCK = threading.Lock()


def state_path() -> str:
    override = os.environ.get("AVATAR_HALT_PATH")
    if override:
        return override
    root = os.environ.get("AVATAR_HOME") or os.getcwd()
    return os.path.join(root, "memory", "halt_state.json")


def _blank() -> Dict[str, Any]:
    return {
        "level": None,
        "source": "",
        "actor": "",
        "at": "",
        "hotkey": DEFAULT_HOTKEY,
        "in_flight_critical": [],
        "audit": [],
    }


def _read() -> Dict[str, Any]:
    path = state_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        # Archivo ausente: no hay parada. Archivo corrupto: fail closed.
        if os.path.exists(path):
            data = _blank()
            data["level"] = "PAUSE"
            data["source"] = "corrupt_state"
            data["actor"] = "halt"
            return data
        return _blank()
    if not isinstance(data, dict):
        blocked = _blank()
        blocked["level"] = "PAUSE"
        blocked["source"] = "corrupt_state"
        return blocked
    data.setdefault("audit", [])
    data.setdefault("in_flight_critical", [])
    data.setdefault("hotkey", DEFAULT_HOTKEY)
    return data


def _write(data: Dict[str, Any]) -> None:
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(tmp, path)


def current_block_reason() -> Optional[str]:
    """None si se puede actuar. Si no, un motivo estable para el ledger."""
    with _LOCK:
        level = _read().get("level")
    if level in LEVELS:
        return f"HALT_{level}"
    return None


def missions_blocked() -> bool:
    return current_block_reason() is not None


def snapshot() -> Dict[str, Any]:
    with _LOCK:
        return _read()


def note_critical(act_id: str) -> None:
    with _LOCK:
        data = _read()
        inflight = list(data.get("in_flight_critical") or [])
        if act_id and act_id not in inflight:
            inflight.append(act_id)
        data["in_flight_critical"] = inflight
        _write(data)


def clear_critical(act_id: str) -> None:
    with _LOCK:
        data = _read()
        data["in_flight_critical"] = [
            item for item in (data.get("in_flight_critical") or []) if item != act_id
        ]
        _write(data)


def _audit(data: Dict[str, Any], event: str, **fields: Any) -> None:
    row = {"event": event, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    row.update(fields)
    audit: List[Dict[str, Any]] = list(data.get("audit") or [])
    audit.append(row)
    data["audit"] = audit[-200:]


def engage(level: str = "PAUSE", source: str = "", actor: str = "") -> Dict[str, Any]:
    """Único camino para activar la parada. Nivel por defecto: PAUSE."""
    if level not in LEVELS:
        level = "PAUSE"
    with _LOCK:
        data = _read()
        # Un nivel superior no baja por un disparo más débil.
        rank = {None: 0, "PAUSE": 1, "STOP": 2, "KILL_SWITCH": 3}
        current = data.get("level")
        if rank.get(current, 0) < rank[level]:
            data["level"] = level
        data["source"] = source or data.get("source") or ""
        data["actor"] = actor or data.get("actor") or ""
        data["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _audit(data, "engage", level=data["level"], source=source, actor=actor,
               in_flight=list(data.get("in_flight_critical") or []))
        _write(data)
        return dict(data)


def resume(actor: str) -> Dict[str, Any]:
    """Solo una acción explícita limpia la parada."""
    if not actor or actor == "model":
        raise PermissionError("RESUME_REQUIRES_EXPLICIT_ACTOR")
    with _LOCK:
        data = _read()
        _audit(data, "resume", actor=actor, previous=data.get("level"))
        data["level"] = None
        data["source"] = ""
        data["at"] = ""
        _write(data)
        return dict(data)


def record_ignored(source: str, actor: str, detail: str) -> None:
    with _LOCK:
        data = _read()
        _audit(data, "ignored", source=source, actor=actor, detail=detail[:300])
        _write(data)


def interpret_control_command(text: str) -> Optional[str]:
    token = (text or "").strip().split()[:1]
    if not token:
        return None
    word = token[0].lower()
    return {"/pause": "PAUSE", "/stop": "STOP", "/kill": "KILL_SWITCH"}.get(word)


def toggle_pause(actor: str, source: str = "telegram") -> str:
    """Primera vez pausa. La segunda, del mismo dueño, quita solo una PAUSA.

    STOP y KILL_SWITCH no se apagan con este gesto.
    """
    if not actor or actor == "model":
        raise PermissionError("RESUME_REQUIRES_EXPLICIT_ACTOR")
    current = snapshot().get("level")
    if current == "PAUSE":
        resume(actor)
        return "RESUMED"
    if current in ("STOP", "KILL_SWITCH"):
        return f"HELD_{current}"
    engage("PAUSE", source=source, actor=actor)
    return "PAUSE"


def apply_control_command(text: str, *, authorized: bool, actor: str, source: str) -> Optional[str]:
    """Devuelve el nivel aplicado, o None si el texto no es una parada.

    Un remitente no autorizado no cambia el estado. Queda en la auditoría.
    """
    level = interpret_control_command(text)
    if level is None:
        return None
    if not authorized:
        record_ignored(source, actor, text)
        return None
    engage(level, source=source, actor=actor)
    return level


def configured_hotkey() -> str:
    return str(snapshot().get("hotkey") or DEFAULT_HOTKEY)


def engage_from_hotkey() -> Dict[str, Any]:
    """Mismo estado que /pause. No depende del orquestador."""
    return engage("PAUSE", source="hotkey", actor="local")


def os_hotkey_hook_available() -> bool:
    """El gancho global de Windows no existe en este proceso Linux."""
    return os.name == "nt"


def poll_trigger_file(path: str) -> Optional[str]:
    """Un proceso aparte escribe PAUSE, STOP o KILL_SWITCH. Un solo uso."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read().strip().upper()
    except OSError:
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    if raw not in LEVELS:
        return None
    engage(raw, source="trigger_file", actor="local")
    return raw
