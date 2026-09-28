# AVATAR AI — FASE 10: AUDITORÍA FORENSE DE F-04
## RECUPERACIÓN DE INTENCIÓN ESTRUCTURADA Y CONTINUIDAD COGNITIVA

**Proyecto:** Avatar AI  
**Ubicación Repository:** `B:\PROYECTOS ANTIGRAVITY\Avatar`  
**Auditor:** Sovereign Antigravity Agent  
**Fecha:** 26 de Septiembre de 2026  
**Fase:** Fase 10 — Auditoría Forense y Diseño Arquitectónico (SIN IMPLEMENTACIÓN)  
**Estado de Gobernanza:**  
- `PHASE_10_AUDIT = COMPLETE`  
- `F-04 = NOT_VERIFIED`  
- `GATE_F = NOT_VERIFIED`  
- `GATE_G = NOT_VERIFIED`  
- `READY_FOR_AVATAR_TAKEOVER = NOT_VERIFIED`  

---

## 1. EXECUTIVE SUMMARY

El presente documento establece la auditoría forense, el análisis de causa raíz y el diseño de arquitectura para la **Fase 10** del proyecto Avatar AI.

El propósito de la Fase 10 es resolver el defecto **F-04 (Continuation Without Cognitive Progression)**, descubierto durante la validación post-Fase 9:
* **Problema:** Cuando una herramienta sufre un error severo de entorno (ej. `COMMAND: pytest` en timeout de 120s), el modelo LLM pierde la sintaxis del Native Function Calling de Gemini y emite un bloque de texto que contiene una estructura JSON (ej. `{"action": "LIST_DIR", ...}`). El orquestador interpreta esta salida de texto como una respuesta final conversacional y ejecuta un `break` en el bucle, impidiendo que el `AdaptiveInvestigationEngine` procese la intención o continúe la investigación adaptativa.
* **Solución Arquitectónica Diseñada:** Introducción de un **`StructuredActionRecoveryLayer`** que intercepte respuestas de texto que contienen intenciones estructuradas perdidas, las valide a través de un parser seguro, las someta al `ToolRegistry` y la capa de `Security/Sandbox`, y las reconecte al `AdaptiveInvestigationEngine` como evidencia y nueva acción.

**Regla de Gobernanza de la Fase 10:** Esta fase es **EXCLUSIVAMENTE DE DISEÑO Y AUDITORÍA**. No se ha modificado código de producción, no se han cambiado archivos en `core/`, ni se ha alterado ninguna prueba.

---

## 2. REPRODUCCIÓN FORENSE DE F-04

### Traza de Ejecución Real (`task-2164`):
1. **Paso 1:** Avatar recibe la misión abierta de investigación del sistema de pruebas.
2. **Paso 1 (Tool Call):** Avatar emite la llamada nativa a función `COMMAND: pytest`.
3. **Paso 1 (Tool Result):** `ShellTool` ejecuta `pytest` sobre el espacio de trabajo. Transcurren 120 segundos y la herramienta finaliza con:  
   `[Error]: El comando tardó demasiado (Timeout de 120s).`
4. **Paso 2 (LLM Output):** El modelo LLM recibe el mensaje de timeout. En lugar de emitir el objeto nativo `functionCall` en el JSON de respuesta de Gemini API, el LLM emite una cadena de texto en Markdown:
```json
{
  "action": "LIST_DIR",
  "args": {
    "path": "b:\\PROYECTOS ANTIGRAVITY\\Avatar"
  }
}
```
5. **Paso 2 (Parsing en `llm_provider.py`):** El método `LLMProvider.generate_response_with_tools` busca el campo `"functionCall"` en la parte de la respuesta. Al no existir nativamente, clasifica el resultado como `{"type": "text", "text": "```json..."}`.
6. **Paso 2 (Orquestación en `orchestrator.py`):** `orchestrator.py` evalúa `if llm_result.get("type") == "function_call":`. Al ser falso, toma la rama `else`, asigna `final_user_response = text` y ejecuta `break`.
7. **Consecuencia:** La intención estructurada (`LIST_DIR`) nunca fue ejecutada, el `AdaptiveInvestigationEngine` no pudo re-evaluar la hipótesis y la misión terminó prematuramente.

