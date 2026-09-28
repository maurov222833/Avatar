# AVATAR GATE F — RECIPE REMOVAL REPORT
## REPARACIÓN QUIRÚRGICA DE AUTONOMÍA COGNITIVA Y ELIMINACIÓN DE RECETAS HARDCODEADAS

**PROYECTO:** `b:\PROYECTOS ANTIGRAVITY\Avatar`  
**FECHA:** 2026-09-26  
**ROL:** INGENIERO DE REPARACIÓN  

---

### 1. Problem Confirmed

La auditoría forense independiente de Gate F demostró que la toma de decisiones en misiones de ingeniería abiertas estaba contaminada por **recetas hardcodeadas** e **instrucciones de continuación que prescribían herramientas, comandos y archivos concretos**. 

Al recibir avisos de continuación o señales de estancamiento, el sistema inyectaba prompts que ordenaban expresamente al modelo ejecutar `COMMAND: python -m unittest discover -v` o leer `READ_FILE: core/orchestrator.py`. Esto impedía demostrar si la siguiente acción de Avatar procedía de una decisión cognitiva basada en la evidencia recopilada o de una orden prefijada por el código fuente.

---

### 2. Exact Hardcoded Recipes Found

1. **`core/orchestrator.py` (Líneas 398–405):**
   ```python
   # RECETA HARDCODEADA ENCONTRADA:
   "- Si el comando anterior falló o produjo error de entorno (ej: pytest), evalúa la causa del fallo y muta la estrategia utilizando el ejecutor nativo: COMMAND: python -m unittest discover -v"
   "- O inspecciona los archivos de código fuente principales usando READ_FILE (ej: READ_FILE: core/orchestrator.py o READ_FILE: core/cognitive/planner.py)."
   ```
2. **`core/cognitive/stagnation_detector.py` (Líneas 114–116):**
   ```python
   # RECETA HARDCODEADA ENCONTRADA:
   "- Muta inmediatamente la estrategia: si un ejecutor de pruebas falló por dependencias de entorno (ej: pytest), ejecuta la alternativa nativa 'COMMAND: python -m unittest discover -v' o inspecciona los archivos usando 'READ_FILE'."
   ```
3. **`core/cognitive/semantic_mission_engine.py` (Línea 158):**
   ```python
   # REGLA CON CADENA DE TEXTO HARDCODEADA EN REASON:
   "reason": "Package installation alone is not code investigation. Run test suite (python -m unittest discover -v) or inspect code files."
   ```
4. **`core/cognitive/adaptive_investigation_engine.py` (Línea 206):**
   ```python
   # INSTRUCCIÓN DE MUTACIÓN HARDCODEADA:
   "- Si falló un ejecutor de pruebas (ej: pytest por falta de dependencias), prueba la alternativa 'python -m unittest discover -v' o inspecciona código con READ_FILE."
   ```

---

### 3. Files Modified

1. `core/orchestrator.py`
2. `core/cognitive/stagnation_detector.py`
3. `core/cognitive/semantic_mission_engine.py`
4. `core/cognitive/adaptive_investigation_engine.py`
5. `tests/test_f05_adaptive_cognitive_progression.py`
6. `tests/test_f08_recipe_removal.py` *(Nuevo conjunto de pruebas unitarias)*

---

### 4. Changes Made

Se removieron quirúrgicamente todas las prescripciones de herramientas, comandos y rutas concretas en los avisos de continuación y directivas de estancamiento. El sistema ahora emite **únicamente contexto semántico y señales cognitivas**, dejando la selección operacional de la herramienta 100% a la decisión del modelo.

---

### 5. SemanticMissionEngine Before/After

#### Before:
- **Reason:** `"Package installation alone is not code investigation. Run test suite (python -m unittest discover -v) or inspect code files."`

#### After:
- **Reason:** `"Package installation alone is not code investigation. Technical evidence requires evaluating implementation details or execution behavior."`

---

### 6. StagnationDetector Before/After

#### Before:
```text
[DIRECTIVA DE RECUPERACIÓN DE ESTANCAMIENTO COGNITIVO]:
- Muta inmediatamente la estrategia: si un ejecutor de pruebas falló por dependencias de entorno (ej: pytest), ejecuta la alternativa nativa 'COMMAND: python -m unittest discover -v' o inspecciona los archivos usando 'READ_FILE'.
```

#### After:
```text
[DIRECTIVA DE SEÑAL COGNITIVA DE ESTANCAMIENTO]:
SITUACIÓN COGNITIVA ACTUAL:
- No se ha producido nueva evidencia física significativa o se detectó repetición de respuestas/acciones.
- Reevalúa la estrategia actual y selecciona autónomamente un nuevo enfoque o herramienta entre tus herramientas disponibles para recopilar la evidencia faltante.
```

---

### 7. AdaptiveInvestigationEngine Analysis

En `AdaptiveInvestigationEngine.evaluate_task_step`, la instrucción cognitiva inyectada tras un fallo de herramienta fue despojada de cualquier prescripción de `python -m unittest discover -v` o `READ_FILE`. La instrucción expresa ahora:
```text
- Reevalúa la causa del fallo y selecciona una estrategia o herramienta alternativa entre tus herramientas disponibles.
```

