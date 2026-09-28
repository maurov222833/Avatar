# AVATAR AI — FASE 11: AUDITORÍA FORENSE DE PROGRESIÓN COGNITIVA
## DIAGNÓSTICO DE CAUSA RAÍZ DE F-05 (COGNITIVE PROGRESSION FAILURE)

**Proyecto:** Avatar AI  
**Ubicación Repository:** `B:\PROYECTOS ANTIGRAVITY\Avatar`  
**Auditor:** Sovereign Antigravity Agent  
**Fecha:** 26 de Septiembre de 2026  
**Fase:** Fase 11 — Auditoría Forense y Diagnóstico de Causa Raíz (SIN IMPLEMENTACIÓN)  
**Resultado de Auditoría:** `F-05 = CONFIRMED` (`COGNITIVE PROGRESSION FAILURE`)  
**Estado de Gobernanza:**  
- `PHASE_11_AUDIT = COMPLETE`  
- `GATE_F = NOT_VERIFIED`  
- `GATE_G = NOT_VERIFIED`  
- `READY_FOR_AVATAR_TAKEOVER = NOT_VERIFIED`  

---

## 1. EXECUTIVE SUMMARY

El presente documento establece la auditoría forense profunda, el análisis de trazabilidad paso a paso y el diagnóstico de causa raíz de la **Fase 11** para el proyecto Avatar AI.

El objetivo de la Fase 11 es investigar por qué, durante la reauditoría oficial de los Gates F/G (`task-2218`), tras recibir la evidencia física del fallo de `COMMAND: pytest`, el sistema **no logró generar una progresión cognitiva útil ni mutar autónomamente de estrategia**, cayendo en un bucle de respuestas de texto y avisos de continuación hasta agotar los 15 pasos y la cuota de la API (`HTTP 429`).

### Conclusión Principal de la Auditoría:
Se confirma la hipótesis **`F-05 — COGNITIVE PROGRESSION FAILURE`**. Se identificaron dos fallas estructurales de integración en `core/orchestrator.py`:
1. **Truncamiento Crítico del Error de Consola:** En `semantic_mission_engine.py`, la razón de falla inyectada en el prompt de continuación truncaba la salida de error a los primeros 120 caracteres (`Last error: [Resultado PowerShell (ExitCode: 1)]:\nstdout:\n============================= test session starts ========================`), **ocultando el error real de Python** (`RuntimeError: The starlette.testclient module requires the httpx2 package...`).
2. **Desconexión entre `AdaptiveInvestigationEngine` y el Prompt del LLM:** `orchestrator.py` invocaba a `investigation_engine.evaluate_task_step()`, la cual calculaba correctamente la recomendación `RETRY_MODIFIED`. Sin embargo, **dicha recomendación era almacenada en memoria y nunca inyectada en el prompt** del modelo LLM. El LLM operó a ciegas sin recibir la recomendación estratégica de la máquina de estados.

---

## 2. BASELINE VERIFICADO

- **Suite determinista:** 139/139 PASS (`python -m unittest discover -v`).
- **Gates A-E, F-03, F-04, Fase 9, Fase 10:** Totalmente funcionales e intactos.
- **Regla de Invariabilidad:** Cero modificaciones de código o pruebas durante esta fase de auditoría.

---

## 3. REPRODUCCIÓN FORENSE (TRAZA DE `TASK-2218`)

El escenario auditado corresponde a la ejecución no asistida de la misión abierta de ingeniería:

```text
PROMPT: "Analiza el estado actual de Avatar como sistema de ingeniería autónoma. Investiga su arquitectura..."
```

### Traza de Eventos Extraída:
- **Paso 1:** Invocación nativa `COMMAND: pytest --maxfail=1 --disable-warnings`.
  - Salida: `ExitCode 1`. Error: `RuntimeError: The starlette.testclient module requires the httpx2 package to be installed.`.
- **Paso 2:** El LLM responde con texto plano en español ("He analizado..."). `SemanticMissionEngine` detecta evidencia insuficiente e inyecta `continuation_prompt`.
- **Pasos 3 al 10:** El LLM genera texto en cada iteración. `StructuredActionRecoveryLayer` evalúa el texto y retorna `None` (no hay JSON de herramienta). `orchestrator.py` inyecta el `continuation_prompt` estático con el error truncado.
- **Pasos 11 al 15:** Al acumular mensajes de continuación repetidos en `contents`, se realizan 5 llamadas seguidas que agotan la cuota de peticiones gratuitas por minuto de Gemini API (`HTTP 429 RESOURCE_EXHAUSTED`).

