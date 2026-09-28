# 02 — AUTHORITY MAP
## AVATAR AI — INDEPENDENT ARCHITECTURE REVIEW 001

**Fecha de Auditoría:** 27 de Septiembre de 2026  
**Auditor:** Independent Architecture Auditor (Antigravity Agent)  
**Estado:** COMPLETED  

---

### 1. Resumen de Autoridad del Sistema

La auditoría determinó la existencia de dos modelos de autoridad en Avatar AI:
1. **Modelo Teórico / Diseñado (De Jure):** La autoridad epistemológica pertenece a `CapabilityEvidenceRegistry` y `MissionCompletionGate` guiados por `PhysicalFactVerifier`.
2. **Modelo Real en Ejecución (De Facto):** La autoridad ejecutiva reside casi en su totalidad en `AvatarOrchestrator` (`core/orchestrator.py`) y en el flujo condicional del bucle ReAct.

---

### 2. Mapa Detallado de Decisiones y Autoridad REAL vs TEÓRICA

#### 1. ¿Quién decide que una herramienta tuvo éxito?
- **Componente Autoritario Real:** `ShellTool.execute_command` (`tools/shell_tool.py:35`), `ComputerControl._execute_gui_action` (`tools/computer_control.py:256`), `BrowserController.navigate` (`tools/browser_controller.py:67`).
- **Función / Método:** Retorno implícito `{"status": "success"}` o `ExitCode: 0`.
- **Entrada:** Argumentos de la herramienta.
- **Salida:** Diccionario o String de salida.
- **Persistencia:** Ninguna directa (capturada por CheckpointEngine si está habilitado).
- **Evidencia:** `raw_output` o boolean `action_ok`.
- **Debilidad Crítica:** Un comando que retorne ExitCode 0 o un script que no lance excepciones se clasifica automáticamente como éxito técnico, sin validar si el efecto deseado en el mundo real ocurrió.

#### 2. ¿Quién decide que una observación es válida?
- **Componente Autoritario Real:** `AvatarOrchestrator._dispatch_native_tool` (`core/orchestrator.py:527`) y `CommandObserver.observe_command` (`core/cognitive/observer.py:15`).
- **Función / Método:** `observe_command(command, raw_output)`.
- **Entrada:** `raw_output` del subproceso o herramienta.
- **Salida:** Objeto `Observation`.
- **Persistencia:** Guardado en `memory/history.json` y `StateEngine.create_checkpoint`.
- **Evidencia:** String de salida de consola o resultado JSON.
- **Debilidad Crítica:** No hay validación de integridad criptográfica o anti-tampering sobre las observaciones.

#### 3. ¿Quién crea evidencia?
- **Componente Autoritario Real:** `PhysicalFactVerifier` (`core/cognitive/physical_fact_verifier.py:31`).
- **Función / Método:** `verify_write_file()`, `verify_modify_file()`, `verify_command()`, `verify_test_execution()`.
- **Entrada:** Ruta de archivo, hash previo, comando, salida de consola.
- **Salida:** Instancia de `VerifiedFact` con datos de hash sha256 y tamaño.
- **Persistencia:** Ninguna automática; `VerifiedFact` se pasa en memoria a `ClaimValidator` o `CapabilityEvidenceRegistry`.
- **Evidencia:** Hashes SHA256, exit codes, conteo de tests.
- **Debilidad Crítica:** Los fakta físicos creados por `PhysicalFactVerifier` solo se invocan en puntos específicos (ej. Checkpoint, ClaimValidator) y NO de forma obligatoria en cada ejecución de herramienta.

#### 4. ¿Quién valida la evidencia?
- **Componente Autoritario Real:** `ClaimValidator.validate_llm_claims` (`core/cognitive/claim_validator.py:97`).
- **Función / Método:** `validate_llm_claims(llm_text, verified_facts, capability_registry)`.
- **Entrada:** Texto generado por el LLM, lista de `VerifiedFact`.
- **Salida:** `ClaimValidationResult` (clasificando claims en `verified_claims` vs `unverified_claims`).
- **Persistencia:** Ninguna en DB.
- **Evidencia:** Coincidencia de rutas de archivos verificados o estados en `CapabilityEvidenceRegistry`.
- **Debilidad Crítica:** `ClaimValidator` NO bloquea la ejecución ni altera la base de datos de misiones; únicamente anexa una nota de texto de advertencia al mensaje visible del usuario.

