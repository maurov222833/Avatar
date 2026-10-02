"""
WhatsApp Web reader — structured DOM access for the live bridge.

Why this exists
---------------
Avatar claimed a "WhatsApp bridge" while the daemon was a sleep-loop and an
attempted root-level script died mid-write with IndentationError. Reading was the
missing half: without it, "escríbeme por WhatsApp y te respondo" is fiction.

Design rules:
  1. Persistent Chromium profile, so the QR login survives restarts (scan once).
  2. Structured DOM reads via data-testid selectors with multi-generation fallbacks.
     WhatsApp Web changes its DOM; when nothing matches we raise an honest
     WhatsAppReadError instead of hallucinating messages.
  3. Sending verifies by read-back: the last outgoing bubble must contain the text.
  4. Message content from the web is UNTRUSTED input — it is returned tagged and the
     orchestrator (not this module) decides what it means.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover - environment without playwright
    HAS_PLAYWRIGHT = False


WA_WEB_URL = "https://web.whatsapp.com"



def _rlog(message: str, level: str = "INFO") -> None:
    try:
        from core.logging_util import log
        log(level, message, component="WhatsAppReader")
    except Exception:
        pass

class WhatsAppReadError(Exception):
    """Honest failure: reason codes, never a fake message list."""

    LOGIN_REQUIRED_QR = "LOGIN_REQUIRED_QR"
    BROWSER_LAUNCH_FAILED = "BROWSER_LAUNCH_FAILED"
    CHAT_NOT_FOUND = "CHAT_NOT_FOUND"
    CHAT_NOT_UNIQUE = "CHAT_NOT_UNIQUE"
    GROUP_REJECTED = "GROUP_REJECTED"
    DOM_UNRECOGNIZED = "DOM_UNRECOGNIZED"
    SEND_UNVERIFIED = "SEND_UNVERIFIED"

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


@dataclass
class WhatsAppMessage:
    msg_id: str
    incoming: bool
    sender: str
    text: str
    timestamp: str = ""


_READ_JS = r"""
() => {
  const pick = (root, sels) => {
    for (const s of sels) {
      const el = root.querySelector(s);
      if (el) return el;
    }
    return null;
  };
  const containers = Array.from(document.querySelectorAll(
    'div[data-testid="msg-container"], div.msg-container'));
  return containers.map((c, idx) => {
    const cls = c.className || "";
    const incoming = /message-in/.test(cls) || !!c.querySelector('.message-in');
    const textEl = pick(c, [
      '[data-testid="msg-text"] span.selectable-text',
      '[data-testid="msg-text"]',
      'span.selectable-text.copyable-text',
      '.copyable-text span',
      '.copyable-text'
    ]);
    // data-pre-plain-text like "[12:03, 28/09/2026] Mauro: " lives on an ancestor
    // (closest, sin límite de profundidad: en auto-chats va más hondo).
    let meta = "";
    const holder = c.closest('[data-pre-plain-text]');
    if (holder) meta = holder.getAttribute('data-pre-plain-text') || "";
    return {idx, incoming, text: textEl ? textEl.innerText : "", meta};
  });
}
"""

_EXACT_CHAT_CLICK_JS = r"""
(want) => {
  const nodes = Array.from(document.querySelectorAll(
    'div[data-testid="chat-list"] span[title], #pane-side span[title]'));
  const exact = nodes.filter((n) => (n.getAttribute("title") || "") === want);
  if (exact.length === 1) exact[0].click();
  return {match_count: exact.length};
}
"""

_CHAT_HEADER_JS = r"""
() => {
  const header = document.querySelector(
    'header[data-testid="conversation-header"], #main header');
  if (!header) return {title: "", is_group: false};
  const titled = header.querySelector("span[title]");
  const title = titled ? (titled.getAttribute("title") || "") : "";
  let isGroup = !!header.querySelector('[data-icon="default-group"], [data-icon="group"]');
  const text = header.innerText || "";
  if (/participan|participants/i.test(text)) isGroup = true;
  return {title, is_group: isGroup};
}
"""

_COMPOSE_SELECTORS = [
    'div[data-testid="conversation-compose-box-input"]',
    'footer div[contenteditable="true"]',
    'div[contenteditable="true"][data-tab="10"]',
]


def _synthetic_id(incoming: bool, sender: str, timestamp: str, text: str) -> str:
    raw = f"{1 if incoming else 0}|{sender}|{timestamp}|{text}"
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def accept_configured_chat(configured: str, title: str, match_count: int, is_group: bool) -> str:
    """Vacío si el chat configurado coincide exacto, una sola vez, y no es grupo.

    El nombre visible no autoriza un parecido ni un grupo. «Mauro Vanegas 2025»
    es el chat propio solo cuando el operador lo configuró así, carácter por carácter.
    """
    if is_group:
        return WhatsAppReadError.GROUP_REJECTED
    if not configured or int(match_count) != 1 or title != configured:
        return WhatsAppReadError.CHAT_NOT_UNIQUE
    return ""


def _text_key(s: str) -> str:
    """Huella alfanumérica: ignora emojis, espacios y puntuación que el DOM altera."""
    import re
    return re.sub(r"[\W_]+", "", (s or "").lower(), flags=re.UNICODE)


class WhatsAppWebReader:
    """Reads and sends via WhatsApp Web DOM in a persistent Chromium profile."""

    #: Segundos tras los cuales un lock sin refrescar se considera rancio
    #: (el dueño murió sin limpiar). Evita esperas eternas.
    LOCK_TTL_S = 180.0

    def __init__(self, profile_dir: str, headless: bool = False,
                 launch_timeout_ms: int = 60000):
        self.profile_dir = profile_dir
        self.headless = headless
        self.launch_timeout_ms = launch_timeout_ms
        self._pw = None
        self._context = None
        self._page = None
        self.current_chat: str = ""
        self.chat_gate: str = ""
        # Textos que ESTE lector envió (normalizados): el loop no los reprocesa.
        self.sent_texts = set()

    def _lock_path(self) -> str:
        return os.path.abspath(self.profile_dir) + ".lock"

    def _take_lock(self) -> None:
        """Un solo dueño del perfil: sin esto dos navegadores pelean y mueren en blanco."""
        import json as _json
        import time as _time
        path = self._lock_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            age = _time.time() - float(data.get("ts", 0))
            if age < self.LOCK_TTL_S:
                raise WhatsAppReadError(
                    WhatsAppReadError.BROWSER_LAUNCH_FAILED,
                    f"PERFIL_OCUPADO: otro proceso lo tomó hace {age:.0f}s; "
                    "detén la tarea 24/7 o espera y reintenta")
        except FileNotFoundError:
            pass
        except WhatsAppReadError:
            raise
        except Exception:
            pass  # lock corrupto = rancio: se toma por encima
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                _json.dump({"pid": os.getpid(), "ts": _time.time()}, f)
        except Exception as exc:
            raise WhatsAppReadError(
                WhatsAppReadError.BROWSER_LAUNCH_FAILED,
                f"no se pudo tomar el lock: {exc}"[:200])

    def _refresh_lock(self) -> None:
        """Mantiene vivo el lock mientras la ventana espera el escaneo."""
        import json as _json
        import time as _time
        path = self._lock_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                _json.dump({"pid": os.getpid(), "ts": _time.time()}, f)
        except Exception:
            pass

    def _release_lock(self) -> None:
        try:
            if os.path.exists(self._lock_path()):
                os.remove(self._lock_path())
        except Exception:
            pass

    def wait_for_login(
        self,
        hold_seconds: Optional[float] = 300,
        poll_seconds: float = 2.0,
        stop_path: str = "",
    ) -> str:
        """Deja la ventana abierta hasta LOGGED_IN, el archivo de parada o el plazo.

        hold_seconds None no corta por tiempo: solo para cuando hay sesión o parada.
        """
        state = self.login_state()
        started = time.time()
        while state != "LOGGED_IN":
            if stop_path and os.path.exists(stop_path):
                break
            if hold_seconds is not None and (time.time() - started) >= float(hold_seconds):
                break
            self._refresh_lock()
            time.sleep(max(0.05, float(poll_seconds)))
            state = self.login_state()
        return state

    # -- lifecycle ------------------------------------------------------
    def launch(self) -> None:
        # Idempotente: si ya hay página viva, no relanzar (evita doble lock del perfil).
        try:
            if self._page is not None and self._page.url:
                return
        except Exception:
            pass
        self._take_lock()
        if not HAS_PLAYWRIGHT:
            self._release_lock()
            raise WhatsAppReadError(
                WhatsAppReadError.BROWSER_LAUNCH_FAILED,
                "playwright no instalado")
        try:
            os.makedirs(self.profile_dir, exist_ok=True)
            self._pw = sync_playwright().start()
            self._context = self._pw.chromium.launch_persistent_context(
                self.profile_dir, headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            pages = self._context.pages
            self._page = pages[0] if pages else self._context.new_page()
            self._page.goto(WA_WEB_URL, timeout=self.launch_timeout_ms)
            self._page.wait_for_timeout(4000)
        except WhatsAppReadError:
            raise
        except Exception as exc:
            self.close()
            raise WhatsAppReadError(
                WhatsAppReadError.BROWSER_LAUNCH_FAILED, str(exc)[:300])

    def close(self, timeout_s: float = 25.0) -> None:
        """Cierre con watchdog: si el chromium headed se cuelga, no cuelga el loop."""
        import threading

        def _do():
            try:
                if self._page is not None:
                    try:
                        self._page.close()
                    except Exception:
                        pass
                if self._context is not None:
                    try:
                        self._context.close()
                    except Exception:
                        pass
            finally:
                try:
                    if self._pw is not None:
                        self._pw.stop()
                except Exception:
                    pass

        worker = threading.Thread(target=_do, daemon=True)
        worker.start()
        worker.join(timeout_s)
        self._context = None
        self._pw = None
        self._page = None
        # Barrido garantizado: tras cada cierre no debe quedar chromium de ESTE
        # perfil. Sin esto cada herramienta deja ventanas blancas huerfanas.
        leftovers = self._own_chromium_pids()
        if worker.is_alive() or leftovers:
            _rlog("[WhatsAppReader] barriendo chromium propio restante...")
            self._kill_own_chromium()
        self._release_lock()

    def _own_chromium_pids(self) -> list:
        """PIDs de chromium cuyo cmdline usa nuestro profile_dir. Solo lectura."""
        import subprocess
        marker = os.path.abspath(self.profile_dir).lower()
        try:
            out = subprocess.run(
                ["wmic", "process", "where", "name='chrome.exe'",
                 "get", "ProcessId,CommandLine", "/format:csv"],
                capture_output=True, text=True, timeout=20)
        except Exception as exc:
            _rlog(f"[WhatsAppReader] wmic no disponible: {exc}")
            return []
        pids = []
        for line in (out.stdout or "").splitlines():
            low = line.lower()
            if marker in low and "wmic" not in low:
                parts = [p.strip().strip('"') for p in line.rsplit(",", 1)]
                pid = parts[-1] if parts else ""
                if pid.isdigit():
                    pids.append(pid)
        return pids

    def _kill_own_chromium(self) -> None:
        # Mata unicamente los PIDs de _own_chromium_pids. Nunca el del usuario.
        import subprocess
        for pid in self._own_chromium_pids():
            try:
                subprocess.run(['taskkill', '/PID', pid, '/F'],
                               capture_output=True, timeout=10)
                _rlog(f"[WhatsAppReader] proceso propio {pid} terminado.")
            except Exception:
                pass

    def _require_page(self):
        if self._page is None:
            raise WhatsAppReadError(
                WhatsAppReadError.BROWSER_LAUNCH_FAILED, "navegador no iniciado")
        return self._page

    # -- state ----------------------------------------------------------
    def login_state(self) -> str:
        """LOGGED_IN | QR_REQUIRED | UNKNOWN — read-only probe, never logs in."""
        page = self._require_page()
        try:
            if page.query_selector('div[data-testid="chat-list"], div#pane-side'):
                return "LOGGED_IN"
            if page.query_selector('canvas[aria-label], div[data-testid="qrcode"]'):
                return "QR_REQUIRED"
            page.wait_for_timeout(5000)
            if page.query_selector('div[data-testid="chat-list"], div#pane-side'):
                return "LOGGED_IN"
            if page.query_selector('canvas[aria-label], div[data-testid="qrcode"]'):
                return "QR_REQUIRED"
            return "UNKNOWN"
        except Exception as exc:
            raise WhatsAppReadError(
                WhatsAppReadError.DOM_UNRECOGNIZED, f"login_state: {exc}"[:200])

    _SEARCH_CANDIDATES = [
        '#side input[aria-label*="Buscar"]',
        'input[aria-label*="chat"]',
        'div[data-testid="chat-list-search"] div[contenteditable="true"]',
        '#side div[contenteditable="true"]',
        'div[role="textbox"]',
    ]

    def open_chat(self, chat_name: str) -> None:
        page = self._require_page()
        try:
            try:
                page.wait_for_selector(
                    'div[data-testid="chat-list"], div#pane-side', timeout=30000)
            except Exception:
                raise WhatsAppReadError(
                    WhatsAppReadError.DOM_UNRECOGNIZED,
                    "lista de chats no cargo (sesion lenta o DOM desconocido)")
            search = None
            # El buscador es una píldora ("Buscar un chat…") que solo crea el input
            # al hacer clic: primero revelar, luego esperar el editable (hasta ~30s).
            for reveal in ('text=Buscar un chat', 'text=Search a chat',
                           'div[data-testid="chat-list-header"]'):
                try:
                    page.click(reveal, timeout=5000)
                    break
                except Exception:
                    continue
            for _ in range(15):
                for sel in self._SEARCH_CANDIDATES:
                    try:
                        search = page.query_selector(sel)
                    except Exception:
                        search = None
                    if search:
                        break
                if search:
                    break
                page.wait_for_timeout(2000)
            if search is None:
                raise WhatsAppReadError(
                    WhatsAppReadError.DOM_UNRECOGNIZED, "search box no encontrado")
            try:
                tag = search.evaluate("(el) => el.tagName")
            except Exception:
                tag = ""
            # Nombre completo. Un sufijo de dígitos o un Enter abrirían otro chat.
            try:
                search.click()
            except Exception:
                pass
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.type(chat_name, delay=30)
            page.wait_for_timeout(2000)
            picked = page.evaluate(_EXACT_CHAT_CLICK_JS, chat_name)
            if not isinstance(picked, dict):
                raise WhatsAppReadError(
                    WhatsAppReadError.DOM_UNRECOGNIZED, "identidad de chat ilegible")
            page.wait_for_timeout(500)
            header = page.evaluate(_CHAT_HEADER_JS)
            if not isinstance(header, dict):
                header = {}
            title = str(header.get("title") or "")
            reason = accept_configured_chat(
                chat_name,
                title,
                int(picked.get("match_count") or 0),
                bool(picked.get("is_group") or header.get("is_group")),
            )
            if reason:
                self.chat_gate = reason
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                raise WhatsAppReadError(
                    reason,
                    f"se rechaza '{chat_name}' (titulo={title!r}, "
                    f"coincidencias={picked.get('match_count')})")
            self.chat_gate = ""
            self.current_chat = chat_name
        except WhatsAppReadError:
            raise
        except Exception as exc:
            raise WhatsAppReadError(
                WhatsAppReadError.CHAT_NOT_FOUND,
                f"no se pudo abrir '{chat_name}': {exc}"[:200])

    # -- read -----------------------------------------------------------
    def read_recent(self, limit: int = 10) -> List[WhatsAppMessage]:
        page = self._require_page()
        try:
            rows = page.evaluate(_READ_JS)
        except Exception as exc:
            raise WhatsAppReadError(
                WhatsAppReadError.DOM_UNRECOGNIZED, f"extract: {exc}"[:200])
        if not rows:
            raise WhatsAppReadError(
                WhatsAppReadError.DOM_UNRECOGNIZED,
                "0 contenedores de mensaje: chat vacío o DOM desconocido")
        out: List[WhatsAppMessage] = []
        seen_counts: Dict[str, int] = {}
        for r in rows[-limit:]:
            text = (r.get("text") or "").strip()
            if not text:
                continue
            meta = r.get("meta") or ""
            sender, timestamp = self._parse_meta(meta)
            base = _synthetic_id(bool(r.get("incoming")), self._id_sender(meta),
                                 timestamp, text)
            # Desempata textos idénticos (p. ej. "Hola Avatar" x6): el occurrence
            # es estable mientras el lote no deslice esos mensajes fuera.
            occ = seen_counts.get(base, 0)
            seen_counts[base] = occ + 1
            out.append(WhatsAppMessage(
                msg_id=f"{base}#{occ}" if occ else base,
                incoming=bool(r.get("incoming")),
                sender=sender,
                text=text,
                timestamp=timestamp,
            ))
        return out

    @staticmethod
    def _parse_meta(meta: str):
        # "[12:03, 28/09/2026] Mauro: " -> ("Mauro", "12:03 28/09/2026")
        try:
            head, _, sender = meta.partition("] ")
            return sender.strip().removesuffix(":").strip() or "?", head.lstrip("[").strip()
        except Exception:
            return "?", ""

    @staticmethod
    def _id_sender(meta: str) -> str:
        # Frozen form used inside msg ids: changing it would re-key messages already
        # persisted as replied and make the bridge process old orders again.
        try:
            return meta.partition("] ")[2].rstrip(":").strip() or "?"
        except Exception:
            return "?"

    # -- send -----------------------------------------------------------
    def send_text(self, text: str) -> str:
        """Type into the chat box and verify by read-back. Returns a report string."""
        page = self._require_page()
        if not text or not text.strip():
            return "[WhatsApp]: Mensaje vacío, no enviado."
        box = None
        for sel in _COMPOSE_SELECTORS:
            try:
                box = page.query_selector(sel)
            except Exception:
                box = None
            if box:
                break
        if box is None:
            raise WhatsAppReadError(
                WhatsAppReadError.DOM_UNRECOGNIZED, "compose box no encontrado")
        try:
            box.click()
            page.keyboard.press("ControlOrMeta+a")
            # Pegar por portapapeles evita problemas con emojis/teclas especiales.
            import pyperclip
            pyperclip.copy(text)
            page.keyboard.press("ControlOrMeta+v")
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1200)
        except Exception as exc:
            raise WhatsAppReadError(
                WhatsAppReadError.SEND_UNVERIFIED, f"envío: {exc}"[:200])
        # Read-back con reintentos: la red puede tardar varios segundos en reflejarlo.
        # Comparación por huella alfanumérica: el DOM altera emojis/espacios.
        norm = " ".join(text.split())
        want = _text_key(norm)[:40]

        def _appeared():
            try:
                recent = self.read_recent(limit=5)
            except WhatsAppReadError:
                return False
            return any(not m.incoming and want and want in _text_key(m.text)
                       for m in recent)

        import time as _time
        for _ in range(7):
            _time.sleep(1.5)
            if _appeared():
                self.sent_texts.add(_text_key(norm))
                return ("[READBACK_VERIFIED] Mensaje enviado y verificado "
                        "por relectura en el chat.")
        # Fallback: botón Enviar en vez de Enter.
        for sel in ('button[aria-label="Enviar"]', 'button[data-testid="send"]',
                    'footer button[type="submit"]'):
            try:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    break
            except Exception:
                continue
        for _ in range(5):
            _time.sleep(1.5)
            if _appeared():
                self.sent_texts.add(_text_key(norm))
                return ("[READBACK_VERIFIED] Mensaje enviado y verificado "
                        "por relectura en el chat (botón Enviar).")
        raise WhatsAppReadError(
            WhatsAppReadError.SEND_UNVERIFIED,
            "texto pegado pero no aparece como saliente tras Enter ni botón")



def profile_lock_fresh(profile_dir: str) -> str:
    """Texto si otro dueño tiene el perfil. Vacío si se puede abrir una ventana."""
    import json as _json
    path = os.path.abspath(profile_dir) + ".lock"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = _json.load(handle)
        age = time.time() - float(data.get("ts", 0))
    except (OSError, ValueError, TypeError):
        return ""
    if age < WhatsAppWebReader.LOCK_TTL_S:
        return f"pid={data.get('pid')} hace {age:.0f}s"
    return ""


def run_blocking(fn, timeout_s: float = 300.0):
    """
    Ejecuta fn en un hilo dedicado SIN event loop y espera el resultado.

    La Sync API de Playwright se niega a correr dentro de un loop asyncio
    (la GUI FastAPI/uvicorn invoca al orquestador desde uno). Un hilo fresco no
    tiene loop, así que el lector funciona igual dentro y fuera de la app.
    """
    import threading
    result: Dict[str, Any] = {}
    errors: Dict[str, Any] = {}

    def _worker():
        try:
            result["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - se propaga al llamador
            errors["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        raise WhatsAppReadError(
            WhatsAppReadError.BROWSER_LAUNCH_FAILED,
            f"timeout {timeout_s}s esperando al navegador")
    if "error" in errors:
        raise errors["error"]
    return result.get("value")


def probe_environment() -> Dict[str, Any]:
    """Read-only prerequisite check: playwright + chromium launch. No WhatsApp touch."""
    if not HAS_PLAYWRIGHT:
        return {"playwright": False, "error": "playwright no instalado"}
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        try:
            b = pw.chromium.launch(headless=True)
            b.close()
            return {"playwright": True, "chromium": True}
        finally:
            pw.stop()
    except Exception as exc:
        return {"playwright": True, "chromium": False, "error": str(exc)[:300]}
