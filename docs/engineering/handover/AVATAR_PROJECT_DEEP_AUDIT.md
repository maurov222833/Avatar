# AVATAR — Auditoría técnica profunda (v-Master-007)

Fecha: 2026-09-28. Auditor: OpenCode (Muse Spark). Idioma: español.
Alcance: solo lectura + tests seguros. **Código fuente no modificado.**
Raíz inspeccionada: `B:\PROYECTOS ANTIGRAVITY\Avatar` (verificada: existe).

## 1. Identidad y propósito

Avatar es un agente de IA soberano local (Windows, Python 3.12.8): orquestador ReAct
con misiones persistentes en SQLite, chokepoint de efectos con política, verificación
física anti-alucinación, 6 proveedores LLM y superficies GUI/CLI/Telegram/WhatsApp.
No es un chatbot: propone, ejecuta con herramientas, observa y verifica con evidencia.

## 2. Estado verificado (2026-09-28)

- Git: repo propio, rama `main`, 4 commits (`ca99bdc` inicial; `dbc97be` WhatsApp;
  `b56620d` 24/7; `4dc7514` Telegram+cerebro local). Árbol limpio.
- Suite: **497 passed, 0 failed en 143.08s** (`python -m pytest tests/ -q --tb=no
  -p no:cacheprovider`). 467 funciones `test_*` en 37 archivos (la diferencia con
  497 viene de herencia: `test_recovery.py` hereda 15 de Phase4).
- Python: 157 archivos `.py` propios; 307 archivos totales (sin `.git`, cachés ni perfil WA).
- Dependencias (`requirements.txt`, 6): requests, pydantic, rich, prompt_toolkit,
  colorama, google-generativeai. Sin lock file.
- Entradas: `server.py` (FastAPI, 9992 B), `main_gui.py`, `main.py` (230 B),
  `interface/cli.py`, `bridges/telegram_bridge.py`, `bridges/whatsapp_bridge.py`,
  `whatsapp_24x7.py`. `core/autoloop.py` existe pero nadie lo importa (muerto).
- Secretos: solo en `config.json` y `.env` locales (gitignored); plantillas
  `config.example.json` + `.env.example` versionadas. Sin valores en este informe.

## 3. Mapa del repositorio

```
core/orchestrator.py (1223 l.)      ReAct loop, misiones, dispatch, gates
core/act_chokepoint.py              11 acts, policy, executors, observers, ledger `acts`
core/state_db.py (1021 l.)          SQLite WAL: missions, planner_tasks, acts(vía chokepoint),
                                    evidences, gaps, history, capability_records
core/llm_provider.py (649+ l.)      6 adaptadores + facade con reparación y cascada
core/checkpoint_engine.py           PRE/POST/VERIFIED/UNCERTAIN + idempotencia
core/resume_engine.py               Evaluación + resume idempotente (conectado 2026-09)
core/cognitive/ (30 módulos)        Semántica, adaptativa, autoridad, recovery, anti-loop
core/rag_memory.py                  Búsqueda por palabras (NO vectorial) sobre StateEngine
bridges/                            telegram_bridge.py, whatsapp_bridge.py, whatsapp_reader.py
tools/                              shell/file/web/browser/screen/computer/audio/whatsapp
server.py / gui/ / interface/       FastAPI + PyWebView + CLI
tests/ (37 archivos)                Ver §6. memory/ = runtime (DB, perfil WA, knowledge)
```

## 4. Arquitectura real (flujos trazados por call-sites)

1. **Chat GUI** `server.py:124 /api/chat` → `orchestrator.process_user_input()` (§4.1).
2. **Turno** (`orchestrator.py:241+`): clasificar → crear Goal (l.251) → crear misión
   (l.260, `raise` si falla) → loop ReAct (máx 5/15): `generate_response_with_tools`
   → nativo / SAR-recuperado / provider_error / vacío (corte al 2º) →
   `_dispatch_native_tool` → `chokepoint.perform` (policy→executor→observer→ledger) →
   verificación física → reconciliación por gate (`_reconcile_mission`) → respuesta
   ejecutiva o escalado honesto.
3. **Terminal GUI** `server.py:166 /api/terminal/execute` → `chokepoint.perform(COMMAND)`
   directo, misión `gui-terminal`.
4. **WhatsApp**: webhook → mismo turno; loop 24/7 `whatsapp_24x7.py` → supervisor →
   `WhatsAppBridge.start_live_bridge` (lector DOM persistente, dedup, autorizados,
   observe, límites) → turno → `SEND_WHATSAPP`/`WHATSAPP_SEND` por chokepoint.
5. **Resume**: `orchestrator.resume_mission()` → `ResumeEngine` → dispatcher por
   chokepoint → gate → idempotente (test_21).
6. **Proveedores**: `default_provider` (groq) + fallback ciego a gemini + reintento
   guiado (tool desconocido / JSON truncado) + cascada local opt-in
   (`providers.local_fallback`, qwen3:8b verificado en vivo).

