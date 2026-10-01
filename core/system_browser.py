"""Abre una página en el navegador del sistema y no se queda con la ventana.

Playwright, sobre todo en modo oculto, no es una ventana que Mauro pueda ver
ni escanear. WhatsApp Web además rechaza el Chromium de Playwright.
"""
from __future__ import annotations

import subprocess
import sys

WHATSAPP_WEB_URL = "https://web.whatsapp.com"

_QR_CUES = (
    "abre", "abrir", "abra", "qr", "escan", "ventana", "web",
    "activar", "conect", "vincular", "código qr", "codigo qr",
)


def wants_visible_whatsapp(text: str) -> bool:
    folded = (text or "").lower()
    if "whatsapp" not in folded and "web.whatsapp" not in folded:
        return False
    return any(cue in folded for cue in _QR_CUES)


def open_system_browser(url: str) -> str:
    """Pide al navegador habitual que abra la URL. No espera ni la cierra."""
    target = (url or "").strip()
    if target != WHATSAPP_WEB_URL:
        return "URL_NO_PERMITIDA"
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/c", "start", "", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["xdg-open", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError as exc:
        return f"NO_ABRIO:{type(exc).__name__}"
    return "ABIERTO"


def open_whatsapp_web() -> str:
    return open_system_browser(WHATSAPP_WEB_URL)
