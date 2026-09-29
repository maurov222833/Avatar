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

from core.orchestrator import AvatarOrchestrator
from core.redaction import redact_secret_text
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
                 allowed_chat_ids=None):
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        self.bot_token = bot_token or self._load_token_from_config()
        entries = list(allowed_chat_ids) if allowed_chat_ids is not None else self._load_allowlist()
        if allowed_chat_id:
            entries.append(allowed_chat_id)
        self.allowed_chat_ids = {str(e).strip() for e in entries if str(e).strip().isdigit()}
        ignored = [e for e in entries if str(e).strip() and not str(e).strip().isdigit()]
        if ignored:
            print(f"[Telegram]: Entradas de allowlist ignoradas (se requiere ID numérico): {ignored}")
        self.orchestrator = AvatarOrchestrator()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        self.last_update_id = 0
        self._reported_chats = set()

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
        if key in self._reported_chats:
            return
        self._reported_chats.add(key)
        where = f"chat {chat.get('id', '?')} ({chat.get('type', '?')})"
        if self.allowed_chat_ids:
            print(f"[Telegram]: Mensaje rechazado del usuario {user_id} en {where}.")
        else:
            print(f"[Telegram]: Sin allowlist configurada; rechazado usuario {user_id} en {where}. "
                  f"Si eres tú, escribe al bot en privado y añade \"{user_id}\" a "
                  f"telegram.allowed_chat_ids en config.json.")

    def _redact(self, text) -> str:
        return redact_secret_text(str(text), [self.bot_token] if self.bot_token else [])

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

    def send_message(self, chat_id: str, text: str):
        if not self.base_url:
            print("[TelegramBridge]: Token de bot no configurado.")
            return
        
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[Error envio Telegram]: {self._redact(e)}")

    def send_photo(self, chat_id: str, photo_path: str, caption: str = ""):
        if not self.base_url or not os.path.exists(photo_path):
            print(f"[TelegramBridge Error]: Foto no encontrada en {photo_path}")
            return
        
        url = f"{self.base_url}/sendPhoto"
        try:
            with open(photo_path, "rb") as photo:
                requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"photo": photo}, timeout=20)
                print(f"[TelegramBridge]: Foto enviada exitosamente a Telegram (Chat {chat_id})")
        except Exception as e:
            print(f"[Error envio foto Telegram]: {self._redact(e)}")

    def start_polling(self):
        if not self.bot_token:
            print("[TelegramBridge]: Para activar Telegram, agrega tu 'bot_token' en config.json.")
            return

        if not self.allowed_chat_ids:
            print("[Telegram Bridge]: Sin allowlist (telegram.allowed_chat_ids): se rechazarán todas las órdenes.")
        print("[Telegram Bridge]: Escuchando ordenes remotas via Telegram (@Avatar_soberano_bot)...")
        while True:
            try:
                url = f"{self.base_url}/getUpdates?offset={self.last_update_id + 1}&timeout=30"
                response = requests.get(url, timeout=35)
                if response.status_code == 200:
                    data = response.json()
                    for result in data.get("result", []):
                        self.last_update_id = result["update_id"]
                        self.handle_message(result.get("message", {}) or {})
            except Exception as e:
                print(f"[Error en loop de Telegram]: {self._redact(e)}")
                time.sleep(5)

    def handle_message(self, message: dict):
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")

        if not self.is_authorized(message):
            self._report_rejected(message)
            return

        if not text:
            return

        print(f"\n[Orden remota recibida de Telegram]: {text}")
        text_lower = text.lower().strip()

        # Función auxiliar para detectar si el mensaje es una instrucción de sistema, pregunta o regla conversacional
        instruction_kws = [
            "integres", "integrar", "sistema", "comprendes", "entiendes", "configurar",
            "aprender", "guardar", "regla", "explicar", "instrucción", "instruccion",
            "retroalimentación", "feedback", "cada vez que", "no se debe", "por qué",
            "porque", "analizar", "diagnóstico", "opinas", "estipulado", "entiendas"
        ]
        is_instruction = any(kw in text_lower for kw in instruction_kws) or \
                         (text_lower.endswith("?") and len(text_lower.split()) > 5) or \
                         (len(text_lower.split()) > 10 and not any(text_lower.startswith(imp) for imp in ["reproduce ", "reproduzca ", "pon ", "ponme ", "toca ", "escuchar "]))

        # Detección de solicitud de captura de pantalla o foto
        if not is_instruction and any(kw in text_lower for kw in ["captura", "pantalla", "screenshot", "foto", "imagen"]):
            self.send_message(chat_id, "📸 Capturando pantalla del escritorio de tu PC...")
            img_path = self._perform("SCREEN_CAPTURE", {}, chat_id, "screen-capture", text).strip()
            if img_path and os.path.isfile(img_path):
                self.send_photo(chat_id, img_path, caption="⚡ Captura de pantalla de tu PC (Avatar AI)")
            else:
                self.send_message(chat_id, "⚠️ No se pudo obtener la captura de pantalla.")
            return

        # Detección directa de solicitud de pausa / silenciar / detener música
        if not is_instruction and any(kw in text_lower for kw in ["pausa", "pausar", "paúsala", "pausala", "detén", "deten", "silenciar", "parar", "stop"]):
            self.send_message(chat_id, "⏸️ Enviando señal multimedia para pausar la música en tu PC...")
            res_msg = self._perform("AUDIO_CONTROL", {"action": "pause"}, chat_id, "pause-audio", text)
            self.send_message(chat_id, f"AVATAR AI:\n{res_msg}")
            return

        # Detección directa de solicitud de música / reproducción
        if not is_instruction and any(kw in text_lower for kw in ["reproduce", "reproduzca", "cancion", "canción", "musica", "música"]):
            from tools.audio_tool import AudioTool
            song_query = AudioTool.sanitize_query(text)
            self.send_message(chat_id, f"🎵 Abriendo YouTube y reproduciendo directamente '{song_query}' en tu PC...")
            # Reproducir música abre un navegador: es un efecto externo y
            # pasa por el chokepoint para quedar registrado y sujeto a política.
            res_msg = self._perform("PLAY_AUDIO", {"audio_source": song_query}, chat_id, "play-music", text)
            self.send_message(chat_id, f"AVATAR AI:\n{res_msg}")
            return

        # Procesar con el orquestador
        raw_output = self.orchestrator.process_user_input(text)
        clean_output = ReasoningEngine.extract_clean_response(raw_output)

        # Evitar enviar bloques de codigo Python crudo como mensaje de chat conversacional
        if "class ScreenTool" in clean_output or "import os" in clean_output:
            clean_output = "Acción procesada en tu PC. Sistema listo para tu siguiente comando."

        self.send_message(chat_id, f"AVATAR AI:\n{self._redact(clean_output)}")
