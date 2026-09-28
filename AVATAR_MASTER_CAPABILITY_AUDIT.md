# AVATAR MASTER CAPABILITY AUDIT
**MASTER MISSION 001 — SOVEREIGN PERSONAL ASSISTANT AUDIT — v2.0**
**Date:** 2026-09-28 | **Owner:** Mauro | **Primary Agent:** AVATAR (vía Antigravity como herramienta)
**Execution Status:** Audited, corrected against physical evidence, 2 justified fixes implemented

> Esta v2.0 sustituye a la v1.0 (March 2025). La v1.0 contenía afirmaciones que la evidencia
> física de esta auditoría no sostiene; cada corrección está marcada con [CORRIGE v1.0] y su
> prueba. Regla aplicada: código existente ≠ capacidad operacional; test ≠ autonomía;
> `exit_code == 0` ≠ objetivo cumplido; respuesta del LLM ≠ acción ejecutada.

---

## 1. Executive Summary

Se auditó el runtime real (orquestador → chokepoint → SQLite), 6 adaptadores de proveedor,
memoria, servidor HTTP, bridges, superficie (browser/visión/control/YouTube) y 34 archivos
de tests. Resultado A–Z (26 capacidades): **11 VERIFIED, 12 PARTIAL,
2 IMPLEMENTED_NOT_INTEGRATED, 1 NOT_IMPLEMENTED, 0 BLOCKED** (más 6 capacidades §§30–35:
3 VERIFIED, 2 PARTIAL, 1 NOT_IMPLEMENTED por decisión explícita).

Debilidades demostradas y corregidas en esta misión (únicos cambios de código, §52):
1. **FIX-SEC-01:** `POST /api/config/update` devolvía `config.json` con claves en claro
   (`server.py:107`). Demostrado con request real (5 secretos en claro). Fix: misma
   redacción que `GET /api/config`. Test: `test_config_update_does_not_return_secrets_in_clear`.
2. **FIX-INT-01:** `ResumeEngine` instanciado pero con **0 llamadas en runtime** — "continúa
   mañana" no tenía camino de código. Fix: `AvatarOrchestrator.resume_mission()` +
   `POST /api/missions/resume`; la ejecución reanudada pasa por el chokepoint ligada a su
   misión. Tests: binding + idempotencia del endpoint.

Suite tras los fixes: **452 passed, 0 failed** (baseline previo: 449).

## 2. Current Architecture

```
MAURO
  │  GUI (server.py FastAPI :8000) / CLI (interface/cli.py) / Telegram / WhatsApp
  ▼
AvatarOrchestrator (core/orchestrator.py:146)
  │  SemanticMissionEngine.classify → CognitiveAdapter goal → create_mission (por turno)
  │  single-task: generate_response_with_tools → SAR fallback → _dispatch_native_tool
  │  multi-task: Planner → ContinuousExecutionEngine + TaskQueue
  ▼
ActChokepoint (core/act_chokepoint.py:197) — 8 acts, policy, executors, observers, ledger `acts`
  │  COMMAND/READ_FILE/WRITE_FILE/LIST_DIR/WEB_SEARCH/FETCH_URL/PLAY_AUDIO/SEND_WHATSAPP
  ▼
PhysicalFactVerifier + AuthorityCore + ClaimValidator + MissionCompletionGate
  ▼
StateEngine SQLite WAL (memory/state_engine.db): missions, planner_tasks, acts, evidences,
gaps, history, capability_records. RAGMemory delega en StateEngine (no es RAG vectorial).
Proveedores: 6 adaptadores en core/llm_provider.py. default_provider: groq.
```

## 3. Capability Matrix (A–Z + §§30–35)

