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
        info["hint"] = (
            "Daemon no arrancado. Reinicia Avatar o POST /api/telegram/start. "
            "Si usas código viejo, actualiza la rama cursor/u1-contencion-5763."
        )
        return info
    info["token_configured"] = bool(_bridge.bot_token)
    info["allowed_chat_ids"] = sorted(_bridge.allowed_chat_ids)
    info["auto_enroll_first_private"] = bool(_bridge.auto_enroll_first_private)
    info["last_inbound_at"] = getattr(_bridge, "last_inbound_at", None)
    info["last_outbound_at"] = getattr(_bridge, "last_outbound_at", None)
    info["last_poll_at"] = getattr(_bridge, "last_poll_at", None)
    info["last_error"] = getattr(_bridge, "last_error", "") or ""
    info["poll_conflicts_409"] = int(getattr(_bridge, "poll_conflicts_409", 0) or 0)
    try:
        me = _bridge.api_get_me()
        info["bot"] = me
    except Exception as e:
        info["bot"] = {"ok": False, "error": str(e)[:120]}
    try:
        wh = _bridge.api_webhook_info()
        info["webhook"] = wh
        if info["poll_conflicts_409"] > 0:
            info["hint"] = (
                f"Hubo {info['poll_conflicts_409']} conflicto(s) 409: cierra TODAS las "
                "ventanas/procesos de Avatar y deja solo uno."
            )
        elif wh.get("ok") and wh.get("url"):
            info["hint"] = (
                "Hay un webhook activo: getUpdates no recibe chats. "
                "Reinicia Avatar (borra el webhook al arrancar) o dile TELEGRAM_STATUS."
            )
        elif not running:
            info["hint"] = "Token OK pero el listener no corre. POST /api/telegram/start o reinicia."
        elif not info["allowed_chat_ids"]:
            info["hint"] = (
                "Listener activo, allowlist vacía: escribe /start al bot en privado "
                f"(@{(info.get('bot') or {}).get('username') or 'tu_bot'}) para auto-enrolarte."
            )
        elif info["last_error"]:
            info["hint"] = f"Listener activo pero último error: {info['last_error']}"
        else:
            info["hint"] = "Listener activo. Escribe al bot en privado."
    except Exception as e:
        info["webhook"] = {"ok": False, "error": str(e)[:120]}
    return info
