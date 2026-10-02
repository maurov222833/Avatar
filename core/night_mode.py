"""Modo noche (spec 003, U13).

De noche solo entran actos A y B dentro del sobre. El resto queda en cola.
"""
from __future__ import annotations

from typing import Any, Dict, List


class NightEnvelope:
    def __init__(self, *, allowed_levels: tuple = ("A", "B"), daily_spend_cap: float = 0.0) -> None:
        self.allowed_levels = set(allowed_levels)
        self.daily_spend_cap = daily_spend_cap
        self.spent = 0.0
        self.queue: List[Dict[str, Any]] = []
        self.done: List[Dict[str, Any]] = []
        self.saved = False

    def admit(self, action: Dict[str, Any]) -> str:
        level = action.get("level")
        cost = float(action.get("cost") or 0)
        if self.spent + cost > self.daily_spend_cap:
            self.saved = True
            self.queue.append(action)
            return "BUDGET_SAVED"
        if level not in self.allowed_levels or action.get("visual"):
            self.queue.append(action)
            return "QUEUED"
        self.spent += cost
        self.done.append(action)
        return "DONE"


def heartbeat_ok(last_beat: float, now: float, interval: float) -> bool:
    return (now - last_beat) <= interval


VISUAL_ACTS = frozenset({
    "SCREEN_CAPTURE",
    "DESKTOP_CLICK",
    "DESKTOP_TYPE",
    "DESKTOP_HOTKEY",
    "DESKTOP_OBSERVE",
})

#: Llegan a otra persona o cambian una sesión. De noche no se ejecutan.
_NIGHT_HEAVY = frozenset({
    "SEND_WHATSAPP",
    "WHATSAPP_SEND",
    "TELEGRAM_SEND",
    "BROWSER_NAVIGATE",
    "BROWSER_CLICK",
    "BROWSER_FILL",
    "UPDATE_CONFIG",
})


def queued_at_night(act_type: str, command_level: str = "") -> bool:
    """C, D y lo visual quedan en cola. A y B siguen el resto de la política."""
    if act_type in VISUAL_ACTS or act_type in _NIGHT_HEAVY:
        return True
    if act_type == "COMMAND" and command_level in ("C", "D", "UNUNDERSTOOD"):
        return True
    return False
