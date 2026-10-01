# Puertas cerradas el 2026-10-01

Mauro pidió resolverlas de una vez. El cierre es el estado de cada una. No se inventó un tope, una respuesta de la carta, una clave ni un gancho de teclado.

| Puerta | Estado | Qué hace el código |
|---|---|---|
| IDE real | `REAL_IDE_OFF` | `core/closed_gates.py`. Con el simulador apagado el interruptor, sin tope o sin clave, no arranca un proceso. `--force` y `--yolo` se niegan. |
| Carta de ingeniería | `CARTA_SIN_RESPUESTAS` | Sigue `config/avatar/mauro_charter.yaml`. `enabled` queda false. El nombre sigue `TODO_MAURO`. |
| Tecla global | `HOTKEY_LISTENER_NOT_INSTALLED` | Aunque `hotkey_listener` sea true, `start_hotkey_listener` no registra un gancho. |
| Analizador de PowerShell | Clasificador actual | `U3_POWERSHELL_AST_ADR.md`. No hay AST nuevo. Lo prohibido sigue `PROHIBITED`. La duda sigue en C. |
| WhatsApp | `WHATSAPP_PARKED` | `channels.yaml` lo deja en false. Encenderlo no pasa `avatar config check`. No hay QR. |
| Fusión a `main` | `QUEUED` | `merge_to_main` no ejecuta git. |
| Segunda opinión | `NO_BUDGET` | `second_opinion` no llama a un modelo. Con tope 0 o moneda `TODO_MAURO` no hay dictamen. Con tope puesto tampoco se envía: no hay revisor local. |

Lo que solo Mauro puede escribir, cuando quiera, sigue siendo el nombre de la carta, la moneda y los tres topes. Esta sesión no los rellena.

## Cuándo se activa la segunda opinión

El 2026-10-01 Mauro dijo que se queda así hasta que el software esté por terminarse. Hasta ese momento el tope sigue en 0 y el estado es `NO_BUDGET`. Aunque hubiera tope y moneda, el estado sería `NOT_SENT`: no hay revisor y no sale ninguna llamada. Un dictamen necesitaría un modelo, el diff saldría de la máquina y el costo hoy es `UNKNOWN`. No se activa en este tramo.
