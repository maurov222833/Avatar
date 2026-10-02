"""Abre WhatsApp Web en el navegador. El destino es fijo.

La apertura real la pide el chokepoint (OPEN_WHATSAPP). Este módulo no
construye un comando de shell.
"""
import webbrowser

WHATSAPP_WEB_URL = "https://web.whatsapp.com"


def open_whatsapp_web(_args=None) -> str:
    """Ignora cualquier URL que venga en la petición. Solo abre el destino fijo."""
    webbrowser.open(WHATSAPP_WEB_URL, new=1)
    return f"OPENED {WHATSAPP_WEB_URL}"


def start_whatsapp_sync() -> str:
    """Pasa por perform(). No abre el navegador por su cuenta."""
    from bridges.whatsapp_bridge import WhatsAppBridge
    return WhatsAppBridge().sync_whatsapp_qr()


if __name__ == "__main__":
    print(start_whatsapp_sync())