| ID | Capability | Status | Implementation | Files | Gaps / Blockers | Sec | Priority |
|---|---|---|---|---|---|---|---|
| A | Conversación inteligente | VERIFIED | Clasificación + multi-turno + SAR | `semantic_mission_engine.py`, `adapter.py`, `structured_action_recovery.py` | Ninguno bloqueante | L1 | P1 |
| B | Autonomía de decisión | VERIFIED | Investigación adaptativa por gaps, sin recetas | `adaptive_investigation_engine.py` | Planner solo corre en rama multi-task | L1 | P1 |
| C | Mission Engine | VERIFIED | Misión persistente: ID, tareas, evidencia, gaps, checkpoints | `state_db.py`, `semantic_mission_engine.py`, `models.py` | Ninguno | L1 | P1 |
| D | Persistent Runtime | PARTIAL | Checkpoint VERIFIED y usado; **resume existía desconectado [CORRIGE v1.0]**; conectado en esta misión; sin watchdog/heartbeat | `checkpoint_engine.py`, `resume_engine.py`, `orchestrator.resume_mission` | Falta daemon watchdog | L1 | P1 |
| E | Multitarea | PARTIAL | TaskQueue solo rama multi-task; sin aislamiento entre misiones | `task_queue.py`, `continuous_loop.py` | Ejecución multi-misión concurrente | L1 | P2 |
| F | Memoria operacional | PARTIAL | Memoria relacional real; **"RAG" es búsqueda por palabras, no vectorial [CORRIGE v1.0]**; sin episódica/semántica | `rag_memory.py`, `state_db.py` | Retrieval semántico | L0 | P2 |
| G | Computer Control | VERIFIED | COMMAND/WRITE observados; pyautogui + Win32 + UIA PowerShell reales | `tools/computer_control.py`, `core/ui_inspector.py`, `tools/shell_tool.py` | Wrapper UIA completo | L3 | P1 |
| H | Visión | PARTIAL | Screenshot + OCR locales reales; sin bucle OBSERVE→VERIFY ligado al orquestador | `tools/screen_tool.py`, `core/ui_inspector.py` | Diff visual en tiempo real | L1 | P2 |
| I | Capturas | VERIFIED | Captura + verificación física del archivo | `tools/screen_tool.py`, `tools/capture.ps1` | Envío a WhatsApp sujeto a policy | L1 | P2 |
| J | Browser Agent | PARTIAL | Playwright real verificado contra localhost; sin verificación en web pública | `tools/browser_controller.py`, `tools/web_tool.py` | CAPTCHA/Cloudflare, anclas visuales DOM | L2 | P2 |
| K | YouTube | PARTIAL | Scraping + automatización de reproducción reales; **sin PyTube/yt_dlp (la v1.0 lo citaba) [CORRIGE v1.0]**; `play_song.py` es stub | `tools/audio_tool.py` | Media keys, backend legítimo | L1 | P3 |
| L | WhatsApp | PARTIAL | Ruta SEND_WHATSAPP + bridge existen; **daemon es sleep-loop stub, live es prints, envío denegado por defecto [CORRIGE v1.0]** | `bridges/whatsapp_bridge.py` | Lectura vive de sync externo; envío exige consentimiento (correcto) | L2 | P1 |
| M | Filesystem Agent | VERIFIED | Ops con scope + anti-traversal + observación | `tools/file_tool.py`, `act_chokepoint.py` | Ninguno | L3 | P1 |
| N | Software Engineering | VERIFIED | Escribir/probar/verificar vía chokepoint (demostrado en esta misión + e2e) | `orchestrator.py`, `tools/*` | Loop nocturno unsupervised (ver W) | L3 | P1 |
| O | Git | IMPLEMENTED_NOT_INTEGRATED | Git vía shell funciona; sin herramienta estructurada en dispatch; subagente muerto | `tools/shell_tool.py` | `git_status/diff/commit` como acts | L2 | P2 |
| P | Testing Engine | VERIFIED | pytest dinámico vía COMMAND + parsing | tests e2e + `orchestrator.py` | Multi-framework | L1 | P1 |
| Q | Debugging Engine | VERIFIED | stdout/stderr completos + clasificador + hipótesis | `error_classifier.py`, `adaptive_*` | Ninguno bloqueante | L1 | P1 |
| R | Physical Fact Verification | VERIFIED | Veredictos físicos firman autoridad; claims sin evidencia rechazados | `physical_fact_verifier.py`, `authority_core.py` | Ninguno | L0 | P1 |
| S | Recovery Engine | PARTIAL | Estrategias + budgets reales; **fallback de proveedor solo hacia gemini, sin cascada ni health-routing [CORRIGE v1.0]** | `recovery_engine.py`, `recovery_policy.py`, `llm_provider.py:637-648` | Router por salud | L1 | P1 |
| T | Skill System | IMPLEMENTED_NOT_INTEGRATED | Esquemas definidos; sin loader ni pipeline; ToolRegistry desconectado del dispatch | `capability_definitions.py`, `tool_registry.py` | Loader + ejecución dinámica | L1 | P2 |
| U | Provider Independence | PARTIAL | 6 adaptadores + fallback de modelos; **capacidades = flags estáticos, health no dirige tráfico, fallback ciego a gemini [CORRIGE v1.0]** | `core/llm_provider.py` | Detección real de capacidades | L1 | P1 |
| V | Local Sovereignty | PARTIAL | Conectores Ollama/LM Studio con health real | `core/llm_provider.py:470-533` | Function-calling local sin verificar físicamente | L0 | P2 |
| W | Long-Running Dev | PARTIAL | Checkpoint+resume cableados; **`autoloop.py` muerto (la v1.0 lo citaba) [CORRIGE v1.0]**; sin daemon nocturno | `checkpoint_engine.py`, `resume_engine.py` | Watchdog daemon | L3 | P2 |
| X | Scheduler | NOT_IMPLEMENTED | Ausencia confirmada (código + deps) | — | Windows Task Scheduler / cron | L2 | P3 |
| Y | Remote Control | PARTIAL | **Telegram polling real + webhook WhatsApp real (la v1.0 decía ausentes) [CORRIGE v1.0]**; + `/api/missions/resume` en esta misión | `bridges/telegram_bridge.py`, `server.py` | Comandos remotos pausa/estado | L3 | P3 |
| Z | Permission Engine | VERIFIED | 5 riesgos, consentimiento externo, dry-run default, ledger append-only, guard AST | `act_chokepoint.py`, `authority_core.py`, `test_chokepoint_enforcement.py` | Límite in-process documentado | L4 | P1 |
| §30 | Multi-Agent | NOT_IMPLEMENTED | `subagents.py` muerto (0 llamadas, `self.chokepoint` inexistente). **Decisión: NO implementar** — valor no demostrado (§§30/44) | `core/subagents.py` | — | L1 | P4 |
| §31 | Anti-Hallucination | VERIFIED | MODEL_CLAIM≠FACT enforced + suites adversariales 003/004 | `claim_validator.py`, tests authority | Ninguno | L4 | P1 |
| §32 | Anti-Stagnation | VERIFIED | Detector cableado al orquestador + tests f05 | `stagnation_detector.py` | Ninguno | L1 | P2 |
| §33 | No-Action-Required | VERIFIED | Ruta de no-acción con evidencia + tests | `semantic_mission_engine.py` | Ninguno | L1 | P2 |
| §34 | Seguridad | PARTIAL | Chokepoint + redacción + guard AST reales; **fuga viva en update corregida aquí**; bypass Telegram sin registro pendiente | `server.py`, `bridges/telegram_bridge.py:111,122` | Registrar screenshot/audio como acts | L4 | P1 |
| §35 | Auto-Diagnóstico | PARTIAL | `operating_mode()` + resume/evaluate responden estado; sin punto único de autodiagnóstico | `orchestrator.py:676-701` | Comando `status` unificado | L0 | P2 |

