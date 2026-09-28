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
    // data-pre-plain-text like "[12:03, 28/09/2026] Mauro: " lives on ancestors
    let meta = "";
    let node = c;
    for (let d = 0; d < 6 && node; d++) {
      if (node.getAttribute && node.getAttribute('data-pre-plain-text')) {
        meta = node.getAttribute('data-pre-plain-text');
        break;
      }
      node = node.parentElement;
    }
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

    # -- lifecycle ------------------------------------------------------
    def launch(self) -> None:
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

    def close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._context = None
        self._pw = None
        self._page = None

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

    def open_chat(self, chat_name: str) -> None:
        page = self._require_page()
        try:
            search = page.query_selector(
                'div[data-testid="chat-list-search"] div[contenteditable="true"], '
                'div[data-testid="chat-list-search"]')
            if search is None:
                raise WhatsAppReadError(
                    WhatsAppReadError.DOM_UNRECOGNIZED, "search box no encontrado")
            search.click()
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.type(chat_name, delay=20)
            page.wait_for_timeout(1500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
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
        for r in rows[-limit:]:
            text = (r.get("text") or "").strip()
            if not text:
                continue
            meta = r.get("meta") or ""
            sender, timestamp = self._parse_meta(meta)
            out.append(WhatsAppMessage(
                msg_id=_synthetic_id(bool(r.get("incoming")), sender, timestamp, text),
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
        # Read-back: el último mensaje saliente debe contener el texto.
        try:
            recent = self.read_recent(limit=3)
            norm = " ".join(text.split())
            for m in reversed(recent):
                if not m.incoming and norm[:60] in " ".join(m.text.split()):
                    return "Mensaje enviado y verificado por relectura en el chat."
        except WhatsAppReadError:
            pass
        raise WhatsAppReadError(
            WhatsAppReadError.SEND_UNVERIFIED,
            "Enter enviado pero el texto no aparece como saliente")


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
