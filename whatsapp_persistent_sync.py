import time
import os
import sys
import pyautogui
import pyperclip

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

def send_whatsapp_message(message: str):
    print(f"[AVATAR WHATSAPP] Enviando mensaje: {message}")
    pyperclip.copy(message)
    time.sleep(0.5)
    
    # Simular atajo para abrir búsqueda o enfocar chat activo
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(0.5)
    
    # Escribir nombre del contacto o chat
    pyautogui.write("Mauro Vanegas 2025", interval=0.05)
    time.sleep(1.0)
    pyautogui.press('enter')
    time.sleep(1.0)
    
    # Pegar mensaje
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    print("[AVATAR WHATSAPP] Mensaje enviado exitosamente.")

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Hola Mauro, este es un mensaje automatizado desde Avatar AI."
    send_whatsapp_message(msg)
