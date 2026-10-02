"""Exclusive lock so only one Avatar process polls Telegram getUpdates."""
from __future__ import annotations

import atexit
import os
import re
import sys
import time
from typing import Optional, Tuple

from core.paths import avatar_home, memory_dir


def _pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            # PROCESS_QUERY_LIMITED_INFORMATION
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, 0, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class TelegramPollLock:
    """
    Cross-process lock for the Telegram getUpdates consumer.

    Two Avatar windows both calling getUpdates cause HTTP 409 and the bot
    looks "disconnected". Whoever holds this lock is the only allowed poller.

    Windows note: msvcrt.locking fails on an empty file (needs >= nbytes). We
    always pad the file before locking, and we steal the lock if the holder PID
    is dead — otherwise a crash left Avatar stuck in STANDBY forever.
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
        self.mode = "none"  # os_lock | pid_file
        self.last_reject_reason = ""
        self._exit_registered = False

    @property
    def held(self) -> bool:
        return self._fh is not None

    def read_holder(self) -> Tuple[Optional[int], Optional[float]]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                text = f.read(200)
        except Exception:
            return None, None
        m = re.search(r"pid=(\d+)", text or "")
        t = re.search(r"ts=(\d+(?:\.\d+)?)", text or "")
        pid = int(m.group(1)) if m else None
        ts = float(t.group(1)) if t else None
        return pid, ts

    def _ensure_padded(self, fh) -> None:
        """msvcrt.locking requires the file to contain at least `nbytes` bytes."""
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        if size < 64:
            fh.write("\0" * (64 - size))
            fh.flush()
        fh.seek(0)

    def _write_identity(self, fh) -> None:
        fh.seek(0)
        fh.truncate()
        fh.write(f"pid={os.getpid()} ts={time.time():.0f}\n")
        fh.write("# avatar telegram poll lock\n")
        fh.flush()
        # Keep enough bytes for future msvcrt locks.
        if fh.tell() < 64:
            fh.write("\0" * (64 - fh.tell()))
            fh.flush()

    def acquire(self, blocking: bool = False, timeout_s: float = 0.0) -> bool:
        if self._fh is not None:
            return True
        deadline = time.time() + max(0.0, timeout_s)
        while True:
            # Steal if previous holder is a dead process (common after Task Manager kill).
            holder_pid, _ = self.read_holder()
            if holder_pid and holder_pid != os.getpid() and not _pid_alive(holder_pid):
                try:
                    os.remove(self.path)
                except Exception:
                    pass
                self.last_reject_reason = f"stale_pid_{holder_pid}_removed"
            elif holder_pid and holder_pid != os.getpid() and _pid_alive(holder_pid):
                self.last_reject_reason = f"held_by_live_pid_{holder_pid}"
                if not blocking:
                    return False

            try:
                fh = open(self.path, "a+", encoding="utf-8")
                self._ensure_padded(fh)
                if sys.platform == "win32":
                    import msvcrt

                    try:
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError:
                        fh.close()
                        # Fall back to PID-file ownership if OS lock cannot be taken
                        # but holder is dead/absent.
                        return self._acquire_pid_file_fallback()
                else:
                    import fcntl

                    flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if not blocking else 0)
                    fcntl.flock(fh.fileno(), flags)

                self._write_identity(fh)
                self._fh = fh
                self.mode = "os_lock"
                self.last_reject_reason = ""
                return True
            except (OSError, BlockingIOError):
                try:
                    fh.close()
                except Exception:
                    pass
                if blocking and time.time() < deadline:
                    time.sleep(0.5)
                    continue
                # Last resort: PID file if OS lock contended by dead/weird state.
                if self._acquire_pid_file_fallback():
                    return True
                if not self.last_reject_reason:
                    self.last_reject_reason = "os_lock_busy"
                return False

    def _acquire_pid_file_fallback(self) -> bool:
        """Advisory PID lock when msvcrt/fcntl cannot be used cleanly."""
        holder_pid, _ = self.read_holder()
        if holder_pid and holder_pid == os.getpid():
            # Another TelegramPollLock in THIS process already owns the file, or
            # we just released but OS lock should be free — do not double-take.
            self.last_reject_reason = "held_by_same_process"
            return False
        if holder_pid and holder_pid != os.getpid() and _pid_alive(holder_pid):
            self.last_reject_reason = f"held_by_live_pid_{holder_pid}"
            return False
        fh = None
        try:
            fh = open(self.path, "w+", encoding="utf-8")
            self._write_identity(fh)
            self._fh = fh
            self.mode = "pid_file"
            self.last_reject_reason = ""
            self._register_exit()
            fh = None
            return True
        except Exception as e:
            if fh is not None and not fh.closed:
                try:
                    fh.close()
                except Exception:
                    pass
            self.last_reject_reason = f"pid_fallback_failed:{e}"[:120]
            return False

    def _register_exit(self) -> None:
        if self._exit_registered:
            return
        self._exit_registered = True
        atexit.register(self.release)

    def force_acquire(self) -> bool:
        """Break stale lock and take ownership (used by supervisor recovery)."""
        self.release()
        holder_pid, _ = self.read_holder()
        if holder_pid and _pid_alive(holder_pid) and holder_pid != os.getpid():
            self.last_reject_reason = f"held_by_live_pid_{holder_pid}"
            return False
        try:
            os.remove(self.path)
        except Exception:
            pass
        return self.acquire(blocking=False)

    def release(self) -> None:
        fh = self._fh
        self._fh = None
        mode = self.mode
        self.mode = "none"
        if not fh:
            return
        try:
            if mode == "os_lock" and sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            elif mode == "os_lock":
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            fh.close()
        except Exception:
            pass