## 4. Verified Capabilities
A, B, C, G, I, M, N, P, Q, R, Z (+ §§31–33). Evidencia: suites verdes + ejecución física
en esta misión (COMMAND/WRITE observados, acts ligados a misión, denegación WhatsApp).

## 5. Partial Capabilities
D, E, F, H, J, K, L, S, U, V, W, Y (+ §§34–35). Patrón común: el mecanismo existe pero le
falta integración, verificación física en entorno real, o una pieza (watchdog, router,
loader, daemon).

## 6. Missing Capabilities
X (Scheduler) ausente total. §30 Multi-Agent ausente **por decisión documentada**.

## 7. Broken Integrations (demostradas, no supuestas)
1. `resume_engine.py` — 0 llamadas runtime → **reparado (FIX-INT-01)**.
2. `POST /api/config/update` devolvía claves → **reparado (FIX-SEC-01)**.
3. `bridges/telegram_bridge.py:111,122` — screenshot/audio directos, sin act → pendiente (diseño en §23.3).
4. `core/subagents.py:63` — `self.chokepoint` inexistente + 0 llamadas → muerto; no reparar, retirar del roadmap (§30).
5. `core/autoloop.py`, `cognitive/closed_loop.py`, `cognitive/self_development_probe.py` — muertos (0 importadores); producción usa `continuous_loop.py`. No reparar; documentar.
6. `cognitive/tool_registry.py` — desconectado del dispatch real (if/elif en `_dispatch_native_tool`). Unificar solo con tests f04 verdes como red.
7. Redacción v1.0 refutada por lectura directa: `main_gui.py` **no** tiene shadowing de bridges (78 líneas, daemons separados); `play_song.py` es `import web browser` (stub, no PyTube); `requirements.txt` sin `yt_dlp/vlc/pytube/APScheduler`.

