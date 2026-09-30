import time
import requests
import json
import os
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.runtime import get_shared_orchestrator
from core.redaction import redact_secret_text
from core.logging_util import log as _avatar_log, register_secrets

def _plog(message: str, level: str = "INFO", **fields):
    _avatar_log(level, message, component="TelegramBridge", **fields)

from tools.reasoning_engine import ReasoningEngine

class TelegramBridge:
    """
    Pasarela de comunicación remota para el Proyecto Avatar vía Telegram Bot.
    Permite enviar mensajes, capturas de pantalla y comandos desde cualquier lugar a tu PC.

    Solo obedece a los usuarios de la allowlist (`telegram.allowed_chat_ids` en config.json o
    TELEGRAM_ALLOWED_CHAT_IDS, separados por comas), y solo en chat privado con el bot. Cada
    entrada es un ID numérico de usuario (en un chat privado coincide con el chat_id). Los
    @usuario no se aceptan porque Telegram permite reasignarlos. Sin allowlist rechaza todo y
    registra el ID de quien escribe, para que el dueño pueda añadir el suyo.
    """
    def __init__(self, bot_token: str = None, allowed_chat_id: str = None,
                 allowed_chat_ids=None, orchestrator=None,
                 auto_enroll_first_private: bool = None):
        from core.paths import config_path as resolve_config_path
        self.config_path = resolve_config_path()
        self.bot_token = bot_token or self._load_token_from_config()
        entries = list(allowed_chat_ids) if allowed_chat_ids is not None else self._load_allowlist()
        if allowed_chat_id:
            entries.append(allowed_chat_id)
        self.allowed_chat_ids = {str(e).strip() for e in entries if str(e).strip().isdigit()}
        ignored = [e for e in entries if str(e).strip() and not str(e).strip().isdigit()]
        if ignored:
            _plog(f"[Telegram]: Entradas de allowlist ignoradas (se requiere ID numérico): {ignored}")
        self.orchestrator = orchestrator if orchestrator is not None else get_shared_orchestrator()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        if self.bot_token:
            register_secrets([self.bot_token])
        self.last_update_id = 0
        # chat_key -> monotonic time of last rejection notice (cooldown, not forever-silent)
        self._reported_chats = {}
        self.last_inbound_at = None
        self.last_outbound_at = None
        self.last_error = ""
        self.last_poll_at = None
        self.poll_conflicts_409 = 0
        if auto_enroll_first_private is None:
            auto_enroll_first_private = self._load_auto_enroll_flag()
        self.auto_enroll_first_private = bool(auto_enroll_first_private)

    def _load_auto_enroll_flag(self) -> bool:
        """Solo-owner UX: first private human may enroll when allowlist is empty."""
        env = os.getenv("TELEGRAM_AUTO_ENROLL_FIRST_PRIVATE", "").strip().lower()
        if env in ("0", "false", "no", "off"):
            return False
        if env in ("1", "true", "yes", "on"):
            return True
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    raw = json.load(f).get("telegram", {}).get("auto_enroll_first_private", None)
                if raw is not None:
                    return bool(raw)
            except Exception:
                pass
        return True

    def _load_allowlist(self) -> list:
        env_val = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
        if env_val.strip():
            return [e for e in env_val.split(",") if e.strip()]
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    raw = json.load(f).get("telegram", {}).get("allowed_chat_ids", [])
                if isinstance(raw, (str, int)):
                    raw = [raw]
                return [str(e) for e in raw or [] if not str(e).startswith("YOUR_")]
            except Exception:
                pass
        return []

    def is_authorized(self, message: dict) -> bool:
        chat = message.get("chat", {}) or {}
        sender = message.get("from", {}) or {}
        if not self.allowed_chat_ids or sender.get("is_bot") is not False:
            return False
        if not isinstance(sender.get("id"), int) or isinstance(sender.get("id"), bool):
            return False
        user_id = str(sender["id"])
        # Group members cannot inherit the owner's authority through a shared chat id.
        if chat.get("type") != "private" or str(chat.get("id", "")) != user_id:
            return False
        return user_id in self.allowed_chat_ids

    def _report_rejected(self, message: dict):
        chat = message.get("chat", {}) or {}
        sender = message.get("from", {}) or {}
        user_id = str(sender.get("id", "?"))
        key = (str(chat.get("id", "")), user_id)
        now = time.monotonic()
        last = self._reported_chats.get(key)
        # Re-aviso cada 2 min: antes el silencio eterno parecía "el bot no recibe nada".
        if last is not None and (now - last) < 120:
            return
        self._reported_chats[key] = now
        where = f"chat {chat.get('id', '?')} ({chat.get('type', '?')})"
        if self.allowed_chat_ids:
            _plog(f"[Telegram]: Mensaje rechazado del usuario {user_id} en {where}.")
            if chat.get("type") == "private" and user_id.isdigit():
                self.send_message(
                    user_id,
                    f"AVATAR: no estás en la allowlist. Tu chat_id numérico es {user_id}. "
                    f"En la GUI de Avatar: UPDATE_CONFIG telegram.allowed_chat_ids = {user_id}",
                )
        else:
            _plog(f"[Telegram]: Sin allowlist configurada; rechazado usuario {user_id} en {where}. "
                  f"Si eres tú, escribe al bot en privado y añade \"{user_id}\" a "
                  f"telegram.allowed_chat_ids en config.json.")
            if chat.get("type") == "private" and user_id.isdigit():
                self.send_message(
                    user_id,
                    f"AVATAR: aún no hay allowlist. Tu chat_id es {user_id}. "
                    f"Dile a Avatar en el PC: UPDATE_CONFIG key=telegram.allowed_chat_ids value={user_id}",
                )

    def _persist_allowlist_id(self, user_id: str) -> bool:
        """Add user_id to config telegram.allowed_chat_ids and in-memory set."""
        if not user_id or not str(user_id).isdigit():
            return False
        uid = str(user_id).strip()
        self.allowed_chat_ids.add(uid)
        try:
            cfg = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f) or {}
            tg = cfg.setdefault("telegram", {})
            existing = tg.get("allowed_chat_ids") or []
            if isinstance(existing, (str, int)):
                existing = [existing]
            existing = [str(e).strip() for e in existing if str(e).strip()]
            if uid not in existing:
                existing.append(uid)
            tg["allowed_chat_ids"] = existing
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            _plog(f"[Telegram]: No se pudo persistir allowlist: {self._redact(e)}")
            return False
        try:
            cp = getattr(self.orchestrator, "chokepoint", None)
            if cp is not None:
                cp.policy.trusted_telegram_chat_ids = tuple(sorted(self.allowed_chat_ids))
        except Exception:
            pass
        _plog(f"[Telegram]: Auto-enrolado chat_id {uid} (primer privado; allowlist vacía).")
        return True

    def _try_auto_enroll(self, message: dict) -> bool:
        """If allowlist empty and first private human, enroll and authorize."""
        if self.allowed_chat_ids or not self.auto_enroll_first_private:
            return False
        chat = message.get("chat", {}) or {}
        sender = message.get("from", {}) or {}
        if chat.get("type") != "private":
            return False
        if sender.get("is_bot") is not False:
            return False
        uid = sender.get("id")
        if not isinstance(uid, int):
            return False
        if str(chat.get("id", "")) != str(uid):
            return False
        if not self._persist_allowlist_id(str(uid)):
            return False
        self.send_message(
            str(uid),
            f"AVATAR: quedaste registrado (chat_id {uid}). Ya puedo leerte y responderte aquí.",
        )
        return True

    def _redact(self, text) -> str:
        return redact_secret_text(str(text), [self.bot_token] if self.bot_token else [])

    def api_get_me(self) -> dict:
        """Verify the bot token against Telegram (no chat message sent)."""
        if not self.base_url:
            return {"ok": False, "error": "TOKEN_NOT_CONFIGURED"}
        try:
            r = requests.get(f"{self.base_url}/getMe", timeout=15)
            data = r.json() if r.content else {}
            if r.status_code == 200 and data.get("ok"):
                result = data.get("result") or {}
                return {
                    "ok": True,
                    "id": result.get("id"),
                    "username": result.get("username"),
                    "first_name": result.get("first_name"),
                    "can_join_groups": result.get("can_join_groups"),
                }
            desc = (data.get("description") or r.text or "")[:200]
            return {"ok": False, "error": f"HTTP_{r.status_code}", "detail": self._redact(desc)}
        except Exception as e:
            return {"ok": False, "error": "REQUEST_FAILED", "detail": self._redact(e)}

    def api_webhook_info(self) -> dict:
        if not self.base_url:
            return {"ok": False, "error": "TOKEN_NOT_CONFIGURED"}
        try:
            r = requests.get(f"{self.base_url}/getWebhookInfo", timeout=15)
            data = r.json() if r.content else {}
            if r.status_code == 200 and data.get("ok"):
                result = data.get("result") or {}
                return {
                    "ok": True,
                    "url": result.get("url") or "",
                    "pending_update_count": result.get("pending_update_count", 0),
                    "last_error_message": result.get("last_error_message") or "",
                }
            return {"ok": False, "error": f"HTTP_{r.status_code}"}
        except Exception as e:
            return {"ok": False, "error": "REQUEST_FAILED", "detail": self._redact(e)}

    def api_delete_webhook(self, drop_pending: bool = False) -> dict:
        """
        Polling (getUpdates) receives nothing while a webhook is set.
        Always clear webhook before listening.
        """
        if not self.base_url:
            return {"ok": False, "error": "TOKEN_NOT_CONFIGURED"}
        try:
            r = requests.get(
                f"{self.base_url}/deleteWebhook",
                params={"drop_pending_updates": "true" if drop_pending else "false"},
                timeout=15,
            )
            data = r.json() if r.content else {}
            return {
                "ok": bool(r.status_code == 200 and data.get("ok")),
                "description": (data.get("description") or "")[:200],
            }
        except Exception as e:
            return {"ok": False, "error": "REQUEST_FAILED", "detail": self._redact(e)}

    def api_recent_private_chat_ids(self, limit: int = 20) -> list:
        """
        Peek getUpdates for recent private chats (owner likely messaged /start).

        WARNING: a concurrent getUpdates while the daemon long-polls causes HTTP 409
        and the listener looks dead. Callers must skip this when the daemon is running.
        """
        if not self.base_url:
            return []
        try:
            r = requests.get(
                f"{self.base_url}/getUpdates",
                params={"limit": max(1, min(limit, 50)), "timeout": 0},
                timeout=20,
            )
            if r.status_code == 409:
                _plog("[Telegram]: api_recent_private_chat_ids omitido — 409 (daemon ya hace polling).")
                return []
            data = r.json() if r.content else {}
            if not (r.status_code == 200 and data.get("ok")):
                return []
            found = []
            seen = set()
            for upd in data.get("result") or []:
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat = msg.get("chat") or {}
                sender = msg.get("from") or {}
                if chat.get("type") != "private":
                    continue
                if sender.get("is_bot") is True:
                    continue
                uid = sender.get("id")
                if not isinstance(uid, int):
                    continue
                key = str(uid)
                if key in seen:
                    continue
                seen.add(key)
                found.append({
                    "chat_id": key,
                    "username": sender.get("username"),
                    "first_name": sender.get("first_name"),
                })
            return found
        except Exception:
            return []

    def send_chat_action(self, chat_id: str, action: str = "typing") -> dict:
        if not self.base_url or not chat_id:
            return {"ok": False}
        try:
            r = requests.post(
                f"{self.base_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
                timeout=5,
            )
            data = r.json() if r.content else {}
            return {"ok": bool(r.status_code == 200 and data.get("ok"))}
        except Exception as e:
            return {"ok": False, "error": self._redact(e)}

    def send_message(self, chat_id: str, text: str) -> dict:
        if not self.base_url:
            return {"ok": False, "error": "TOKEN_NOT_CONFIGURED"}
        if not chat_id:
            return {"ok": False, "error": "CHAT_ID_REQUIRED"}
        body = (text or "").strip()
        if not body:
            body = "Te escuché, pero no generé texto útil. ¿Lo intentamos de nuevo?"
        # Telegram hard limit ~4096; keep a margin.
        if len(body) > 4000:
            body = body[:3990] + "…"
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": body}
        try:
            r = requests.post(url, json=payload, timeout=10)
            data = r.json() if r.content else {}
            if r.status_code == 200 and data.get("ok"):
                mid = (data.get("result") or {}).get("message_id")
                self.last_outbound_at = time.time()
                return {"ok": True, "chat_id": str(chat_id), "message_id": mid}
            desc = (data.get("description") or r.text or "")[:200]
            err = {"ok": False, "error": f"HTTP_{r.status_code}", "detail": self._redact(desc)}
            self.last_error = f"sendMessage {err.get('error')}: {err.get('detail', '')}"[:240]
            _plog(f"[TelegramBridge]: sendMessage falló: {self.last_error}")
            return err
        except Exception as e:
            self.last_error = f"sendMessage REQUEST_FAILED: {self._redact(e)}"[:240]
            _plog(f"[TelegramBridge]: {self.last_error}")
            return {"ok": False, "error": "REQUEST_FAILED", "detail": self._redact(e)}

    def send_photo(self, chat_id: str, photo_path: str, caption: str = ""):
        if not self.base_url or not os.path.exists(photo_path):
            _plog(f"[TelegramBridge Error]: Foto no encontrada en {photo_path}")
            return {"ok": False, "error": "PHOTO_MISSING"}
        
        url = f"{self.base_url}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo:
                r = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": caption},
                    files={"photo": photo},
                    timeout=20,
                )
                _plog(f"[TelegramBridge]: Foto enviada exitosamente a Telegram (Chat {chat_id})")
                ok = r.status_code == 200
                return {"ok": ok, "status_code": r.status_code}
        except Exception as e:
            _plog(f"[Error envio foto Telegram]: {self._redact(e)}")
            return {"ok": False, "error": self._redact(e)}

    def _perform(self, act_type: str, args: dict, chat_id: str, task_id: str, text: str) -> str:
        if getattr(self.orchestrator, "chokepoint", None) is None:
            self.orchestrator.chokepoint = self.orchestrator._build_chokepoint()
        return self.orchestrator.chokepoint.perform(
            act_type=act_type,
            args=args,
            mission_id=f"telegram-{chat_id}",
            task_id=task_id,
            execution_id=f"tg-exec-{abs(hash(text)) % 10**8}",
        )

    def _load_token_from_config(self) -> str:
        env_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if env_token and not env_token.startswith("YOUR_"):
            return env_token.strip()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    tok = cfg.get("telegram", {}).get("bot_token", "")
                    if tok and not tok.startswith("YOUR_"):
                        return tok.strip()
            except Exception:
                pass
        return ""

    def _reload_token(self) -> bool:
        tok = self._load_token_from_config()
        if tok:
            self.bot_token = tok
            self.base_url = f"https://api.telegram.org/bot{tok}"
            return True
        return False

    def start_polling(self, on_update=None, should_stop=None):
        """
        Long-poll forever.

        on_update: optional callback(msg_dict) — if set, messages are handed off
        (daemon queue) so LLM work never blocks getUpdates.
        should_stop: optional callable() -> bool for cooperative shutdown/restart.
        """
        stop = should_stop or (lambda: False)

        while not stop():
            if not self.bot_token and not self._reload_token():
                _plog("[TelegramBridge]: Sin bot_token — reintento en 15s (config.json / .env).")
                self.last_error = "TOKEN_NOT_CONFIGURED"
                for _ in range(15):
                    if stop():
                        return
                    time.sleep(1)
                continue

            # If a webhook is set, getUpdates is empty forever — silent "bot ignores me".
            wh = self.api_webhook_info()
            if wh.get("ok") and wh.get("url"):
                _plog(
                    f"[Telegram Bridge]: Webhook activo ({wh.get('url')[:80]}). "
                    "Lo borro para poder usar getUpdates."
                )
            deleted = self.api_delete_webhook(drop_pending=False)
            if not deleted.get("ok"):
                _plog(f"[Telegram Bridge]: deleteWebhook falló: {deleted}")

            if not self.allowed_chat_ids:
                # Refresh allowlist from disk (auto-enroll may have written it).
                try:
                    self.allowed_chat_ids = {
                        str(e).strip()
                        for e in self._load_allowlist()
                        if str(e).strip().isdigit()
                    }
                except Exception:
                    pass
            if not self.allowed_chat_ids:
                if self.auto_enroll_first_private:
                    _plog(
                        "[Telegram Bridge]: Allowlist vacía — el primer chat privado "
                        "humano se auto-enrolará."
                    )
                else:
                    _plog(
                        "[Telegram Bridge]: Sin allowlist (telegram.allowed_chat_ids): "
                        "se rechazarán todas las órdenes."
                    )

            me = self.api_get_me()
            bot_label = (
                f"@{me.get('username')}"
                if me.get("ok") and me.get("username")
                else "(token ok o pendiente)"
            )
            if me.get("ok"):
                _plog(f"[Telegram Bridge]: getMe OK → {bot_label}. Escuchando getUpdates...")
            else:
                _plog(
                    f"[Telegram Bridge]: getMe falló ({me.get('error')}); "
                    "igual intento getUpdates."
                )
                # Bad token: back off and reload config.
                if me.get("error") in ("HTTP_401", "HTTP_Unauthorized") or "unauthorized" in str(
                    me.get("detail", "")
                ).lower():
                    self.last_error = f"getMe failed: {me.get('error')}"
                    time.sleep(20)
                    self._reload_token()
                    continue

            _plog(f"[Telegram Bridge]: Escuchando ordenes remotas via Telegram {bot_label}...")
            idle_loops = 0
            conflicts_streak = 0

            while not stop():
                try:
                    self.last_poll_at = time.time()
                    url = (
                        f"{self.base_url}/getUpdates"
                        f"?offset={self.last_update_id + 1}&timeout=25"
                    )
                    response = requests.get(url, timeout=35)
                    if response.status_code == 200:
                        conflicts_streak = 0
                        data = response.json()
                        results = data.get("result", []) if data.get("ok") else []
                        if not results:
                            idle_loops += 1
                            if idle_loops in (1, 10, 30):
                                _plog(
                                    f"[Telegram Bridge]: sin updates nuevos "
                                    f"(loop vacío #{idle_loops}). "
                                    f"Escribe a {bot_label} en privado."
                                )
                        else:
                            idle_loops = 0
                            _plog(f"[Telegram Bridge]: {len(results)} update(s) recibidos.")
                        for result in results:
                            self.last_update_id = result["update_id"]
                            msg = (
                                result.get("message")
                                or result.get("edited_message")
                                or {}
                            )
                            if on_update is not None:
                                try:
                                    on_update(msg)
                                except Exception as cb_err:
                                    self.last_error = f"on_update: {self._redact(cb_err)}"[:240]
                                    _plog(f"[Telegram Bridge]: {self.last_error}")
                            else:
                                try:
                                    self.handle_message(msg)
                                except Exception as msg_err:
                                    self.last_error = (
                                        f"handle_message: {self._redact(msg_err)}"[:240]
                                    )
                                    _plog(
                                        f"[Telegram Bridge]: error procesando update: "
                                        f"{self.last_error}"
                                    )
                                    chat_id = str((msg.get("chat") or {}).get("id") or "")
                                    if chat_id:
                                        self.send_message(
                                            chat_id,
                                            "Recibí tu mensaje pero falló el procesamiento "
                                            "en la PC. Revisa la consola de Avatar o reinténtalo.",
                                        )
                    elif response.status_code == 409:
                        conflicts_streak += 1
                        self.poll_conflicts_409 += 1
                        self.last_error = (
                            "getUpdates 409 Conflict — otra instancia hace polling"
                        )
                        _plog(
                            "[Telegram Bridge]: 409 Conflict — otra instancia ya está "
                            "haciendo polling. Cierra el otro Avatar; reintento…"
                        )
                        # Re-clear webhook; sometimes leftover webhook+poll fights.
                        if conflicts_streak in (1, 3, 6):
                            self.api_delete_webhook(drop_pending=False)
                        # Backoff so the other process can exit; supervisor may take lock.
                        time.sleep(min(30, 5 * conflicts_streak))
                        if conflicts_streak >= 8:
                            # Yield outer loop so daemon can release lock / standby.
                            _plog(
                                "[Telegram Bridge]: Demasiados 409 — salgo del poll para "
                                "que el supervisor reintente con candado."
                            )
                            return
                    elif response.status_code in (401, 404):
                        self.last_error = f"getUpdates HTTP {response.status_code} (token?)"
                        _plog(f"[Telegram Bridge]: {self.last_error}")
                        time.sleep(20)
                        self._reload_token()
                        break  # re-prepare
                    else:
                        _plog(
                            f"[Telegram Bridge]: getUpdates HTTP {response.status_code}: "
                            f"{self._redact((response.text or '')[:200])}"
                        )
                        self.last_error = f"getUpdates HTTP {response.status_code}"[:240]
                        time.sleep(5)
                except requests.exceptions.Timeout:
                    # Normal for long-poll edge; keep going.
                    self.last_poll_at = time.time()
                    continue
                except Exception as e:
                    _plog(f"[Error en loop de Telegram]: {self._redact(e)}")
                    self.last_error = f"poll loop: {self._redact(e)}"[:240]
                    time.sleep(5)


    def handle_message(self, message: dict):
        if not message:
            return
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "") or message.get("caption", "") or ""

        if not self.is_authorized(message):
            if self._try_auto_enroll(message) and self.is_authorized(message):
                # Enrolled; fall through and process this same message.
                pass
            else:
                self._report_rejected(message)
                return

        if not text:
            return

        self.last_inbound_at = time.time()
        _plog(f"\n[Orden remota recibida de Telegram]: {text}")
        # Feedback inmediato en Telegram: se ve "escribiendo…" mientras piensa el LLM.
        self.send_chat_action(chat_id, "typing")
        text_lower = text.lower().strip()

        # Función auxiliar: solo para rutas de charla / reglas. NUNCA bloquea actos físicos.
        instruction_kws = [
            "integres", "integrar", "sistema", "comprendes", "entiendes", "configurar",
            "aprender", "guardar", "regla", "explicar", "instrucción", "instruccion",
            "retroalimentación", "feedback", "cada vez que", "no se debe", "por qué",
            "porque", "analizar", "diagnóstico", "opinas", "estipulado", "entiendas"
        ]
        is_instruction = any(kw in text_lower for kw in instruction_kws) or \
                         (text_lower.endswith("?") and len(text_lower.split()) > 5) or \
                         (len(text_lower.split()) > 10 and not any(text_lower.startswith(imp) for imp in ["reproduce ", "reproduzca ", "pon ", "ponme ", "toca ", "escuchar "]))

        try:
            from tools.audio_tool import AudioTool
            from tools.desktop_hotkey import DesktopHotkey

            # ——— Actos físicos: SIEMPRE tienen prioridad sobre is_instruction ———
            # (mensajes largos tipo «quiero que le tomes una captura…» no deben ir al LLM)

            # 1) Captura → SCREEN_CAPTURE + send_photo (obligatorio en este canal)
            if any(kw in text_lower for kw in ["captura", "pantalla", "screenshot", "foto del escritorio", "foto de mi pantalla"]):
                # Evitar falsos positivos de «foto» suelta en charla; «imagen» solo con captura/pantalla
                wants_shot = (
                    any(kw in text_lower for kw in ["captura", "pantalla", "screenshot"])
                    or ("foto" in text_lower and any(k in text_lower for k in ["escritorio", "pantalla", "pc", "envía", "enviame", "envíame", "manda"]))
                )
                if wants_shot:
                    self.send_message(chat_id, "Capturando pantalla del escritorio de tu PC…")
                    img_path = self._perform("SCREEN_CAPTURE", {}, chat_id, "screen-capture", text).strip()
                    if img_path and os.path.isfile(img_path):
                        self.send_photo(chat_id, img_path, caption="Captura de pantalla de tu PC (Avatar)")
                    else:
                        self.send_message(chat_id, "No se pudo obtener la captura de pantalla.")
                    return

            # 2) Hotkeys de ventana (minimizar, escritorio…) — sin EXEC
            hotkey_action = DesktopHotkey.extract_action(text)
            if hotkey_action:
                label = {
                    "minimize": "Minimizando la ventana…",
                    "maximize": "Maximizando la ventana…",
                    "show_desktop": "Mostrando el escritorio…",
                }.get(hotkey_action, f"Enviando atajo «{hotkey_action}»…")
                self.send_message(chat_id, label)
                res_msg = self._perform(
                    "DESKTOP_HOTKEY",
                    {
                        "action": hotkey_action,
                        "target": DesktopHotkey.extract_target(text) or "",
                    },
                    chat_id,
                    "desktop-hotkey",
                    text,
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            # 3) Cerrar SOLO la pestaña pedida (YouTube u otra) en el navegador del sistema.
            close_target = AudioTool.extract_close_target(text)
            if close_target is not None:
                label = close_target or "activa"
                self.send_message(chat_id, f"Cerrando la pestaña «{label}» en tu navegador…")
                res_msg = self._perform(
                    "AUDIO_CONTROL",
                    {"action": "close", "target": close_target or "youtube"},
                    chat_id,
                    "close-tab",
                    text,
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            # 4) Siguiente / anterior pista
            if any(
                kw in text_lower for kw in ["siguiente canción", "siguiente cancion", "siguiente pista", "next track", "siguiente tema"]
            ) or text_lower.strip() in ("siguiente", "next", "skip"):
                self.send_message(chat_id, "Pasando a la siguiente pista…")
                res_msg = self._perform(
                    "AUDIO_CONTROL", {"action": "next"}, chat_id, "next-track", text
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            if any(
                kw in text_lower for kw in ["anterior canción", "anterior cancion", "anterior pista", "previous"]
            ) or text_lower.strip() in ("anterior", "prev"):
                self.send_message(chat_id, "Volviendo a la pista anterior…")
                res_msg = self._perform(
                    "AUDIO_CONTROL", {"action": "previous"}, chat_id, "prev-track", text
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            # 5) Reanudar / «dale play» (ANTES que PLAY_AUDIO para no relanzar otra canción)
            if AudioTool.is_resume_request(text):
                self.send_message(chat_id, "Reanudando la música en tu PC…")
                res_msg = self._perform(
                    "AUDIO_CONTROL", {"action": "resume"}, chat_id, "resume-audio", text
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            # 6) Pausa
            if any(
                kw in text_lower
                for kw in ["pausa", "pausar", "paúsala", "pausala", "detén", "deten", "silenciar", "parar", "stop"]
            ) and "desktop" not in text_lower:
                self.send_message(chat_id, "Pausando la música en tu PC…")
                res_msg = self._perform(
                    "AUDIO_CONTROL", {"action": "pause"}, chat_id, "pause-audio", text
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            # 7) Abrir o CAMBIAR canción (misma pestaña del sistema)
            song_query = None
            if any(
                kw in text_lower
                for kw in [
                    "cambia", "cambiar", "reproduce", "reproduzca", "reproduscas",
                    "reproduzcas", "cancion", "canción", "musica", "música",
                    "ponme", "pon ",
                ]
            ):
                song_query = AudioTool.extract_song_request(text)
            if song_query:
                self.send_message(chat_id, f"Reproduciendo «{song_query}» en YouTube (tu PC)…")
                res_msg = self._perform(
                    "PLAY_AUDIO", {"audio_source": song_query}, chat_id, "play-music", text
                )
                self.send_message(chat_id, self._redact(res_msg))
                return

            # Charla / reglas → orquestador (is_instruction solo afecta aquí de forma implícita)
            _ = is_instruction  # retained for diagnostics / future tone routing
            raw_output = self.orchestrator.process_user_input(text, channel="remote")
            clean_output = ReasoningEngine.extract_clean_response(raw_output or "")

            # Evitar enviar bloques de codigo Python crudo como mensaje de chat conversacional
            if "class ScreenTool" in clean_output or "import os" in clean_output:
                clean_output = "Acción procesada en tu PC. Sistema listo para tu siguiente comando."

            if not (clean_output or "").strip():
                clean_output = (
                    "Te escuché, pero el modelo no devolvió texto. "
                    "Prueba de nuevo o revisa el proveedor de IA en la PC."
                )

            # Si el LLM hizo SCREEN_CAPTURE (o dejó la ruta), envía la foto al chat.
            self._maybe_send_llm_screenshot(chat_id, text_lower, clean_output)

            sent = self.send_message(chat_id, self._redact(clean_output)) or {}
            if not sent.get("ok"):
                # Segundo intento sin markdown raro / texto mínimo.
                self.send_message(chat_id, "Te escuché. Hubo un fallo al enviar la respuesta completa; reinténtalo.")
        except Exception as e:
            self.last_error = f"handle_message body: {self._redact(e)}"[:240]
            _plog(f"[Telegram Bridge]: {self.last_error}")
            self.send_message(
                chat_id,
                f"Recibí tu mensaje («{(text or '')[:80]}») pero falló al procesarlo en la PC. "
                "Revisa la consola de Avatar.",
            )

    def _maybe_send_llm_screenshot(self, chat_id: str, text_lower: str, clean_output: str) -> None:
        """After an LLM turn, attach screenshot.png if Mauro asked for a capture."""
        looks_like_capture = any(
            kw in text_lower for kw in ("captura", "pantalla", "screenshot")
        ) or ("foto" in text_lower and "escritorio" in text_lower)
        path = None
        # Path returned/mentioned in the reply
        for token in (clean_output or "").replace("`", " ").replace("'", " ").split():
            if token.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) and os.path.isfile(token):
                path = token
                break
        if path is None:
            try:
                from core.paths import memory_dir
                candidate = os.path.join(memory_dir(), "screenshot.png")
            except Exception:
                candidate = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "memory",
                    "screenshot.png",
                )
            if looks_like_capture and os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                # Only if freshly written (last 3 minutes) — avoids re-sending stale shots
                try:
                    age = time.time() - os.path.getmtime(candidate)
                except Exception:
                    age = 9999
                if age <= 180:
                    path = candidate
        if path and os.path.isfile(path):
            self.send_photo(chat_id, path, caption="Captura de pantalla de tu PC (Avatar)")
