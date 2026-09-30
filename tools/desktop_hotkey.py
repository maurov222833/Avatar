"""Safe desktop hotkeys for the owner (minimize, show desktop, etc.)."""
from __future__ import annotations

import re
import time
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


class DesktopHotkey:
    """
    Window/chrome hotkeys on Mauro's real desktop — not Playwright.

    Used for "minimiza el explorador", Win+D, etc. without inventing shell
    scripts. Goes through DESKTOP_HOTKEY (LOCAL_WRITE) so Telegram owner
    flow does not need per-click EXEC approval.
    """

    ALLOWED = {
        "minimize": "win+down",
        "minimize_window": "win+down",
        "maximizar": "win+up",
        "maximize": "win+up",
        "show_desktop": "win+d",
        "desktop": "win+d",
        "restore": "win+shift+up",
        "close_window": "alt+f4",
        "switch_window": "alt+tab",
    }

    @staticmethod
    def _focus_browser() -> bool:
        try:
            from tools.audio_tool import AudioTool
            return bool(AudioTool._focus_browser_matching("chrome") or AudioTool._focus_browser_matching("edge") or AudioTool._focus_youtube_or_browser())
        except Exception:
            return False

    @staticmethod
    def extract_action(text: str) -> Optional[str]:
        """Parse natural-language window requests → ALLOWED key (or None)."""
        if not text:
            return None
        low = " ".join(text.lower().strip().split())
        if any(
            k in low
            for k in (
                "minimiza", "minimizar", "minimize", "minimices", "minimice",
                "minimícela", "minimicela", "minimízala", "minimizala",
                "minimiza la ventana", "minimiza el explorador", "minimiza el navegador",
            )
        ):
            return "minimize"
        if any(
            k in low
            for k in (
                "maximiza", "maximizar", "maximize", "maximices", "maximice",
                "maximiza la ventana",
            )
        ):
            return "maximize"
        if any(
            k in low
            for k in (
                "muestra el escritorio", "mostrar escritorio", "muestra escritorio",
                "show desktop", "win+d", "win + d",
            )
        ):
            return "show_desktop"
        if re.search(r"(?i)\bcierra\s+la\s+ventana\b", low) or "cerrar ventana" in low:
            return "close_window"
        if "cambia de ventana" in low or "switch window" in low or "alt+tab" in low:
            return "switch_window"
        return None

    @staticmethod
    def extract_target(text: str) -> Optional[str]:
        if not text:
            return None
        low = text.lower()
        for tok in (
            "chrome", "edge", "navegador", "explorador", "explorer",
            "youtube", "browser", "ventana",
        ):
            if tok in low:
                return tok
        return None

    @staticmethod
    def run(action: str, target: Optional[str] = None) -> str:
        if not HAS_PYAUTOGUI:
            return "[Desktop]: Sin pyautogui no puedo enviar teclas de ventana."

        act = (action or "").strip().lower()
        # Spanish aliases
        aliases = {
            "minimiza": "minimize",
            "minimizar": "minimize",
            "minimizar ventana": "minimize",
            "minimiza la ventana": "minimize",
            "minimiza el explorador": "minimize",
            "minimiza el navegador": "minimize",
            "muestra escritorio": "show_desktop",
            "mostrar escritorio": "show_desktop",
            "escritorio": "show_desktop",
            "cierra ventana": "close_window",
            "cerrar ventana": "close_window",
        }
        if act in aliases:
            act = aliases[act]
        if act not in DesktopHotkey.ALLOWED and act not in DesktopHotkey.ALLOWED.values():
            # try substring
            for k, v in list(aliases.items()) + [(k, k) for k in DesktopHotkey.ALLOWED]:
                if k in act:
                    act = aliases.get(k, k) if k in aliases else k
                    break

        if act not in DesktopHotkey.ALLOWED:
            return (
                f"[Desktop]: Acción «{action}» no permitida. "
                f"Usa: {', '.join(sorted(DesktopHotkey.ALLOWED))}."
            )

        try:
            tgt = (target or "").lower()
            if any(x in tgt for x in ("chrome", "edge", "navegador", "explorer", "explorador", "youtube", "browser")) or not target:
                DesktopHotkey._focus_browser()
                time.sleep(0.25)
            elif target:
                try:
                    from core.ui_inspector import UIInspector
                    win = UIInspector.find_window_by_title(target)
                    if win:
                        UIInspector.focus_window(win.get("hwnd") or win.get("title"))
                        time.sleep(0.25)
                except Exception:
                    pass

            combo = DesktopHotkey.ALLOWED[act]
            keys = combo.split("+")
            # win key is 'win' in pyautogui
            pyautogui.hotkey(*keys)
            return f"[Desktop]: Enviado {combo} ({act}) a la ventana enfocada."
        except Exception as e:
            return f"[Desktop]: Error al enviar hotkey: {e}"
