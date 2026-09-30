"""Contención por contadores (spec 003, U4).

Los umbrales viven en el código. Una misión no los recibe como argumento.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

SAME_ACTION_LIMIT = 5
WINDOW_SWITCH_LIMIT = 20


class ContainmentMonitor:
    def __init__(self) -> None:
        self._recent: Deque[str] = deque(maxlen=SAME_ACTION_LIMIT)
        self._window_switches = 0
        self._tripped = False

    def observe(
        self,
        act_type: str,
        args: Optional[Dict[str, Any]] = None,
        *,
        mission_status: str = "ACTIVE",
        window_switched: bool = False,
    ) -> Optional[str]:
        if self._tripped:
            return "CONTAINMENT_ALREADY_ACTIVE"
        if mission_status in ("CANCELLED", "COMPLETED", "PAUSED"):
            self._tripped = True
            return "CONTAINMENT_MISSION_INACTIVE"
        signature = act_type + "|" + repr(sorted((args or {}).items()))
        self._recent.append(signature)
        if len(self._recent) == SAME_ACTION_LIMIT and len(set(self._recent)) == 1:
            self._tripped = True
            return "CONTAINMENT_REPEATED_ACTION"
        if window_switched:
            self._window_switches += 1
            if self._window_switches > WINDOW_SWITCH_LIMIT:
                self._tripped = True
                return "CONTAINMENT_WINDOW_THRASH"
        return None

    def thresholds(self) -> Tuple[int, int]:
        return SAME_ACTION_LIMIT, WINDOW_SWITCH_LIMIT
