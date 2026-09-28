# AVATAR AI — CHECKPOINT ENGINE + RESUME ENGINE (FASE 2)
## DOCUMENTACIÓN TÉCNICA, CICLO DE VIDA Y RESILIENCIA ANTE CRASHES

```text
COMPONENTS: CheckpointEngine (core/checkpoint_engine.py), ResumeEngine (core/resume_engine.py)
PERSISTENCE: StateEngine (core/state_db.py - SQLite WAL Mode)
PHASE: Phase 2 (Fault Tolerance & Task Resume)
STATUS: FULLY VERIFIED & INTEGRATED
FULL REGRESSION: 254/254 PASS
```

---

## 1. ARQUITECTURA GENERAL Y CICLO DE VIDA

`CheckpointEngine` y `ResumeEngine` proporcionan tolerancia a fallos trans-proceso para misiones complejas de Avatar AI.

Garantizan que si el proceso Python o la máquina de Windows se apaga o sufre una caída forzada (`kill -9`) en medio de un plan de tareas:
1. Ninguna tarea verificada se vuelve a ejecutar (Principio de Anti-Duplicación).
2. Las herramientas **no idempotentes** interrumpidas en estado incierto NO se re-ejecutan a ciegas.
3. Se invoca a `PhysicalFactVerifier` para confirmar empíricamente si el efecto secundario de la herramienta ya ocurrió.
4. Las misiones se reanudan exactamente desde la primera tarea no completada y segura.

```mermaid
flowchart TD
    Start["Boot Process / Start Task"] --> PreChk["CheckpointEngine: PRE_TOOL_EXECUTION (SQLite WAL Commit)"]
    PreChk --> ExecTool["Tool Dispatcher: Execute Tool"]
    ExecTool --> PostChk["CheckpointEngine: POST_TOOL_EXECUTION"]
    PostChk --> Verify["Verifier / PhysicalFactVerifier"]
    Verify -->|PASS| MarkVer["CheckpointEngine: mark_verified (VERIFIED)"]
    Verify -->|FAIL| Recovery["RecoveryEngine: Replan / Retry"]

    subgraph Crash Recovery Flow
        Crash["Crash / Interrupt (kill -9)"] -.-> Reboot["Reboot Avatar / ResumeEngine"]
        Reboot --> Inspect["ResumeEngine: inspect_active_missions()"]
        Inspect --> IdemCheck{"Tool Idempotency?"}
        IdemCheck -->|IDEMPOTENT| RetrySafe["Safe Retry: PRE_TOOL_EXECUTION"]
        IdemCheck -->|NON_IDEMPOTENT / UNKNOWN| Uncertain["Mark UNCERTAIN_EXECUTION"]
        Uncertain --> FactCheck{"PhysicalFactVerifier Check Effect?"}
        FactCheck -->|YES (Effect Occurred)| MarkVer
        FactCheck -->|NO (Effect Did Not Occur)| RetrySafe
        FactCheck -->|UNKNOWN| Blocked["UNCERTAIN_EXECUTION Blocked (No Auto-retry)"]
    end
```

---

## 2. ESTADOS DE TAREA Y CLASIFICACIÓN DE IDEMPOTENCIA

### 2.1. Estados de Tarea
* `PENDING`: Tarea registrada en el planificador, aún no iniciada.
* `PRE_TOOL_EXECUTION`: Checkpoint atómico guardado en SQLite WAL *antes* de invocar la herramienta.
* `IN_PROGRESS`: Herramienta en ejecución.
* `POST_TOOL_EXECUTION`: Salida de la herramienta capturada, pendiente de verificación.
* `COMPLETED`: Salida y evidencia observadas.
* `VERIFIED`: Verificada empíricamente por `Verifier` o `PhysicalFactVerifier`.
* `FAILED`: Fallo no recuperable o presupuesto de reintentos agotado.
* `UNCERTAIN_EXECUTION`: Proceso interrumpido entre `PRE_TOOL` y `POST_TOOL` para herramienta no idempotente.

### 2.2. Clasificación de Idempotencia de Herramientas
* **IDEMPOTENT (`IDEMPOTENT`):** Operaciones de solo lectura que pueden reejecutarse sin efectos secundarios destructivos (`READ_FILE`, `LIST_DIR`, `FETCH_URL`, `WEB_SEARCH`).
* **NON_IDEMPOTENT (`NON_IDEMPOTENT`):** Operaciones que alteran el entorno o poseen efectos secundarios (`WRITE_FILE`, `COMMAND`, `SEND_WHATSAPP`, `DELETE_FILE`, `MOVE_FILE`).
* **DESCONOCIDAS (`UNKNOWN`):** Herramientas no registradas expresamente. **Se tratan por defecto como `NON_IDEMPOTENT` por seguridad estricta.**

---

## 3. CHECKPOINT ENGINE (`core/checkpoint_engine.py`)

* **Atomicidad Pre-Tool:** Invocación obligatoria de `save_pre_tool_checkpoint()` antes de ejecutar la herramienta. Si el `commit` de SQLite WAL falla, se lanza una excepción y la herramienta NO se ejecuta.
* **Trazabilidad Post-Tool:** `save_post_tool_checkpoint()` registra la salida y crea la evidencia en `evidences`.
* **Verificación:** `mark_verified()` marca el estado `VERIFIED` y guarda la prueba física en `verification_records`.

---

## 4. RESUME ENGINE (`core/resume_engine.py`)

Al inicializarse Avatar, `ResumeEngine` consulta las misiones activas en `StateEngine`:

1. Reconstrucción completa desde `StateEngine` (cero dependencia de memoria volátil).
2. Clasificación de Estado de Misión:
   - `NO_ACTIVE_MISSION`
   - `ACTIVE_MISSION_SAFE_TO_RESUME`
   - `ACTIVE_MISSION_UNCERTAIN`
   - `ACTIVE_MISSION_FAILED`
   - `ACTIVE_MISSION_COMPLETED`
3. Omisión estricta de tareas `VERIFIED` / `COMPLETED` (Garantía Anti-Duplicación).
4. Reanudación secuencial a partir del primer paso pendiente.

---

## 5. EVIDENCIA FÍSICA Y CRASH TEST DEMOSTRADO

La suite [tests/test_checkpoint_resume.py](file:///b:/PROYECTOS%20ANTIGRAVITY/Avatar/tests/test_checkpoint_resume.py) incluye la prueba E2E de simulación de caída real de 5 tareas (`test_20_e2e_5_task_mission_resume`):

1. Misión creada con 5 tareas (`TASK_1` a `TASK_5`).
2. `TASK_1` a `TASK_3` ejecutadas y verificadas.
3. Simulación de cierre físico del proceso Python (`state_db.close()`).
4. Instanciación de un nuevo proceso Avatar (`StateEngine` y `ResumeEngine` limpios).
5. Reanudación: `ResumeEngine` omite `TASK_1`, `TASK_2` y `TASK_3` y ejecuta únicamente `TASK_4` y `TASK_5`, completando la misión al 100%.

---

## 6. PREPARACIÓN PARA FASE 3 (DESKTOP CONTROL & VISION)

Con las Fases 1 y 2 completadas y verificadas:
- Avatar cuenta con persistencia SQLite WAL autoritativa.
- Avatar soporta interrupciones y caídas de proceso sin perder misiones ni duplicar comandos.
- Las Fases 3 (Desktop Control) y 4 (Playwright Browser) pueden construirse sobre esta base sólida.
