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

- Prints de WhatsApp (auto-reply, bridge y reader), watchdog, chokepoint, memoria y bucle continuo al logger JSON
- Errores de `/api/chat` y `/api/missions/resume`, el webhook de WhatsApp y `whatsapp_24x7.log` pasan por el logger JSON (consola solo si el logger no arranca)

## Siguiente

La cola escrita está cerrada. No abras R7 ni cambies la política EXEC.
En el siguiente turno solo corrige un test rojo o un hueco ya nombrado en STATUS.md.
No inventes módulos nuevos.

## Parar

- Si el reloj ya pasó las 9:00 (Bogotá) / 14:00 UTC.
- Si el siguiente cambio toca EXEC global o el control físico del PC.