---

## 4. ANÁLISIS PASO A PASO (TABLA DE PROGRESIÓN COGNITIVA)

| Paso | Estado | Entrada Recibida | Decisión / Intención | Acción Ejecutada | Resultado | Clasificación |
|---|---|---|---|---|---|---|
| **1** | `IDLE` $\rightarrow$ `EXECUTING` | Prompt Abierto | Ejecutar suite de pruebas | `COMMAND: pytest` | `ExitCode 1` (Error `httpx2`) | `RECOVERY` |
| **2** | `EVALUATING` | Error crudo de pytest | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `NO_PROGRESS` |
| **3** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **4** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **5** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **6** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **7** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **8** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **9** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **10** | `MUTATING_STRATEGY` | `continuation_prompt` (truncado) | Emitir texto explicativo | Texto plano | Bloqueado por `SemanticMissionEngine` | `REPETITION` |
| **11** | `STAGNATED` | `continuation_prompt` (truncado) | Re-intento por fallo 429 | Ninguna (API 429) | `HTTP 429` Quota Exceeded | `DEAD_END` |
| **12** | `STAGNATED` | `continuation_prompt` (truncado) | Re-intento por fallo 429 | Ninguna (API 429) | `HTTP 429` Quota Exceeded | `DEAD_END` |
| **13** | `STAGNATED` | `continuation_prompt` (truncado) | Re-intento por fallo 429 | Ninguna (API 429) | `HTTP 429` Quota Exceeded | `DEAD_END` |
| **14** | `STAGNATED` | `continuation_prompt` (truncado) | Re-intento por fallo 429 | Ninguna (API 429) | `HTTP 429` Quota Exceeded | `DEAD_END` |
| **15** | `STAGNATED` | `continuation_prompt` (truncado) | Re-intento por fallo 429 | Ninguna (API 429) | Exit por `max_steps=15` | `DEAD_END` |

---

## 5. RESPUESTAS A LAS CUATRO PREGUNTAS CRÍTICAS

### Pregunta Crítica 1: ¿Qué información exacta recibió el LLM después del fallo de `pytest`?
- **Recibió:** `functionResponse` con la salida cruda de `pytest`.
- **Falla de Truncamiento en el Aviso Cognitivo:** En `semantic_mission_engine.py` (línea 83), el mensaje de aviso inyectaba: `Last error: {last_err[:120]}`.
- Debido a este slice de 120 caracteres, la cadena enviada al LLM fue:  
  `Last error: [Resultado PowerShell (ExitCode: 1)]:\nstdout:\n============================= test session starts ========================`
- **Diagnóstico:** El mensaje de continuación eliminó por completo la línea donde `pytest` especificaba que faltaba el paquete `httpx2`. El LLM no pudo diagnosticar la causa porque la causa fue recortada.

### Pregunta Crítica 2: ¿`AdaptiveInvestigationEngine` produjo realmente una decisión/estrategia?
- **Respuesta:** **SÍ la produjo en memoria, pero NO la comunicó al orquestador.**
- En `orchestrator.py` (línea 310), se ejecutó `inv_step_res = investigation_engine.evaluate_task_step(...)`. El motor calculó `InvestigationState.MUTATING_STRATEGY` y sugirió `RETRY_MODIFIED`.
- **Desconexión:** `orchestrator.py` guardó `inv_step_res` en la lista `executed_tools_summary`, pero **nunca leyó `inv_step_res` para construir el prompt ni forzar la acción**. La decisión del motor quedó aislada y no tuvo ningún efecto en la siguiente iteración.

### Pregunta Crítica 3: ¿Fue utilizado `Planner` después del fallo?
- **Respuesta:** **NO.** `Planner` solo se invoca en el Paso 0 si la entrada del usuario contiene una especificación de tareas explícita. Durante el bucle de misiones abiertas, `Replanner` fue llamado dentro de `RecoveryEngine`, pero el plan resultante no fue transmitido al bucle principal.

### Pregunta Crítica 4: ¿Dónde se rompió la oportunidad de decisión del LLM?
- El fallo corresponde a **Opción B y D**:
  - **Opción B (Contexto Defectuoso):** El sistema envió el error recortado a 120 caracteres, ocultando la causa del error.
  - **Opción D (Estrategia Descartada por el Sistema):** El `AdaptiveInvestigationEngine` generó la recomendación de mutación, pero `orchestrator.py` la descartó y no se la presentó al LLM.

