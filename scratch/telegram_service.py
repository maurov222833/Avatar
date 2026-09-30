"""Script histórico de laboratorio. No lo arranca Avatar.

main_gui.py, server.py y el daemon de Telegram no importan scratch/.
Este archivo hace getUpdates y responde sin allowlist: lanzarlo a la vez
que el puente real provoca HTTP 409 y contesta a cualquiera.
"""
import json
import os
import time
import requests

CONFIG_FILE = r"b:\PROYECTOS ANTIGRAVITY\Avatar\telegram_bot_config.json"

def get_token():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("token")
    return None

def check_bot():
    token = get_token()
    if not token:
        print("[ERROR] Token no configurado.")
        return False
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("ok"):
            print(f"[OK] Bot conectado: @{res['result']['username']} ({res['result']['first_name']})")
            return True
        else:
            print(f"[ERROR] Respuesta Telegram: {res}")
            return False
    except Exception as e:
        print(f"[ERROR] Conexión fallida: {e}")
        return False

def listen_and_respond():
    token = get_token()
    last_update_id = None
    print("[INFO] Escuchando mensajes en Telegram...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            params = {"timeout": 30}
            if last_update_id:
                params["offset"] = last_update_id + 1
            res = requests.get(url, params=params, timeout=35).json()
            if res.get("ok"):
                for update in res.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message")
                    if msg:
                        chat_id = msg["chat"]["id"]
                        user = msg.get("from", {}).get("first_name", "Usuario")
                        text = msg.get("text", "")
                        print(f"[{user} | {chat_id}]: {text}")
                        # Respuesta autónoma de Avatar
                        reply_url = f"https://api.telegram.org/bot{token}/sendMessage"
                        reply_payload = {
                            "chat_id": chat_id,
                            "text": f"AVATAR AI conectado y operativo. Recibí tu mensaje: '{text}'"
                        }
                        requests.post(reply_url, json=reply_payload, timeout=10)
        except Exception as e:
            print(f"[WARN] Error en ciclo: {e}")
            time.sleep(3)
        time.sleep(1)

if __name__ == "__main__":
    if check_bot():
        listen_and_respond()
