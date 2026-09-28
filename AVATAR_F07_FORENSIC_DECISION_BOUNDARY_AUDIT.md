# AVATAR AI — F-07: FORENSIC DECISION BOUNDARY AUDIT
# ANÁLISIS FORENSE DE FRONTERA DE DECISIÓN POST-LIST_DIR

PROYECTO: `b:\PROYECTOS ANTIGRAVITY\Avatar`  
FECHA: 2026-09-26  
ESTADO DE AUDITORÍA: **COMPLETADA (DIAGNÓSTICO EXCLUSIVO - SIN IMPLEMENTACIÓN)**

---

## 1. REPRODUCCIÓN CONTROLADA Y HALLAZGO CLAVE

Se ejecutó una prueba de reproducción controlada en un único flujo de 2 ciclos cognitivos para la misión abierta:
> *"Analiza el estado actual de Avatar AI, identifica una debilidad real relacionada con su capacidad de ingeniería autónoma y determina cómo debería resolverse."*

### Hallazgo Forense Crítico:
En el **Ciclo 2**, tras la ejecución exitosa de `LIST_DIR`, el orquestador (`orchestrator.py`) intentó enviar al provider de Gemini el historial conversacional `contents` incluyendo la respuesta de la función formateada con el rol `"function"`:

```json
{
  "role": "function",
  "parts": [{
    "functionResponse": {
      "name": "LIST_DIR",
      "response": {"output": "..."}
    }
  }]
}
```

La API REST de Google Gemini devolvió un error incontrovertible de esquema **HTTP 400 Bad Request**:

```json
{
  "error": {
    "code": 400,
    "message": "Role 'function' is not supported. Please use a valid role: SYSTEM, SYSTEM_1, USER, ASSISTANT, DEVELOPER, CONTEXT, USER_CONTEXT, MODEL, USER.",
    "status": "INVALID_ARGUMENT"
  }
}
```

Al recibir este error HTTP 400 en la llamada multi-turno de `generate_response_with_tools`, el cliente de LLM (`llm_provider.py`) activó de forma silenciosa el mecanismo de **fallback mono-turno** (`generate_response`), el cual envía **únicamente el texto del último mensaje como una nueva consulta individual, destruyendo el historial conversacional, omitiendo las declaraciones de herramientas (`tools`) y omitiendo la directiva de `EvidenceGap`**.

En consecuencia, el modelo recibió una consulta mono-turno descontextualizada y sin herramientas declaradas, respondiendo en texto plano con un bloque JSON `{"action": "LIST_DIR", "args": {"dir_path": "."}}`, el cual fue posteriormente interceptado y recuperado por `StructuredActionRecoveryLayer` como una nueva ejecución de `LIST_DIR`.

---

## 2. CAPTURA EXACTA DEL SEGUNDO CICLO

A. **System Prompt:**  
   Prompt supremo de Avatar AI incluyendo las directivas de misión abierta de ingeniería autónoma (Goal ID: `goal-xxx`).

B. **User Prompt Original:**  
   *"Analiza el estado actual de Avatar AI, identifica una debilidad real relacionada con su capacidad de ingeniería autónoma y determina cómo debería resolverse."*

C. **Function Declaration / Schema:**  
   Esquema JSON `AVATAR_TOOLS_SCHEMA` declarando `COMMAND`, `READ_FILE`, `WRITE_FILE`, `LIST_DIR`, `WEB_SEARCH`, `FETCH_URL`, `PLAY_AUDIO`, `SEND_WHATSAPP`.

D. **Model Message (Paso 1):**  
   Part de rol `"model"` con `functionCall` nativo: `LIST_DIR` en `b:\PROYECTOS ANTIGRAVITY\Avatar`.

E. **Function Response (Paso 1):**  
   Part de rol `"function"` conteniendo `functionResponse` con la salida real del directorio (45 elementos).

F. **Cognitive Instruction (`EvidenceGap`):**  
   Instrucción del motor de brecha de evidencia adjuntando `CURRENT_EVIDENCE`, `REQUIRED_EVIDENCE`, `EVIDENCE_GAP` y `NEXT_INFORMATION_TARGET`.

G. **Orden Exacto de Mensajes Enviados al Provider en Ciclo 2:**
   - Mensaje 0 `[rol: 'user']`: Prompt original.
   - Mensaje 1 `[rol: 'model']`: `functionCall` (`LIST_DIR`).
   - Mensaje 2 `[rol: 'function']`: `functionResponse` (`LIST_DIR`).
   - Mensaje 3 `[rol: 'user']`: `cognitive_instruction` (`EvidenceGap`).

H. **Parámetros de la Llamada HTTP al Provider:**
   - `model`: `gemini-3.5-flash-lite` (o fallbacks `gemini-3.5-flash` / `gemini-3.8-flash`).
   - `temperature`: `0.1`
   - `tools`: `AVATAR_TOOLS_SCHEMA`
   - `url`: `https://generativelanguage.googleapis.com/v1beta/models/...:generateContent`

