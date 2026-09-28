# 03 — EXECUTION FLOW
## AVATAR AI — INDEPENDENT ARCHITECTURE REVIEW 001

**Fecha de Auditoría:** 27 de Septiembre de 2026  
**Auditor:** Independent Architecture Auditor (Antigravity Agent)  
**Estado:** COMPLETED  

---

### 1. Reconstrucción del Flujo de Ejecución Real (Grounded in Code)

El siguiente diagrama y trazado paso a paso documenta el camino exacto que sigue una instrucción enviada por el usuario a través de `AvatarOrchestrator.process_user_input()` (`core/orchestrator.py:181`).

```
USER INPUT
   │
   ▼
[1] SemanticMissionEngine.classify_interaction()  ──> core/cognitive/semantic_mission_engine.py:183
   │
   ▼
[2] StateEngine.create_mission(status="IN_PROGRESS") ──> core/state_db.py:190
   │
   ▼
[3] CognitiveAdapter.create_goal() ──> core/cognitive/adapter.py:200
   │
   ├───────► IF DIRECT_ACTION / JSON BLOCK:
   │            │
   │            ▼
   │         _parse_multi_task_specs() ──> core/orchestrator.py:211
   │            │
   │            ▼
   │         ContinuousExecutionEngine.execute_continuous_plan() ──> core/cognitive/continuous_loop.py:244
   │            │
   │            ▼
   │         StateEngine.update_mission_status("COMPLETED") ──> core/orchestrator.py:271 [BYPASS GATE!]
   │
   └───────► ELSE (STANDARD REACT LOOP):
                │
                ▼
             LLMProvider.generate_response_with_tools() ──> core/llm_provider.py:572
                │
                ▼
             StructuredActionRecoveryLayer.extract_and_validate() ──> core/cognitive/structured_action_recovery.py:341
                │
                ▼
             _dispatch_native_tool() / ShellTool / ComputerControl ──> core/orchestrator.py:527
                │
                ▼
             PhysicalFactVerifier.verify_command() / verify_write_file() ──> core/cognitive/physical_fact_verifier.py:127
                │
                ▼
             ClaimValidator.validate_llm_claims() ──> core/cognitive/claim_validator.py:455
                │
                ▼
             Return Text Response (Annotated if claims unverified)
```

---

### 2. Trazado Detallado Paso a Paso con Líneas de Código

#### Paso 1: Recepción de Prompt e Intención Semántica
- **Línea:** `core/orchestrator.py:181-184`
- **Código:**
  ```python
  interaction_type = SemanticMissionEngine.classify_interaction(user_input)
  ```
- **Comportamiento:** Clasifica el texto en `CHAT`, `DIRECT_ACTION`, `CODE_ENGINEERING`, `SYSTEM_ADMIN` o `INVESTIGATION`.

#### Paso 2: Creación de Misión Persistente en DB
- **Línea:** `core/orchestrator.py:187-195`
- **Código:**
  ```python
  current_mission_id = self.state_db.create_mission(
      session_id=self.session_id, raw_prompt=user_input,
      classified_intent=interaction_type.value, status="IN_PROGRESS"
  )
  ```
- **Persistencia:** Registra la misión en SQLite WAL (`memory/avatar_state.db`).

#### Paso 3: Evaluación de Plan Multi-Tarea Deterministico
- **Línea:** `core/orchestrator.py:206-218`
- **Comportamiento:** Si la interacción es `DIRECT_ACTION` o contiene un bloque ` ```json `, invoca `_parse_multi_task_specs()`.
- **Ruta A (Multi-Task):**
  - Invoca `ContinuousExecutionEngine.execute_continuous_plan()` (`core/cognitive/continuous_loop.py:244`).
  - Ejecuta la secuencia de herramientas y guarda checkpoints `PRE_TOOL` y `POST_TOOL`.
  - **BYPASS DETECTADO:** Al finalizar el último paso, ejecuta directamente:
    `self.state_db.update_mission_status(current_mission_id, "COMPLETED")` (`core/orchestrator.py:271`).
    **NO INVOCA `MissionCompletionGate.evaluate_mission_completion()`!**

#### Paso 4: Bucle ReAct Estándar (Ruta B)
- **Línea:** `core/orchestrator.py:280-520`
- **Invocación LLM:** `self.llm_provider.generate_response_with_tools()` (`core/llm_provider.py:572`).
- **Parseo de Acción:** `StructuredActionRecoveryLayer.extract_and_validate_structured_action()` (`core/cognitive/structured_action_recovery.py:341`).
- **Despacho de Herramienta:** `_dispatch_native_tool()` (`core/orchestrator.py:527`).

#### Paso 5: Verificación de Hecho Físico y Validación de Claims
- **Línea:** `core/orchestrator.py:403-460`
- **Verificación Física:** Se invoca `PhysicalFactVerifier` para generar un `VerifiedFact`.
- **Validación de Afirmaciones:** `ClaimValidator.validate_llm_claims(response_text, verified_facts)` (`core/cognitive/claim_validator.py:455`).
- **Resultado:** Si el LLM afirmó haber creado un archivo o verificado una capacidad sin hecho físico, `ClaimValidator` anexa una advertencia en el texto final sent al usuario.

---

### 3. Identificación de Puntos Frágiles y Desviaciones Epistémicas

1. **Bypass del Completion Gate:**  
   En la ruta de tareas múltiples deterministas (`orchestrator.py:271`), el orquestador marca la misión como `"COMPLETED"` sin validar ni una sola regla de `MissionCompletionGate`.
2. **Ausencia de Registro de Evidencia en Herramientas:**  
   Durante el despacho de herramientas en `_dispatch_native_tool()`, el resultado se pasa a `StagnationDetector` y `InvestigationEngine`, pero **NUNCA se invoca `CapabilityEvidenceRegistry.register_evidence()`**. La evidencia no se acumula en el registro de capacidades.
3. **Conversión de Error a Texto Educativo:**  
   Si una herramienta falla o lanza una excepción, el error se convierte en texto para el prompt del LLM en el siguiente turno. Si el LLM responde en el siguiente turno con una disculpa en texto plano sin reintentar la herramienta, la misión finaliza sin ejecutar la acción requerida.
