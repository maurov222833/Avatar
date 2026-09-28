# 14 — ARCHITECTURE COMPLEXITY MAP
## AVATAR AI — INDEPENDENT ARCHITECTURE REVIEW 001

**Fecha de Auditoría:** 27 de Septiembre de 2026  
**Auditor:** Independent Architecture Auditor (Antigravity Agent)  
**Estado:** COMPLETED  

---

### 1. Resumen de Complejidad Arquitectónica

El análisis estático y dinámico de la base de código identificó **34 módulos Python**. Aunque la arquitectura cuenta con componentes bien definidos (ej. `StateEngine`, `CheckpointEngine`), existe una alta densidad de pequeñas capas cognitivas creadas para corregir fallas históricas específicas (F-01 a F-07).

---

### 2. Mapa de Acción Arquitectónica por Componente

| Módulo / Clase | Archivo | Acción Clasificada | Justificación Técnica |
| :--- | :--- | :---: | :--- |
| **StateEngine** | `core/state_db.py` | `KEEP` | Núcleo autoritativo de persistencia SQLite WAL. Inextricable y libre de errores. |
| **CheckpointEngine** | `core/checkpoint_engine.py` | `KEEP` | Gestión transaccional PRE/POST tool de alta fiabilidad. |
| **ResumeEngine** | `core/resume_engine.py` | `REFACTOR` | Consolidar la lógica de re-ejecución para evitar duplicación con el orquestador. |
| **CapabilityEvidenceRegistry** | `core/cognitive/capability_registry.py` | `INTEGRATE` | Conectar directamente a la tubería de ejecución de herramientas nativas en `orchestrator.py`. |
| **MissionCompletionGate** | `core/cognitive/mission_completion_gate.py` | `INTEGRATE` | Hacer obligatoria su llamada en `orchestrator.py:271` antes de actualizar a `COMPLETED`. |
| **PhysicalFactVerifier** | `core/cognitive/physical_fact_verifier.py` | `KEEP` | Motor determinista de cálculo de fakta físicos (hashes, exit codes, files). |
| **ClaimValidator** | `core/cognitive/claim_validator.py` | `REFACTOR` | Transformar de un simple anotador de texto a un filtro activo pre-persistencia. |
| **AvatarOrchestrator** | `core/orchestrator.py` | `REFACTOR` | Descomponer en `ExecutionLoop`, `ToolDispatcher` y `EpistemicPipelineAuditor`. |
| **SemanticMissionEngine** | `core/cognitive/semantic_mission_engine.py` | `KEEP` | Clasificador de precedencia semántica limpio y desacoplado. |
| **StagnationDetector** | `core/cognitive/stagnation_detector.py` | `KEEP` | Detector de bucles ligero y efectivo. |
| **AdaptiveInvestigationEngine** | `core/cognitive/adaptive_investigation_engine.py` | `MERGE` | Fusionar con `Replanner` y `HypothesisTracker` para reducir capas cognitivas superpuestas. |
| **ClosedLoopExecutor / ContinuousLoop** | `core/cognitive/closed_loop.py`, `continuous_loop.py` | `MERGE` | Unificar los 3 bucles de ejecución en un único `UnifiedAgentControlLoop`. |
| **BrowserController** | `tools/browser_controller.py` | `KEEP` | Control Playwright sano; requiere pruebas físicas en vivo. |
| **ComputerControl** | `tools/computer_control.py` | `KEEP` | Control Win32/pyautogui sano; requiere integración con `CapabilityRegistry`. |
| `whatsapp_auto_reply.py` / bridges | `tools/whatsapp_auto_reply.py` | `REPLACE / REMOVE` | Eliminar scripts sueltos y reemplazarlos por una sola herramienta estándar `WhatsAppTool`. |

---

### 3. Resumen Estadístico de Clasificaciones

```
KEEP:       8 componentes (53.3%)
INTEGRATE:  2 componentes (13.3%)
REFACTOR:   3 componentes (20.0%)
MERGE:      1 componente  ( 6.7%)
REPLACE:    1 componente  ( 6.7%)
--------------------------------
TOTAL:     15 módulos clave evaluados
```
