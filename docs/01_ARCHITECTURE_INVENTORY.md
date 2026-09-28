# 01 — ARCHITECTURE INVENTORY
## AVATAR AI — INDEPENDENT ARCHITECTURE REVIEW 001

**Fecha de Auditoría:** 27 de Septiembre de 2026  
**Auditor:** Independent Architecture Auditor (Antigravity Agent)  
**Estado:** COMPLETED  

---

### 1. Resumen de Componentes Inventariados

El inventario estático del repositorio `b:\PROYECTOS ANTIGRAVITY\Avatar` reveló un total de **34 módulos Python principales**, **13 herramientas operativas**, **21 suites de pruebas unitarias/integración**, **1 base de datos SQLite WAL** y **26 documentos de especificación/auditoría previos**.

---

### 2. Inventario Estructurado por Componente

| Component Name | Path | Responsibility | Callers | Callees | Persistence | Tests | Integration Status | Authority Level | Dependencies | Duplication Risk | Current Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **StateEngine** | `core/state_db.py` | Persistencia WAL autoritativa de misiones, tareas, checkpoints y evidencias | `Orchestrator`, `CheckpointEngine`, `ResumeEngine`, `CapabilityRegistry` | SQLite WAL (`memory/avatar_state.db`) | SQLite DB | `test_state_engine.py` (281 lines) | `INTEGRATED` | **PERSISTENCE AUTHORITY** | `sqlite3`, `json` | LOW | `VERIFIED_OPERATIONAL` |
| **CheckpointEngine** | `core/checkpoint_engine.py` | Captura de checkpoints PRE_TOOL, POST_TOOL y UNCERTAIN_EXECUTION | `Orchestrator`, `ComputerControl`, `ContinuousExecutionEngine` | `StateEngine`, `PhysicalFactVerifier` | SQLite DB via StateEngine | `test_checkpoint_resume.py` | `INTEGRATED` | **CHECKPOINT AUTHORITY** | `StateEngine`, `PhysicalFactVerifier` | LOW | `VERIFIED_OPERATIONAL` |
| **ResumeEngine** | `core/resume_engine.py` | Inspección y reanudación idéntica de misiones interrumpidas o fallidas | `Orchestrator`, CLI | `StateEngine`, `CheckpointEngine`, `PhysicalFactVerifier` | SQLite DB via StateEngine | `test_checkpoint_resume.py` | `INTEGRATED` | **RESUME AUTHORITY** | `StateEngine`, `CheckpointEngine` | MEDIUM (Duplica lógica de re-ejecución) | `VERIFIED_OPERATIONAL` |
| **CapabilityEvidenceRegistry** | `core/cognitive/capability_registry.py` | Registro estructurado de evidencia fìsica y estados de capacidades | Manual en tests (`test_forensic_repair_002.py`) | `StateEngine` | SQLite DB via StateEngine | `test_forensic_repair_002.py` | `IMPLEMENTED_NOT_INTEGRATED` | **EPISTEMIC CAPABILITY AUTHORITY (PASSIVE)** | `StateEngine` | LOW | `PASSED_TESTS_UNINTEGRATED_IN_PIPELINE` |
| **MissionCompletionGate** | `core/cognitive/mission_completion_gate.py` | Evaluación determinista de condiciones para autorizar `MISSION_COMPLETED` | `SemanticMissionEngine` (solo helper) | `CapabilityEvidenceRegistry` | Ninguna directa | `test_forensic_repair_002.py` | `IMPLEMENTED_NOT_INTEGRATED` | **COMPLETION GATE AUTHORITY (PASSIVE)** | `CapabilityEvidenceRegistry` | LOW | `PASSED_TESTS_UNINTEGRATED_IN_PIPELINE` |
| **PhysicalFactVerifier** | `core/cognitive/physical_fact_verifier.py` | Verificación determinista de archivos, hashes, exit codes de comandos y tests | `CheckpointEngine`, `ResumeEngine`, `ClaimValidator` | OS Filesystem, hashlib, re | Memoria volatile / retornado en fact | `test_f03_physical_evidence.py` | `INTEGRATED` | **PHYSICAL FACT VERIFIER** | `os`, `hashlib`, `re` | LOW | `VERIFIED_OPERATIONAL` |
| **ClaimValidator** | `core/cognitive/claim_validator.py` | Intercepción de afirmaciones del LLM y anotación de degradación si falta evidencia | `Orchestrator` (L455) | `CapabilityEvidenceRegistry`, `PhysicalFactVerifier` | Ninguna (Anotación de string) | `test_forensic_repair_002.py` | `PARTIALLY_INTEGRATED` | **CLAIM ANNOTATOR (NO BLOCKING)** | `re`, `CapabilityEvidenceRegistry` | LOW | `OPERATIONAL_TEXT_ANNOTATOR` |
| **AvatarOrchestrator** | `core/orchestrator.py` | Bucle ReAct principal, despacho de herramientas, invocación LLM y parseo | `main.py`, `main_gui.py`, CLI | `LLMProvider`, `Tools`, `StateEngine`, `CognitiveAdapter` | SQLite WAL / JSON history | `test_cognitive_integration.py` | `INTEGRATED` | **EXECUTIVE orchestrator (MONOLITH)** | `LLMProvider`, `StateEngine`, `Tools` | HIGH (God Object) | `OPERATIONAL_MONOLITH` |
| **SemanticMissionEngine** | `core/cognitive/semantic_mission_engine.py` | Clasificación de intención del usuario (DIRECT_ACTION vs CHAT vs CODE) | `Orchestrator` (L183) | `MissionCompletionGate` | Ninguna | `test_semantic_mission_engine.py` | `INTEGRATED` | **INTENT CLASSIFIER** | `re` | LOW | `VERIFIED_OPERATIONAL` |
| **StagnationDetector** | `core/cognitive/stagnation_detector.py` | Detección de bucles repetitivos de texto o herramientas | `Orchestrator` | Ninguno | Memoria volatile | `test_cognitive_integration.py` | `INTEGRATED` | **ANTI-LOOP ADVISOR** | None | LOW | `VERIFIED_OPERATIONAL` |
| **AdaptiveInvestigationEngine** | `core/cognitive/adaptive_investigation_engine.py` | Evaluación de brechas de evidencia y formulación de hipótesis de investigación | `Orchestrator` (L403) | Ninguno | Memoria volatile | `test_f02_adaptive_investigation.py` | `INTEGRATED` | **RESEARCH ADVISOR** | None | LOW | `VERIFIED_OPERATIONAL` |
| **ProviderManager / LLMProvider** | `core/llm_provider.py` | Gestión de adaptadores LLM (Gemini, OpenAI, Ollama), fallback y health checks | `Orchestrator` | `GeminiAdapter`, `OllamaAdapter`, `OpenAIAdapter` | Config JSON | `test_provider_manager.py` | `INTEGRATED` | **PROVIDER ROUTING AUTHORITY** | `requests`, `google.genai` | LOW | `VERIFIED_OPERATIONAL` |
| **BrowserController** | `tools/browser_controller.py` | Control de automatización web con Playwright y restricción de dominio | `Orchestrator` (vía `native_tool`) | Playwright API | Screenshots en disco | `test_browser_engine.py` | `INTEGRATED_WITH_MOCKS` | **BROWSER EXECUTION TOOL** | `playwright` | LOW | `TESTED_NOT_PHYSICALLY_VERIFIED` |
| **ComputerControl** | `tools/computer_control.py` | Control GUI de escritorio (mouse, teclado, screenshots, focus) | `Orchestrator` | `pyautogui`, `UIInspector`, `ScreenTool` | Screenshots en disco | `test_desktop_vision.py` | `INTEGRATED` | **DESKTOP EXECUTION TOOL** | `pyautogui`, `win32gui` | LOW | `VERIFIED_LOCAL` |
| **UIInspector / OCR** | `core/ui_inspector.py` | Inspección Win32 API y OCR local (pytesseract/EasyOCR) | `ComputerControl` | `ctypes`, `win32gui`, PIL | Ninguna | `test_desktop_vision.py` | `INTEGRATED` | **UI OBSERVATION TOOL** | `ctypes`, `win32gui`, `PIL` | LOW | `VERIFIED_LOCAL` |
| **ShellTool** | `tools/shell_tool.py` | Ejecución de comandos PowerShell/Cmd en workspace aislado | `Orchestrator` | `subprocess` | Execution logs | `test_f03_physical_evidence.py` | `INTEGRATED` | **SHELL EXECUTION TOOL** | `subprocess` | LOW | `VERIFIED_OPERATIONAL` |
| **FileTool** | `tools/file_tool.py` | Operaciones de lectura, escritura y listado en workspace aislado | `Orchestrator` | `os`, `shutil` | Disk files | `test_state_engine.py` | `INTEGRATED` | **FILE EXECUTION TOOL** | `os`, `pathlib` | LOW | `VERIFIED_OPERATIONAL` |

---

### 3. Conclusión del Inventario

Todos los componentes requeridos por la arquitectura existen en el código fuente y 288 tests pasan de forma consistente. Sin embargo, existe una **desconexión crítica entre los componentes cognitivos autoritativos (CapabilityEvidenceRegistry, MissionCompletionGate) y el motor ejecutivo principal (Orchestrator)**.
