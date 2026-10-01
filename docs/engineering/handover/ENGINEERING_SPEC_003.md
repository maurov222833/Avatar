# AVATAR AI — ENGINEERING SPEC 003

## Plan de ingeniería para cerrar las brechas de la Directriz 002

**Propietario y autoridad:** Mauro
**Estado de este archivo:** propuesta. La versión que manda es la 2.0 consolidada del 2026-09-30 (U0 a U17). Ninguna unidad de código está autorizada.
**Directriz íntegra:** `MASTER_DIRECTIVE_002.md`
**Dictamen:** `MASTER_DIRECTIVE_002_COMPARISON.md`
**Índice de los nombres que pidió Mauro el 2026-10-01:** `docs/engineering/INDEX.md`
**Relación:** complementa la Directriz 002. No sustituye el roadmap R0–R7.

La versión 2.0 consolidada (U0 a U17, más U14.4, U15.5, U15.6 y U15.7) sustituye a la spec inicial y a las adendas. Este archivo guarda el resultado de U0, el orden registrado y el historial. La comparación de U11 a U17 está en `SPEC_003_V2_GAP.md`. No reescribe el diseño ni toca el motor.

## Historial de revisión

### 2026-09-30 — v2 consolidada, solo registro

Mauro entregó la spec 2.0 (seguridad, documentos, asistente, 24/7, marketing, marketplaces con dropshipping, mercados financieros y conocimiento experto). Se registró el orden de su sección 5. U11 a U17 se compararon contra el código en `SPEC_003_V2_GAP.md`. No hay adaptador de tienda. No hay código nuevo. U1 (parada de emergencia) sigue pendiente de autorización. No es la U1 histórica de contención de canales.

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

## Orden registrado (spec 2.0, sección 5)

No se adelanta ninguna unidad. La seguridad de ejecución va primero.

1. Fase 1: U0 hecho. U1 parada de emergencia, autorizada e implementada. U2 rutas. U3 ADR de clasificación y código, con la aprobación de EXEC todavía activa.
2. Fase 2: U4 contención (depende de U1). U9 canal remoto (depende de U1 y U3). U6 informes. U5 investigación. U7 modelos y gasto.
3. Fase 3: U12.4 respaldos. U13 operación 24/7. U12.2 tareas programadas.
4. Fase 4: U11 documentos (depende de U2, U5 y U6). U12.1 correo y calendario. U12.3 OCR de documentos.
5. Fase 5: U14 marketing, incluida U14.4. U16 análisis de mercados, sin ejecutar operaciones. U15 marketplaces: primero U15.7 y U15.5, y U15.6 con dropshipping como modelo principal.
6. Fase 6: U8 IDE externos. U10 subagentes, conectando `core/subagents.py`. **U18 director de desarrollo** (adenda 3, 2026-10-01), después de U8 y U10. Depende de U1, U2, U3, U4, U6, U7, U8, U10, U13 y U17. Luego U12.5 voz y U17 conocimiento experto.

U1 a U17 tienen código. El alcance real de cada una está en `SPEC_003_CIERRE.md`. La comparación previa sigue en `SPEC_003_V2_GAP.md`.

### 2026-10-01 — Adenda 3, U18, solo registro y U18.0

Mauro entregó la adenda «Director de desarrollo». Quedó como U18 en la fase 6, después de U8 y U10. U18.0 es documentación: `U18_0_PREPARACION.md` y `U18_COMPARACION.md`. No hay `DevMission`, no hay adaptador real de Cursor y no cambió ninguna política de aprobación. El código de U18.1 a U18.9 espera autorización de cada sub-unidad.

## Prueba en el PC

El 2026-09-30 Mauro confirmó que funcionó: captura con foto, «dale play» y «pausa» sobre la misma canción, y `/pause` a mitad de un acto inocuo. Quedó como `VERIFIED_PC` de esos tres pasos en `SPEC_003_CIERRE.md`.

## Autorización

Mauro autorizó el recorrido U1 a U17. El código está en la rama `cursor/spec-003-u1-u17-5763`. `exec_requires_approval` sigue activo. El gesto de pausa es `/pause`: la primera vez pausa y la segunda quita la pausa. La tecla global no se instala.
