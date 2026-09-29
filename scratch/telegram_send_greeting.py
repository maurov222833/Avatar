import json
import requests

CONFIG_PATH = r"b:\PROYECTOS ANTIGRAVITY\Avatar\telegram_bot_config.json"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_updates(token):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    response = requests.get(url)
    return response.json()

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    return requests.post(url, json=payload).json()

def main():
    cfg = load_config()
    token = cfg["token"]
    
    print("Consultando actualizaciones recientes de Telegram para obtener tu chat_id...")
    data = get_updates(token)
    
    if not data.get("result"):
        print("Aún no hay mensajes previos en el bot.")
        print("Por favor, abre tu Telegram, busca tu bot y envíale un mensaje cualquiera (ej: 'Hola').")
        print("Luego vuelve a ejecutar este script para que detecte tu chat_id y te envíe el saludo.")
        return

    for update in data["result"]:
        message = update.get("message")
        if message:
            chat_id = message["chat"]["id"]
            user_name = message["from"].get("first_name", "Mauro")
            print(f"¡Chat ID detectado! ({chat_id}) de {user_name}")
            
            # Enviar saludo
            saludo = f"¡Hola Mauro! Soy AVATAR AI, tu asistente soberano. Ya estamos conectados por Telegram exitosamente."
            res = send_message(token, chat_id, saludo)
            if res.get("ok"):
                print("¡Mensaje de saludo enviado con éxito a Telegram!")
            else:
                print(f"Error al enviar mensaje: {res}")
            return

if __name__ == "__main__":
    main()
