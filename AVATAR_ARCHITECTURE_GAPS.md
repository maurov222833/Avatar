# AVATAR AI — ARCHITECTURE GAPS (001)
## ESPECIFICACIÓN DETALLADA DE BRECHAS ARQUITECTÓNICAS Y DISEÑO DE COMPONENTES

```text
DOCUMENT_ID: AVATAR_ARCHITECTURE_GAPS_001
DATE: 2026-09-27
AUTHORITY: AUDITOR TÉCNICO DE ARQUITECTURA E IMPLEMENTACIÓN DE AVATAR AI
STATUS: COMPLETED / AUTHORITATIVE
CODE_MODIFIED: NO
PROJECT: Avatar (Sovereign Digital Assistant for Mauro)
```

---

## 1. RESUMEN ARQUITECTÓNICO

Aunque la suite core de Avatar AI (`CognitiveEngine`, `Verifier`, `RecoveryEngine`, `SemanticMissionEngine`, `TaskQueue`) está **100% verificada** con inmunidad semántica y autoridad de ejecución, existen **8 brechas estructurales de arquitectura** que impiden el funcionamiento de Avatar como servicio continuo, soberano y de memoria persistente a largo plazo.

Este documento especifica técnicamente cada una de las 8 brechas identificadas en la auditoría de baseline, detallando su diseño de clase, contrato de API, punto de integración y estrategia de mitigación.

---

## 2. LAS 8 BRECHAS ARQUITECTÓNICAS CRÍTICAS

| ID Brecha | Componente Faltante | Categoría | Impacto en Autonomía | Prioridad |
| :---: | :--- | :--- | :--- | :---: |
| **GAP-01** | `OperationalMemory DB` | Persistencia de Estado | Pérdida de contexto al cerrar proceso | **P0** |
| **GAP-02** | `Checkpoints Engine` | Tolerancia a Fallos | Imposibilidad de pausar/guardar misiones | **P0** |
| **GAP-03** | `Resume Engine` | Recuperación Autónoma | Misiones canceladas quedan incompletas | **P0** |
| **GAP-04** | `Scheduler Service` | Automatización Temporal | No hay ejecución programada de cron/recordatorios | **P1** |
| **GAP-05** | `24/7 Windows Daemon` | Infraestructura | Avatar requiere consola GUI abierta | **P1** |
| **GAP-06** | `Headless Remote Bridge` | Comunicación Soberana | WhatsApp requiere pantalla desbloqueada y PyAutoGUI | **P1** |
| **GAP-07** | `Playwright Browser Controller` | Herramientas Web | Sin interacción con sitios Web complejas JS | **P1** |
| **GAP-08** | `Vector RAG DB` | Memoria Profunda | Búsqueda contextual limitada a buffer temporal | **P2** |

---

## 3. ESPECIFICACIÓN TÉCNICA DETALLADA POR BRECHA

---

### GAP-01: `OperationalMemory DB` (Persistencia de Estado de Sesión)

#### Problema Actual
`core/orchestrator.py` almacena las misiones y la memoria operacional únicamente en variables de instancia Python (`self.operational_memory = []`). Al finalizar el proceso o reiniciarlo, toda la evidencia acumulada se elimina.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `core/state_db.py`
* **Motor Recomendado:** SQLite en modo WAL (Write-Ahead Logging) o base JSON indexada local.
* **Esquema de Tablas:**
  ```sql
  CREATE TABLE sessions (
      session_id TEXT PRIMARY KEY,
      started_at TIMESTAMP,
      updated_at TIMESTAMP,
      status TEXT CHECK(status IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'FAILED'))
  );

  CREATE TABLE missions (
      mission_id TEXT PRIMARY KEY,
      session_id TEXT,
      raw_prompt TEXT,
      classified_intent TEXT,
      created_at TIMESTAMP,
      FOREIGN KEY(session_id) REFERENCES sessions(session_id)
  );

  CREATE TABLE task_history (
      task_id TEXT PRIMARY KEY,
      mission_id TEXT,
      step_index INTEGER,
      tool_name TEXT,
      tool_args JSON,
      execution_result JSON,
      verifier_status TEXT,
      FOREIGN KEY(mission_id) REFERENCES missions(mission_id)
  );
  ```
