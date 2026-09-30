# Cierre Spec 003 — U1 a U17

Fecha: 2026-09-30. Rama `cursor/spec-003-u1-u17-5763`.
Pruebas: `tests/test_spec003.py` en Linux (`TESTED_LINUX`). El 2026-09-30 Mauro confirmó en su PC la captura, «dale play» y «pausa» sobre la misma canción, y `/pause` a mitad de un acto inocuo (`VERIFIED_PC` de esos tres pasos). Las demás unidades siguen sin esa prueba en el PC.

`exec_requires_approval` sigue activo. No hay claves de pago, ni frases semilla, ni llamadas a Amazon, Mercado Libre o un broker.

## Por unidad

| Unidad | Estado | Dónde | Qué no quedó |
|---|---|---|---|
| U1 Parada | `IMPLEMENTED + INTEGRATED + TESTED_LINUX + VERIFIED_PC` | `core/halt.py`. `/pause` pausa y el segundo `/pause` quita la pausa. Mauro lo confirmó en el PC. | `/stop` y `/kill` no se apagan con `/pause`. La tecla global no se instala. |
| U2 Rutas | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | `core/path_guard.py` en escrituras y en comandos que nombran una ruta prohibida | Junctions, nombres 8.3 y UNC no se crearon en Windows. La denylist se probó sobre el texto de la ruta. |
| U3 Comandos | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | `core/command_risk.py`, `core/grants.py`, ADR en `U3_COMMAND_RISK_ADR.md` | Sin AST de PowerShell. Sin grant, nada rutinario se cuela: sigue la aprobación de EXEC. |
| U4 Contención | `IMPLEMENTED + TESTED_LINUX` | `core/containment.py`. El orquestador la enciende solo si `security.containment_enabled` es verdadero | Apagada por defecto para no pausar el PC a los cinco actos iguales sin que Mauro lo active. |
| U5 Procedencia | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Cada página o búsqueda deja una línea en `memory/provenance.jsonl`. Una orden dentro del texto contamina el turno. | No promociona sola nada a memoria permanente. |
| U6 Informes | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Si el turno ejecutó actos, la respuesta cierra con `Estado de la misión:` calculado desde la evidencia. | Una charla sin actos no lleva esa línea. |
| U7 Modelos | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Un proveedor listado en `providers.paid_upgrade` no entra como reemplazo. | El precio real sigue `UNKNOWN` si no se comprobó. |
| U8 IDE | `IMPLEMENTED + TESTED_LINUX` | `core/external_dev.py`, adaptador simulado | Ningún IDE real. Falta la lista que autorice Mauro. |
| U9 Canal | `IMPLEMENTED + INTEGRATED + TESTED_LINUX + VERIFIED_PC` en tres pasos | `core/remote_guard.py` dentro de `handle_message`. En el PC: captura, play/pausa de la misma canción y `/pause`. | WhatsApp no usa todavía el mismo anti-repetición. Falta el resto del protocolo (remitente ajeno, reinicio a mitad, pantalla bloqueada). |
| U10 Subagentes | `PARTIAL + TESTED_LINUX` | `run_scoped` en `core/subagents.py` | El servidor y Telegram siguen sin lanzar la flota. |
| U11 Documentos | `IMPLEMENTED + TESTED_LINUX` | `core/documents.py` (OOXML mínimo) | No hay Word ni Excel recalculando. No es un dictamen contable. |
| U12 Asistente | `IMPLEMENTED + TESTED_LINUX` | `core/assistant.py` | Sin OAuth, sin correo real, sin micrófono. |
| U13 Noche | `IMPLEMENTED + TESTED_LINUX` | `core/night_mode.py`. El watchdog ya no reanuda si hay parada | El modo noche no envuelve solo el bucle 24/7. |
| U14 Marketing | `IMPLEMENTED + TESTED_LINUX` | `core/marketing.py` | No publica ni gasta en anuncios. |
| U15 Marketplaces | `IMPLEMENTED + TESTED_LINUX` | `core/marketplace.py`, simulador | Sin API real. Dropshipping de cada país sigue sin leerse del sitio oficial. |
| U16 Mercados | `IMPLEMENTED + TESTED_LINUX` | `core/market_signals.py` | No hay cliente de broker. Operar y retirar se rechazan por nombre de ruta. |
| U17 Conocimiento | `IMPLEMENTED + TESTED_LINUX` | `core/expertise.py` | No está unido a la memoria RAG del servidor. |

## Riesgo que queda

La parada vive en el proceso. Otro código que llame a una herramienta saltándose el chokepoint no la ve. La tecla global y las pruebas de rutas en Windows siguen pendientes. La prueba corta de Telegram en el PC ya la cerró Mauro el 2026-09-30.

## Siguiente paso

La contención automática sigue apagada hasta que Mauro pida encenderla. Lo que sigue en el orden, cuando se programe, son los respaldos que una misión no pueda borrar y el modo noche dentro de un sobre. WhatsApp aún no comparte el anti-repetición de Telegram.