## 8. Security Findings
- **F-01 (reparado):** fuga de 5 secretos vía update-config. Causa: asimetría redactada/no-redactada. Regla: todo endpoint que devuelva config pasa por `redact_secrets`.
- **F-02 (abierto, L1):** acciones Telegram fuera del ledger. No es escape de efectos (son locales/observación), es hueco de auditabilidad.
- **F-03 (aceptado):** el chokepoint es in-process; no detiene código arbitrario en el intérprete. Requiere frontera out-of-process (diseño futuro, §23.5).
- `config.json` contiene claves reales (GROQ/Gemini). Nunca incluir valores en reportes, logs ni respuestas. `redact_secrets` cubre `key/token/secret/password`.
- El repo git raíz versiona NEXUS; **`Avatar/` está untracked: el propio Avatar carece de control de versiones**. Recomendación: repo propio (NO auto-iniciar sin aprobación: la raíz pertenece a otro proyecto).

## 9. Infrastructure Dependencies
Red (proveedores cloud, DuckDuckGo/Wikipedia, Telegram API), local (Ollama/LM Studio
opcionales, Playwright/Chromium, Tesseract para OCR, PowerShell/Win32), externas
(sync de WhatsApp vía proceso externo + teléfono). Sin watchdog, sin scheduler del SO.

## 10. Provider Matrix
| Proveedor | Texto | FuncCall | Visión | Streaming | Health | Fallback modelos |
|---|---|---|---|---|---|---|
| gemini | sí | sí | no¹ | no¹ | por presencia de key | 5 modelos, 2 intentos |
| openai/github | sí | sí | sí¹ | no¹ | por presencia de key | — |
| groq (default) | sí | sí | no¹ | no¹ | por presencia de key | 3 modelos |
| ollama/lmstudio | sí | no (ollama) | no¹ | no¹ | ping HTTP real | — |
¹ Flags estáticos en código, no detectados. Routing = `default_provider` + fallback
unidireccional a gemini ante `provider_error` + reintento con poda de mensajes (413/429/503).

## 11. Computer Control Assessment
COMMAND/WRITE/LIST/READ verificados físicamente vía chokepoint. `computer_control.py`
(pyautogui FAILSAFE, click/type/hotkey) + `ui_inspector.py` (Win32 DPI/ventanas, UIA por
PowerShell, OCR con fallback) reales. `mouse_tool.py` es stub (`import time`).

## 12. Vision Assessment
`screen_tool.py` (ImageGrab → PNG verificado, fallback `capture.ps1`, sintética) + OCR
local reales, con tests físicos (`test_desktop_vision.py`, 25 tests). Falta el bucle
cerrado OBSERVE→DECIDE→ACT→OBSERVE→VERIFY gobernado por el orquestador.

## 13. Browser Assessment
`browser_controller.py` (Playwright, scope por dominio, sanitize UNTRUSTED) real, probado
contra servidor local de fixtures. Sin evidencia en web pública; CAPTCHA/Cloudflare fuera
de alcance verificado.

## 14. WhatsApp Assessment
Envío: ruta técnica existe, denegada por defecto sin consentimiento (comportamiento
correcto y probado). Lectura/clasificación: depende de proceso externo de sync; daemon
propio es stub. Auto-reply operativo real: NO (por diseño de seguridad + infra).