* **Integración:** `core/orchestrator.py` escribe automáticamente en `state_db` tras cada ciclo de `TaskQueue` y `Verifier`.

---

### GAP-02: `Checkpoints Engine` (Serialización de Estado de Misión)

#### Problema Actual
No existe un formato ni contrato de datos para capturar un snapshot del estado ejecutable de Avatar en medio de una plan de tareas de 10 pasos.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `core/checkpoint_engine.py`
* **Contrato de Snapshot (JSON Schema):**
  ```json
  {
    "checkpoint_id": "chk_20260927_153022_001",
    "mission_id": "msn_engineering_audit",
    "timestamp": "2026-09-27T15:30:22Z",
    "pending_tasks": [
      {"task_id": "T3", "tool": "COMMAND", "args": {"command": "pytest core/tests"}}
    ],
    "completed_tasks": [
      {"task_id": "T1", "result": "PASS"},
      {"task_id": "T2", "result": "PASS"}
    ],
    "evidence_gap_state": {"unresolved_gaps": []},
    "retry_counters": {"T3": 0}
  }
  ```
* **Integración:** `core/orchestrator.py` llama a `CheckpointEngine.save()` antes de invocar cualquier herramienta destructiva o comando de larga duración.

---

### GAP-03: `Resume Engine` (Restauración de Misiones Interrumpidas)

#### Problema Actual
Si Avatar sufre una desconexión o reinicio del sistema mientras ejecuta una tarea, al volver a abrir el sistema inicia desde cero con prompt en blanco, ignorando el estado previo.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `core/resume_engine.py`
* **Flujo de Inicialización:**
  ```text
  Boot Avatar Process
         │
         ▼
  ResumeEngine.check_interrupted_missions()
         │
    ┌────┴──────────────────────────┐
    ▼                               ▼
  [Checkpoint Encontrado]   [No hay Checkpoint Pendiente]
    │                               │
    ▼                               ▼
  Presentar/Resume Auto     Esperar Nuevo Prompt
  Continuar Tarea T_k
  ```
* **Integración:** Se invoca automáticamente en `main_gui.py` o `main.py` durante la fase de bootstrap del sistema.

---

### GAP-04: `Scheduler Service` (Ejecución Programada y Cron)

#### Problema Actual
Avatar solo reacciona a entradas explícitas del usuario presentadas en tiempo real. No puede ejecutar chequeos matutinos, respaldos automáticos o monitoreo periódico.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `core/scheduler.py`
* **Librería Base:** `APScheduler` (BackgroundScheduler con backend SQLite).
* **API de Registro:**
  ```python
  class AvatarScheduler:
      def add_cron_job(self, cron_expr: str, prompt: str, name: str): ...
      def add_interval_job(self, minutes: int, prompt: str): ...
  ```
* **Integración:** Se conecta con `SemanticMissionEngine` para encolar misiones programadas en la `TaskQueue` cuando vence el timer.

---

### GAP-05: `24/7 Windows Service Daemon` (Ejecución Invisible en Segundo Plano)

#### Problema Actual
El funcionamiento de Avatar depende de que el script `main_gui.py` o el proceso de consola permanezca abierto en la sesión de escritorio interactiva de Mauro.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `service/windows_daemon.py`
* **Herramientas de Servicio:** Wrapper con `pywin32` (`win32serviceutil.ServiceFramework`) o instalación administrada con `NSSM` (Non-Sucking Service Manager).
* **Manejo de GUI vs Daemon:**
  - Modo Daemon: Ejecuta headless, atiende peticiones de WhatsApp/Scheduler.
  - Modo GUI: Se conecta al Daemon en ejecución mediante socket local RPC / HTTP.

---

### GAP-06: `Headless Remote Control Protocol` (WhatsApp / Telegram Soberano)

