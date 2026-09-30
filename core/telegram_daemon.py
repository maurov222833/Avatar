"""Durable Telegram getUpdates listener: supervisor + queue + single-poller lock."""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, Optional

from core.telegram_poll_lock import TelegramPollLock

_lock = threading.Lock()
_poll_thread: Optional[threading.Thread] = None
_worker_thread: Optional[threading.Thread] = None
_supervisor_thread: Optional[threading.Thread] = None
_bridge = None
_msg_queue: "queue.Queue[dict]" = queue.Queue()
_stop = threading.Event()
_poll_lock = TelegramPollLock()
_restart_count = 0
_standby_other_instance = False
_last_supervisor_at: Optional[float] = None
_stale_poll_seconds = 90.0
_poll_gen = 0


def _alive(t: Optional[threading.Thread]) -> bool:
    return bool(t is not None and t.is_alive())


def ensure_telegram_daemon(orchestrator=None) -> Dict[str, Any]:
    """
    Start (or keep) the durable Telegram stack:

    - poll thread: getUpdates only (never blocked by LLM)
    - worker thread: handle_message from a queue
    - supervisor: restarts dead/stale threads; waits for poll lock if another
      Avatar instance already owns getUpdates
    """
    global _bridge, _supervisor_thread
    with _lock:
        if orchestrator is not None or _bridge is None:
            from bridges.telegram_bridge import TelegramBridge

            if _bridge is None:
                _bridge = TelegramBridge(orchestrator=orchestrator)
            elif orchestrator is not None and getattr(_bridge, "orchestrator", None) is None:
                _bridge.orchestrator = orchestrator

        if not _bridge.bot_token:
            try:
                _bridge.bot_token = _bridge._load_token_from_config()
                if _bridge.bot_token:
                    _bridge.base_url = f"https://api.telegram.org/bot{_bridge.bot_token}"
            except Exception:
                pass
        if not _bridge.bot_token:
            return {
                "status": "NO_TOKEN",
                "running": False,
                "message": "telegram.bot_token no configurado en config.json",
            }

        _stop.clear()
        _ensure_workers_locked()
        if not _alive(_supervisor_thread):
            _supervisor_thread = threading.Thread(
                target=_supervisor_loop,
                name="avatar-telegram-supervisor",
                daemon=True,
            )
            _supervisor_thread.start()
        return status()


def _ensure_workers_locked() -> None:
    """Start poll+worker if missing. Caller must hold _lock."""
    global _poll_thread, _worker_thread, _restart_count, _standby_other_instance, _poll_gen

    if not _alive(_worker_thread):
        _worker_thread = threading.Thread(
            target=_worker_loop, name="avatar-telegram-worker", daemon=True
        )
        _worker_thread.start()

    if _alive(_poll_thread):
        return

    if not _poll_lock.held:
        got = _poll_lock.acquire(blocking=False)
        if not got:
            # Stale/crash leftover or empty-file Windows lock bug → steal if safe.
            got = _poll_lock.force_acquire()
        if not got:
            _standby_other_instance = True
            print(
                "[AVATAR Telegram]: En espera — otra instancia tiene el candado "
                f"({_poll_lock.last_reject_reason})."
            )
            return

    _standby_other_instance = False
    _restart_count += 1
    my_gen = _poll_gen

    def _should_stop() -> bool:
        return _stop.is_set() or my_gen != _poll_gen

    def _run() -> None:
        print("[AVATAR Telegram]: Poll loop activo (getUpdates desacoplado del LLM).")
        try:
            assert _bridge is not None
            _bridge.start_polling(on_update=_enqueue_update, should_stop=_should_stop)
        except Exception as e:
            print(f"[AVATAR Telegram Poll Error]: {e}")
            if _bridge is not None:
                _bridge.last_error = f"poll_loop: {e}"[:240]
        finally:
            try:
                _poll_lock.release()
            except Exception:
                pass

    _poll_thread = threading.Thread(target=_run, name="avatar-telegram-poll", daemon=True)
    _poll_thread.start()
    print(f"[AVATAR Telegram]: Poll arrancado (restart #{_restart_count}, lock={_poll_lock.mode}).")


def _enqueue_update(msg: dict) -> None:
    if not msg:
        return
    try:
        chat_id = str((msg.get("chat") or {}).get("id") or "")
        if chat_id and _bridge is not None:
            try:
                _bridge.send_chat_action(chat_id, "typing")
            except Exception:
                pass
        _msg_queue.put(msg)
    except Exception as e:
        print(f"[AVATAR Telegram]: enqueue failed: {e}")


def _worker_loop() -> None:
    print("[AVATAR Telegram]: Worker de mensajes activo.")
    while not _stop.is_set():
        try:
            msg = _msg_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            if _bridge is not None:
                _bridge.handle_message(msg)
        except Exception as e:
            print(f"[AVATAR Telegram Worker Error]: {e}")
            if _bridge is not None:
                _bridge.last_error = f"worker: {e}"[:240]


