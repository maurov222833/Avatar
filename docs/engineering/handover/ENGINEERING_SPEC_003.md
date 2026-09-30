# AVATAR AI — ENGINEERING SPEC 003

## Plan de ingeniería para cerrar las brechas de la Directriz 002

**Propietario y autoridad:** Mauro
**Estado de este archivo:** propuesta archivada en U0. Ninguna unidad de código está autorizada.
**Directriz íntegra:** `MASTER_DIRECTIVE_002.md`
**Dictamen:** `MASTER_DIRECTIVE_002_COMPARISON.md`
**Relación:** complementa la Directriz 002. No sustituye el roadmap R0–R7.

El mensaje de Mauro del 2026-09-30 es la especificación completa (secciones 0 a 16 y unidades U0 a U10). Este archivo guarda el resultado de U0 y el historial de revisión que pide la sección 16. No reescribe el diseño de U1 a U10.

## Historial de revisión

### 2026-09-30 — U0, comparación contra el código

Afirmaciones de la sección 0 de la especificación, confirmadas en `cursor/u0-integridad-documental-5763`:

| Afirmación | Resultado | Evidencia |
|---|---|---|
| Existe un chokepoint | Confirmada | `core/act_chokepoint.py`, clase `ActChokepoint`, método `perform` |
| Existe `ActPolicy` | Confirmada | `core/act_chokepoint.py`, clase `ActPolicy` |
| Existe el ledger de actos | Confirmada | `CREATE TABLE IF NOT EXISTS acts` en el mismo archivo |
| Existe la cascada R4 | Confirmada | `core/llm_provider.py`, `_provider_cascade` |
| Existe el watchdog | Confirmada | `core/watchdog.py`, clase `Watchdog` |
| `core/subagents.py` no lo usa el servidor ni Telegram | Confirmada | Solo lo importan `tests/test_acceptance_surfaces.py` y `tests/test_r6_hygiene.py` |

Precisión que no estaba en la sección 0 y no debe quedar como hecho:

La fase 1 de U3 dice «transición desde el estado actual (aprobar todo)». Eso no es exacto. `exec_requires_approval` sigue en verdadero y obliga a aprobar el riesgo EXEC (`COMMAND`, `DESKTOP_CLICK`, `DESKTOP_TYPE`). Lectura, varias escrituras locales ya clasificadas y la cascada de proveedores no piden esa aprobación. El ADR de U3, si Mauro lo pide, debe partir de esa política, no de «aprobar todo».

No se cambió `exec_requires_approval`. No se escribió código de U1 a U10.

### Integridad del Markdown (U0, tarea 3)

En `MASTER_DIRECTIVE_002.md` no hay secuencias literales `\#`, `\*\*` ni `\##`. Los títulos y las negritas están guardados como Markdown normal.

## U0 — hecho

Antes de este archivo, `MASTER_DIRECTIVE_002.md` tenía 55 líneas: nota, título y un índice. No contenía los apartados 0 a 22.

Ahora la copia oficial es:

`docs/engineering/handover/MASTER_DIRECTIVE_002.md`

Incluye los encabezados `# 0.` a `# 22.` y el cierre `FIN DE MASTER DIRECTIVE 002`. El índice corto permanece en el commit `f544a5f`.

## Orden propuesto

Se mantiene el orden de la especificación. No se adelanta ninguna unidad.

1. U0 — integridad documental. Hecho en esta rama. Sin código de ejecución.
2. U1 — parada de emergencia. Primera unidad de código, si Mauro la autoriza.
3. U2 — protección de rutas en el ejecutor.
4. U3 — primero el ADR de clasificación de comandos. Código solo después de ese ADR.
5. U4 — contención. Depende de U1.
6. U5, U6 y U7 — después de U1 a U3, y no a la vez en el mismo cambio.
7. U8 — IDE externos. Depende de U2, U3 y U6, y de la lista de herramientas que Mauro autorice.
8. U9 — canal remoto. Depende de U1 y U3.
9. U10 — subagentes. Depende de U2, U3 y U6. No se crea otra flota.

La prueba de Telegram en el PC (captura con foto, «dale play» y «pausa» en la misma canción, minimizar sin luz verde) no necesita código nuevo.

## Esperando autorización

No empieza U1 hasta que Mauro lo diga. Decisiones que la especificación deja en Mauro y que U1 necesitaría antes de codificar el hotkey: tecla de parada y nivel por defecto (`PAUSE`, `STOP` o `KILL_SWITCH`). El diseño puede usar mientras tanto el comando remoto autenticado y un estado `HALT` leído por el chokepoint, si esa es la autorización.
