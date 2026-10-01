"""Cierres pedidos el 2026-10-01.

No lanza un IDE, no registra una tecla, no abre WhatsApp, no fusiona a main
y no llama a un modelo. El tope de gasto y las respuestas de la carta siguen
en TODO_MAURO.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.dev_director import DevEnvelope, request_merge, second_opinion
from core.halt import start_hotkey_listener


def real_ide_gate(roster: Dict[str, Any], caps: Dict[str, Any], env: Dict[str, str]) -> str:
    """El simulador es el único agente. Esta función no arranca un proceso."""
    if roster.get("real_ides_enabled") is not True:
        return "REAL_IDE_OFF"
    currency = str(caps.get("currency") or "")
    amounts = [caps.get("per_session"), caps.get("per_day"), caps.get("per_month")]
    if currency in ("", "TODO_MAURO") or any(not isinstance(item, int) or item <= 0 for item in amounts):
        return "REAL_IDE_NO_BUDGET"
    if not str(env.get("CURSOR_API_KEY") or "").strip():
        return "REAL_IDE_NO_KEY"
    return "REAL_IDE_NOT_LAUNCHED"


def reject_ide_argv(argv: List[str]) -> Optional[str]:
    folded = [str(item).lower() for item in argv]
    if "--force" in folded or "--yolo" in folded:
        return "REAL_IDE_FORCE_DENIED"
    return None


def charter_gate(charter: Dict[str, Any]) -> str:
    """Sin las respuestas de Mauro la carta no queda aprobada."""
    if charter.get("enabled") is True:
        return "CARTA_NO_SE_ENCIENDE_SOLA"
    if str(charter.get("display_name") or "") in ("", "TODO_MAURO"):
        return "CARTA_SIN_RESPUESTAS"
    return "CARTA_BORRADOR"


def hotkey_gate(config: Optional[Dict[str, Any]] = None) -> str:
    """Aunque el interruptor esté en true, no hay gancho."""
    return start_hotkey_listener(config)


def whatsapp_gate(channels: Dict[str, Any]) -> str:
    block = channels.get("whatsapp") or {}
    if isinstance(block, dict) and block.get("enabled") is True:
        return "WHATSAPP_REFUSED"
    return "WHATSAPP_PARKED"


def merge_to_main(target: str = "main") -> Dict[str, Any]:
    """No ejecuta git. main y master quedan en cola."""
    return request_merge(target, DevEnvelope())


def opinion_gate(*, per_session: int, currency: str) -> Dict[str, Any]:
    return second_opinion(per_session=per_session, currency=currency)
