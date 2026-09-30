import os
import sys
import time
import ctypes
import pyperclip

# Prevenir UnicodeEncodeError en consola Windows cp1252
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


def _wlog(message: str, level: str = "INFO") -> None:
    try:
        from core.logging_util import log
        log(level, message, component="WhatsAppAutoReply")
    except Exception:
        pass

class WhatsAppAutoReply:
    """
    Modulo nativo de respuesta automatica con enfoque de ventana en tiempo real.
    Trae WhatsApp Web al frente de la pantalla en Windows antes de pegar el mensaje.
    """
    @staticmethod
    def focus_whatsapp_window() -> bool:
        """Busca y trae al primer plano de la pantalla la ventana de WhatsApp Web o Navegador."""
        if sys.platform != "win32":
            return True
            
        try:
            user32 = ctypes.windll.user32
            top_hwnd = None
            
            def enum_windows_cb(hwnd, extra):
                nonlocal top_hwnd
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if user32.IsWindowVisible(hwnd) and any(w.lower() in title.lower() for w in ["whatsapp", "chrome", "edge", "navegador"]):
                        top_hwnd = hwnd
                        return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_windows_cb), 0)
            
            if top_hwnd:
                user32.ShowWindow(top_hwnd, 9) # SW_RESTORE
                time.sleep(0.1)
                user32.SetForegroundWindow(top_hwnd)
                time.sleep(0.2)
                _wlog(f"[WhatsAppAutoReply]: Ventana enfocada en pantalla (HWND {top_hwnd}).")
                return True
        except Exception as e:
            _wlog(f"[WhatsAppAutoReply Warning Focus]: {e}")
            
        return False

    @staticmethod
    def send_reply(message_text: str) -> str:
        if not message_text:
            return "[WhatsApp]: Mensaje vacio, no enviado."
            
        if not HAS_PYAUTOGUI:
            return "[Error WhatsApp]: PyAutoGUI no esta disponible para simular escritura."

        try:
            # 1. Traer la ventana de WhatsApp Web al frente de la pantalla
            focused = WhatsAppAutoReply.focus_whatsapp_window()
            if not focused:
                _wlog("[Aviso]: No se encontro la ventana activa de WhatsApp Web en primer plano.")

            # 2. Copiar mensaje al portapapeles
            pyperclip.copy(message_text)
            time.sleep(0.2)
            
            # 3. Pegar texto en la casilla enfocada y presionar Enter
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.2)
            pyautogui.press('enter')
            
            _wlog(f"[WhatsAppAutoReply]: Mensaje pegado y enviado al chat activo.")
            return "✅ Mensaje pegado y enviado exitosamente a la ventana de WhatsApp Web."
        except Exception as e:
            return f"[Error envio WhatsApp]: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        res = WhatsAppAutoReply.send_reply(text)
        _wlog(res)