#### 5. ¿Quién decide que una capacidad está `VERIFIED`?
- **Componente Autoritario Teórico:** `CapabilityEvidenceRegistry.register_evidence` (`core/cognitive/capability_registry.py:121`).
- **Componente Autoritario Real:** Código de tests unitarios (`tests/test_browser_engine.py`, `tests/test_forensic_repair_002.py`).
- **Entrada:** Objeto `CapabilityEvidence` (con `physical_evidence=True`).
- **Salida:** `CapabilityStatus.VERIFIED` o `PARTIAL`.
- **Persistencia:** Guardado en `StateEngine` DB via `save_capability_record`.
- **Evidencia:** `evidence_id`, `verifier`, timestamp.
- **Debilidad Crítica:** **GAP DE INTEGRACIÓN DE FACTO:** Ninguna herramienta en `tools/` ni el orquestador principal durante la ejecución real de un turno invoca `CapabilityEvidenceRegistry.register_evidence()`.

#### 6. ¿Quién decide que una misión está `COMPLETED`?
- **Componente Autoritario Teórico:** `MissionCompletionGate.evaluate_mission_completion` (`core/cognitive/mission_completion_gate.py:31`).
- **Componente Autoritario Real:** `AvatarOrchestrator.process_user_input` (`core/orchestrator.py:271`) y `ResumeEngine.resume_active_mission` (`core/resume_engine.py:63, 232`).
- **Función / Método:** `self.state_db.update_mission_status(current_mission_id, "COMPLETED")`.
- **Entrada:** Finalización del bucle de tareas de la lista.
- **Salida:** Registro de la misión con status `"COMPLETED"` en SQLite DB.
- **Persistencia:** Directa en DB SQLite WAL.
- **Evidencia:** Ninguna requerida por el código de `orchestrator.py:271` o `resume_engine.py:63`.
- **Debilidad Crítica:** **HALLAZGO DE AUTORIDAD GRAVE:** `orchestrator.py:271` actualiza la base de datos a `"COMPLETED"` sin llamar a `MissionCompletionGate.evaluate_mission_completion()`. El Gate es completamente ignorado en la ruta de ejecución principal.

#### 7. ¿Quién decide si existe un critical gap o blocking finding?
- **Componente Autoritario Real:** `AdaptiveInvestigationEngine.calculate_evidence_gap` (`core/cognitive/adaptive_investigation_engine.py:85`).
- **Entrada:** `TaskState`, `VerifiedFact`.
- **Salida:** Objeto `EvidenceGap`.
- **Persistencia:** Memoria volátil.
- **Debilidad Crítica:** Los brechas reportadas por `AdaptiveInvestigationEngine` no se alimentan automáticamente a `MissionCompletionGate`.

#### 8. ¿Quién decide que debe hacerse replanning?
- **Componente Autoritario Real:** `Orchestrator` en respuesta a `StagnationDetector.get_stagnation_directive` (`core/cognitive/stagnation_detector.py:53`) o fallos repetidos.

#### 9. ¿Quién decide detener la misión?
- **Componente Autoritario Real:** Límite `max_steps` en `Orchestrator.process_user_input` (`core/orchestrator.py:181`) o interrupción por excepción no capturada.

#### 10. ¿Quién autoriza acciones peligrosas?
- **Componente Autoritario Real:** `FileTool.is_within_workspace` (`tools/file_tool.py:15`) y `ShellTool.is_within_workspace` (`tools/shell_tool.py:22`).
- **Debilidad Crítica:** Solo se valida aislamiento de directorio (Path traversal). No existe un sandbox ni confirmación de usuario para comandos destructivos (ej. `rm -rf` o `git reset --hard`) dentro del workspace.

#### 11. ¿Quién decide si un provider fallback es válido?
- **Componente Autoritario Real:** `ProviderManager.get_adapter` y `LLMProvider.generate_response` (`core/llm_provider.py:567`).

#### 12. ¿Quién controla el estado persistente?
- **Componente Autoritario Real:** `StateEngine` (`core/state_db.py`).

#### 13. ¿Puede el LLM modificar directa o indirectamente alguno de estos estados?
- **Respuesta:** **SÍ, DE FORMA INDIRECTA.** Si el LLM emite un bloque JSON de tareas directas o responde de forma que satisfaga el bucle ReAct, `Orchestrator` ejecuta las herramientas y marca la misión como `"COMPLETED"` en SQLite WAL (L271), pasando por alto el `MissionCompletionGate`.

---

### 3. Matriz Resumen de Autoridades

| Decisión Epistémica | Autoridad Diseñada | Autoridad Real en Ejecución | ¿Pasa por Gate? | ¿LLM puede influir? |
| :--- | :--- | :--- | :--- | :--- |
| **Tool Success** | `PhysicalFactVerifier` | Status de retorno del Tool | NO | NO |
| **Observation Validity** | `CommandObserver` + `Verifier` | Concatenación de texto | NO | NO |
| **Capability VERIFIED** | `CapabilityEvidenceRegistry` | Tests unitarios manuales | NO | INDIRECTO |
| **Mission COMPLETED** | `MissionCompletionGate` | `Orchestrator.py:271` direct update | **NO (BYPASSED)** | **SÍ** |
| **File Modification** | `PhysicalFactVerifier` | `FileTool` return code | NO | INDIRECTO |
