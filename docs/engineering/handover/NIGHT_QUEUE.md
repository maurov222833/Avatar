# Cola de noche (hasta las 9:00 America/Bogota)

Tope: **2026-09-30 14:00 UTC**. Después de esa hora, parar y resumir.
No abrir pull requests. No cambiar `exec_requires_approval`. No automatizar el escritorio.

## Hecho

- R2 logger + lockfile
- R4 cascada de proveedores
- R6 autoloop fuera; dispatch vía ToolRegistry; STATUS.md
- Prints de audio, captura y orquestador al logger JSON (`7db7015`)
- ToolRegistry registra los actos del chokepoint (el planificador ya no los rechaza)
- `scratch/telegram_service.py` no lo arranca Avatar; quedó advertido (sin allowlist, no borrar)
- El fixture del navegador explica si el puerto 8765 está ocupado

## Siguiente, en orden

1. Pasar al logger los `print` que quedan en producción: `tools/whatsapp_auto_reply.py`, `core/watchdog.py`, `bridges/whatsapp_bridge.py`. No tocar scripts de `scratch/`.

## Parar

- Si el reloj ya pasó las 9:00 (Bogotá) / 14:00 UTC.
- Si el siguiente cambio toca EXEC global o el control físico del PC.
