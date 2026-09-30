# Cierre Spec 003 — U1 a U17

Fecha: 2026-09-30. Rama `cursor/spec-003-u1-u17-5763`.
Pruebas: `tests/test_spec003.py` en Linux. No es `VERIFIED_WINDOWS` ni `VERIFIED_PC`.

`exec_requires_approval` sigue activo. No hay claves de pago, ni frases semilla, ni llamadas a Amazon, Mercado Libre o un broker.

## Por unidad

| Unidad | Estado | Dónde | Qué no quedó |
|---|---|---|---|
| U1 Parada | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | `core/halt.py`, consultado al inicio de `ActChokepoint.perform` y al resolver una aprobación. `/pause`, `/stop` y `/kill` en Telegram. | El gancho de teclado global de Windows no existe en Linux. La tecla configurada es `ctrl+alt+shift+x`; aquí se dispara por archivo o por código. Falta la prueba en el PC. |
| U2 Rutas | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | `core/path_guard.py`, usado por el chokepoint y por `FileTool.write_file` | Junctions, nombres 8.3 y UNC no se crearon en Windows. La denylist se probó sobre el texto de la ruta. |
| U3 Comandos | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | `core/command_risk.py`, `core/grants.py`, ADR en `U3_COMMAND_RISK_ADR.md` | Sin AST de PowerShell. Sin grant, nada rutinario se cuela: sigue la aprobación de EXEC. |
| U4 Contención | `IMPLEMENTED + TESTED_LINUX` | `core/containment.py`. El orquestador la enciende solo si `security.containment_enabled` es verdadero | Apagada por defecto para no pausar el PC a los cinco actos iguales sin que Mauro lo active. |
| U5 Procedencia | `IMPLEMENTED + TESTED_LINUX` | `core/provenance_store.py` | `FETCH_URL` todavía no guarda solo en este almacén. |
| U6 Informes | `IMPLEMENTED + TESTED_LINUX` | `core/mission_report.py` | El orquestador aún no sustituye su texto final por este cálculo. |
| U7 Modelos | `IMPLEMENTED + TESTED_LINUX` | `core/model_inventory.py`. La cascada de `core/llm_provider.py` se mantiene | El inventario nuevo no elige el proveedor en vivo. Precios no comprobados quedan `UNKNOWN`. |
| U8 IDE | `IMPLEMENTED + TESTED_LINUX` | `core/external_dev.py`, adaptador simulado | Ningún IDE real. Falta la lista que autorice Mauro. |
| U9 Canal | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` en Telegram | `core/remote_guard.py` dentro de `handle_message` | WhatsApp no usa todavía el mismo anti-repetición. Falta el protocolo en el PC. |
| U10 Subagentes | `PARTIAL + TESTED_LINUX` | `run_scoped` en `core/subagents.py` | El servidor y Telegram siguen sin lanzar la flota. |
| U11 Documentos | `IMPLEMENTED + TESTED_LINUX` | `core/documents.py` (OOXML mínimo) | No hay Word ni Excel recalculando. No es un dictamen contable. |
| U12 Asistente | `IMPLEMENTED + TESTED_LINUX` | `core/assistant.py` | Sin OAuth, sin correo real, sin micrófono. |
| U13 Noche | `IMPLEMENTED + TESTED_LINUX` | `core/night_mode.py`. El watchdog ya no reanuda si hay parada | El modo noche no envuelve solo el bucle 24/7. |
| U14 Marketing | `IMPLEMENTED + TESTED_LINUX` | `core/marketing.py` | No publica ni gasta en anuncios. |
| U15 Marketplaces | `IMPLEMENTED + TESTED_LINUX` | `core/marketplace.py`, simulador | Sin API real. Dropshipping de cada país sigue sin leerse del sitio oficial. |
| U16 Mercados | `IMPLEMENTED + TESTED_LINUX` | `core/market_signals.py` | No hay cliente de broker. Operar y retirar se rechazan por nombre de ruta. |
| U17 Conocimiento | `IMPLEMENTED + TESTED_LINUX` | `core/expertise.py` | No está unido a la memoria RAG del servidor. |

## Riesgo que queda

La parada vive en el proceso. Otro código que llame a una herramienta saltándose el chokepoint no la ve. Eso ya era el límite del chokepoint. La tecla global y las pruebas de Windows siguen pendientes.

## Siguiente paso

Probar en el PC, sin borrar nada: captura, play/pausa y `/pause` durante un acto inocuo. Encender `security.containment_enabled` solo cuando Mauro quiera la pausa automática.
