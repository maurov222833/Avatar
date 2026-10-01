import time
import requests
import json
import os
import sys
from typing import Optional

# Garantizar resolución de imports raíz ('core', 'tools', 'memory')
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.runtime import get_shared_orchestrator
from tools.whatsapp_auto_reply import WhatsAppAutoReply
from bridges.whatsapp_reader import (
    WhatsAppReadError,
    WhatsAppWebReader,
    _text_key,
    probe_environment,
)

DEFAULT_PROFILE_DIR = os.path.join(base_dir, "memory", "whatsapp_profile")
DEFAULT_STATE_PATH = os.path.join(base_dir, "memory", "whatsapp_bridge_state.json")



def _walog(message: str, level: str = "INFO") -> None:
    try:
        from core.logging_util import log
        log(level, message, component="WhatsAppBridge")
    except Exception:
        pass

class WhatsAppBridge:
    """
    Pasarela de integración para WhatsApp del Proyecto Avatar.

    Dos modos:
      - process_incoming_whatsapp(sender, message): procesa UN mensaje ya obtenido
        (usado por el webhook HTTP y por el loop vivo). Responde vía chokepoint.
      - start_live_bridge(target_chat): loop real — lee WhatsApp Web con un lector
        DOM, procesa lo nuevo con el orquestador y responde en el mismo chat.
    """
    def __init__(self, bridge_url: str = "http://localhost:8000/api/whatsapp/webhook",
                 reader=None, state_path: str = DEFAULT_STATE_PATH,
                 authorized_senders=None, poll_seconds: int = 8,
                 max_replies: int = 50, observe_only: bool = False,
                 respond_to_own_outgoing: bool = False,
                 orchestrator=None):
        self.bridge_url = bridge_url
        self.orchestrator = orchestrator if orchestrator is not None else get_shared_orchestrator()
        self.reader = reader  # inyectable para tests; si None se crea al arrancar
        self.state_path = state_path
        # None = solo el propio chat objetivo (en un chat 1:1 el remitente entrante lleva el
        # nombre del chat). En un grupo cualquier otro remitente queda rechazado.
        self.authorized_senders = (
            list(authorized_senders) if authorized_senders is not None else None
        )
        self.poll_seconds = poll_seconds
        self.max_replies = max_replies
        self.observe_only = observe_only
        # Auto-chat ("Mensaje a ti mismo"): lo de Mauro llega como saliente.
        # Se procesa salvo que sea eco de un envío propio del lector.
        self.respond_to_own_outgoing = respond_to_own_outgoing
        self._stop = False
        self._replied_ids = self._load_state()

    # -- estado ---------------------------------------------------------
    def _load_state(self):
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return set(data.get("replied_ids", []))
        except Exception:
            pass
        return set()

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump({"replied_ids": sorted(self._replied_ids)[-500:]}, f)
        except Exception as exc:
            _walog(f"[WhatsAppBridge aviso]: no se pudo persistir cursor: {exc}")

    def stop(self):
        self._stop = True

    # -- QR -------------------------------------------------------------
    def sync_whatsapp_qr(self) -> str:
        """Abre WhatsApp Web en la PC para permitir el escaneo del código QR."""
        sync_script = os.path.join(base_dir, "whatsapp_native_sync.py")
        if os.path.exists(sync_script):
            import subprocess
            subprocess.Popen([sys.executable, sync_script])
            return "✅ Iniciando sincronización de WhatsApp Web en tu pantalla. Por favor escanea el código QR desde tu celular."
        return "⚠️ No se encontró el script de sincronización whatsapp_native_sync.py."

    # -- procesar un mensaje -------------------------------------------
    def process_incoming_whatsapp(self, sender: str, message_body: str,
                                  message_id: str = "", sent_at=None) -> str:
        """
        Recibe un mensaje de WhatsApp, lo procesa con el Agente Avatar y envía la respuesta.

        El envío pasa por el ActChokepoint, igual que cualquier otro efecto secundario. Antes
        llamaba a `WhatsAppAutoReply.send_reply` directamente, lo que significaba que un
        mensaje real podía salir a otra persona sin política, sin registro y sin dry-run.
        `/pause` del dueño autorizado pausa y el segundo `/pause` quita la pausa.
        """
        _walog(f"\n💬 [Mensaje de WhatsApp de {sender}]: {message_body}")
        handled = self._owner_control(
            sender, message_body, message_id=message_id, sent_at=sent_at,
        )
        if handled is not None:
            if handled:
                self._deliver(sender=sender, message_body=message_body, response=handled)
            return handled
        response = self.orchestrator.process_user_input(message_body, channel="remote")
        self._deliver(sender=sender, message_body=message_body, response=response)
        return response

    def _control_allowed(self, sender: str, extra_allowed=None) -> bool:
        allowed = self.authorized_senders
        if allowed is None:
            allowed = extra_allowed
        if not allowed:
            return False
        return sender in list(allowed)

    def _owner_control(self, sender: str, text: str, message_id: str = "",
                       sent_at=None, extra_allowed=None):
        """None si no es una parada. Texto de respuesta si el dueño la ordenó."""
        from core.halt import apply_control_command, interpret_control_command, toggle_pause
        if not interpret_control_command(text):
            return None
        actor = sender or "unknown"
        if not self._control_allowed(sender, extra_allowed):
            apply_control_command(text, authorized=False, actor=actor, source="whatsapp")
            return ""
        inbox = getattr(self, "_remote_inbox", None)
        if inbox is None:
            from core.remote_guard import RemoteInbox
            inbox = RemoteInbox()
            self._remote_inbox = inbox
        accepted, _why = inbox.accept(
            sender=sender,
            message_id=str(message_id or ""),
            text=text,
            authorized=True,
            sent_at=sent_at,
        )
        if not accepted:
            return ""
        if interpret_control_command(text) == "PAUSE":
            result = toggle_pause(actor=actor, source="whatsapp")
            if result == "RESUMED":
                return "Pausa quitada."
            if result == "PAUSE":
                return "Pausa activa. Otro /pause la quita."
            return "Sigue la parada fuerte. /pause no la quita."
        level = apply_control_command(
            text, authorized=True, actor=actor, source="whatsapp",
        )
        return f"Parada {level} activa."

    def _deliver(self, sender: str, message_body: str, response: str) -> str:
        """Envía una respuesta ya generada vía chokepoint (política + ledger)."""
        if self.orchestrator.chokepoint is None:
            self.orchestrator.chokepoint = self.orchestrator._build_chokepoint()
        delivery = self.orchestrator.chokepoint.perform(
            act_type="SEND_WHATSAPP",
            args={"message": response},
            mission_id=f"whatsapp-{sender}",
            task_id="whatsapp-reply",
            execution_id=f"wa-exec-{abs(hash(message_body)) % 10**8}",
        )
        _walog(f"📤 [Entrega a {sender}]: {delivery[:160]}")
        return delivery

    # -- loop vivo ------------------------------------------------------
    def start_live_bridge(self, target_chat: str = "Mauro Vanegas 2025",
                          max_polls: int = 0, heartbeat_cb=None,
                          stop_path: str = "",
                          qr_hold_seconds: Optional[float] = 300) -> dict:
        """
        Puente activo real para el chat indicado.

        Lee mensajes entrantes nuevos, los procesa con el orquestador y responde en el
        mismo chat. Dedup por msg_id persistido (nunca responde dos veces lo mismo),
        solo remitentes autorizados, y la política del chokepoint decide cada envío:
        sin opt-in del operador el envío se DENIEGA y queda registrado (correcto).

        max_polls=0 significa infinito (hasta stop()); >0 lo limita (útil en pruebas).
        Devuelve un resumen con lo procesado.
        """
        _walog("==================================================")
        _walog(f"⚡ [AVATAR AI]: Puente de WhatsApp Activo para '{target_chat}'")
        _walog("==================================================")

        reader = self.reader or WhatsAppWebReader(profile_dir=DEFAULT_PROFILE_DIR)
        reader.launch()
        try:
            state = reader.login_state()
            if state != "LOGGED_IN" and qr_hold_seconds != 0:
                _walog(
                    "QR visible. La ventana queda abierta hasta que escanees "
                    "o aparezca el archivo de parada."
                )
                if heartbeat_cb is not None:
                    try:
                        heartbeat_cb({"phase": "waiting_qr"})
                    except Exception:
                        pass
                waiter = getattr(reader, "wait_for_login", None)
                if waiter is not None:
                    state = waiter(
                        hold_seconds=qr_hold_seconds,
                        poll_seconds=2.0,
                        stop_path=stop_path,
                    )
            if state != "LOGGED_IN":
                raise WhatsAppReadError(
                    WhatsAppReadError.LOGIN_REQUIRED_QR,
                    "Sesión no iniciada: la ventana del QR sigue el plazo de espera. "
                    "Escanéala con el celular antes de que se cierre.")
            reader.open_chat(target_chat)
            # El envío del loop usa el lector DOM (verificado por relectura) en lugar
            # del AutoReply de ventana activa. La política y el ledger se conservan:
            # perform() sigue decidiendo y registrando cada SEND_WHATSAPP.
            if self.orchestrator.chokepoint is None:
                self.orchestrator.chokepoint = self.orchestrator._build_chokepoint()
            self.orchestrator.chokepoint.executors["SEND_WHATSAPP"] = (
                lambda a: reader.send_text(a.get("message") or a.get("params") or "")
            )
            return self._poll_loop(reader, target_chat, max_polls,
                                    heartbeat_cb=heartbeat_cb, stop_path=stop_path)
        finally:
            if self.reader is None:
                reader.close()

    #: Respuestas que indican silencio del proveedor: enviarlas al chat solo
    #: generaría ruido; se registra el salto y se avanza el cursor (el dueño
    #: puede reenviar el mensaje).
    SILENCE_MARKERS = (
        "El proveedor devolvió respuestas vacías",
        "No obtuve respuesta del proveedor",
    )

    #: Respuestas que son fontanería interna (conclusiones de relleno del
    #: orquestador): jamás salen al chat. Contrato estable con el fallback
    #: ejecutivo — si cambia su prefijo, este filtro debe actualizarse.
    SUPPRESS_PREFIXES = (
        "🔍 Solo observé",
    )

    #: Longitud máxima de una respuesta de WhatsApp: lo que exceda se recorta
    #: con aviso en vez de volcar bloques técnicos al teléfono.
    MAX_REPLY_CHARS = 1000

    @classmethod
    def format_whatsapp_reply(cls, response: str):
        """
        Política de respuesta del canal: devuelve (enviar: bool, texto).

        - Silencio del proveedor o relleno interno -> no enviar (ruido).
        - Resto -> texto recortado a lo esencial, sin bloques de evidencia.
        """
        text = (response or "").strip()
        if not text:
            return False, ""
        if any(m in text for m in cls.SILENCE_MARKERS):
            return False, ""
        if text.startswith(cls.SUPPRESS_PREFIXES):
            return False, ""
        if len(text) > cls.MAX_REPLY_CHARS:
            text = (text[:cls.MAX_REPLY_CHARS].rsplit(" ", 1)[0]
                    + "… (continúo por aquí si me lo pides)")
        return True, text

    def _poll_loop(self, reader, target_chat: str, max_polls: int,
                   heartbeat_cb=None, stop_path: str = "") -> dict:
        polls = 0
        processed = 0
        replied = 0
        stop_file = stop_path or os.path.join(base_dir, "memory", "AVATAR_WA_STOP")
        allowed_senders = (self.authorized_senders if self.authorized_senders is not None
                           else [target_chat])
        while not self._stop:
            if max_polls and polls >= max_polls:
                break
            if os.path.exists(stop_file):
                _walog(f"[WhatsAppBridge] stop-file detectado ({stop_file}); paro limpio.")
                break
            polls += 1
            try:
                messages = reader.read_recent(limit=10)
            except WhatsAppReadError as exc:
                _walog(f"[WhatsAppBridge] lectura fallida ({exc.code}): {exc.detail}")
                time.sleep(self.poll_seconds)
                continue
            for msg in messages:
                if not msg.text.strip():
                    continue
                own = (self.respond_to_own_outgoing and not msg.incoming
                       and _text_key(msg.text)
                       not in getattr(reader, "sent_texts", set()))
                if not msg.incoming and not own:
                    continue
                if msg.msg_id in self._replied_ids:
                    continue  # dedup: ya respondido (o descartado) antes
                # Los salientes salen de la cuenta del dueño; solo los entrantes se filtran.
                if msg.incoming and msg.sender not in allowed_senders:
                    _walog(f"[WhatsAppBridge] remitente no autorizado: {msg.sender}")
                    self._replied_ids.add(msg.msg_id)
                    self._save_state()
                    continue
                if self.observe_only:
                    _walog(f"[observe] {msg.sender}: {msg.text[:120]}")
                    self._replied_ids.add(msg.msg_id)
                    self._save_state()
                    continue
                if self.max_replies and replied >= self.max_replies:
                    _walog("[WhatsAppBridge] límite de respuestas alcanzado; paro.")
                    self._stop = True
                    break
                processed += 1
                try:
                    handled = self._owner_control(
                        msg.sender, msg.text, message_id=msg.msg_id,
                        extra_allowed=allowed_senders,
                    )
                    if handled is not None:
                        response = handled
                    else:
                        response = self.orchestrator.process_user_input(
                            msg.text, channel="remote",
                        )
                    send, shaped = self.format_whatsapp_reply(response)
                    if not send:
                        _walog(f"[WhatsAppBridge] respuesta suprimida por política "
                              f"({msg.msg_id}): {response[:80]!r}")
                    else:
                        self._deliver(sender=msg.sender, message_body=msg.text,
                                      response=shaped)
                    replied += 1
                    # Solo marcar respondido tras éxito o supresión deliberada (F-19).
                    self._replied_ids.add(msg.msg_id)
                    self._save_state()
                except Exception as exc:
                    # No marcar: el mensaje debe poder reintentarse en el siguiente poll.
                    _walog(f"[WhatsAppBridge] fallo procesando {msg.msg_id}: {exc}")
            if heartbeat_cb is not None:
                try:
                    heartbeat_cb({"polls": polls, "processed": processed,
                                  "replied": replied, "chat": target_chat})
                except Exception:
                    pass
            time.sleep(self.poll_seconds)
        summary = {"polls": polls, "processed": processed, "replied": replied,
                   "chat": target_chat}
        _walog(f"[WhatsAppBridge] fin del loop: {summary}")
        return summary

    def start_daemon(self):
        """
        Demonio de pasarela. Solo arranca el loop vivo si el operador lo activó en
        config (`whatsapp.autostart_live: true`); en caso contrario lo dice y no hace
        nada. Un reply-loop autónomo sin opt-in explícito sería incorrecto.
        """
        cfg = {}
        try:
            cfg = (self.orchestrator.config or {}).get("whatsapp", {}) or {}
        except Exception:
            pass
        if not cfg.get("autostart_live"):
            _walog("[AVATAR WhatsApp Daemon]: autostart_live desactivado en config; "
                  "el puente vivo requiere arranque explícito.")
            return
        self.start_live_bridge(target_chat=cfg.get("target_chat", "Mauro Vanegas 2025"))

    def start_live_bridge_legacy(self, target_chat: str = "Mauro Vanegas 2025"):
        """Nombre anterior del stub: ahora delega al puente real."""
        return self.start_live_bridge(target_chat=target_chat)

if __name__ == "__main__":
    bridge = WhatsAppBridge()
    bridge.start_live_bridge()