I. **Raw Response del Provider en Ciclo 2 (Llamada Multi-Turno):**
   ```json
   {
     "error": {
       "code": 400,
       "message": "Role 'function' is not supported. Please use a valid role: SYSTEM, SYSTEM_1, USER, ASSISTANT, DEVELOPER, CONTEXT, USER_CONTEXT, MODEL, USER.",
       "status": "INVALID_ARGUMENT"
     }
   }
   ```

J. **Raw Response del Provider en Fallback (Llamada Mono-Turno):**
   ```text
   ```json
   {
     "action": "LIST_DIR",
     "args": {
       "dir_path": "."
     }
   }
   ```
   ```

K. **Parsed Response / Tool Call:**  
   `StructuredActionRecoveryLayer` recuperó `LIST_DIR` del texto plano devuelto por el fallback.

---

## 3. PREGUNTA PRINCIPAL

**¿El LLM recibe simultáneamente y de forma inequívoca GOAL, CURRENT_EVIDENCE, EVIDENCE_GAP, NEXT_INFORMATION_TARGET y AVAILABLE_TOOLS en la llamada multi-turno?**

**NO.**  
Aunque el orquestador prepara el mensaje conceptualmente en memoria, la llamada a la API REST del provider es **RECHAZADA CON HTTP 400 BAD REQUEST** por la invalidez del rol `"function"` en la API de Google Gemini.

Por este motivo, la petición multi-turno falla antes de ser procesada por los pesos del modelo, y el sistema degrada al fallback mono-turno despojado de historial, de brecha de evidencia y de esquema de herramientas.

---

## 4. POSICIÓN DEL EVIDENCE GAP

En la estructura de la lista `contents`, la `cognitive_instruction` se inserta como el Mensaje 3 (`role: 'user'`):

```text
Mensaje 2 [rol: 'function']: functionResponse (LIST_DIR)
   ↓
cognitive_instruction (Mensaje 3 [rol: 'user']): [MOTOR COGNITIVO - EVIDENCE GAP]
```

Debido a que el Mensaje 2 utiliza el rol desautorizado `"function"`, la API de Gemini rechaza el arreglo completo `contents`, impidiendo que el Mensaje 3 llegue a ser evaluado por el LLM.

---

## 5. HERRAMIENTAS DISPONIBLES EN LA LLAMADA AL PROVIDER

- En la llamada multi-turno del Ciclo 2, el parámetro `tools` incluye la totalidad de las 8 herramientas declaradas (`READ_FILE`, `COMMAND`, `WRITE_FILE`, etc.).
- Sin embargo, al fallar la llamada multi-turno por HTTP 400, el método `generate_response_with_tools` ejecuta el fallback a `generate_response()`, el cual realiza una petición HTTP **SIN el parámetro `tools`**.
- Esto obliga al modelo a responder en texto libre, produciendo bloques de código JSON textuales que son posteriormente interceptados por la capa de recuperación.

---

## 6. COMPARACIÓN DE CASOS

| Dimensión | CASO A (Ciclo 2 - Multi-turno con Evidencia) | CASO B (Ciclo 1 - Primer Turno Inicial) |
|---|---|---|
| **Estructura de Mensajes** | Contiene `user`, `model`, `function`, `user` | Contiene únicamente 1 mensaje (`user`) |
| **HTTP Status Code** | **HTTP 400 Bad Request** (por `role: "function"`) | **HTTP 200 OK** |
| **Procesamiento de Tools** | Falla -> cae a fallback mono-turno sin `tools` | Éxito -> responde con `functionCall` nativo |
| **Presencia del Historial** | Destruido por la caída al fallback | No requerido (primer paso) |
| **Respuesta del Modelo** | Texto JSON recuperado por `StructuredActionRecoveryLayer` | Function Call nativo directo |

---

## 7. CLASIFICACIÓN DE LA CAUSA

1. **C. ORCHESTRATOR MESSAGE-ORDER / SCHEMA FAILURE (CAUSA PRIMARIA):**  
   Uso del rol `"function"` en la construcción de la lista `contents` enviada a la API de Gemini REST, lo cual viola el esquema aceptado por el provider y causa rechazo HTTP 400.

2. **B. TOOL AVAILABILITY / CONFIGURATION FAILURE (CAUSA SECUNDARIA):**  
   El fallback de error en `llm_provider.py` remueve la configuración de `tools` al degradar a `generate_response()`, despojando al modelo de la capacidad de emitir Function Calls nativos.

3. **F. PARSING / ACTION PIPELINE FAILURE (CAUSA TERCIARIA):**  
   `StructuredActionRecoveryLayer` enmascara el fallo de degradación al recuperar texto plano JSON como si fuera una decisión deliberada del modelo.

---

