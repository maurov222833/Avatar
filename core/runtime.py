"""Process-wide Avatar runtime: one orchestrator, serialized user turns.

F-16: the GUI used to build a fresh AvatarOrchestrator in the HTTP server, the
Telegram bridge, and the WhatsApp bridge. Each kept its own in-memory history on
top of the same SQLite file, so concurrent turns raced and last-writer semantics
could drop context. Callers in this process take the shared instance instead.
"""
from __future__ import annotations

import threading
from typing import Optional

from core.orchestrator import AvatarOrchestrator

_lock = threading.Lock()
_shared: Optional[AvatarOrchestrator] = None


def get_shared_orchestrator() -> AvatarOrchestrator:
    """Return the single orchestrator for this process, creating it on first use."""
    global _shared
    with _lock:
        if _shared is None:
            _shared = AvatarOrchestrator()
        return _shared


def reset_shared_orchestrator() -> None:
    """Drop the shared instance. Tests only; production paths must not call this."""
    global _shared
    with _lock:
        _shared = None
