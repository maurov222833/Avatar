# AVATAR — Roadmap de implementación (secuenciado)

Orden: seguridad → rutas reales → estado/evidencia → integraciones → higiene → capacidades.

## R0 — Congelar garantías (hecho, mantener)

Objetivo: que nada futuro rompa lo verificado. Red: suites autoridad (129),
chokepoint AST, e2e/superficies, `test_21` idempotencia. Cierre: suite verde.

## R1 — Cerrar bypass Telegram (E-02)

Acts `SCREEN_CAPTURE`/`AUDIO_CONTROL` (READ) con observers físicos; `telegram_bridge`
por chokepoint; extender guard AST. Aceptación: enviar/capturar por Telegram deja act;
test AST en verde. Complejidad baja. Tokens: ~15-30k.

## R2 — Logger estructurado + lockfile (E-17) ✅

Sustituir prints por logging JSON con redacción (conservar `redact_secrets`);
`requirements.lock`. Aceptación: sin secretos en logs; `pip install -r` reproducible.

**Hecho (2026-09-30):** `core/logging_util.py`, cableado en server/GUI/Telegram,
`requirements.lock`, `tests/test_r2_logging.py`. Informe en el repo de docs:
`docs/engineering/r2_logging/R2_INFORME.md`.

Complejidad baja. Tokens: ~10-20k.

## R3 — Watchdog y scheduler (E-18)

`core/watchdog.py` (heartbeat, reinicio, re-resume) + `core/scheduler.py` o Task
Scheduler documentado. Aceptación: kill nocturno simulado con misión que continúa
sola. Complejidad media. Tokens: ~30-60k. Requiere decisión del dueño (servicio
propio vs programador del SO).

## R4 — Routing por salud y costos (E-19)

Health real que dirige tráfico, cascada configurable, registro de uso por proveedor,
techos de costo. Aceptación: caída de groq deriva sin intervención; uso visible.
Complejidad media. Tokens: ~25-50k.

## R5 — Integración Telegram Bot API (canal superior)

Token ya en `.env`; scripts en `scratch/` como referencia (NO producción: responden a
cualquiera). Polling con allowlist de chat, ledger y misma política WA. Aceptación:
ida y vuelta con relectura. Complejidad media. Tokens: ~30-60k. Requiere: probar con
el bot real del dueño.

## R6 — Higiene y consolidación (E-20, E-15)

Podar muertos, `ToolRegistry` como fuente del dispatch, STATUS.md único, archivar
históricos a `docs/archive/`. Aceptación: suite verde + árbol limpio. Tokens: ~15-30k.

## R7 — Verificador externo (E-03, solo si ADR-01 dice sí)

Proceso separado + IPC para Modelo-B. Es el único cambio arquitectónico mayor;
no iniciar sin ADR y sin amenaza que lo justifique. Complejidad alta. Tokens: 100k+.

## Puerta de cada fase

Reproducir síntoma → implementar → test dedicado → suite verde → evidencia en
ledger/log → actualizar este roadmap. Rollback: `git revert` (repo limpio, 4 commits).
Estimaciones de tokens marcadas como estimaciones, no compromisos.
