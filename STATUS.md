# Avatar — estado vivo (R6)

Rama de trabajo: `cursor/u1-contencion-5763`.  
Este archivo es el estado corto. Los `AVATAR_*.md` de la raíz son auditoría histórica; no se movieron en R6 para no romper enlaces.

## Qué está cableado

- Un orquestador por proceso; efectos por `ActChokepoint`.
- Telegram: allowlist, listener durable, captura con `send_photo`, música en el navegador del sistema, `DESKTOP_HOTKEY` (minimizar, maximizar, mostrar escritorio) sin aprobación EXEC. Cerrar o cambiar de ventana no es un atajo permanente.
- Logger JSON (`core/logging_util.py`) y `requirements.lock` (R2). Diagnóstico de núcleo, HTTP, WhatsApp 24/7, chokepoint, audio y captura pasa por ese logger. Si el logger no arranca, el servidor aún avisa por consola.
- Cascada de proveedores y ledger de uso (R4).
- Watchdog en proceso (D-7). El Programador de tareas de Windows sigue opcional.

## Qué no es producción

| Módulo | Estado |
|---|---|
| `core/autoloop.py` | Retirado (0 importadores). El bucle real es el orquestador. |
| `core/subagents.py` | No lo llama el server ni Telegram. Lo cubre `tests/test_acceptance_surfaces.py`. |
| `core/cognitive/closed_loop.py`, `self_development_probe.py` | Solo tests. Producción usa `continuous_loop.py`. |

## Dispatch

El parser de texto (`_parse_tool_action`) acepta los nombres de `ToolRegistry.list_tools()`, que une el registro cognitivo con `ACT_TYPES`. La ejecución sigue siendo el chokepoint.

## Directriz 002

Propuesta de Mauro del 2026-09-30. No sustituye este estado ni el roadmap R0–R7.
Texto íntegro: `docs/engineering/handover/MASTER_DIRECTIVE_002.md`.
Dictamen: `docs/engineering/handover/MASTER_DIRECTIVE_002_COMPARISON.md`.
Plan de unidades: `docs/engineering/handover/ENGINEERING_SPEC_003.md` (v2, U0 a U17).
Comparación de negocio y asistente: `docs/engineering/handover/SPEC_003_V2_GAP.md`.
U0 archivó la directriz. U1 a U17 tienen código en `cursor/spec-003-u1-u17-5763`, con el cierre en `docs/engineering/handover/SPEC_003_CIERRE.md`. La parada de emergencia consulta el chokepoint. `exec_requires_approval` sigue activo. No hay tiendas ni brokers conectados.

## Prueba en el PC (2026-09-30)

Mauro la ejecutó y confirmó que funcionó:

1. Captura: llegó la foto.
2. «Dale play» y «pausa»: la misma canción.
3. `/pause` a mitad de un acto inocuo.

Eso es `VERIFIED_PC` para esos tres pasos. La tecla global `Ctrl+Alt+Shift+X` no entra en este reporte.
