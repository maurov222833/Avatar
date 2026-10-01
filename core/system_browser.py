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


_FOLLOW_UP = (
    "nuevamente", "otra vez", "de nuevo", "no vi", "no la vi",
    "repite", "repit", "proceso",
)

_LIE_MARKERS = (
    "navegador controlado",
    "frente a ti",
    "playwright",
    "ventana del navegador abierta",
    "esten listos",
    "estén listos",
)


def wants_visible_whatsapp(text: str, history=None) -> bool:
    folded = (text or "").lower()
    mentions = "whatsapp" in folded or "web.whatsapp" in folded
    if mentions and any(cue in folded for cue in _QR_CUES):
        return True
    recent = ""
    for turn in history or []:
        recent += " " + str((turn or {}).get("content") or "")
    recent = recent.lower()
    if "whatsapp" in recent and any(word in folded for word in _FOLLOW_UP):
        return True
    return False


def drop_model_status_lines(text: str) -> str:
    """Quita el estado que escribe el modelo. El que vale lo calcula el programa."""
    kept = []
    for line in (text or "").splitlines():
        if line.strip().lower().startswith("estado de la misión"):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def claims_visible_whatsapp(text: str) -> bool:
    folded = (text or "").lower()
    if "whatsapp" not in folded and "qr" not in folded:
        return False
    return any(mark in folded for mark in _LIE_MARKERS)


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