#### Problema Actual
La automatización actual de WhatsApp (`tools/whatsapp_automation.py`) utiliza `PyAutoGUI` para mover el ratón y escribir en la aplicación gráfica de escritorio. Requiere que la pantalla esté encendida, desbloqueada y en primer plano.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `tools/whatsapp_bridge.py`
* **Arquitectura Tecnológica:**
  - Opción A: Browser Headless con Playwright interactuando con WhatsApp Web en segundo plano.
  - Opción B: Cliente WebSocket/API local conectado a contenedor sidecar (ej. `evolution-api` / `baileys`).
* **Seguridad & Inmunidad Remote:**
  - Whitelist de números autorizados (`MAURO_PHONE_NUMBER`).
  - Verificación de hash/firma en comandos sensibles.

---

### GAP-07: `Playwright Browser Controller` (Navegación Web Interactiva Headless)

#### Problema Actual
Avatar carece de herramienta nativa para navegar por páginas web complejas (Single Page Applications, autenticación con JS, formularios dinámicos).

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `tools/browser_controller.py`
* **Capacidades de Clase:**
  ```python
  class PlaywrightBrowserController:
      def navigate(self, url: str) -> str: ...
      def click(self, selector: str) -> None: ...
      def fill_form(self, selector: str, text: str) -> None: ...
      def extract_text(self) -> str: ...
      def take_screenshot(self) -> bytes: ...
  ```
* **Integración con Verifier:** Visual HTML/DOM diff verifier para confirmar renderizado correcto de la página.

---

### GAP-08: `Vector RAG DB` (Memoria Semántica de Largo Plazo)

#### Problema Actual
No hay indexación vectorial de los archivos del sistema, conversaciones previas ni documentación de repositorios. El contexto se limita a lo que cabe en la ventana del LLM.

#### Diseño Arquitectónico Propuesto
* **Ubicación:** `core/vector_store.py`
* **Librerías:** `chromadb` (local persistente sin servidor externo) + `sentence-transformers` (`all-MiniLM-L6-v2`).
* **Colecciones Vectoriales:**
  - `project_codebase`: Indexación de código fuente Python/JS.
  - `mauro_preferences`: Guías de estilo, reglas y decisiones tomadas.
  - `past_missions_outcomes`: Histórico de diagnósticos y soluciones exitosas.

---

## 4. INTEGRACIÓN DE ARQUITECTURA GLOBAL TARGET

```mermaid
graph TB
    subgraph Frontend Layer
        GUI["main_gui.py (PyQt/Custom)"]
        WhatsApp["tools/whatsapp_bridge.py (Headless)"]
        Remote["core/remote_command_parser.py"]
    end

    subgraph Service & Daemon Layer
        Daemon["service/windows_daemon.py (24/7)"]
        Scheduler["core/scheduler.py (APScheduler)"]
    end

    subgraph Core Engine Layer
        Semantic["SemanticMissionEngine"]
        Planner["Planner / Replanner"]
        TaskQ["TaskQueue"]
        Verifier["Verifier Engine"]
        Recovery["RecoveryEngine"]
    end

    subgraph State & Memory Layer
        StateDB[("StateEngine (SQLite WAL)")]
        Checkpoints["CheckpointEngine"]
        Resume["ResumeEngine"]
        VectorDB[("Vector RAG DB (ChromaDB)")]
    end

    subgraph Tooling Layer
        Cmd["tools/command.py"]
        Browser["tools/browser_controller.py (Playwright)"]
        Desktop["tools/computer_control.py (PyAutoGUI/Vision)"]
    end

    WhatsApp --> Remote
    Remote --> Semantic
    GUI --> Semantic
    Scheduler --> Semantic
    Daemon --> Core Engine Layer

    Semantic --> Planner
    Planner --> TaskQ
    TaskQ --> Tooling Layer
    Tooling Layer --> Verifier
    Verifier --> Recovery

    Core Engine Layer <--> StateDB
    Core Engine Layer <--> Checkpoints
    Core Engine Layer <--> VectorDB
    Checkpoints <--> Resume
```