def _supervisor_loop() -> None:
    global _last_supervisor_at, _standby_other_instance, _poll_gen
    print("[AVATAR Telegram]: Supervisor de conexión activo.")
    while not _stop.is_set():
        _last_supervisor_at = time.time()
        try:
            with _lock:
                if _bridge is not None and not _bridge.bot_token:
                    try:
                        tok = _bridge._load_token_from_config()
                        if tok:
                            _bridge.bot_token = tok
                            _bridge.base_url = f"https://api.telegram.org/bot{tok}"
                    except Exception:
                        pass

                if _bridge is not None and _bridge.bot_token:
                    last = getattr(_bridge, "last_poll_at", None)
                    if _alive(_poll_thread) and last is not None:
                        age = time.time() - float(last)
                        if age > _stale_poll_seconds:
                            print(
                                "[AVATAR Telegram]: Poll stale "
                                f"({age:.0f}s sin getUpdates). Señal de reinicio."
                            )
                            _poll_gen += 1

                    if not _alive(_poll_thread):
                        if not _poll_lock.held:
                            if not _poll_lock.acquire(blocking=False):
                                _poll_lock.force_acquire()
                        if _poll_lock.held:
                            _standby_other_instance = False
                            _ensure_workers_locked()
                        else:
                            _standby_other_instance = True
                    else:
                        _standby_other_instance = False

                    if not _alive(_worker_thread):
                        _ensure_workers_locked()
        except Exception as e:
            print(f"[AVATAR Telegram Supervisor Error]: {e}")
        _stop.wait(10.0)


def force_recover_telegram() -> Dict[str, Any]:
    """
    Break a stale poll lock (dead holder PID / empty Windows lock file) and
    request a fresh poll generation so the supervisor/ensure can start clean.
    """
    global _poll_gen, _standby_other_instance
    with _lock:
        _poll_gen += 1
        _standby_other_instance = False
        _poll_lock.release()
        stolen = _poll_lock.force_acquire()
        # Release again so ensure_telegram_daemon/acquire owns it via the normal path,
        # unless we want to keep it — keep held so ensure can start poll immediately.
        return {
            "recovered": bool(stolen or _poll_lock.held),
            "lock_held": _poll_lock.held,
            "lock_mode": _poll_lock.mode,
            "reject": _poll_lock.last_reject_reason,
        }


def stop_telegram_daemon() -> None:
    """Test helper / clean shutdown."""
    global _poll_gen
    _stop.set()
    _poll_gen += 1
    try:
        _poll_lock.release()
    except Exception:
        pass


def status() -> Dict[str, Any]:
    running = _alive(_poll_thread)
    worker_ok = _alive(_worker_thread)
    info: Dict[str, Any] = {
        "status": (
            "STANDBY_OTHER_INSTANCE"
            if _standby_other_instance and not running
            else ("RUNNING" if running else "STOPPED")
        ),
        "running": running,
        "worker_running": worker_ok,
        "supervisor_running": _alive(_supervisor_thread),
        "queue_size": _msg_queue.qsize(),
        "restart_count": _restart_count,
        "standby_other_instance": _standby_other_instance,
        "poll_lock_held": _poll_lock.held,
        "poll_lock_mode": getattr(_poll_lock, "mode", "") or "",
        "poll_lock_reject": getattr(_poll_lock, "last_reject_reason", "") or "",
        "last_supervisor_at": _last_supervisor_at,
        "poll_generation": _poll_gen,
    }
    try:
        holder_pid, holder_ts = _poll_lock.read_holder()
        info["poll_lock_holder_pid"] = holder_pid
        info["poll_lock_holder_ts"] = holder_ts
    except Exception:
        info["poll_lock_holder_pid"] = None
        info["poll_lock_holder_ts"] = None
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
        if _standby_other_instance:
            info["hint"] = (
                "Otra instancia de Avatar tiene el candado de Telegram "
                f"({info.get('poll_lock_reject') or 'telegram_poll.lock'}). "
                "Cierra la otra ventana en el Administrador de tareas y reinicia Avatar, "
                "o POST /api/telegram/start."
            )
        elif info["poll_conflicts_409"] > 0 and not running:
            info["hint"] = (
                f"Hubo {info['poll_conflicts_409']} conflicto(s) 409. "
                "Cierra TODAS las ventanas de Avatar; el supervisor reintentará solo."
            )
        elif wh.get("ok") and wh.get("url"):
            info["hint"] = (
                "Hay un webhook activo: getUpdates no recibe chats. "
                "Reinicia Avatar (borra el webhook al arrancar)."
            )
        elif not running:
            info["hint"] = (
                "Listener detenido; el supervisor debería reiniciarlo en ~10s. "
                "Si no, POST /api/telegram/start."
            )
        elif not worker_ok:
            info["hint"] = "Poll OK pero worker caído — supervisor reiniciando worker."
        elif not info["allowed_chat_ids"]:
            info["hint"] = (
                "Listener activo, allowlist vacía: escribe /start al bot en privado "
                f"(@{(info.get('bot') or {}).get('username') or 'tu_bot'}) para auto-enrolarte."
            )
        elif info["last_error"]:
            info["hint"] = f"Listener activo pero último error: {info['last_error']}"
        else:
            info["hint"] = (
                "Listener durable activo (poll + worker + supervisor). "
                "Escribe al bot en privado."
            )
    except Exception as e:
        info["webhook"] = {"ok": False, "error": str(e)[:120]}
    return info