## 8. PRUEBA DE CONTRAFACTUAL

Se ejecutó la comprobación determinista en el motor de ejecuciones:

```python
sample_read = orc._dispatch_native_tool("READ_FILE", {"file_path": "core/orchestrator.py"})
```

- **Resultado:** `[OK] READ_FILE funcional. Salida leída: 33,296 caracteres.`
- **Conclusión Contrafactual:** **SÍ**. Si el LLM hubiese seleccionado `READ_FILE`, el pipeline de herramientas de Avatar lo habría ejecutado de forma impecable sin ningún tipo de error ni bloqueo en la capa de ejecución.

---

## 9. REGRESIÓN DE SUITE DE PRUEBAS

Se ejecutó la verificación de regresión previa sin haber realizado ninguna modificación en el código:

```bash
C:\Users\Mauro\AppData\Local\Programs\Python\Python312\python.exe -m unittest discover -v
```

```text
----------------------------------------------------------------------
Ran 172 tests in 0.966s

OK
```
**172/172 PASS.**

---

## 10. RESULTADO Y ESTRUCTURA OBLIGATORIA DE DIAGNÓSTICO

PRIMARY ROOT CAUSE:
La causa primaria es un fallo de esquema en el formato de mensajes del orquestador (`ORCHESTRATOR SCHEMA FAILURE`). En `orchestrator.py`, la respuesta de ejecución de herramientas se añade al historial `contents` asignando el rol `"function"` (`{"role": "function", ...}`). La API REST v1beta de Google Gemini no soporta el rol `"function"` en el arreglo `contents` (solicita usar `USER` o `MODEL` con `functionResponse` o formato compatible), provocando un error **HTTP 400 Bad Request (INVALID_ARGUMENT)** en el segundo turno conversacional. Este error rompe el pipeline multi-turno y fuerza una degradación silenciosa a una consulta mono-turno sin historial, sin EvidenceGap y sin herramientas declaradas.

SECONDARY CAUSES:
1. Fallo de configuración en el mecanismo de fallback de `llm_provider.py`, el cual ante un error HTTP deshecha las declaraciones de herramientas (`tools`) y el historial conversacional `contents`, reduciendo la consulta a un prompt de texto plano.
2. Enmascaramiento de fallos por parte de `StructuredActionRecoveryLayer`, la cual interpreta el texto plano de emergencia devuelto por el fallback y lo convierte nuevamente en un comando ejecutable (`LIST_DIR`), creando la ilusión de que el modelo decidió libremente repetir la primera herramienta.

EVIDENCE:
- Respuesta literal de la API de Gemini durante el Ciclo 2: `HTTP 400 Bad Request`: `"Role 'function' is not supported. Please use a valid role: SYSTEM, SYSTEM_1, USER, ASSISTANT, DEVELOPER, CONTEXT, USER_CONTEXT, MODEL, USER."`.
- Traza de red confirmando que el Ciclo 1 (mono-turno) devuelve HTTP 200 OK con `functionCall`, mientras que el Ciclo 2 (multi-turno con `role: "function"`) devuelve HTTP 400 Bad Request.
- Prueba contrafactual exitosa demostrando que `READ_FILE` y la infraestructura de herramientas ejecutan sin errores (33 KB leídos sin fallos).

WHAT IS ALREADY WORKING:
- El motor de brecha de evidencia (`AdaptiveInvestigationEngine` y `EvidenceGap`) calcula y redacta correctamente `CURRENT_EVIDENCE`, `REQUIRED_EVIDENCE`, `EVIDENCE_GAP` y `NEXT_INFORMATION_TARGET`.
- La capa de verificación de hechos físicos (`PhysicalFactVerifier`) y la prueba contrafactual de herramientas (`READ_FILE`, `COMMAND`).
- El ciclo inicial de clasificación de intenciones y generación de `Goal` cognitivo.
- La suite de regresión con 172/172 tests pasando.

WHAT IS NOT WORKING:
- La serialización del historial de llamadas a funciones en `orchestrator.py` para compatibilidad nativa con la API de Google Gemini (incompatibilidad por `role: "function"`).
- La gestión de errores HTTP 400 en `llm_provider.py`, que cae a un fallback sin tools en lugar de corregir la estructura del payload.
- La progresión autónoma multi-turno en misiones abiertas debido al colapso del contexto conversacional en el paso 2.

MINIMUM REQUIRED INTERVENTION:
1. Corregir en `orchestrator.py` el formato y rol asignado a las respuestas de herramientas en el arreglo `contents` para cumplir con las especificaciones exactas de la API de Google Gemini v1beta (usando `role: "user"` con las partes de `functionResponse` o la estructura oficial indicada por el provider).
2. Asegurar en `llm_provider.py` que ante reintentos o fallbacks se preserve el esquema de herramientas (`tools`) y no se destruya el historial conversacional `contents`.

CONFIDENCE:
HIGH
