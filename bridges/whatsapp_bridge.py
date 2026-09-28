import time
import requests
import json
import os
import sys

# Garantizar resolución de imports raíz ('core', 'tools', 'memory')
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.orchestrator import AvatarOrchestrator
from tools.whatsapp_auto_reply import WhatsAppAutoReply

class WhatsAppBridge:
    """
    Pasarela de integración para WhatsApp del Proyecto Avatar.
    Soporta sincronización nativa por código QR y comunicación bidireccional en tiempo real.
    """
    def __init__(self, bridge_url: str = "http://localhost:8000/api/whatsapp/webhook"):
        self.bridge_url = bridge_url
        self.orchestrator = AvatarOrchestrator()

    def sync_whatsapp_qr(self) -> str:
        """Abre WhatsApp Web en la PC para permitir el escaneo del código QR."""
        sync_script = os.path.join(base_dir, "whatsapp_native_sync.py")
        if os.path.exists(sync_script):
            import subprocess
            subprocess.Popen([sys.executable, sync_script])
            return "✅ Iniciando sincronización de WhatsApp Web en tu pantalla. Por favor escanea el código QR desde tu celular."
        return "⚠️ No se encontró el script de sincronización whatsapp_native_sync.py."

    def process_incoming_whatsapp(self, sender: str, message_body: str) -> str:
        """
        Recibe un mensaje de WhatsApp, lo procesa con el Agente Avatar y envía la respuesta.

        El envío pasa por el ActChokepoint, igual que cualquier otro efecto secundario. Antes
        llamaba a `WhatsAppAutoReply.send_reply` directamente, lo que significaba que un
        mensaje real podía salir a otra persona sin política, sin registro y sin dry-run.
        """
        print(f"\n💬 [Mensaje de WhatsApp de {sender}]: {message_body}")
        response = self.orchestrator.process_user_input(message_body)

        # Enviar respuesta nativa al chat activo, sujeto a la política de autonomía.
        if self.orchestrator.chokepoint is None:
            self.orchestrator.chokepoint = self.orchestrator._build_chokepoint()
        delivery = self.orchestrator.chokepoint.perform(
            act_type="SEND_WHATSAPP",
            args={"message": response},
            mission_id=f"whatsapp-{sender}",
            task_id="whatsapp-reply",
            execution_id=f"wa-exec-{abs(hash(message_body)) % 10**8}",
        )
        print(f"📤 [Entrega a {sender}]: {delivery[:160]}")
        return response

    def start_daemon(self):
        """
        Ejecuta el demonio en segundo plano para escuchar peticiones de WhatsApp.
        """
        print("[AVATAR WhatsApp Daemon]: Servicio de pasarela activo en segundo plano.")
        while True:
            time.sleep(30)

    def start_live_bridge(self, target_chat: str = "Mauro Vanegas 2025"):
        """
        Inicia el puente activo para el chat especificado.
        """
        print(f"==================================================")
        print(f"⚡ [AVATAR AI]: Puente de WhatsApp Activo para '{target_chat}'")
        print(f"==================================================")
        print(f"Instrucción: Ten abierta la ventana de WhatsApp Web en el chat '{target_chat}'.")
        print("El sistema está listo para procesar y responder tus mensajes.")

if __name__ == "__main__":
    bridge = WhatsAppBridge()
    bridge.start_live_bridge()