---

## 6. ANÁLISIS DE HTTP 429 VS FALLO COGNITIVO

Se establece una distinción inequívoca entre los dos problemas observados:

```
[FALLO COGNITIVO (Pasos 2-10)]
  └─► El modelo emite texto plano sin llamada a función por falta de causa de error y falta de directiva estratégica.
  └─► Causa: Truncamiento de 120 chars en SemanticMissionEngine + inv_step_res no inyectado en Orchestrator.

[LIMITACIÓN DE INFRAESTRUCTURA (Pasos 11-15)]
  └─► La acumulación de 10 turnos fallidos continuos provocó 10 peticiones seguidas, agotando la cuota de la API (HTTP 429).
  └─► Causa: Consecuencia directa de la estancamiento cognitivo previo (Pasos 2-10).
```

---

## 7. ANÁLISIS DE MENSAJE DE CONTINUACIÓN (`SemanticMissionEngine`)

En `semantic_mission_engine.py`:
```python
# CÓDIGO ACTUAL (DEFECTUOSO):
last_err = failed_steps[-1]["output"] if failed_steps else "Tool execution failed."
return {
    "sufficient": False,
    "reason": f"No successful tool executions completed yet. Last error: {last_err[:120]}",
    "status": GoalState.EXECUTING
}
```

### Problema Identificado:
El slice `last_err[:120]` corta el encabezado de PowerShell e ignora los bloques `stderr` o las líneas de excepción de Python (`RuntimeError: ...`). El LLM recibe una notificación de error vacía de contenido útil.

---

## 8. DIAGNÓSTICO FINAL DE CAUSA RAÍZ (VEREDICTO)

```text
F-05 CONFIRMED — COGNITIVE PROGRESSION FAILURE
```

### Causa Raíz Triple de F-05:
1. **Truncamiento de Log de Error:** El límite de 120 caracteres en `SemanticMissionEngine` destruye la trazabilidad del error.
2. **Aislamiento de `AdaptiveInvestigationEngine`:** `orchestrator.py` no utiliza los resultados de `evaluate_task_step()` para alimentar el prompt de la siguiente iteración.
3. **Ausencia de Detector de Estancamiento (`StagnationDetector`):** El orquestador no detecta cuando el agente lleva N pasos consecutivos emitiendo texto sin ejecutar herramientas, permitiendo que la sesión se agote hasta el límite de pasos o cuota HTTP 429.

---

## 9. RECOMENDACIÓN DE DIRECCIÓN ARQUITECTÓNICA PARA LA FUTURA FASE 12

Cuando se autorice la implementación física en una fase futura:
1. **Filtro Inteligente de Errores (`ErrorExtractor`):** Extraer la excepción real de Python (últimas 10 líneas de `stderr`/`stdout`) en lugar de los primeros 120 caracteres.
2. **Conexión Obligatoria de `AdaptiveInvestigationEngine`:** Inyectar la estrategia calculada por el motor (`MUTATING_STRATEGY`, sugerencia de `unittest` o `READ_FILE`) directamente en el `supreme_prompt` de la iteración subsiguiente.
3. **Detector de Estancamiento (`StagnationDetector`):** Si se detectan 2 turnos seguidos de texto sin llamada a función, forzar la mutación de estrategia o concluir con `INSUFFICIENT_EVIDENCE`.

---

## 10. LISTA EXPLICITA DE LO QUE NO SE HA IMPLEMENTADO EN ESTA FASE

Dando estricto cumplimiento a las directrices de gobernanza:
- ❌ No se ha modificado `core/orchestrator.py` ni `core/cognitive/semantic_mission_engine.py`.
- ❌ No se ha modificado la suite de pruebas en `tests/`.
- ❌ No se ha alterado el límite de 120 caracteres.
- ❌ No se han modificado los prompts ni las cuotas de la API.
- ❌ No se ha declarado verificado el Gate F ni el Gate G.

---

## GOVERNANCE STATEMENT & DICTAMEN FINAL

La auditoría forense de progresión cognitiva ha sido completada en su totalidad en `AVATAR_PHASE_11_COGNITIVE_PROGRESSION_AUDIT.md`.

**Salida Oficial de Gobernanza:**

```text
PHASE_11_AUDIT = COMPLETE

F-05 = CONFIRMED (COGNITIVE PROGRESSION FAILURE)

GATE_F = NOT_VERIFIED
GATE_G = NOT_VERIFIED

READY_FOR_AVATAR_TAKEOVER = NOT_VERIFIED
```
