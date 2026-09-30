"""R4 — usage ledger for LLM providers (calls, errors, soft ceilings)."""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from core.paths import memory_dir

_LOCK = threading.Lock()


class ProviderUsageLedger:
    """Append-only JSONL of provider attempts + in-memory rolling counters."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(memory_dir(), "provider_usage.jsonl")
        self._events: List[Dict[str, Any]] = []

    def record(
        self,
        provider: str,
        *,
        outcome: str,
        reason: str = "",
        latency_ms: float = 0.0,
    ) -> None:
        event = {
            "ts": time.time(),
            "provider": (provider or "").lower().strip() or "unknown",
            "outcome": outcome,  # attempt | success | error | denied_budget
            "reason": (reason or "")[:240],
            "latency_ms": float(latency_ms or 0.0),
        }
        with _LOCK:
            self._events.append(event)
            try:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def calls_since(self, seconds: float) -> int:
        """Count billed attempts in the window (one per generate call start)."""
        cutoff = time.time() - max(0.0, seconds)
        with _LOCK:
            return sum(
                1
                for e in self._events
                if e.get("ts", 0) >= cutoff and e.get("outcome") == "attempt"
            )

    def summary(self, window_seconds: float = 3600.0) -> Dict[str, Any]:
        cutoff = time.time() - max(0.0, window_seconds)
        by_provider: Dict[str, Dict[str, int]] = {}
        with _LOCK:
            events = [e for e in self._events if e.get("ts", 0) >= cutoff]
        for e in events:
            p = e.get("provider") or "unknown"
            bucket = by_provider.setdefault(p, {"attempts": 0, "success": 0, "error": 0, "denied_budget": 0})
            outcome = e.get("outcome") or "attempt"
            if outcome == "success":
                bucket["success"] += 1
                bucket["attempts"] += 1
            elif outcome == "error":
                bucket["error"] += 1
                bucket["attempts"] += 1
            elif outcome == "denied_budget":
                bucket["denied_budget"] += 1
            else:
                bucket["attempts"] += 1
        return {
            "window_seconds": window_seconds,
            "total_attempts": sum(b["attempts"] for b in by_provider.values()),
            "by_provider": by_provider,
        }


_DEFAULT: Optional[ProviderUsageLedger] = None


def get_usage_ledger() -> ProviderUsageLedger:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ProviderUsageLedger()
    return _DEFAULT


def reset_usage_ledger_for_tests(path: Optional[str] = None) -> ProviderUsageLedger:
    global _DEFAULT
    _DEFAULT = ProviderUsageLedger(path=path)
    return _DEFAULT
