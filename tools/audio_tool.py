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




def _alog(message: str, level: str = "INFO") -> None:
    try:
        from core.logging_util import log
        log(level, message, component="AudioTool")
    except Exception:
        pass

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
            r"\bcambia(?:r)?(?:\s+la\s+canci[oó]n)?(?:\s+(?:a|por))?\b",
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
                    _alog(f"[AudioTool]: Video ID resuelto directamente -> {first_id}")
                    return direct_url
        except Exception as e:
            _alog(f"[AudioTool Warning Direct URL]: {e}")

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
                _alog("[AudioTool]: Pestaña existente reutilizada con éxito.")
                AudioTool._last_url = target_url
                return
            except Exception as e:
                _alog(f"[AudioTool Reuse Warning]: {e}")

        webbrowser.open(target_url)
        AudioTool._browser_opened = True
        AudioTool._last_url = target_url

    @staticmethod
    def extract_song_request(text: str) -> Optional[str]:
        """
        Detecta pedidos de poner/cambiar canción y devuelve el título limpio.
        Ej: 'cambia a Despacito', 'ponme Bonito bonito', 'ahora reproduce X'.
        """
        if not text:
            return None
        raw = text.strip()
        low = raw.lower()
        change_hints = (
            "cambia", "cambiar", "pon ", "ponme", "ponme ", "toca ", "tocame",
            "reproduce", "reproduscas", "reproduzcas", "reproduzca", "cancion",
            "canción", "musica", "música",
        )
        if not any(h in low for h in change_hints):
            return None
        # «cambia (la canción) a/por TITLE»
        m = re.search(
            r"(?is)\bcambia(?:r)?(?:\s+la\s+canci[oó]n)?\s+(?:a|por|por\s+la)?\s*(.+)$",
            raw,
        )
        if m:
            return AudioTool.sanitize_query(m.group(1))
        return AudioTool.sanitize_query(raw)

    @staticmethod
    def extract_close_target(text: str) -> Optional[str]:
        """Extrae el objetivo de 'cierra la pestaña de YouTube' → 'youtube'."""
        if not text:
            return None
        low = text.lower()
        if not any(k in low for k in ("cierra", "cerrar", "close")):
            return None
        # "cierra la ventana" is not a browser tab. Only a tab word or a known app.
        known = ("youtube", "youtu", "chrome", "edge", "spotify", "gmail")
        has_tab = "pestaña" in low or "pestana" in low or re.search(r"\btab\b", low)
        if not has_tab and not any(tok in low for tok in known):
            return None
        m = re.search(
            r"(?is)\b(?:cierra|cerrar|close)\s+(?:en\s+concreto\s+)?(?:solo\s+)?"
            r"(?:la\s+)?(?:pesta[ñn]a\s+)?(?:de\s+)?(.+)$",
            text.strip(),
        )
        if m:
            target = AudioTool.sanitize_query(m.group(1))
            # sanitize may over-strip; fallback tokens
            if not target or target == "bonito bonito":
                for tok in ("youtube", "youtu", "chrome", "edge", "spotify", "gmail"):
                    if tok in low:
                        return tok
                return "youtube"
            return target
        if "youtube" in low or "youtu" in low:
            return "youtube"
        if "pestaña" in low or "pestana" in low:
            return "youtube" if AudioTool._browser_opened else ""
        return None

    @staticmethod
    def _focus_browser_matching(hint: str = "youtube") -> bool:
        """Enfoca ventana del sistema cuyo título/proceso encaje con hint."""
        hint_l = (hint or "youtube").strip().lower() or "youtube"
        try:
            from core.ui_inspector import UIInspector

            wins = UIInspector.list_windows() or []
            ranked = []
            for w in wins:
                title = str(w.get("title") or "")
                proc = str(w.get("process_name") or "")
                low = f"{title} {proc}".lower()
                score = 0
                if hint_l in low:
                    score += 20
                if "youtube" in low and hint_l in ("youtube", "youtu", "musica", "música", "video"):
                    score += 10
                if any(b in low for b in ("chrome", "msedge", "edge", "brave", "firefox")):
                    score += 2
                if score:
                    ranked.append((score, w))
            ranked.sort(key=lambda x: -x[0])
            if ranked:
                target = ranked[0][1]
                hwnd = target.get("hwnd") or target.get("title")
                return bool(UIInspector.focus_window(hwnd))
        except Exception as e:
            _alog(f"[AudioTool Focus Warning]: {e}")
        return False

    @staticmethod
    def _focus_youtube_or_browser() -> bool:
        return AudioTool._focus_browser_matching("youtube")

    @staticmethod
    def _send_media_key(vk_code: int, pyauto_name: Optional[str] = None):
        if sys.platform == "win32":
            ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)
        if HAS_PYAUTOGUI and pyauto_name:
            try:
                pyautogui.press(pyauto_name)
            except Exception:
                pass

    @staticmethod
    def _send_media_play_pause():
        # VK_MEDIA_PLAY_PAUSE = 0xB3
        AudioTool._send_media_key(0xB3, "playpause")

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
            _alog(f"[AudioTool YouTube K Warning]: {e}")
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
            _alog("[AudioTool]: Fuerza de reproducción ejecutada con éxito.")
            AudioTool._is_playing = True
        except Exception as e:
            _alog(f"[AudioTool Warning Play]: {e}")

    @staticmethod
    def is_resume_request(text: str) -> bool:
        """True for «dale play», «reanuda», «play nuevamente», etc. (no song title)."""
        if not text:
            return False
        low = " ".join(text.lower().strip().split())
        if any(
            kw in low
            for kw in (
                "reanuda", "reanudar", "continúa", "continua", "continuar",
                "despausa", "unpause", "resume",
            )
        ):
            return True
        # «Dale play» / «dale play nuevamente» / solo «play»
        if re.search(r"(?i)\bdale\s+play\b", low):
            return True
        if re.search(r"(?i)\bplay\s+nuevamente\b", low):
            return True
        if re.search(r"(?i)\bdale\s+nuevamente\b", low):
            return True
        if low in ("play", "dale play", "play nuevamente", "dale"):
            return True
        return False

    @staticmethod
    def pause_audio(force: Optional[str] = "pause") -> str:
        """
        Pausa o reanuda en el navegador del sistema.
        force: 'pause' | 'resume' | 'toggle'

        Pause skips a second press if we already believe it is paused (avoids
        accidentally un-pausing). Resume ALWAYS sends the key: our `_is_playing`
        flag drifts (YouTube autoplay, user paused in the browser), and Mauro's
        «dale play» must force play even when the flag says already playing.
        """
        want = (force or "pause").lower().strip()
        try:
            if want == "pause" and not AudioTool._is_playing:
                return (
                    "[Audio]: Ya estaba en pausa (no volví a pulsar Play/Pause para "
                    "no reanudarla por error). Di 'reanuda' o 'dale play' si quieres continuar."
                )

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
    def next_track() -> str:
        """Siguiente pista (tecla multimedia del sistema)."""
        try:
            AudioTool._send_media_key(0xB0, "nexttrack")  # VK_MEDIA_NEXT_TRACK
            AudioTool._is_playing = True
            return "[Audio]: Siguiente pista (media next) enviada al sistema."
        except Exception as e:
            return f"[Error siguiente pista]: {e}"

    @staticmethod
    def previous_track() -> str:
        """Pista anterior (tecla multimedia del sistema)."""
        try:
            AudioTool._send_media_key(0xB1, "prevtrack")  # VK_MEDIA_PREV_TRACK
            AudioTool._is_playing = True
            return "[Audio]: Pista anterior (media prev) enviada al sistema."
        except Exception as e:
            return f"[Error pista anterior]: {e}"

    @staticmethod
    def close_tab(target: str = "youtube") -> str:
        """
        Cierra SOLO la pestaña del navegador del sistema que coincida con
        `target` (p. ej. youtube, gmail). No usa Playwright.
        """
        hint = (target or "youtube").strip().lower() or "youtube"
        try:
            if not HAS_PYAUTOGUI:
                return (
                    f"[Audio]: Sin pyautogui no puedo cerrar la pestaña «{hint}». "
                    "Enfócala y pulsa Ctrl+W."
                )

            focused = AudioTool._focus_browser_matching(hint)
            if not focused and not AudioTool._browser_opened:
                return (
                    f"[Audio]: No encontré una ventana/pestaña para «{hint}». "
                    "Si la ves, enfócala y usa Ctrl+W."
                )

            time.sleep(0.25)
            url = ""
            title_ok = focused
            try:
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.15)
                pyautogui.hotkey("ctrl", "c")
                time.sleep(0.1)
                try:
                    url = (pyperclip.paste() or "").lower()
                except Exception:
                    url = ""
                pyautogui.press("escape")
                time.sleep(0.05)
            except Exception:
                pass

            hint_tokens = {hint, hint.replace(" ", "")}
            if hint in ("youtube", "youtu", "musica", "música", "video", "vídeo"):
                hint_tokens.update({"youtube.com", "youtu.be", "youtube"})
            url_ok = bool(url) and any(tok in url for tok in hint_tokens if len(tok) >= 3)

            if url and not url_ok and not AudioTool._browser_opened and not title_ok:
                return (
                    f"[Audio]: La pestaña activa no parece «{hint}» "
                    f"(URL: {url[:80]}). No cerré otras pestañas."
                )

            pyautogui.hotkey("ctrl", "w")
            if hint in ("youtube", "youtu") or "youtube" in hint:
                AudioTool._browser_opened = False
                AudioTool._is_playing = False
                AudioTool._last_url = ""
            return (
                f"[Audio]: Cerrada la pestaña «{hint}» en tu navegador del sistema. "
                "Solo esa pestaña (Ctrl+W); el resto del navegador sigue abierto."
            )
        except Exception as e:
            return f"[Error al cerrar pestaña]: {str(e)}"

    @staticmethod
    def close_youtube_tab() -> str:
        return AudioTool.close_tab("youtube")

    @staticmethod
    def control_audio(args: Optional[dict] = None) -> str:
        """Dispatcher: pause | resume | toggle | close | next | previous | change."""
        args = args or {}
        action = str(args.get("action") or args.get("params") or "pause").lower().strip()
        target = str(args.get("target") or args.get("tab") or "youtube").strip()
        query = str(args.get("query") or args.get("audio_source") or args.get("song") or "").strip()

        if action in ("close", "cerrar", "close_tab", "close_youtube", "cerrar_pestana", "cerrar_pestaña"):
            return AudioTool.close_tab(target or "youtube")
        if action in ("next", "siguiente", "skip"):
            return AudioTool.next_track()
        if action in ("previous", "prev", "anterior"):
            return AudioTool.previous_track()
        if action in ("change", "cambiar", "play_song", "song"):
            if not query:
                return "[Audio]: Para cambiar de canción indica el título (query)."
            return AudioTool.play_online_music(query)
        if action in ("resume", "play", "reanudar", "continua", "continuar"):
            return AudioTool.pause_audio(force="resume")
        if action in ("toggle", "playpause", "play_pause"):
            return AudioTool.pause_audio(force="toggle")
        return AudioTool.pause_audio(force="pause")

    @staticmethod
    def play_online_music(song_name: str) -> str:
        """Busca, abre/reutiliza pestaña del sistema y reproduce (también sirve para cambiar)."""
        try:
            clean_name = AudioTool.sanitize_query(song_name)
            AudioTool._last_query = clean_name
            target_url = AudioTool.get_direct_youtube_url(clean_name)
            AudioTool.open_or_reuse_tab(target_url)
            AudioTool.force_video_play()
            return (
                f"[Audio]: Reproduciendo «{clean_name}» en YouTube "
                f"(navegador del sistema, misma pestaña si ya había una)."
            )
        except Exception as e:
            return f"[Error al buscar/reproducir música]: {str(e)}"
