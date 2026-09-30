"""Canal remoto: repetición, antigüedad e idempotencia (spec 003, U9).

No sustituye la allowlist de Telegram. Se suma a ella.
"""
from __future__ import annotations

import time
from typing import Dict, Optional, Set, Tuple

MAX_AGE_SECONDS = 600


class RemoteInbox:
    def __init__(self) -> None:
        self._seen: Set[Tuple[str, str, str]] = set()

    def accept(
        self,
        sender: str,
        message_id: str,
        text: str,
        *,
        authorized: bool,
        sent_at: Optional[float] = None,
        now: Optional[float] = None,
    ) -> Tuple[bool, str]:
        if not authorized:
            return False, "SENDER_NOT_AUTHORIZED"
        if sent_at is not None:
            current = now if now is not None else time.time()
            if current - sent_at > MAX_AGE_SECONDS:
                return False, "STALE_MESSAGE"
        if message_id:
            key = (str(sender), str(message_id), text)
            if key in self._seen:
                return False, "DUPLICATE_MESSAGE"
            self._seen.add(key)
        return True, "ACCEPTED"