---

## 3. FULL EXECUTION TRACE (PUNTO DE RUPTURA COGNITIVA)

```
[User Request]
       │
       ▼
[Orchestrator.process_user_input()]
       │
       ├─► Paso 1: LLM ──► Function Call: COMMAND (pytest)
       │           │
       │           └─► ShellTool.execute_command() ──► Timeout 120s
       │                                                     │
       └─► Paso 2: LLM ──► Text Part: ```json {"action": "LIST_DIR"} ```
                   │
                   ▼
     [LLMProvider.generate_response_with_tools()]
                   │
                   ├─► "functionCall" in part? ──► FALSE
                   └─► Returns: {"type": "text", "text": "```json..."}
                                     │
                                     ▼
                     [Orchestrator text branch]
                                     │
                                     ├─► ClaimValidator.validate_llm_claims()
                                     ├─► final_user_response = clean_text
                                     └─► BREAK (TERMINACIÓN PREMATURA) ❌
```

---

## 4. ROOT CAUSE (CAUSA RAÍZ)

1. **Rigidez en la Frontera de Function Calling:** `LLMProvider.generate_response_with_tools` depende al 100% de que el proveedor de LLM devuelva el objeto `"functionCall"` en los metadatos de la API HTTP. Si el modelo sufre una degradación por estrés de contexto (provocada por un error severo de 120s) y emite la acción en el texto, el sistema la trata como texto final.
2. **Ausencia de un `StructuredActionRecoveryLayer`:** `orchestrator.py` carece de una capa de recuperación que inspeccione las salidas de texto en busca de acciones JSON válidas cuando la misión abierta está activa.
3. **Falta de Modelado de Timeout como Evidencia:** El timeout de `ShellTool` es devuelto como una cadena de texto dentro de `raw_output`. El sistema no posee un tipo de evidencia distinguible `TIMEOUT` que active automáticamente un replanteamiento de estrategia en el `AdaptiveInvestigationEngine`.

---

## 5. FUNCTION CALLING BOUNDARY ANALYSIS (ANÁLISIS DE FRONTERA DE FORMATOS)

| Formato | Ejemplo | Quién lo recibe | Cómo se interpreta hoy | Riesgo / Deficiencia |
|---|---|---|---|---|
| **A. Function Call Nativo** | `{"functionCall": {"name": "COMMAND", "args": {...}}}` | Gemini API / `LLMProvider` | Ejecución nativa perfecta en `orchestrator.py`. | Ninguno (Comportamiento ideal). |
| **B. Texto Plano** | `"El análisis demuestra que..."` | `orchestrator.py` | Respuesta final al usuario. | Falsos positivos si el texto describe acciones sin ejecutarlas. |
| **C. JSON Textual Válido** | ````json\n{"action": "LIST_DIR"}\n```` | `orchestrator.py` | **Tratado como texto final (F-04)**. | **Intención estructurada perdida y ruptura cognitiva.** |
| **D. JSON Parcialmente Válido** | `{"action": "COMMAND", "args": {` | `orchestrator.py` | Tratado como texto final. | Salida incompleta del modelo por truncamiento. |
| **E. JSON Inválido** | `{"action": "INVALID_TOOL", ...}` | `orchestrator.py` | Tratado como texto final. | Si se ejecutara sin filtro, provocaría errores en el dispatcher. |
| **F. Texto Mezclado con JSON** | `"Recomiendo listar:\n```json\n{...}\n```"` | `orchestrator.py` | Tratado como texto final. | Ambigüedad entre informe y propuesta de acción. |

---

## 6. DESIGN DEL `STRUCTURED ACTION RECOVERY LAYER`

Se diseña un componente intermediario seguro llamado **`StructuredActionParser`** / **`StructuredActionRecoveryLayer`** que actuará como filtro de recuperación de intenciones estructuradas:

```
                  ┌──────────────────────────────────────────┐
                  │            LLM OUTPUT (TEXT)             │
                  └────────────────────┬─────────────────────┘
                                       │
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │             FORMAT DETECTOR              │
                  │   (¿Contiene bloque ```json o JSON?)     │
                  └──────┬────────────────────────────┬──────┘
                         │                            │
                     No JSON                       Sí JSON
                         │                            │
                         ▼                            ▼
                  ┌──────────────┐             ┌──────────────┐
                  │ PASS THROUGH │             │  SAFE PARSER │
                  │  (LLM TEXT)  │             │ (json.loads) │
                  └──────────────┘             └──────┬───────┘
                                                      │
                                                      ▼
                                               ┌──────────────┐
                                               │ TOOL REGISTRY│
                                               │ VALIDATION   │
                                               └──────┬───────┘
                                                      │
                                                      ▼
                                               ┌──────────────┐
                                               │   SECURITY   │
                                               │   CHECKER    │
                                               └──────┬───────┘
                                                      │
                                                      ▼
                                               ┌──────────────┐
                                               │  RECOVERED   │
                                               │ FUNCTION CALL│
                                               └──────────────┘
```

### Reglas Inquebrantables de Seguridad:
1. **NUNCA ejecutar JSON textual directamente:** Todo JSON recuperado debe pasar por `json.loads`, validación de esquema, verificación de existencia en `ToolRegistry` y comprobación de parámetros de seguridad (Sandbox).
2. **Rechazo de Herramientas Desconocidas:** Si el JSON especifica una acción fuera de `AVATAR_TOOLS_SCHEMA`, se descarta como acción y permanece como texto.
3. **Sin Bypass de Security:** No se permite la ejecución de comandos que violen las restricciones de directorio o de sistema operativo.

---

## 7. TIMEOUT EVIDENCE MODEL (MODELADO DE TIMEOUT COMO EVIDENCIA)

Se formaliza una distinción explícita entre los 4 tipos de resultados negativos:

```
                       ┌──────────────────────────────────────────┐
                       │            RESULTADO NEGATIVO            │
                       └────────────────────┬─────────────────────┘
                                            │
         ┌──────────────────┬───────────────┴───────────────┬──────────────────┐
         ▼                  ▼                               ▼                  ▼
  ┌─────────────┐    ┌─────────────┐                 ┌─────────────┐    ┌─────────────┐
  │   TIMEOUT   │    │TOOL_FAILURE │                 │VERIFICATION_│    │INSUFFICIENT_│
  │ (Excedido   │    │ (ExitCode !=│                 │   FAILURE   │    │  EVIDENCE   │
  │ tiempo SO)  │    │      0)     │                 │(Criterio no │    │(Presupuesto │
  └──────┬──────┘    └─────────────┘                 │ cumplido)   │    │  agotado)   │
         │                                           └─────────────┘    └─────────────┘
         ▼
  ┌──────────────────────────────────────────┐
  │      EVIDENCIA DE ANÁLISIS DE COSTO      │
  │  (Estrategia demasiado pesada/alcance)   │
  └──────────────────┬───────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────┐
  │      MUTACIÓN ADAPTATIVA DE ALCANCE      │
  │  (Cambiar a ejecutor focalizado/unittest)│
  └──────────────────────────────────────────┘
```

---

## 8. INTEGRACIÓN CON ADAPTIVE INVESTIGATION ENGINE (FASE 9)

Cuando el `PhysicalFactVerifier` o `ShellTool` registra un `TIMEOUT`:
1. `AdaptiveInvestigationEngine` clasifica el evento como `TaskResultStatus.TIMEOUT`.
2. El motor marca la hipótesis de "Ejecución global pesada" como refutada por costo.
3. Sugiere una mutación de alcance (ej. pasar de escaneo global a ejecutor ligero determinista).
4. Si se recupera una llamada JSON vía `StructuredActionRecoveryLayer`, el evento se procesa como un paso normal de investigación dentro del bucle ReAct, impidiendo el `break` en `orchestrator.py`.

---

## 9. AUTHORITY MODEL (REFORZADO)

```
LLM (Propuesta en texto o JSON)
  ↓
StructuredActionParser (Validación sintáctica)
  ↓
ToolRegistry (Validación de herramienta permitida)
  ↓
Security / Sandbox (Autorización de ejecución)
  ↓
Orchestrator (Invocación a herramienta nativa)
  ↓
PhysicalFactVerifier (Captura de Hecho Físico Nivel 4)
  ↓
AdaptiveInvestigationEngine (Control de Misión y Terminación)
```

El LLM nunca decide la finalización de la misión; la finalización es potestad exclusiva del `AdaptiveInvestigationEngine`.

---

## 10. SECURITY MODEL & SANDBOX PROTECTION

- **Prevención de Injection Attack:** El `StructuredActionParser` sanitiza argumentos removiendo inyecciones de comandos shell arbitrarios.
- **Respeto a `allowed_workspace`:** Todas las rutas contenidas en JSON recuperados son validadas contra `b:\PROYECTOS ANTIGRAVITY\Avatar`.
- **Prevención de Re-entry Loops:** Se establece un presupuesto máximo de 2 recuperaciones de JSON textual por sesión de misión abierta.

---

## 11. ANÁLISIS DE CONDICIONES DE TERMINACIÓN EN `ORCHESTRATOR.PY`

En `core/orchestrator.py`, la condición actual de finalización es:

```python
# CÓDIGO ACTUAL (INCORRECTO ANTE F-04):
if llm_result.get("type") == "function_call":
    # ejecuta herramienta...
else:
    raw_text = llm_result.get("text", "")
    final_user_response = clean_text
    break # <--- ABANDONO PREMATURO
```

### Condición Arquitectónica Diseñada para Fase 10:

```python
# DISEÑO OBJETIVO PARA FASE 10:
if llm_result.get("type") == "function_call":
    # ejecución nativa...
else:
    raw_text = llm_result.get("text", "")
    recovered_action = StructuredActionParser.parse_and_validate(raw_text, AVATAR_TOOLS_SCHEMA)
    
    if recovered_action.is_valid:
        # Ejecutar herramienta recuperada como una llamada a función física
        tool_name = recovered_action.tool_name
        args = recovered_action.args
        # Re-conectar al bucle continuo sin romper la iteración...
    else:
        # Si no hay acción recuperable, consultar al AdaptiveInvestigationEngine si la misión puede concluir
        if interaction_type == InteractionType.OPEN_ENGINEERING_MISSION:
            inv_res = investigation_engine.evaluate_mission_conclusion(executed_tools_summary, raw_text)
            if not inv_res.is_terminal and step_count < max_steps:
                # Inyectar prompt de continuación e iterar...
                continue
        break
```

---

## 12. MAQUINA DE ESTADOS REFORZADA (`InvestigationState`)

```
IDLE ──► HYPOTHESIZING ──► EXECUTING_PROBE ──► EVALUATING_EVIDENCE
                                                      │
                       ┌──────────────────────────────┼──────────────────────────────┐
                       ▼                              ▼                              ▼
                 [Evidencia OK]               [Tool Failure]                    [Timeout]
                       │                              │                              │
                       ▼                              ▼                              ▼
                 CONTINUE_PROBE               MUTATING_STRATEGY             MUTATING_SCOPE/REPLAN
```

---

## 13. MODELO DE EVENTOS (`EventModel`)

- `StructuredActionRecovered`: Registra la recuperación exitosa de un JSON textual.
- `StructuredActionRejected`: Registra el rechazo de un JSON por fallo de esquema o seguridad.
- `TimeoutEvidenceRecorded`: Registra un evento de timeout con la métrica de duración.

---

## 14. INTEGRACIÓN CON RECOVERY ENGINE Y REPLANNER

- `RecoveryEngine` procesará el evento `TIMEOUT` con la estrategia `MUTATE_SCOPE` o `RETRY_MODIFIED`.
- `Replanner` reestructurará la cola de tareas cuando una herramienta pesada expire.

---

## 15. ESTRATEGIA DE PRUEBAS PARA LA FUTURA IMPLEMENTACIÓN

Para verificar la futura Fase 10, se exigirán 17 pruebas unitarias e integradas:

1. `test_001_native_function_call_works`: Verifica la llamada nativa intacta.
2. `test_002_valid_json_text_recovered`: Comprueba la recuperación de un JSON textual válido (`LIST_DIR`).
3. `test_003_invalid_json_text_ignored`: Verifica que JSON malformado no rompa el sistema.
4. `test_004_unregistered_tool_json_rejected`: Rechaza JSONs con herramientas inexistentes.
5. `test_005_invalid_arguments_json_rejected`: Rechaza argumentos fuera de esquema.
6. `test_006_json_recovery_respects_tool_registry`: Comprueba paso obligatorio por `ToolRegistry`.
7. `test_007_json_recovery_respects_security_sandbox`: Comprueba paso obligatorio por validación de seguridad.
8. `test_008_timeout_does_not_terminate_open_mission`: Un timeout de comando no cierra la misión.
9. `test_009_timeout_generates_timeout_evidence`: Verifica creación de evidencia `TIMEOUT`.
10. `test_010_timeout_evidence_triggers_replanning`: Comprueba replanificación ante timeout.
11. `test_011_mission_continues_after_timeout`: La misión continúa investigando tras timeout.
12. `test_012_llm_can_propose_new_action_after_timeout`: El agente propone nueva acción válida tras timeout.
13. `test_013_new_action_validated_before_execution`: La nueva acción se valida antes de ejecutar.
14. `test_014_recovered_action_returns_to_observation`: La salida de la acción recuperada pasa por `Observer`.
15. `test_015_anti_loop_recovery_prevention`: Impide bucles infinitos de recuperación de JSON.
16. `test_016_recovered_json_does_not_become_verified_fact`: El JSON recuperado no es hecho hasta su ejecución física.
17. `test_017_full_regression_gates_a_to_e_and_f03`: Suite completa de 123 pruebas previas en PASS.

---

## 16. CRITERIOS DE ACEPTACIÓN DE LA FASE 10

1. **Recuperación Segura:** Recuperación comprobada de acciones estructuradas JSON sin violaciones de seguridad.
2. **Resiliencia ante Timeout:** Ante un timeout de 120s, la misión continuará investigando en lugar de abortar.
3. **Regresión Impecable:** 123/123 pruebas en PASS + 17 pruebas de Fase 10 en PASS.

---

## 17. MATRIZ DE RIESGOS Y MITIGACIÓN

| Riesgo | Impacto | Mitigación Arquitectónica |
|---|---|---|
| Falsos positivos al parsear bloques de código markdown que contengan ejemplos JSON | Medio | El `StructuredActionParser` comprobará que el JSON corresponda a una herramienta válida en `AVATAR_TOOLS_SCHEMA`. |
| Bucles infinitos de emisión de JSON textual | Alto | Contador `recovery_attempts_count` limitado a 2 por misión. |

---

## 18. COMPATIBILIDAD CON GATES A-E Y FASE 9

- **Gates A-E:** 100% compatibles.
- **F-03 (Claim Validation):** Mantiene la exigencia de evidencia física comprobada en disco.

---

## 19. CONTRATO DE IMPLEMENTACIÓN PARA LA FUTURA FASE 10

Cuando Mauro apruebe este diseño, la implementación física creará/modificará:
- `core/cognitive/structured_action_parser.py` [NUEVO]
- `core/orchestrator.py` [MODIFICACIÓN CONTROLADA]
- `tests/test_f04_structured_action_recovery.py` [NUEVO]

---

## 20. EXPLICIT NON-GOALS (LO QUE NO SE HACE EN ESTA FASE)

- ❌ No se ha modificado ningún archivo de código Python (`.py`).
- ❌ No se ha alterado `orchestrator.py` ni `llm_provider.py`.
- ❌ No se ha creado el parser físico ni modificado las pruebas.
- ❌ No se ha declarado verificado el Gate F ni el Gate G.

---

## GOVERNANCE STATEMENT & DICTAMEN FINAL

El análisis forense y el diseño de arquitectura para la resolución del defecto **F-04** han sido completados en su totalidad en `AVATAR_PHASE_10_ARCHITECTURE_AUDIT.md`.

El proyecto Avatar AI queda listo para someter este diseño a la revisión y aprobación de Mauro antes de proceder al desarrollo físico.

**Salida Oficial de Gobernanza:**

```text
PHASE_10_AUDIT = COMPLETE

F-04 = NOT_VERIFIED

GATE_F = NOT_VERIFIED
GATE_G = NOT_VERIFIED

READY_FOR_AVATAR_TAKEOVER = NOT_VERIFIED
```