---

### 8. EvidenceGap Analysis

Se verificó que `EvidenceGap` y su método `format_cognitive_instruction()` permanecen 100% semánticos. El atributo `next_information_target` expresa únicamente la meta semántica (ej: `"Obtener evidencia sobre la persistencia y recuperación de contexto de memoria"`) sin prescribir rutas o herramientas concretas.

---

### 9. Decision Boundary Before/After

| Componente | Comportamiento Anterior (Roto por Receta) | Comportamiento Corregido (Semántico) |
| :--- | :--- | :--- |
| **`orchestrator.py`** | Inyectaba prompt ordenando `COMMAND: python -m unittest` o `READ_FILE: core/orchestrator.py` | Inyecta aviso semántico de misión abierta y gap de evidencia sin nombres de herramientas |
| **`stagnation_detector.py`** | Exigía ejecutar `unittest` o `READ_FILE` para salir de estancamiento | Emite señal cognitiva de estancamiento y exige reevaluación autónoma de la estrategia |
| **`semantic_mission_engine.py`**| Transmitía razones con comandos hardcodeados | Transmite razones semánticas sobre evidencia técnica requerida |
| **`adaptive_investigation_engine.py`**| Recomendaba sustituir `pytest` por `unittest` o `READ_FILE` | Recomienda mutación de estrategia genérica sin prescribir herramientas fijas |

---

### 10. Tests Added

Se creó la suite `tests/test_f08_recipe_removal.py` que añade 11 pruebas unitarias y de análisis estático:
- **Test A:** Prompt de continuación sin nombres explícitos de herramientas.
- **Test B:** Prompt de continuación sin comandos específicos (`python -m unittest`, `pytest`).
- **Test C:** Prompt de continuación sin nombres de archivos específicos.
- **Test D:** `EvidenceGap` semántico.
- **Test E:** `StagnationDetector` sin prescripción de herramientas.
- **Test F:** `AdaptiveInvestigationEngine` sin prescripción de recetas.
- **Test G:** Transmisión normal de `MODEL_DECISION` hacia `ToolRegistry`.
- **Test H:** Funcionamiento correcto de `RecoveryEngine`.
- **Test I:** Preservación de seguridad y validación de workspace en `ShellTool`.
- **Test J:** Análisis estático de código fuente verificando ausencia de recetas hardcodeadas en componentes cognitivos.
- **Test K:** Generación de metas semánticas distintas en `EvidenceGap` para objetivos de dominios diferentes.

---

### 11. Regression Results

- **Pruebas de Regresión:** **194/194 PASS** (0 fallos, 0 errores en 1.098s).
- **Verificación Baseline:** `python -c "print('AVATAR_GATE_F_REPAIR_BASELINE_OK')"` -> **`AVATAR_GATE_F_REPAIR_BASELINE_OK`** (ExitCode = 0).

---

### 12. Static Recipe Search Results

Una búsqueda estática completa en `core/orchestrator.py`, `core/cognitive/stagnation_detector.py`, `core/cognitive/semantic_mission_engine.py` y `core/cognitive/adaptive_investigation_engine.py` confirmó que:
- `python -m unittest discover -v` **0 ocurrencias en prompts cognitivos generales**.
- `READ_FILE: core/orchestrator.py` **0 ocurrencias**.
- `READ_FILE: core/cognitive/planner.py` **0 ocurrencias**.

---

### 13. Security / Tool Validation Preservation

Todas las restricciones de seguridad (`workspace_path` en `ShellTool` y `FileTool`), validaciones de esquemas en `ToolRegistry` y límites de ejecución se conservan 100% intactos.

---

### 14. Remaining Risks

- **Dispersión del Modelo:** Al no recibir la sugerencia explícita de ejecutar `python -m unittest discover -v` o leer `core/orchestrator.py`, el modelo LLM puede requerir más iteraciones para deducir qué archivos leer o qué pruebas ejecutar, o bien agotar el presupuesto de pasos (`max_steps=15`) si responde repetidamente con texto. Esto se evaluará en la auditoría independiente de Gate F.

---

### 15. What Was NOT Changed

- **`max_steps`:** Se conservó exactamente en 15 para misiones abiertas.
- **Mecanismos de Seguridad:** `ShellTool` y `FileTool` permanecen sin cambios.
- **Arquitectura:** No se crearon nuevos motores cognitivos ni capas de abstracción redundantes.
- **`EvidenceGap` y `StagnationDetector`:** La estructura de clases y su lógica de estados se mantuvieron intactas.

---

### 16. Governance Status

```text
============================================================
ESTADO OFICIAL DE GOBERNANZA - POST REPARACIÓN FASE 15
============================================================

FASE DE REPARACIÓN DE RECETAS = COMPLETADA

Gate A = VERIFIED
Gate B = VERIFIED
Gate C = VERIFIED
Gate D = VERIFIED
Gate E = VERIFIED

F-03 = VERIFIED
F-04 = VERIFIED
F-05 = VERIFIED
F-06 = VERIFIED
F-07 = VERIFIED

Gate F = NOT_VERIFIED
Gate G = NOT_VERIFIED

READY_FOR_AVATAR_TAKEOVER = NOT_VERIFIED
============================================================
```
