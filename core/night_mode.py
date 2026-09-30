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
