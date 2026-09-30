import os
import sys
import time
import re
import subprocess
import webbrowser
import requests
import ctypes
from urllib.parse import quote_plus
from typing import Optional

try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


class AudioTool:
    """
    Reproducción y control multimedia en el navegador DEL SISTEMA (Chrome/Edge
    de Mauro vía webbrowser/pyautogui) — NO en Playwright/BROWSER_*.

    Por eso cerrar YouTube con BROWSER_CLOSE no afecta la pestaña que abrió
    PLAY_AUDIO: son dos navegadores distintos.
    """
    _browser_opened = False
    _is_playing = False
    _last_query = ""
    _last_url = ""

    @staticmethod
    def sanitize_query(raw_query: str) -> str:
        """Aísla el nombre de la canción quitando muletillas y órdenes."""
        if not raw_query:
            return "bonito bonito"

        text = raw_query.strip()

        # Si hay "canción/cancion/tema …", tomar lo que sigue (suele ser el título).
        after_song = re.search(
            r"(?is)\b(?:canci[oó]n|tema|track|video)\s*[,:\-]?\s+(.+)$",
            text,
        )
        if after_song:
            text = after_song.group(1).strip()

        # Prefijos conversacionales / órdenes (incluye typos: reproduscas, reproduzcas).
        fillers = [
            r"^\s*(?:si|sí)\s*[,.]?\s*",
            r"\bquiero\s+que\s+",
            r"\b(?:me\s+)?(?:puedes|podes|podr[ií]as)\s+",
            r"\breprodu[szc]+(?:e|es|a|as|ca|cas)?\b",
            r"\brepruduce\b",
            r"\bpon(?:me|nos)?\b",
            r"\btoca(?:me)?\b",
            r"\bescuchar\b",
            r"\bdale\s+play(?:\s+a)?\b",
            r"\bahora\b",
            r"\bpor\s+favor\b",
            r"\ben\s+(?:el\s+)?(?:mismo\s+)?youtube\b",
            r"\be\.\s*youtube\b",
            r"\byoutube\b",
            r"\bla\s+canci[oó]n\b",
            r"\bcanci[oó]n\b",
            r"\bmusica\b",
            r"\bmúsica\b",
            r"\ben\s+el\s+mismo\b",
            r"\bno\s+abras\s+otro\b",
            r"\bno\s+habras\s+otro\b",
            r"\bque\s+ya\s+se\s+encuentra\s+abierto\b",
            r"\bve\s+a\s+mi\s+navegador(?:\s+y)?\b",
            r"\babre\s+youtube(?:\s+y)?\b",
            r"\bnuevamente\b",
            r"\besa\s+misma\b",
            r"\besta\s+misma\b",
            r"\bpon\s+la\b",
            r"\bla\b",
        ]
        clean = text
        for pat in fillers:
            clean = re.sub(rf"(?i){pat}", " ", clean)

        clean = re.sub(r"[^\w\s]", " ", clean)
        clean = " ".join(clean.split()).strip()
        return clean if clean else "bonito bonito"

    @staticmethod
    def get_direct_youtube_url(song_name: str) -> str:
        """URL directa del primer resultado de YouTube (o búsqueda)."""
        clean_name = AudioTool.sanitize_query(song_name)
        encoded = quote_plus(clean_name)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            res = requests.get(search_url, headers=headers, timeout=8)
            if res.status_code == 200:
                ids = re.findall(r'"videoId":"([^"]+)"', res.text)
                if ids:
                    first_id = ids[0]
                    direct_url = f"https://www.youtube.com/watch?v={first_id}&autoplay=1"
                    print(f"[AudioTool]: Video ID resuelto directamente -> {first_id}")
                    return direct_url
        except Exception as e:
            print(f"[AudioTool Warning Direct URL]: {e}")

        return search_url

    @staticmethod
    def open_or_reuse_tab(target_url: str):
        """Abre o reutiliza la pestaña del navegador del sistema (no Playwright)."""
        if AudioTool._browser_opened and HAS_PYAUTOGUI:
            try:
                AudioTool._focus_youtube_or_browser()
                pyperclip.copy(target_url)
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.2)
                pyautogui.hotkey("ctrl", "v")
                pyautogui.press("enter")
                print("[AudioTool]: Pestaña existente reutilizada con éxito.")
                AudioTool._last_url = target_url
                return
            except Exception as e:
                print(f"[AudioTool Reuse Warning]: {e}")

        webbrowser.open(target_url)
        AudioTool._browser_opened = True
        AudioTool._last_url = target_url

    @staticmethod
    def _focus_youtube_or_browser() -> bool:
        """Intenta enfocear la ventana del sistema cuya título menciona YouTube."""
        try:
            from core.ui_inspector import UIInspector

            wins = UIInspector.list_windows() or []
            ranked = []
            for w in wins:
                title = str(w.get("title") or "")
                low = title.lower()
                score = 0
                if "youtube" in low:
                    score += 10
                if "chrome" in low or "edge" in low or "msedge" in str(w.get("process_name", "")).lower():
                    score += 2
                if score:
                    ranked.append((score, w))
            ranked.sort(key=lambda x: -x[0])
            if ranked:
                target = ranked[0][1]
                hwnd = target.get("hwnd") or target.get("title")
                return bool(UIInspector.focus_window(hwnd))
        except Exception as e:
            print(f"[AudioTool Focus Warning]: {e}")
        return False

    @staticmethod
    def _send_media_play_pause():
        """Tecla multimedia global Play/Pause (toggle del SO)."""
        if sys.platform == "win32":
            # VK_MEDIA_PLAY_PAUSE = 0xB3 (179). Nota: 0xAF es volume down.
            ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
        if HAS_PYAUTOGUI:
            try:
                pyautogui.press("playpause")
            except Exception:
                pass

    @staticmethod
    def _youtube_press_k():
        """Tecla K en YouTube (play/pause del player de la pestaña enfocada)."""
        if not HAS_PYAUTOGUI:
            return False
        try:
            AudioTool._focus_youtube_or_browser()
            time.sleep(0.2)
            sw, sh = pyautogui.size()
            pyautogui.click(sw // 2, sh // 2 - 20)
            time.sleep(0.15)
            pyautogui.press("k")
            return True
        except Exception as e:
            print(f"[AudioTool YouTube K Warning]: {e}")
            return False

    @staticmethod
    def play_local_audio(file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"[Error Audio]: El archivo de audio '{file_path}' no existe en disco."

        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            else:
                subprocess.Popen(["xdg-open", file_path])
            AudioTool._is_playing = True
            return f"[Audio]: Reproduciendo archivo local '{os.path.basename(file_path)}' en tu PC."
        except Exception as e:
            return f"[Error al reproducir audio local]: {str(e)}"

    @staticmethod
    def force_video_play():
        """Click + K/espacio para arrancar el video en la pestaña del sistema."""
        try:
            time.sleep(2.5)
            if HAS_PYAUTOGUI:
                AudioTool._focus_youtube_or_browser()
                sw, sh = pyautogui.size()
                pyautogui.click(sw // 2, sh // 2 - 20)
                time.sleep(0.2)
                pyautogui.press("k")
                pyautogui.press("space")
            elif sys.platform == "win32":
                width = ctypes.windll.user32.GetSystemMetrics(0)
                height = ctypes.windll.user32.GetSystemMetrics(1)
                ctypes.windll.user32.SetCursorPos(width // 2, height // 2 - 20)
                ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x4B, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x4B, 0, 2, 0)
                ctypes.windll.user32.keybd_event(0x20, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x20, 0, 2, 0)
            print("[AudioTool]: Fuerza de reproducción ejecutada con éxito.")
            AudioTool._is_playing = True
        except Exception as e:
            print(f"[AudioTool Warning Play]: {e}")

    @staticmethod
    def pause_audio(force: Optional[str] = "pause") -> str:
        """
        Pausa o reanuda en el navegador del sistema.

        force: 'pause' | 'resume' | 'toggle'
        Evita el doble-toggle: si ya está pausado y piden pausa otra vez, no pulsa.
        """
        want = (force or "pause").lower().strip()
        try:
            if want == "pause" and not AudioTool._is_playing:
                return (
                    "[Audio]: Ya estaba en pausa (no volví a pulsar Play/Pause para "
                    "no reanudarla por error). Di 'reanuda' si quieres continuar."
                )
            if want == "resume" and AudioTool._is_playing:
                return "[Audio]: Ya estaba reproduciendo."

            used_yt = AudioTool._youtube_press_k()
            if not used_yt:
                AudioTool._send_media_play_pause()

            if want == "pause":
                AudioTool._is_playing = False
                return "[Audio]: Pausa enviada a YouTube/navegador del sistema."
            if want == "resume":
                AudioTool._is_playing = True
                return "[Audio]: Reanudación enviada a YouTube/navegador del sistema."
            AudioTool._is_playing = not AudioTool._is_playing
            state = "reproduciendo" if AudioTool._is_playing else "en pausa"
            return f"[Audio]: Play/Pause enviado. Estado estimado: {state}."
        except Exception as e:
            return f"[Error al pausar multimedia]: {str(e)}"

    @staticmethod
    def close_youtube_tab() -> str:
        """
        Cierra la pestaña de YouTube en el navegador DEL SISTEMA (la misma que
        abrió PLAY_AUDIO). No usa Playwright: BROWSER_CLOSE no sirve aquí.
        """
        try:
            focused = AudioTool._focus_youtube_or_browser()
            if not HAS_PYAUTOGUI:
                return (
                    "[Audio]: Sin pyautogui no puedo cerrar la pestaña. "
                    "Enfoca YouTube y pulsa Ctrl+W."
                )

            if not focused and not AudioTool._browser_opened:
                return (
                    "[Audio]: No encontré una ventana de YouTube abierta. "
                    "Si la ves, enfócala y usa Ctrl+W."
                )

            time.sleep(0.25)
            # Confirmar que la pestaña activa parece YouTube (barra de direcciones).
            try:
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.15)
                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.1)
                url = ""
                try:
                    url = (pyperclip.paste() or "").lower()
                except Exception:
                    url = ""
                # Escape address bar then close tab
                pyautogui.press("escape")
                time.sleep(0.05)
                if url and ("youtube.com" not in url and "youtu.be" not in url):
                    # Aún intentamos Ctrl+W solo si habíamos abierto nosotros la sesión.
                    if not AudioTool._browser_opened:
                        return (
                            "[Audio]: La ventana enfocada no parece YouTube "
                            f"(URL: {url[:80] or 'desconocida'}). No cerré otras pestañas."
                        )
            except Exception:
                pass

            pyautogui.hotkey("ctrl", "w")
            AudioTool._browser_opened = False
            AudioTool._is_playing = False
            AudioTool._last_url = ""
            return (
                "[Audio]: Cerrada la pestaña de YouTube en tu navegador del sistema "
                "(Chrome/Edge). Nota: BROWSER_* / Playwright es otro navegador y no "
                "afecta esta pestaña."
            )
        except Exception as e:
            return f"[Error al cerrar YouTube]: {str(e)}"

    @staticmethod
    def control_audio(args: Optional[dict] = None) -> str:
        """Dispatcher para AUDIO_CONTROL: pause | resume | toggle | close."""
        args = args or {}
        action = str(args.get("action") or args.get("params") or "pause").lower().strip()
        if action in ("close", "cerrar", "close_tab", "close_youtube", "cerrar_pestana", "cerrar_pestaña"):
            return AudioTool.close_youtube_tab()
        if action in ("resume", "play", "reanudar", "continua", "continuar"):
            return AudioTool.pause_audio(force="resume")
        if action in ("toggle", "playpause", "play_pause"):
            return AudioTool.pause_audio(force="toggle")
        return AudioTool.pause_audio(force="pause")

    @staticmethod
    def play_online_music(song_name: str) -> str:
        """Busca, abre/reutiliza pestaña del sistema y reproduce."""
        try:
            clean_name = AudioTool.sanitize_query(song_name)
            AudioTool._last_query = clean_name
            target_url = AudioTool.get_direct_youtube_url(clean_name)
            AudioTool.open_or_reuse_tab(target_url)
            AudioTool.force_video_play()
            return (
                f"[Audio]: Reproduciendo «{clean_name}» en YouTube "
                f"(navegador del sistema, pestaña reutilizada)."
            )
        except Exception as e:
            return f"[Error al buscar/reproducir música]: {str(e)}"
