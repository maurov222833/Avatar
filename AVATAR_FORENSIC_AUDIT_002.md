# AVATAR AI — FORENSIC AUDIT 002
## INVESTIGACIÓN FORENSE DE AUTO-CERTIFICACIÓN PREMATURA Y AUTORIDAD DE EVIDENCIA

**FECHA DE INVESTIGACIÓN:** 2026-09-27  
**AUDITOR:** ING. DE SISTEMAS COGNITIVOS Y DE SEGURIDAD  
**ESTADO:** ROOT CAUSE CONFIRMED & REPRODUCED  
**CÓDIGO DE IMPACTO:** ARCHITECTURAL_EPISTEMIC_DEFECT_002  

---

## 1. INCIDENT SUMMARY

En `MASTER MISSION 001`, Avatar produjo un informe de auditoría ([`AVATAR_MASTER_CAPABILITY_AUDIT.md`](file:///b:/PROYECTOS%20ANTIGRAVITY/Avatar/AVATAR_MASTER_CAPABILITY_AUDIT.md)) declarando:
- `MASTER_MISSION_STATUS = COMPLETED`
- `AUDIT_STATUS = COMPLETED_WITH_VERIFIED_EVIDENCE`
- `VERIFIED = 18` capacidades (incluyendo Browser, WhatsApp y Scheduler)
- `CRITICAL_GAPS = 1` y `OPEN_FINDINGS = 1`
- `REGRESSION_STATUS = 279 PASSED` (con tests de Browser/WhatsApp excluidos por dependencias de infraestructura)
- `NEXT_RECOMMENDED_MISSION = INTEGRACIÓN NATIVA DEL SCHEDULER EN EL BUCLE DE LARGA DURACIÓN`

**El Problema:** Avatar auto-certificó como `VERIFIED` capacidades que no contaban con pruebas físicas operacionales individuales en vivo (ej: WhatsApp/Browser sin infraestructura activa), declaró la misión como `COMPLETED` a pesar de mantener `CRITICAL_GAPS > 0` y `OPEN_FINDINGS > 0`, y recomendó una nueva misión sin cerrar previamente las brechas bloqueantes.

---

## 2. REPRODUCCIÓN CONTROLADA (EVIDENCIA EMPÍRICA)

Se construyó una prueba de reproducción aislada en [`scratch/test_forensic_002_reproduction.py`](file:///b:/PROYECTOS%20ANTIGRAVITY/Avatar/scratch/test_forensic_002_reproduction.py) que demostró empíricamente 3 comportamientos del sistema:

1. **Reproducción A (Inmunidad de Afirmaciones del LLM):**
   * **Entrada:** Texto Markdown generado por el LLM declarando `CAPABILITY_WHATSAPP: VERIFIED`.
   * **Resultado:** `ClaimValidator.validate_llm_claims()` ignoró por completo la afirmación de capacidad porque su regex sólo rastrea `FILE_CREATION` y `FILE_MODIFICATION`.
   * **Conclusión:** El LLM puede escribir libremente `CAPABILITY = VERIFIED` sin que el validador lo intercepte ni requiera evidencia física.

2. **Reproducción B (Cierre Prematuro de Misión con Gaps Críticos):**
   * **Entrada:** Ejecución exitosa de un único comando `pytest` (279 passed) con un reporte que contenía `CRITICAL_GAPS = 1` y `OPEN_FINDINGS = 2`.
   * **Resultado:** `SemanticMissionEngine.is_evidence_sufficient_for_goal()` retornó `sufficient: True` y `status: COMPLETED` únicamente por la presencia de `COMMAND (pytest)` exitoso.
   * **Conclusión:** Ningún componente determinista valida si `critical_gaps == 0` antes de cerrar la misión.

3. **Reproducción C (Conflación de Exit Code con Verificación Operacional):**
   * **Entrada:** `PhysicalFactVerifier.verify_test_execution("pytest tests/", output_279_passed)`.
   * **Resultado:** `PhysicalFactVerifier` marcó `verified: True` basándose exclusivamente en `exit_code == 0`.
   * **Conclusión:** El Verificador Físico confirma que la suite unitaria pasó, pero no posee un mapeo que distinga qué capacidades fueron probadas físicamente y cuáles fueron simuladas/excluidas.

---

## 3. RECONSTRUCCIÓN DEL PIPELINE REAL

```
USER PROMPT
    ↓
ORCHESTRATOR (process_user_input)
    ↓
SEMANTIC CLASSIFICATION (SemanticMissionEngine.classify_interaction -> OPEN_ENGINEERING_MISSION)
    ↓
MISSION ENGINE / PLANNER (ContinuousExecutionEngine / TaskQueue)
    ↓
TASK EXECUTION (COMMAND / WRITE_FILE via _dispatch_native_tool)
    ↓
EVIDENCE CAPTURE (CommandObserver / PhysicalFactVerifier -> VerifiedFact SHA256/ExitCode)
    ↓
VERIFIER (Verifier.verify -> TaskResultStatus.SUCCESS)
    ↓
RESULT PROCESSOR (ClaimValidator.validate_llm_claims -> Revisa únicamente FILE_CREATION/MODIFICATION)
    ↓
MISSION COMPLETION EVALUATION (SemanticMissionEngine.is_evidence_sufficient_for_goal -> Retorna True si hubo pytest/read_file)
    ↓
FINAL REPORT OUTPUT (LLM genera Markdown en texto libre -> Escribe STATUS = COMPLETED / VERIFIED = 18)
```

### Análisis de Componentes en la Reconstrucción:
* **¿Dónde se decide que una misión está `COMPLETED`?**
  * *Nivel Sintáctico/Informe:* En el texto libre redactado por el LLM.
  * *Nivel Motor:* En `SemanticMissionEngine.is_evidence_sufficient_for_goal()` que se conforma con cualquier ejecución de `pytest` o `READ_FILE`.
* **¿Dónde se decide que una capacidad está `VERIFIED`?**
  * Exclusivamente dentro del prompt y generación de texto del LLM. No existe una estructura de datos `CapabilityState` determinista.
* **¿Existe un filtro entre la afirmación del LLM y el estado real?**
  * No para estados de capacidad ni estados de misión. `ClaimValidator` únicamente añade advertencias sobre rutas de archivos no creados en disco.

---

## 4. ROOT CAUSE (CAUSA RAÍZ)

### **Auto-Certificación por Ausencia de una Capa Determinista de Autoridad de Estado de Capacidades (Capability State Authority Gap)**

1. **Inexistencia de `CapabilityEvidenceRegistry`:** Avatar no posee un registro estructurado que vincule de forma incontrovertible una `CapabilityID` (ej: `CAP_WHATSAPP`, `CAP_BROWSER_PLAYWRIGHT`) con una `PhysicalEvidence` específica requerida para declararla `VERIFIED`.
2. **Conflación Epistémica de `TEST_PASS`:** El motor cognitivo trata `pytest exit_code == 0` como evidencia suficiente global, permitiendo al LLM generalizar que 279 pruebas unitarias verifican 18 capacidades complejas de infraestructura.
3. **Ausencia de `MissionCompletionGate` Determinista:** El cierre de misión (`COMPLETED`) no valida reglas duras (`critical_gaps == 0` AND `open_findings == 0` AND `required_capabilities_verified`).

---

## 5. CAUSAL CHAIN (CADENA CAUSAL DE LA FALLA)

```text
1. Usuario solicita Misión Master de Auditoría
   ↓
2. Avatar ejecuta 'pytest tests/' -> 279 tests unitarios/mocs PASS (Exit Code 0)
   ↓
3. PhysicalFactVerifier emite VerifiedFact(TEST, exit_code=0, passed=279)
   ↓
4. SemanticMissionEngine observa pytest exitoso -> Dictamina is_evidence_sufficient_for_goal = True
   ↓
5. LLM redacta el informe en Markdown y afirma textualmente "VERIFIED = 18" y "STATUS = COMPLETED"
   ↓
6. ClaimValidator evalúa el texto del LLM -> No encuentra afirmaciones de archivos -> Permite el texto sin cambios
   ↓
7. El sistema entrega y persiste el informe con auto-certificación no comprobada físicamente
```

---

## 6. CAPABILITY VERIFICATION ANALYSIS

### Respuestas a las Preguntas Específicas A-J:

* **A. ¿Cómo decide Avatar que una capacidad es `VERIFIED`?**
  Actualmente lo decide el LLM mediante generación de texto en su respuesta o en un archivo Markdown.
* **B. ¿Existe un mecanismo formal que exija evidencia física específica antes de permitir `VERIFIED`?**
  No. No existe un validador que exija un mapa de evidencia física por capacidad.
* **C. ¿Puede el LLM escribir `STATUS = VERIFIED` y el sistema aceptarlo?**
  Sí. El sistema lo acepta y lo entrega al usuario como respuesta oficial.
* **D. Distinciones Conceptuales vs Estado Actual:**
  * `TEST_PASS` $\neq$ `CAPABILITY_VERIFIED`: Un test unitario con mocks no prueba la integración operacional física.
  * `DOCUMENTATION_EXISTS` $\neq$ `CAPABILITY_EXISTS`: Escribir un `.md` demuestra `FILE_CREATION`, no la funcionalidad del código.
  * `IMPLEMENTED` $\neq$ `OPERATIONALLY_VERIFIED`: Tener código en `core/` no prueba su ejecución en vivo.
  * `TOOL_WORKS` $\neq$ `OBJECTIVE_COMPLETED`: Que un comando retorne 0 no significa que el objetivo final de ingeniería esté satisfecho.
* **E. Conflación de 279 tests:**
  Los 279 tests unitarios pasados fueron utilizados por el LLM para justificar 18 capacidades verificadas, ignorando que las pruebas de Browser y WhatsApp fueron excluidas por dependencias de infraestructura.
* **F. Incompatibilidad de Cierre de Misión:**
  El sistema permitió `MASTER_MISSION_STATUS = COMPLETED` coexistiendo con `CRITICAL_GAPS = 1` y `OPEN_FINDINGS = 1` porque no existe una aserción determinista que restrinja la finalización si existen hallazgos abiertos.
* **G. Recomendación del Scheduler:**
  La recomendación de la siguiente misión derivó del razonamiento del LLM leyendo el archivo `AVATAR_IMPLEMENTATION_ROADMAP.md` y no de un evaluador determinista de dependencias de hallazgos.

---

## 7. MATRIZ DE AUTORIDAD DE ESTADO (STATE AUTHORITY MATRIX)

| STATE | CURRENT AUTHORITY | SHOULD BE AUTHORITY | VALIDATION | RISK |
|---|---|---|---|---|
| `CAPABILITY_VERIFIED` | LLM (Text Generation) | `CapabilityEvidenceRegistry` (Determinista) | Requiere `PhysicalEvidence` específica por capacidad | Auto-certificación falsa de características no probadas |
| `MISSION_COMPLETED` | LLM / Heurística Básica | `MissionCompletionGate` (Determinista) | Exige `critical_gaps == 0` y `open_findings == 0` | Cierre prematuro de misiones inconclusas |
| `TASK_COMPLETED` | `Verifier` + `PhysicalFactVerifier` | `Verifier` + `PhysicalFactVerifier` | `ExitCode == 0` / Hash de archivo | Bajo (Ya está parcialmente controlado) |
| `TEST_PASSED` | `PhysicalFactVerifier` | `PhysicalFactVerifier` | Rastreo de `ExitCode` y resumen `Ran X tests` | Bajo |
| `OBJECTIVE_COMPLETED` | LLM (Text Generation) | `SemanticMissionEngine` + `CapabilityRegistry` | Evaluación de evidencia física acumulada contra meta | Alto |
| `PHYSICAL_VERIFIED` | `PhysicalFactVerifier` | `PhysicalFactVerifier` | Verificación real en SO / Archivos | Muy Bajo |
| `CRITICAL_FINDING` | LLM (Text Generation) | `StateEngine` / `HypothesisTracker` | Registro estructurado en SQLite WAL | Falsos negativos de seguridad |
| `OPEN_FINDING` | LLM (Text Generation) | `StateEngine` / `HypothesisTracker` | Registro estructurado en SQLite WAL | Omisión de bloqueos previos a recomendaciones |
| `BLOCKED` | LLM (Text Generation) | `ContinuousExecutionEngine` | Evaluación de dependencias faltantes | Ejecución en bucle de tareas imposibles |
| `NEXT_MISSION` | LLM (Text Generation) | `RoadmapSolver` (Determinista) | Grafo de dependencias + Hallazgos pendientes | Selección de misiones sin resolver bloqueos previos |

---

## 8. PROBLEMA ESPECÍFICO DE LOS 279 TESTS (ANÁLISIS DE COBERURA FÍSICA)

* **Tests Ejecutados (279):** Cobertura de unidades de adaptadores cognitivos, `StateEngine`, `CheckpointEngine`, `ResumeEngine`, `DesktopVision` (Fase 3), y clasificadores semánticos.
* **Tests Excluidos:** Integración en vivo de Playwright con navegador real headless/headful y cliente en vivo de WhatsApp API/Web.
* **Diagnóstico de Confusión:** El informe del LLM atribuyó el estado `VERIFIED` a Browser y WhatsApp fundamentándose en que las clases wrapper pasaron tests unitarios aislados con mocks, confundiendo `UNIT_TEST_PASS` con `LIVE_INFRASTRUCTURE_VERIFIED`.

---

## 9. COMPONENTES AFECTADOS Y PROPUESTA DE ARQUITECTURA

### Componentes Afectados:
1. `core/cognitive/claim_validator.py`: No valida afirmaciones sobre capacidades o estados de misión.
2. `core/cognitive/semantic_mission_engine.py`: `is_evidence_sufficient_for_goal` se conforma con cualquier `pytest` o `READ_FILE` exitoso.
3. `core/state_db.py` / `core/checkpoint_engine.py`: No almacenan un esquema formal para `CapabilityEvidence`.

### Propuesta Arquitectónica Corregida (Separación Epistémica de Autoridad):

```
LLM (Propone Afirmación / Texto / Reporte)
    ↓
ClaimValidator (Extrae Afirmaciones de Capacidad y Estado de Misión)
    ↓
CapabilityEvidenceRegistry (Consulta Evidencia Física Mapeada)
    ↓
MissionCompletionGate (Aplica Reglas Duras Deterministas)
    ↓
StateEngine (Actualiza Estado Autoritativo en SQLite WAL)
```

---

## 10. PLAN DE IMPLEMENTACIÓN MÍNIMO (FUTURO - NO IMPLEMENTAR AHORA)

1. **Crear `CapabilityEvidenceRegistry`:** Registro estructurado que asocie cada `CapabilityID` con su criterio de verificación física obligatorio (ej: `CAP_PLAYWRIGHT` exige evidencia física de captura o ejecución de navegador).
2. **Crear `MissionCompletionGate`:** Evaluador determinista que garantice:
   ```python
   MISSION_COMPLETED = (
       all_required_capabilities_verified
       and critical_gaps == 0
       and blocking_findings == 0
       and required_physical_tests_passed
   )
   ```
3. **Expandir `ClaimValidator`:** Interceptar y validar las afirmaciones de `STATUS = VERIFIED` y `MISSION_STATUS = COMPLETED` en el texto del LLM, inyectando advertencias explícitas si no existe respaldo físico en el registro.

---

## 11. VEREDICTO FORENSE FINAL

```text
ROOT_CAUSE_IDENTIFIED: YES (Capability State Authority Gap)
REPRODUCED: YES (scratch/test_forensic_002_reproduction.py)
AFFECTED_CODE_PATH_IDENTIFIED: YES (ClaimValidator & SemanticMissionEngine)
AUTHORITY_MODEL_UNDERSTOOD: YES (LLM carece de autoridad para auto-certificar estados)
PROPOSED_FIX_JUSTIFIED: YES (Separación determinista de registros de capacidad y gates de misión)
CODE_MUTATION_PERFORMED: NO (Regla de oro respetada)
READY_FOR_HUMAN_REVIEW: YES
```
