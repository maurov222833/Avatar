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


class WhatsAppReadError(Exception):
    """Honest failure: reason codes, never a fake message list."""

    LOGIN_REQUIRED_QR = "LOGIN_REQUIRED_QR"
    BROWSER_LAUNCH_FAILED = "BROWSER_LAUNCH_FAILED"
    CHAT_NOT_FOUND = "CHAT_NOT_FOUND"
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

_COMPOSE_SELECTORS = [
    'div[data-testid="conversation-compose-box-input"]',
    'footer div[contenteditable="true"]',
    'div[contenteditable="true"][data-tab="10"]',
]


def _synthetic_id(incoming: bool, sender: str, timestamp: str, text: str) -> str:
    raw = f"{1 if incoming else 0}|{sender}|{timestamp}|{text}"
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _text_key(s: str) -> str:
    """Huella alfanumérica: ignora emojis, espacios y puntuación que el DOM altera."""
    import re
    return re.sub(r"[\W_]+", "", (s or "").lower(), flags=re.UNICODE)


class WhatsAppWebReader:
    """Reads and sends via WhatsApp Web DOM in a persistent Chromium profile."""

    def __init__(self, profile_dir: str, headless: bool = False,
                 launch_timeout_ms: int = 60000):
        self.profile_dir = profile_dir
        self.headless = headless
        self.launch_timeout_ms = launch_timeout_ms
        self._pw = None
        self._context = None
        self._page = None
        self.current_chat: str = ""
        # Textos que ESTE lector envió (normalizados): el loop no los reprocesa.
        self.sent_texts = set()

    # -- lifecycle ------------------------------------------------------
    def launch(self) -> None:
        # Idempotente: si ya hay página viva, no relanzar (evita doble lock del perfil).
        try:
            if self._page is not None and self._page.url:
                return
        except Exception:
            pass
        if not HAS_PLAYWRIGHT:
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
        if worker.is_alive():
            print("[WhatsAppReader] cierre colgado; mato solo procesos de ESTE perfil...",
                  flush=True)
            self._kill_own_chromium()

    def _kill_own_chromium(self) -> None:
        """Mata únicamente chromium cuyo cmdline use nuestro profile_dir. Nunca el del usuario."""
        import subprocess
        marker = os.path.abspath(self.profile_dir).lower()
        try:
            out = subprocess.run(
                ["wmic", "process", "where", "name='chrome.exe'",
                 "get", "ProcessId,CommandLine", "/format:csv"],
                capture_output=True, text=True, timeout=20)
        except Exception as exc:
            print(f"[WhatsAppReader] wmic no disponible: {exc}", flush=True)
            return
        for line in (out.stdout or "").splitlines():
            low = line.lower()
            if marker in low and "wmic" not in low:
                parts = [p.strip() for p in line.split(",")]
                pid = next((p for p in parts if p.isdigit()), "")
                if pid:
                    try:
                        subprocess.run(["taskkill", "/PID", pid, "/F"],
                                       capture_output=True, timeout=10)
                        print(f"[WhatsAppReader] proceso propio {pid} terminado.",
                              flush=True)
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
            # Tecleo real (fill no siempre dispara el filtrado de WA Web).
            # Si parece un número, buscar por los últimos dígitos: el "+" y los
            # espacios del formato internacional rompen el match exacto.
            digits = "".join(ch for ch in chat_name if ch.isdigit())
            query = digits[-8:] if len(digits) >= 7 else chat_name
            try:
                search.click()
            except Exception:
                pass
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.type(query, delay=30)
            page.wait_for_timeout(2000)
            # Clic directo en la sugerencia que contenga el nombre/dígitos (más
            # robusto que Enter, que con 0-1 coincidencias abre paneles ajenos).
            needle = (digits[-8:] if len(digits) >= 7
                      else "".join(ch for ch in chat_name if ch.isalnum())[-8:])
            suggestion = None
            try:
                suggestion = page.query_selector(
                    f'div[data-testid="chat-list"] span[title*="{needle}"]')
            except Exception:
                suggestion = None
            if suggestion is not None:
                try:
                    suggestion.click()
                except Exception:
                    page.keyboard.press("Enter")
            else:
                page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
            # Verificar que se abrió LA conversación pedida (cabecera dedicada,
            # no el primer header genérico de la página).
            header = ""
            for hsel in ('header[data-testid="conversation-header"]',
                         '#main header'):
                try:
                    header = page.inner_text(hsel) or ""
                except Exception:
                    header = ""
                if header:
                    break
            if not header:
                try:
                    header = page.inner_text("header") or ""
                except Exception:
                    header = ""
            hlow = header.lower()
            tail = "".join(ch for ch in chat_name if ch.isdigit())[-8:]
            if chat_name.lower() not in hlow and (not tail or tail not in hlow):
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                raise WhatsAppReadError(
                    WhatsAppReadError.CHAT_NOT_FOUND,
                    f"sin coincidencia para '{chat_name}' (cabecera: {header[:80]!r})")
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
            base = _synthetic_id(bool(r.get("incoming")), sender, timestamp, text)
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
            return sender.rstrip(":").strip() or "?", head.lstrip("[").strip()
        except Exception:
            return "?", ""

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
