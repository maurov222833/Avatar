import os
import sys
import threading
import time
import uvicorn
import webview

# Configurar encodings para Windows sin errores de cp1252
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Asegurar path de Avatar
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server import app
from core.telegram_daemon import ensure_telegram_daemon

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def start_telegram_daemon():
    ensure_telegram_daemon()

def start_whatsapp_daemon():
    try:
        from bridges.whatsapp_bridge import WhatsAppBridge
        bridge = WhatsAppBridge()
        print("[AVATAR WhatsApp]: Daemon pasarela activo y escuchando en segundo plano.")
        bridge.start_daemon()
    except Exception as e:
        print(f"[AVATAR WhatsApp Daemon Error]: {e}")

def launch_desktop_gui():
    # 1. Iniciar servidor Backend FastAPI en segundo plano
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 2. Pasarela WhatsApp en segundo plano.
    #    Telegram ya lo arranca el lifespan de FastAPI (server.py) — no lanzar
    #    un segundo getUpdates aquí: eso provoca HTTP 409 y el bot “no responde”.
    wa_thread = threading.Thread(target=start_whatsapp_daemon, daemon=True)
    wa_thread.start()

    # Esperar a que el servidor (y su lifespan/Telegram daemon) quede activo
    time.sleep(1.5)
    # Idempotente: si el lifespan aún no arrancó el listener, lo arrancamos ahora.
    ensure_telegram_daemon()

    print("[AVATAR] Lanzando Ventana Grafica de Escritorio Avatar AI...")

    # 2. Abrir Ventana Nativa de Escritorio con PyWebView
    try:
        webview.create_window(
            title="AVATAR AI - Sovereign Agent Workspace",
            url="http://127.0.0.1:8000",
            width=1280,
            height=800,
            min_size=(900, 600),
            resizable=True
        )
        webview.start()
    except Exception as e:
        print(f"[AVATAR AVISO] PyWebView fallback: Abriendo en navegador/modo app: {e}")
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    launch_desktop_gui()