## 5. Capacidades: lo que sí / lo que no (con evidencia)

- VERIFICADO físicamente: misiones persistentes, chokepoint+ledger (126+ acts),
  COMMAND/WRITE observados, denegación externa sin consentimiento, resume idempotente,
  ida y vuelta WhatsApp con relectura, 6 providers conmutables, fallback local.
- PARCIAL: memoria "RAG" por palabras (`rag_memory.py:141`); capacidades de proveedor
  estáticas; fallback ciego a gemini; visión sin bucle cerrado al orquestador;
  YouTube por scraping; Telegram con bypasses (ver §7).
- AUSENTE: scheduler, watchdog/heartbeat de proceso (hay heartbeat de fichero del
  runner), multi-agent por decisión, UIA total, RAG vectorial.
- MUERTO (0 importadores): `core/subagents.py`, `core/autoloop.py`,
  `core/cognitive/closed_loop.py`, `core/cognitive/self_development_probe.py`.

## 6. Tests: qué prueban y sus límites

- Entradas reales: `test_acceptance_e2e.py` (ScriptedLLM, 15),
  `test_acceptance_surfaces.py` (TestClient HTTP, 15), `test_whatsapp_live_bridge.py`
  (loop con lector simulado, 15), `test_desktop_vision.py` (25, real),
  `test_browser_engine.py` (fixtures locales), `test_checkpoint_resume.py` (21).
- Autoridad adversarial: 003 (45), 004 (39), consolidación (39): forja, replay,
  substitution, mocks como evidencia — todo rechazado.
- Reglas de higiene verificadas: prohibición de mocks que afirman éxito
  (`test_forensic_repair_002`), aislamiento DB bajo pytest (`conftest.py` + `_TempWorld`),
  policies fijadas por test (no dependen del `config.json` real), `local_fallback`
  desactivado en tests de routing/f14.
- Límites honestos: sin LLM vivo (ScriptedLLM/fakes), sin web pública (localhost),
  sin WhatsApp real (dobles), 1 flaky ambiental conocido (ventanas de escritorio;
  pasa aislado). Lo no ejecutado se marca NO verificado.

## 7. Hallazgos históricos: estado actual

- Los 17 documentos §3.1 (technical_audit_report, PROJECT_MASTER, UNIT_001/002, …):
  **ninguno existe**; equivalentes cercanos en `docs/` y raíz (§1 del informe forense).
- "Strategic Review 005" como documento **no existe**; lo cercano es
  `docs/AUTHORITY_CONSOLIDATION_005_REPORT.md` (modelo de autoridad, sin código) y
  `INDEPENDENT_ARCHITECTURE_REVIEW_001.md` (27/09/2026, vigente).
- Sus afirmaciones §3.6, verificadas hoy: `current_goal` use-before-assignment
  **CORREGIDO** (`orchestrator.py:251` crea primero; l.268-273 propaga el error);
  bypass WhatsApp **corregido**, bypass Telegram **CONFIRMADO_ABIERTO**
  (`bridges/telegram_bridge.py:111,122` directos); entradas convergen en el
  orquestador **confirmado**; ~257 archivos entonces vs 307 hoy.
- UNIT-001/UNIT-002 (TypeScript/Postgres/Redis/Stripe/Pino): **cero evidencias** —
  pertenecen a otro proyecto (NEXUM). Avatar es Python; NEXUM solo aparece como
  texto dentro de `memory/state_engine.db` (contenido de misiones, no código).
- Logging: **sin logger estructurado** (36 `print` en `core/`, `logging` solo en
  `browser_controller.py` sin configurar); redacción solo ad-hoc en `/api/config`
  (`server.py:30-45`, extendida a `/api/config/update` en 2026-09 tras fuga real).
- Autoridad §3.5: forja/reúso/auto-afirmación **corregidas en Modelo-A** (frozen+HMAC,
  `PermissionError` en setters, ledger single-use, sello D-5 con `BLOCKED` ante
  manipulación); **abiertas por diseño ante Modelo-B** (atacante en el mismo proceso:
  sin garantía posible in-process, declarado en `authority_core.py:19-28` y
  `act_chokepoint.py:25-28`).

## 8. Deuda técnica y preguntas abiertas

Deuda: 111 `.md` (64 en raíz, sin STATUS único vivo); logging plano; ramas muertas sin
podar; `ToolRegistry` desconectado del dispatch real; `operating_mode` no expone todo;
sin `requirements.lock`; Task Scheduler como único watchdog externo.
Abiertas: repo NEXUM padre muestra `Avatar/` untracked (cosmético); modelo local lento
en CPU (~45s); cuota gratuita de proveedores sujeta a cambios; rediseño total de
Telegram pendiente (hay token en `.env`, scripts en `scratch/`).

Evidencia: citas con archivo:línea en este documento; comandos y salidas en §2;
histórico Git: `git log --oneline` (4 commits). Nada afirmado sin fuente.
