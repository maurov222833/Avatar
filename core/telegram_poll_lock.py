"""Exclusive lock so only one Avatar process polls Telegram getUpdates."""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

from core.paths import avatar_home, memory_dir


class TelegramPollLock:
    """
    Cross-process lock for the Telegram getUpdates consumer.

    Two Avatar windows both calling getUpdates cause HTTP 409 and the bot
    looks "disconnected". Whoever holds this lock is the only allowed poller.
    """

    def __init__(self, path: Optional[str] = None):
        base = memory_dir()
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            base = avatar_home()
            os.makedirs(base, exist_ok=True)
        self.path = path or os.path.join(base, "telegram_poll.lock")
        self._fh = None

    @property
    def held(self) -> bool:
        return self._fh is not None

    def acquire(self, blocking: bool = False, timeout_s: float = 0.0) -> bool:
        if self._fh is not None:
            return True
        deadline = time.time() + max(0.0, timeout_s)
        while True:
            try:
                fh = open(self.path, "a+", encoding="utf-8")
                if sys.platform == "win32":
                    import msvcrt

                    try:
                        # Lock one byte near the start of the file.
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError:
                        fh.close()
                        raise
                else:
                    import fcntl

                    flags = fcntl.LOCK_EX
                    if not blocking and timeout_s <= 0:
                        flags |= fcntl.LOCK_NB
                    fcntl.flock(fh.fileno(), flags)
                fh.seek(0)
                fh.truncate()
                fh.write(f"pid={os.getpid()} ts={time.time():.0f}\n")
                fh.flush()
                self._fh = fh
                return True
            except (OSError, BlockingIOError):
                if self._fh:
                    try:
                        self._fh.close()
                    except Exception:
                        pass
                    self._fh = None
                if blocking and time.time() < deadline:
                    time.sleep(0.5)
                    continue
                if blocking and timeout_s > 0 and time.time() >= deadline:
                    return False
                return False

    def release(self) -> None:
        fh = self._fh
        self._fh = None
        if not fh:
            return
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            fh.close()
        except Exception:
            pass
