import os
import sys
import subprocess
import time

# Garantizar compatibilidad con consola de Windows UTF-8
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def start_whatsapp_sync():
    print("==================================================")
    print("[AVATAR AI]: Sincronizacion Nativa de WhatsApp Web")
    print("==================================================")
    print("Desplegando ventana de WhatsApp Web en tu pantalla...")
    
    url = "https://web.whatsapp.com"
    
    # 1. Abrir en el navegador activo via Windows Shell (No se cierra al salir Python)
    try:
        if sys.platform == "win32":
            cmd = f'powershell -Command "Start-Process \'{url}\'"'
            subprocess.Popen(cmd, shell=True)
            print("[OK] WhatsApp Web abierto en tu navegador por defecto.")
    except Exception as e:
        print(f"[Aviso Shell]: {e}")

    # 2. Desplegar tambien ventana nativa PyWebView de escritorio permanente
    try:
        import webview
        print("[AVATAR AI]: Abriendo ventana flotante PyWebView...")
        window = webview.create_window(
            title="WhatsApp Web - Escanea el codigo QR (Avatar AI)",
            url=url,
            width=1000,
            height=800,
            resizable=True,
            on_top=True
        )
        print("[OK] Ventana PyWebView abierta. Escanea el codigo QR con tu celular.")
        webview.start()
    except Exception as e:
        print(f"[Aviso PyWebView]: {e}")

if __name__ == "__main__":
    start_whatsapp_sync()