"""In-process Telegram getUpdates listener (singleton per process)."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_bridge = None


def ensure_telegram_daemon(orchestrator=None) -> Dict[str, Any]:
    """
    Start the Telegram polling thread once for this process.

    Safe to call from FastAPI startup and from main_gui (idempotent).
    """
    global _thread, _bridge
    with _lock:
        if _thread is not None and _thread.is_alive():
            return status()

        from bridges.telegram_bridge import TelegramBridge
        _bridge = TelegramBridge(orchestrator=orchestrator)
        if not _bridge.bot_token:
            return {
                "status": "NO_TOKEN",
                "running": False,
                "message": "telegram.bot_token no configurado en config.json",
            }

        def _run():
            try:
                print("[AVATAR Telegram]: Bot daemon activo y escuchando en segundo plano.")
                _bridge.start_polling()
            except Exception as e:
                print(f"[AVATAR Telegram Daemon Error]: {e}")

        _thread = threading.Thread(target=_run, name="avatar-telegram-daemon", daemon=True)
        _thread.start()
        return status()


def status() -> Dict[str, Any]:
    running = bool(_thread is not None and _thread.is_alive())
    info: Dict[str, Any] = {
        "status": "RUNNING" if running else "STOPPED",
        "running": running,
    }
    if _bridge is None:
        info["token_configured"] = False
        info["allowed_chat_ids"] = []
        return info
    info["token_configured"] = bool(_bridge.bot_token)
    info["allowed_chat_ids"] = sorted(_bridge.allowed_chat_ids)
    info["auto_enroll_first_private"] = bool(_bridge.auto_enroll_first_private)
    try:
        me = _bridge.api_get_me()
        info["bot"] = me
    except Exception as e:
        info["bot"] = {"ok": False, "error": str(e)[:120]}
    return info