## 15. Software Engineering Assessment
El sistema escribe, ejecuta, observa y verifica (esta misión lo demuestra: 4 archivos
tocados, cada cambio con test + regresión). Límite: el driver de largo aliento es externo;
no hay daemon propio de desarrollo nocturno.

## 16. Mission Runtime Assessment
Misión persistente por turno + reconciliación por gate + checkpoint + resume cableado +
idempotencia probada (test_21) + supervivencia a reinicio. DB real: 31 misiones
(18 NO_REQUIREMENTS_DECLARED, 8 COMPLETED, 3 IN_PROGRESS, 2 BLOCKED), 31/31 tareas
VERIFIED, acts persistidos en ledger.

## 17. Memory Assessment
Operacional-relacional VERIFIED (misiones, acts, evidencias, historial, capabilities).
"RAG" = índice por palabras (topics), top-5, sin embeddings: útil, mal nombrado. Sin
memoria episódica ni semántica diferenciada. Ventana de 10 turnos al LLM + knowledge por
tópico.

## 18. Skills Assessment
Solo esquemas (`capability_definitions.py`: 5 capabilities protegidas, solo
`CAP_STATE_ENGINE` verificable por diseño). Sin loader, sin pipeline de ejecución, sin
registro conectado al dispatch. Los "skills" efectivos hoy son los 8 acts del chokepoint.

## 19. Scheduler Assessment
NOT_IMPLEMENTED. Sin código, sin dependencia, con spec previa en docs. Requiere Task
Scheduler de Windows o servicio propio (que a su vez requiere watchdog, §23.1).

## 20. Remote Control Assessment
Parcial operativo: Telegram responde (texto + captura + música vía chokepoint),
webhook WhatsApp procesa, y desde esta misión `/api/missions/resume` permite continuar
trabajo remoto. Falta: comandos remotos de estado/pausa unificados.

## 21. Architecture Target
Se conserva la arquitectura vigente (probada por 452 tests): NO se propone rewrite.
Cambios objetivo: (1) watchdog + scheduler (§23.1), (2) acts de observación para cerrar
F-02 (§23.3), (3) ToolRegistry como fuente del dispatch (§23.4), (4) frontera
out-of-process para F-03 (§23.5). Todo lo demás es completar parciales, no rediseñar.

## 22. Dependency Graph
```
Scheduler → Watchdog → Persistent Runtime(D/W) → Mission Engine(C) → todo lo demás
Remote(Y) → Runtime + Bridges(L) | Vision(H) → Computer Control(G) → Chokepoint(Z)
Browser(J) → POLICY Network | Skills(T) → ToolRegistry → Dispatch | U/V → LLM
```

## 23. Implementation Roadmap
- **Fase 1 — Watchdog + Scheduler (D/W/X):** `core/watchdog.py` (heartbeat 30s, reinicio,
  re-resume al arrancar) + `core/scheduler.py` (cron persistido en SQLite) o Task Scheduler.
  Desbloquea "trabaja esta noche" y "todos los días a las 23:00".
- **Fase 2 — Control remoto (Y):** comandos `estado/pausa/continúa/captura` sobre Telegram +
  webhook, leyendo estado real (evaluate_mission + operating_mode).
- **Fase 3 — Cierre de auditabilidad (F-02):** acts `SCREEN_CAPTURE` (READ) y `AUDIO_CONTROL`
  con observers físicos; telegram_bridge por chokepoint; extender guard AST.
- **Fase 4 — Registry como fuente (T/O):** dispatch consulta `ToolRegistry`; git estructurado
  como acts; skills con loader mínimo (manifiesto + permisos + verificación).
- **Fase 5 — Frontera out-of-process (F-03):** ejecutor COMMAND en proceso hijo/sandbox con
  política de rutas; holomorphic con chokepoint (el ledger sigue dentro).
- **No-hacer:** multi-agent, rewrite del orquestador, "RAG vectorial" (sin necesidad
  demostrada), UIA total (con lo actual basta para el 90%).

## 24. Priority Order
P1: Fase 3 (F-02) + `status` unificado (§35) + repo propio para Avatar (§8). P2: Fase 1,
Fase 4. P3: Fase 2 completa, Fase 5, Scheduler fino, multimodal real. P4/excluido: multi-agent.

