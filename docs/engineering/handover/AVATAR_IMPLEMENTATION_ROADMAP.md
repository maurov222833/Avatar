# AVATAR — Roadmap de implementación (secuenciado)

Orden: seguridad → rutas reales → estado/evidencia → integraciones → higiene → capacidades.

## R0 — Congelar garantías (hecho, mantener)

Objetivo: que nada futuro rompa lo verificado. Red: suites autoridad (129),
chokepoint AST, e2e/superficies, `test_21` idempotencia. Cierre: suite verde.

## R1 — Cerrar bypass Telegram (E-02) ✅

Acts `SCREEN_CAPTURE`/`AUDIO_CONTROL` por chokepoint; puente con allowlist.
Hecho en U1 y siguientes (captura → `send_photo`, atajos físicos). Complejidad baja.

## R2 — Logger estructurado + lockfile (E-17) ✅

Sustituir prints por logging JSON con redacción (conservar `redact_secrets`);
`requirements.lock`. Aceptación: sin secretos en logs; `pip install -r` reproducible.

**Hecho (2026-09-30):** `core/logging_util.py`, cableado en server/GUI/Telegram,
`requirements.lock`, `tests/test_r2_logging.py`. Informe en el repo de docs:
`docs/engineering/r2_logging/R2_INFORME.md`.

Complejidad baja. Tokens: ~10-20k.

## R3 — Watchdog y scheduler (E-18) ✅ (en proceso)

`core/watchdog.py` reanuda misiones evaluadas como seguras (D-7). El Programador
de tareas de Windows queda opcional; no se auto-aprueba EXEC.

## R4 — Routing por salud y costos (E-19) ✅

Health real que dirige tráfico, cascada configurable, registro de uso por proveedor,
techos de costo. Aceptación: caída de groq deriva sin intervención; uso visible.

**Hecho (2026-09-30):** `providers.cascade` / `max_calls_per_hour`, ledger
`memory/provider_usage.jsonl`, `tests/test_llm_provider_routing.py` (TestR4HealthCascade).
Informe: `docs/engineering/r4_provider_routing/R4_INFORME.md`.

Complejidad media. Tokens: ~25-50k.

## R5 — Integración Telegram Bot API (canal superior) ✅ (código)

Polling con allowlist, daemon durable, `TELEGRAM_STATUS/SEND/TEST`. Residual del
dueño: probar ida y vuelta con el bot real (captura, play, minimizar).

## R6 — Higiene y consolidación (E-20, E-15) ✅

**Hecho (2026-09-30):** `core/autoloop.py` retirado (0 importadores).
`core/subagents.py` se conserva: lo usa `tests/test_acceptance_surfaces.py`.
`ToolRegistry.list_tools()` (registro ∪ `ACT_TYPES`) alimenta el parser de texto.
`STATUS.md` es el estado corto. Los `AVATAR_*.md` históricos no se archivaron
(rompería enlaces); quedan como auditoría, no como estado vivo.

## R7 — Verificador externo (E-03, solo si ADR-01 dice sí)

Proceso separado + IPC para Modelo-B. Es el único cambio arquitectónico mayor;
no iniciar sin ADR y sin amenaza que lo justifique. Complejidad alta. Tokens: 100k+.

## MD002 — Directriz propuesta (no iniciar)

Texto: `MASTER_DIRECTIVE_002.md`. Dictamen: `MASTER_DIRECTIVE_002_COMPARISON.md`.
No reemplaza R0–R7. Ninguna sección de esa directriz se implementa hasta que
Mauro acepte una unidad concreta del dictamen.

## Puerta de cada fase

Reproducir síntoma → implementar → test dedicado → suite verde → evidencia en
ledger/log → actualizar este roadmap. Rollback: `git revert` (repo limpio, 4 commits).
Estimaciones de tokens marcadas como estimaciones, no compromisos.
