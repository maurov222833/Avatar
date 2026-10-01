# AVATAR — Registro de errores y riesgos (evidencia)

Estados: `CONFIRMED_OPEN` (abierto), `CONFIRMED_FIXED` (corregido),
`CONFIRMED_PARTIALLY_FIXED` (parcial), `NOT_REPRODUCED`, `HISTORICAL_ONLY`,
`BLOCKED_EXTERNAL/INFRASTRUCTURE`. Confianza: HIGH (reproducido), MEDIUM (traza),
LOW (histórico).

## Críticos y altos

| ID | Nombre | Sev | Estado | Evidencia / causa | Corrección y verificación |
|---|---|---|---|---|---|
| E-01 | Fuga de claves en `POST /api/config/update` | Alta | CONFIRMED_FIXED (HIGH) | `server.py:107` devolvía `config.json` crudo; probado con TestClient (5 secretos) | `redact_secrets` en la respuesta + `test_config_update_does_not_return_secrets_in_clear` |
| E-02 | Bypass Telegram fuera de chokepoint | Alta | CONFIRMED_FIXED (HIGH) | Captura, audio y hotkeys pasan por `chokepoint.perform`. Allowlist numérica en chat privado. | R1. Alt+F4 y Alt+Tab no son atajos permanentes. Prueba en el bot real: pendiente del dueño. |
| E-03 | Amenaza Modelo-B (mismo proceso) | Alta | Abierta por diseño (HIGH) | `authority_core.py:19-28`, `act_chokepoint.py:25-28`; HMAC/ledger no resisten código arbitrario local | Requiere verificador externo (ADR-01); sin él, solo Modelo-A |
| E-04 | Forja/reúso de autorización y evidencia | Alta | CONFIRMED_FIXED en Modelo-A (HIGH) | Suites 003/004/consolidación (129 tests): replay, substitution, mocks | `frozen+HMAC`, `PermissionError`, ledger single-use, re-derivación |
| E-05 | Sello de requisitos manipulable con resellado | Media | CONFIRMED_PARTIALLY_FIXED (MEDIUM) | `state_db.py:221-227` lo admite; detección → `BLOCKED`, no prevención | Solo proceso separado lo cierra |
| E-06 | `current_goal` sin asignar tragado por `except` | Alta | CONFIRMED_FIXED (HIGH) | Review-005 §3.6; hoy `orchestrator.py:251` crea primero y l.268-273 propaga | Flujo leído + suite verde |
| E-07 | Resume desconectado ("continúa mañana" imposible) | Alta | CONFIRMED_FIXED (HIGH) | 0 llamadas runtime en su día | `resume_mission()` + `POST /api/missions/resume` + test_21 |
| E-08 | Plantillas presentadas como éxito | Media | CONFIRMED_FIXED (HIGH) | "Auditoría…" hardcodeada; vacíos presentados como texto | Respaldo ejecutivo + `provider_empty` + corte×2 + truncado |
| E-09 | Relleno LIST_DIR/READ_FILE como avance | Media | CONFIRMED_FIXED (MEDIUM) | 126 acts de ruido en ledger real | Lectura ≠ completada + corte de racha + acts nativos WA |
| E-10 | Secretos en plano por agentes (`token.txt`) | Alta | CONFIRMED_FIXED (HIGH) | Avatar escribió el token del bot en raíz (46 chars) | Migrado a `.env`, archivos eliminados, gitignore blindado, pre-commit escaneado |

## Medios y bajos

| ID | Nombre | Estado | Evidencia |
|---|---|---|---|
| E-11 | Pelea por perfil Chromium (ventanas en blanco) | CONFIRMED_FIXED | Lock `PERFIL_OCUPADO` + barrido garantizado + navegador compartido (`whatsapp_reader.py`) |
| E-12 | Playwright sync dentro de loop asyncio | CONFIRMED_FIXED | `run_blocking` en hilo dedicado; probado `RESULT:OK` en loop |
| E-13 | Relectura ciega a emojis/espacios | CONFIRMED_FIXED | `_text_key` + prueba física |
| E-14 | Tests atados al config real | CONFIRMED_FIXED | Policies y `local_fallback` fijados por test |
| E-15 | `main_gui`/`autoloop`/subagentes muertos o sombra | HISTORICAL_ONLY (MEDIUM) | `core/autoloop.py` retirado. `core/subagents.py` solo lo usa la suite de superficies. |
| E-16 | RAG por palabras, no vectorial | CONFIRMED_PARTIALLY_FIXED (HIGH) | Sigue sin vectores. Una palabra partida por guion ya coincide (`canal` encuentra `canal-24-7`). |
| E-17 | Sin logger estructurado | CONFIRMED_FIXED (HIGH) | `core/logging_util.py` y `requirements.lock`. Consola solo si el logger no arranca. |
| E-18 | Sin scheduler/watchdog de proceso | CONFIRMED_PARTIALLY_FIXED (HIGH) | `core/watchdog.py` reanuda misiones seguras. El Programador de tareas de Windows no se instaló. |
| E-19 | Capacidades proveedor estáticas + fallback ciego | CONFIRMED_PARTIALLY_FIXED (MEDIUM) | Cascada por salud, ledger de uso y techo por hora. Las capacidades de cada adaptador siguen declaradas en código. |
| E-20 | 111 `.md` sin estado único vivo | CONFIRMED_PARTIALLY_FIXED (LOW) | `STATUS.md` es el estado corto. Los `AVATAR_*.md` históricos se dejaron para no romper enlaces. |

## Verificación de cierre (todas)

Reproducir el síntoma original → aplicar corrección → test dedicado en verde →
suite completa verde → evidencia en ledger/log donde aplique. Ningún cierre por
"test pasa" sin reproducir primero.