## 25. Test Strategy
Determinista sin red ni LLM vivo: TestClient, ScriptedLLM, fixtures locales (browser_server),
DBs temporales (`conftest.py` redirige bajo pytest; `_TempWorld` puntual). Prohibido:
mocks que afirmen éxito (forensic_repair_002), truncar errores, `unittest` directo sin
conftest (tocaría la DB real — documentado en informe de tests).

## 26. Acceptance Criteria
Cada capacidad: prueba física (archivo/proceso/ventana/paquete observables) + evidencia en
ledger/registry + regresión verde. Ningún VERIFIED sin los tres. Esta misión los cumple
para sus 2 fixes (request real → cambio → test → 452 verdes).

## 27. Risks
Modelo propone y sistema dispone (el LLM nunca es autoridad); deriva de capacidades
estáticas; proveedor único efectivo (groq default, gemini red); claves en `config.json`
plano (permiso de archivo del SO como única protección); control in-process (F-03);
Avatar sin versionar (§8); tests que tocan la DB real si se corre `unittest` sin conftest.

## 28. Open Questions
1. ¿Repo propio para Avatar o monorepo con NEXUS? (requiere decisión de Mauro).
2. ¿Windows Task Scheduler o servicio propio para X? (servicio propio exige watchdog primero).
3. ¿Límite de autonomía nocturna (tiempo/acts) antes de pedir decisión humana?
4. ¿Qué proveedor sostiene visión real cuando J la necesite (ninguno verificado hoy)?

## 29. Recommended Next Mission
**MISSION 002 — Watchdog + `status` + F-02.** Concreto y verificable: (1) `core/watchdog.py`
con heartbeat y re-resume al arrancar; (2) comando/endpoint `status` unificado (misión,
acts recientes, providers, modo); (3) acts `SCREEN_CAPTURE`/`AUDIO_CONTROL` y telegram
por chokepoint. Criterio de cierre: noche simulada (kill + restart) con misión que continúa
sola + ledger completo. Todo lo demás del roadmap espera a 002.

---

## Evidence Log (esta misión)

| ID | Action | Expected | Actual | Evidence | Result |
|---|---|---|---|---|---|
| RESUME-001 | grep llamadas a `resume_active_mission` fuera de su archivo/tests | alguna | 0 en runtime | informe forense + `orchestrator.py:153` sin llamadas | GAP confirmado |
| RESUME-002 | `orch.resume_mission` ejecuta COMMAND ligado a misión | 1 act ligado | act COMMAND OBSERVED con mission_id | `test_acceptance_surfaces.py::TestResumeSurface` | VERIFIED |
| RESUME-003 | `POST /api/missions/resume` idempotente | shape estable | `COMPLETED/[]` en 2ª pasada | mismo test + `test_21` | VERIFIED |
| SEC-001 | `POST /api/config/update` con `{}` | sin secretos | 5 secretos en claro | request real TestClient | FAIL→FIX |
| SEC-002 | mismo tras fix + test regresión | redactado | `***set(n)***`, 0 prefijos reales | `test_config_update_...` + suite 452 | VERIFIED |
| BASE-001 | suite completa pre-cambios | verde | 449 passed | pytest 134.50s | VERIFIED |
| BASE-002 | suite completa post-cambios | verde | **452 passed, 0 failed (114.34s)** | pytest | VERIFIED |

## Audit Certification Log
```
AUDIT_ID: AUDIT-MASTER-001-v2
SUITE_EXECUTION: 452 PASSED, 0 FAILED (114.34s)
A-Z: 11 VERIFIED / 12 PARTIAL / 2 IMPLEMENTED_NOT_INTEGRATED / 1 NOT_IMPLEMENTED / 0 BLOCKED
SS30-35: 3 VERIFIED / 2 PARTIAL / 1 NOT_IMPLEMENTED (por decision)
CODE_CHANGES: 4 archivos (server.py, orchestrator.py, resume_engine.py, tests) + este informe
V1_CORRECTIONS: D,F,K,L,S,U rebajadas; Y subida; 4 citas falsas corregidas
AUDIT_STATUS: COMPLETED & VERIFIED
```
*Informe generado y verificado físicamente contra código, DB y suite. Sin Antigravity en
el runtime: es herramienta de desarrollo, no parte de la arquitectura.*