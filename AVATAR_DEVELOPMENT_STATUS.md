# AVATAR — ESTADO DE DESARROLLO

> **Este es el documento de referencia del proyecto.** Actualízalo en cada hito.
> Si una sesión se interrumpe, retoma desde aquí.

**Última actualización:** 2026-09-28 · **Suite:** 438 tests · 0 fallos

---

## 1. Por qué existe este documento

Cuatro ciclos anteriores (auditorías 002–005) sumaron ~2.000 líneas de maquinaria de autoridad
y ~1.400 de tests, y Aun así el sistema **no hacía nada útil**: la ruta de ejecución real nunca
creaba una misión, así que todo ese subsistema era código muerto.

Este documento existe para que eso no vuelva a pasar: cada hito debe dejar el producto en un
estado **más funcional**, no solo más analizado.

---

## 2. Arquitectura actual (real, no la documentada antes)

```
usuario (CLI / server.py / bridges / autoloop)
        │
        ▼
AvatarOrchestrator.process_user_input()          ← único punto de entrada
        │
        ├─ crea Goal cognitivo
        ├─ crea y persiste MISIÓN (StateEngine)    ← reparado en esta sesión
        │
        ▼
   bucle ReAct ── LLM propone herramienta
        │
        ▼
   ActChokepoint.perform()                        ← NUEVO: punto único de efecto
        ├─ política (permiso / dry-run / workspace)
        ├─ ejecuta
        ├─ observa (independiente del executor)
        └─ registra en tabla `acts`
        │
        ▼
   _reconcile_mission()                          ← NUEVO: cierra el estado de la misión
        │
        ▼
   respuesta al usuario
```

**Regla central:** ningún efecto secundario ocurre fuera del chokepoint.

---

## 3. Qué se reparó en esta sesión (IMPLEMENTATION 006)

| # | Defecto | Impacto | Estado |
|---|---|---|---|
| 1 | `current_goal` usado antes de asignarse en `orchestrator.py` | El orquestador **nunca creaba misión**. Toda la autoridad era inalcanzable. | **REPARADO** |
| 2 | La suite escribía en `memory/state_engine.db` (la BD operativa) | Corrompía datos reales del propietario en cada `pytest` | **REPARADO** (`tests/conftest.py`) |
| 3 | `SEND_WHATSAPP` sin política, sin registro, sin dry-run | Mensaje real a una persona sin control ni trazabilidad | **REPARADO** (chokepoint) |
| 4 | La misión quedaba `IN_PROGRESS` para siempre al cerrar un turno | Misiones colgantes que Resume intentaba reanudar | **REPARADO** (`_reconcile_mission`) |
| 5 | Doble de test emitía formato crudo de Gemini | Tests de aceptación pasaban **sin despachar ninguna herramienta** (verde vacío) | **REPARADO** |

---

## 4. Módulos nuevos

- **`core/act_chokepoint.py`** (297 líneas) — punto único de efecto secundario. Política,
  ejecución, observación independiente y registro append-only en la tabla `acts`.
- **`tests/conftest.py`** (45 líneas) — aislamiento global de base de datos para toda la suite.
- **`tests/test_acceptance_e2e.py`** (15 tests) — aceptación end-to-end por la ruta real.

## 5. Módulos modificados

- `core/orchestrator.py` — orden de inicialización, reconciliación de misión, dispatch vía chokepoint, `operating_mode()`.
- `tests/test_f05_adaptive_cognitive_progression.py` — mock actualizado a la nueva firma.

---

## 6. Modos de operación (lo que el propietario controla)

| Modo | Significado |
|---|---|
| `DRY_RUN` | **Por defecto.** Los efectos externos se simulan y se registran, no se envían. |
| `LIVE_LOCAL_ONLY` | Acciones locales reales; mensajes externos siguen bloqueados. |
| `LIVE_WITH_EXTERNAL_EFFECTS` | Solo si el propietario lo activa explícitamente en `config.json`. |

Configuración (`config.json`):

```json
{
  "autonomy": {
    "dry_run": true,
    "allow_external_messages": false
  },
  "security": {
    "allowed_workspace": "b:/PROYECTOS ANTIGRAVITY/Avatar",
    "denied_act_types": []
  }
}
```

Consultar el modo actual: `/status` en el CLI, o `AvatarOrchestrator.operating_mode()`.

---

## 7. Cómo lanzar Avatar

```bash
cd b:/PROYECTOS ANTIGRAVITY/Avatar
python main.py            # CLI interactiva
python server.py          # servidor HTTP
```

Requiere `.env` con las llaves del proveedor (ver `.env.example`). Sin llaves, el LLM remoto
no está disponible — eso se reporta honestamente como `BLOCKED_EXTERNAL`, no como éxito.

---

## 8. Estado de capacidades (honesto)

| Capacidad | Estado | Nota |
|---|---|---|
| Lectura de archivos / listar directorios | `VERIFIED` | Probado end-to-end por la ruta real |
| Escritura de archivos | `PARTIAL` | Funciona dentro del workspace; bloqueada fuera |
| Comandos PowerShell | `IMPLEMENTED_NOT_INTEGRATED` | El ejecutor existe; falta exercised E2E controlado |
| Persistencia de misiones y tareas | `VERIFIED` | SQLite WAL, migración probada |
| Checkpoint / Resume | `PARTIAL` | Lógica existe; no validado end-to-end tras la reconexión |
| Envío WhatsApp real | `BLOCKED_SECURITY` | Ahora bloqueado por política; requiere opt-in del propietario |
| Visión de escritorio | `SIMULATED_ONLY` | Sin prueba física E2E |
| Navegador (Playwright) | `NOT_IMPLEMENTED` | Sin verificador específico |
| OCR | `NOT_IMPLEMENTED` | — |
| Telegram / servidor HTTP | `IMPLEMENTED_NOT_INTEGRATED` |Necesitan reconfigurar tras el chokepoint |

---

## 9. Problemas abiertos

1. **`server.py` y los bridges no se han revalidado** tras el cambio del chokepoint. Requieren
   una pasada de integración.
2. **El bucle ReAct no despacha para `INFORMATIVE_QUERY`** en algunos casos; la clasificación
   de interacción merece revisión.
3. **La ruta multi-tarea determinista** usa `ContinuousExecutionEngine` y aún no pasa contexto
   de misión al chokepoint.
4. **Checkpoint/Resume** no se ha revalidado end-to-end desde la reconexión.
5. **El modelo de capabilities sigue siendo mayormente decorativo**: 1 de 5 capabilities es
   verificable, y es autorreferencial (el SQLite certifica su propia existencia).

---

## 10. Siguiente tarea concreta

**Revalidar las superficies de entrada restantes** (`server.py`, `bridges/*`, `interface/cli.py`,
`core/autoloop.py`) contra el chokepoint, y añadir cobertura de aceptación para cada una.

Criterio de aceptación: cada superficie entra por la ruta real, produce una misión persistida,
registra al menos un acto, y respeta la política de efectos externos.

---

## 11. Cómo verificar el estado actual

```bash
# suite completa
python -m pytest tests/ -q                     # esperado: 438 passed

# aceptación end-to-end
python -m pytest tests/test_acceptance_e2e.py -v

# demostración por la ruta real (no toca la BD operativa)
python %TEMP%\opencode\demo_e2e.py
```

**Lo que los tests NO prueban:** que un proveedor LLM real esté disponible, que un mensaje real
de WhatsApp se entregue, ni nada sobre amenazas para las que no fueron diseñados. Un test
verde no significa que toda integración externa esté viva.
