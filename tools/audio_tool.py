import os
import sys
import time
import re
import subprocess
import webbrowser
import requests
import ctypes
from urllib.parse import quote_plus

try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

class AudioTool:
    """
    Herramienta nativa para reproducción, pausa, reutilización de pestañas y control multimedia en la PC de Mauro.
    Reutiliza la misma pestaña del navegador para evitar abrir 10 ventanas diferentes.
    """
    _browser_opened = False

    @staticmethod
    def sanitize_query(raw_query: str) -> str:
        """Limpia muletillas y frases conversacionales avanzadas para aislar el nombre exacto de la canción."""
        if not raw_query:
            return "bonito bonito"
            
        clean = re.sub(
            r'(?i)\b(en\s+el\s+mismo\s+youtube|que\s+ya\s+se\s+encuentra\s+abierto|no\s+abras\s+otro|no\s+habras\s+otro|en\s+el\s+mismo|dale\s+play\s+a\s+la|dale\s+play|ahora\s+reproduce|ahora\s+repruduce|reproduce\s+esa\s+misma|esta\s+misma|esa\s+misma|nuevamente|ve\s+a\s+mi\s+navegador(\s+y)?|abre\s+youtube(\s+y)?|reproduce(\s+ahora|\s+la\s+canción|\s+la\s+cancion|\s+musica|\s+música)?|canción|cancion|en\s+youtube|e\.\s*youtube|por\s+favor|pon\s+la|escuchar|quiero\s+que\s+reproduscas|la)\b',
            ' ',
            raw_query
        )
        clean = re.sub(r'[^\w\s]', ' ', clean)
        clean = ' '.join(clean.split()).strip()
        
        return clean if clean else "bonito bonito"

    @staticmethod
    def get_direct_youtube_url(song_name: str) -> str:
        """Obtiene la URL directa de reproducción del primer video de YouTube."""
        clean_name = AudioTool.sanitize_query(song_name)
        encoded = quote_plus(clean_name)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
        """Abre la URL en la misma pestaña activa si el navegador ya está abierto, evitando pestañas duplicadas."""
        if AudioTool._browser_opened and HAS_PYAUTOGUI:
            try:
                pyperclip.copy(target_url)
                # Enfocar barra de direcciones de la pestaña existente
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'v')
                pyautogui.press('enter')
                print("[AudioTool]: Pestaña existente reutilizada con éxito.")
                return
            except Exception as e:
                print(f"[AudioTool Reuse Warning]: {e}")
        
        # Si es la primera vez o falla la reutilización
        webbrowser.open(target_url)
        AudioTool._browser_opened = True

    @staticmethod
    def play_local_audio(file_path: str) -> str:
        """Reproduce un archivo de audio local utilizando el reproductor del sistema."""
        if not os.path.exists(file_path):
            return f"[Error Audio]: El archivo de audio '{file_path}' no existe en disco."
        
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            else:
                subprocess.Popen(["xdg-open", file_path])
            return f"[Audio]: Reproduciendo archivo local '{os.path.basename(file_path)}' en tu PC."
        except Exception as e:
            return f"[Error al reproducir audio local]: {str(e)}"

    @staticmethod
    def force_video_play():
        """Simula la tecla 'k' y barra espaciadora para garantizar que el video empiece inmediatamente."""
        try:
            time.sleep(2.5)
            if HAS_PYAUTOGUI:
                sw, sh = pyautogui.size()
                pyautogui.click(sw // 2, sh // 2 - 20)
                time.sleep(0.2)
                pyautogui.press('k')
                pyautogui.press('space')
            else:
                width = ctypes.windll.user32.GetSystemMetrics(0)
                height = ctypes.windll.user32.GetSystemMetrics(1)
                ctypes.windll.user32.SetCursorPos(width // 2, height // 2 - 20)
                ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x4B, 0, 0, 0) # Key K
                ctypes.windll.user32.keybd_event(0x4B, 0, 2, 0)
                ctypes.windll.user32.keybd_event(0x20, 0, 0, 0) # Key Space
                ctypes.windll.user32.keybd_event(0x20, 0, 2, 0)
            print("[AudioTool]: Fuerza de reproducción ejecutada con éxito.")
        except Exception as e:
            print(f"[AudioTool Warning Play]: {e}")

    @staticmethod
    def pause_audio() -> str:
        """Pausa o reanuda cualquier música o video que esté sonando en la PC usando la tecla multimedia global."""
        try:
            # VK_MEDIA_PLAY_PAUSE = 0xAF (175)
            ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
            
            if HAS_PYAUTOGUI:
                try:
                    pyautogui.press('playpause')
                except Exception:
                    pass
                    
            print("[AudioTool]: Comando multimedia Pausa/Play global enviado.")
            return "[Audio]: Transmisión multimedia pausada/reanudada exitosamente en tu PC."
        except Exception as e:
            return f"[Error al pausar multimedia]: {str(e)}"

    @staticmethod
    def play_online_music(song_name: str) -> str:
        """Busca el video exacto, reutiliza la misma pestaña del navegador y reproduce automáticamente."""
        try:
            clean_name = AudioTool.sanitize_query(song_name)
            target_url = AudioTool.get_direct_youtube_url(clean_name)
            
            # Reutilizar pestaña existente o abrir una sola
            AudioTool.open_or_reuse_tab(target_url)
            
            # Forzar inicio de reproducción
            AudioTool.force_video_play()
            
            return f"[Audio]: Reproduciendo la canción '{clean_name}' directamente en YouTube (Pestaña Reutilizada)."
        except Exception as e:
            return f"[Error al buscar/reproducir música]: {str(e)}"
