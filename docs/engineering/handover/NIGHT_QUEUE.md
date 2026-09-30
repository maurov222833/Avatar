# Cola de noche (hasta las 9:00 America/Bogota)

Tope: **2026-09-30 14:00 UTC**. Después de esa hora, parar y resumir.
No abrir pull requests. No cambiar `exec_requires_approval`. No automatizar el escritorio.

## Hecho

- R2 logger + lockfile
- R4 cascada de proveedores
- R6 autoloop fuera; dispatch vía ToolRegistry; STATUS.md
- Prints de audio, captura y orquestador al logger JSON (`7db7015`)

## Siguiente, en orden

1. Registrar en `ToolRegistry._register_default_tools` los actos que faltan (AUDIO_CONTROL, SCREEN_CAPTURE, DESKTOP_HOTKEY, TELEGRAM_*, BROWSER_*) para que el planificador no los trate como desconocidos.
3. Revisar `scratch/` : no es producción. Si un script responde a cualquiera en Telegram, dejarlo fuera del arranque (no borrarlo si un test lo importa).
4. Si sobra tiempo: un test que falle en claro cuando el puerto 8765 del fixture de navegador esté ocupado, en vez de un error opaco.

## Parar

- Si el reloj ya pasó las 9:00 (Bogotá) / 14:00 UTC.
- Si el siguiente cambio toca EXEC global o el control físico del PC.
