# 07 — ORCHESTRATOR AUDIT
## AVATAR AI — INDEPENDENT ARCHITECTURE REVIEW 001

**Fecha de Auditoría:** 27 de Septiembre de 2026  
**Auditor:** Independent Architecture Auditor (Antigravity Agent)  
**Target Module:** `core/orchestrator.py` (757 líneas)  
**Estado:** COMPLETED  

---

### 1. Resumen Ejecutivo del Orquestador

`AvatarOrchestrator` (`core/orchestrator.py`) es el componente central de la arquitectura de Avatar AI. Actúa como el controlador de entrada para todas las peticiones de usuario (`process_user_input`), orquestando el modelo de lenguaje, la selección y ejecución de herramientas, la detección de loops, la persistencia en base de datos y la sanitización de respuestas.

---

### 2. Desglose de Responsabilidades y Clasificación

El análisis estático del archivo reveló **10 responsabilidades heterogéneas** concentradas en una sola clase:

| # | Responsabilidad | Métodos / Line Range | Clasificación | Impacto en Complejidad |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Inicialización de Configuración y Providers | `__init__`, `_load_config` (`L140-180`) | `CORE` | Conecta base de datos, provider manager, registries y adaptadores. |
| 2 | Clasificación Semántica de Intención | `process_user_input` (`L181-184`) | `POLICY` | Invoca `SemanticMissionEngine.classify_interaction`. |
| 3 | Persistencia Inicial de Misión | `process_user_input` (`L186-198`) | `PERSISTENCE` | Invocación a `StateEngine.create_mission`. |
| 4 | Parseo de Planes Multi-Tarea JSON | `_parse_multi_task_specs` (`L563-663`) | `PARSING` | 100 líneas de heurística regex y validación JSON para extraer tareas de prompts del usuario. |
| 5 | Bucle de Ejecución Continua | `process_user_input` (`L220-275`) | `EXECUTION` | Instancia y ejecuta `ContinuousExecutionEngine`. |
| 6 | Invocación y Despacho del LLM | `process_user_input` (`L280-340`) | `COORDINATION` | Llama a `LLMProvider.generate_response_with_tools`. |
| 7 | Parseo de Acciones de Herramientas | `_parse_tool_action` (`L664-709`) | `PARSING` | Extrae llamadas a herramientas de texto o bloques formateados. |
| 8 | Despacho Directo de Herramientas Nativas | `_dispatch_native_tool`, `_dispatch_tool_action` (`L527-562, L710-757`) | `EXECUTION` | Invoca `ShellTool`, `ComputerControl`, `BrowserController`, `FileTool`. |
| 9 | Detección de Estancamiento e Investigación | `process_user_input` (`L400-450`) | `RECOVERY` | Consulta `StagnationDetector` y `AdaptiveInvestigationEngine`. |
| 10| Validación de Afirmaciones del LLM | `process_user_input` (`L454-465`) | `VERIFICATION` | Invoca `ClaimValidator.validate_llm_claims`. |

---

### 3. Evaluación de Acoplamiento y Complejidad ("God Orchestrator")

#### Diagnóstico:
- **Líneas de Código:** 757 líneas.
- **Grado de Acoplamiento:** **MUY ALTO.** Importa 18 módulos internos (StateEngine, CheckpointEngine, LLMProvider, ClaimValidator, CapabilityRegistry, MissionCompletionGate, ComputerControl, BrowserController, ShellTool, FileTool, RAGMemory, Subagents, etc.).
- **Evaluación "God Object":** `AvatarOrchestrator` reúne las funciones de:
  - Router de entrada;
  - Parser de sintaxis;
  - Despachador de herramientas;
  - Gestor de persistencia;
  - Gestor de errores y recuperación;
  - Sanitizador de respuestas.

---

### 4. Veredicto y Recomendación de Refactorización

> **CONCLUSIÓN:**  
> `AvatarOrchestrator` **NO debe ser dividido inmediatamente sin antes establecer los contratos de los submódulos**.  
>  
> La refactorización recomendada (a ejecutar en la siguiente fase de desarrollo) debe separar `core/orchestrator.py` en 3 componentes especializados:
> 1. `ExecutionLoop` (Manejo exclusivo del ciclo Prompt -> LLM -> Tool -> Observation).
> 2. `ToolDispatcher` (Manejo exclusivo del mapeo, validación de permisos y ejecución de herramientas).
> 3. `EpistemicPipelineAuditor` (Interceptación previa a la persistencia de estado de misiones).
