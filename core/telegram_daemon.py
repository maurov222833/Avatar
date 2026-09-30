"""Durable Telegram getUpdates listener: supervisor + queue + single-poller lock."""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from typing import Any, Dict, Optional

from core.paths import memory_dir
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
_poll_started_gen = -1
_last_kick_at: Optional[float] = None


def _alive(t: Optional[threading.Thread]) -> bool:
    return bool(t is not None and t.is_alive())


def _heartbeat_path() -> str:
    try:
        os.makedirs(memory_dir(), exist_ok=True)
    except Exception:
        pass
    return os.path.join(memory_dir(), "telegram_heartbeat.json")


def _write_heartbeat(extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {
        "ts": time.time(),
        "pid": os.getpid(),
        "running": _alive(_poll_thread),
        "worker_running": _alive(_worker_thread),
        "supervisor_running": _alive(_supervisor_thread),
        "restart_count": _restart_count,
        "poll_generation": _poll_gen,
        "standby_other_instance": _standby_other_instance,
        "lock_held": _poll_lock.held,
        "lock_mode": getattr(_poll_lock, "mode", ""),
    }
    if _bridge is not None:
        payload["last_poll_at"] = getattr(_bridge, "last_poll_at", None)
        payload["last_inbound_at"] = getattr(_bridge, "last_inbound_at", None)
        payload["last_error"] = getattr(_bridge, "last_error", "") or ""
        payload["token_configured"] = bool(getattr(_bridge, "bot_token", ""))
    if extra:
        payload.update(extra)
    try:
        with open(_heartbeat_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass


def ensure_telegram_daemon(orchestrator=None) -> Dict[str, Any]:
    """
    Start (or keep) the durable Telegram stack.

    Even without a token yet, the supervisor starts so it can pick up
    telegram.bot_token from config.json later without a full Avatar restart.
    """
    global _bridge, _supervisor_thread
    with _lock:
        if orchestrator is not None or _bridge is None:
            from bridges.telegram_bridge import TelegramBridge

            if _bridge is None:
                _bridge = TelegramBridge(orchestrator=orchestrator)
            elif orchestrator is not None:
                _bridge.orchestrator = orchestrator

        # Always reload token from disk — config may have been saved after boot.
        try:
            tok = _bridge._load_token_from_config()
            if tok and tok != _bridge.bot_token:
                _bridge.bot_token = tok
                _bridge.base_url = f"https://api.telegram.org/bot{tok}"
            elif tok and not _bridge.bot_token:
                _bridge.bot_token = tok
                _bridge.base_url = f"https://api.telegram.org/bot{tok}"
            # Refresh allowlist from disk too.
            try:
                ids = [
                    str(e).strip()
                    for e in _bridge._load_allowlist()
                    if str(e).strip().isdigit()
                ]
                if ids:
                    _bridge.allowed_chat_ids = set(ids)
            except Exception:
                pass
        except Exception:
            pass

        _stop.clear()

        # Supervisor must run even with NO_TOKEN so it can start later.
        if not _alive(_supervisor_thread):
            _supervisor_thread = threading.Thread(
                target=_supervisor_loop,
                name="avatar-telegram-supervisor",
                daemon=True,
            )
            _supervisor_thread.start()
            print("[AVATAR Telegram]: Supervisor arrancado.")

        if not _bridge.bot_token:
            _write_heartbeat({"status": "NO_TOKEN"})
            return {
                "status": "NO_TOKEN",
                "running": False,
                "supervisor_running": _alive(_supervisor_thread),
                "message": "telegram.bot_token no configurado en config.json",
                "hint": (
                    "Guarda el token (UPDATE_CONFIG / GUI) y ejecuta TELEGRAM_STATUS; "
                    "el supervisor arrancará el listener solo."
                ),
            }

        _ensure_workers_locked()
        _write_heartbeat()
        return status()


def kick_telegram_listener(orchestrator=None) -> Dict[str, Any]:
    """
    Force-recover stale state and ensure poll+worker+supervisor are up.
    Safe to call often (status, config save, TELEGRAM_STATUS).
    """
    global _last_kick_at
    _last_kick_at = time.time()
    try:
        force_recover_telegram()
    except Exception as e:
        print(f"[AVATAR Telegram]: force_recover: {e}")
    return ensure_telegram_daemon(orchestrator=orchestrator)


def _ensure_workers_locked() -> None:
    """Start poll+worker if missing. Caller must hold _lock."""
    global _poll_thread, _worker_thread, _restart_count, _standby_other_instance
    global _poll_gen, _poll_started_gen

    if not _alive(_worker_thread):
        _worker_thread = threading.Thread(
            target=_worker_loop, name="avatar-telegram-worker", daemon=True
        )
        _worker_thread.start()

    # Alive but from an old generation → wait for exit, then respawn.
    if _alive(_poll_thread) and _poll_started_gen == _poll_gen:
        return
    if _alive(_poll_thread) and _poll_started_gen != _poll_gen:
        print("[AVATAR Telegram]: Poll de generación vieja aún vivo; esperando salida…")
        return

    if not _poll_lock.held:
        got = _poll_lock.acquire(blocking=False)
        if not got:
            got = _poll_lock.force_acquire()
        if not got:
            _standby_other_instance = True
            print(
                "[AVATAR Telegram]: En espera — otra instancia tiene el candado "
                f"({_poll_lock.last_reject_reason})."
            )
            _write_heartbeat({"status": "STANDBY_OTHER_INSTANCE"})
            return

    _standby_other_instance = False
    _restart_count += 1
    my_gen = _poll_gen
    _poll_started_gen = my_gen

    def _should_stop() -> bool:
        return _stop.is_set() or my_gen != _poll_gen

    def _run() -> None:
        print("[AVATAR Telegram]: Poll loop activo (getUpdates desacoplado del LLM).")
        _write_heartbeat({"status": "POLL_START"})
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
            _write_heartbeat({"status": "POLL_EXIT"})
            print("[AVATAR Telegram]: Poll loop terminó (supervisor puede reiniciar).")

    _poll_thread = threading.Thread(target=_run, name="avatar-telegram-poll", daemon=True)
    _poll_thread.start()
    print(f"[AVATAR Telegram]: Poll arrancado (restart #{_restart_count}, lock={_poll_lock.mode}).")
    _write_heartbeat({"status": "POLL_STARTED"})


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
                if _bridge is not None:
                    try:
                        tok = _bridge._load_token_from_config()
                        if tok and tok != (_bridge.bot_token or ""):
                            print("[AVATAR Telegram]: Token nuevo detectado en config — aplicando.")
                            _bridge.bot_token = tok
                            _bridge.base_url = f"https://api.telegram.org/bot{tok}"
                        elif tok and not _bridge.bot_token:
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
                    elif _poll_started_gen != _poll_gen:
                        # Old gen still draining; next loop will start fresh when dead.
                        pass
                    else:
                        _standby_other_instance = False

                    if not _alive(_worker_thread):
                        _ensure_workers_locked()
                _write_heartbeat()
        except Exception as e:
            print(f"[AVATAR Telegram Supervisor Error]: {e}")
        # Faster retry when down; normal cadence when healthy.
        wait_s = 3.0 if not _alive(_poll_thread) else 10.0
        _stop.wait(wait_s)


def force_recover_telegram() -> Dict[str, Any]:
    """Break stale lock and bump generation so a fresh poll can start."""
    global _poll_gen, _standby_other_instance
    with _lock:
        if _alive(_poll_thread):
            _poll_gen += 1
        _standby_other_instance = False
        _poll_lock.release()
        stolen = _poll_lock.force_acquire()
        _write_heartbeat({"status": "FORCE_RECOVER", "stolen": bool(stolen)})
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
    _write_heartbeat({"status": "STOPPED"})


def status() -> Dict[str, Any]:
    running = _alive(_poll_thread)
    worker_ok = _alive(_worker_thread)
    info: Dict[str, Any] = {
        "status": (
            "NO_TOKEN"
            if (_bridge is not None and not _bridge.bot_token)
            else (
                "STANDBY_OTHER_INSTANCE"
                if _standby_other_instance and not running
                else ("RUNNING" if running else "STOPPED")
            )
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
        "last_kick_at": _last_kick_at,
        "poll_generation": _poll_gen,
        "heartbeat_path": _heartbeat_path(),
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
            "Daemon no arrancado. Reinicia Avatar, guarda el token, o dile TELEGRAM_STATUS."
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
        wh = _bridge.api_webhook_info() if _bridge.bot_token else {}
        info["webhook"] = wh
        if not _bridge.bot_token:
            info["hint"] = (
                "Sin token: configura telegram.bot_token y ejecuta TELEGRAM_STATUS."
            )
        elif _standby_other_instance:
            info["hint"] = (
                "Otra instancia tiene el candado "
                f"({info.get('poll_lock_reject') or 'telegram_poll.lock'}). "
                "Cierra la otra ventana en el Administrador de tareas."
            )
        elif not running:
            info["hint"] = (
                "Listener DETENIDO (no hay polling). Dile TELEGRAM_STATUS o "
                "POST /api/telegram/start — el sistema intentará arrancarlo solo. "
                f"last_error={info.get('last_error') or 'none'}"
            )
        elif not worker_ok:
            info["hint"] = "Poll OK pero worker caído — supervisor reiniciando."
        elif wh.get("ok") and wh.get("url"):
            info["hint"] = "Webhook activo; se borra al poll. Si persiste, reinicia Avatar."
        elif not info["allowed_chat_ids"]:
            info["hint"] = (
                "Listener activo, allowlist vacía: /start al bot en privado "
                f"(@{(info.get('bot') or {}).get('username') or 'tu_bot'})."
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
