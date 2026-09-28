# 11 — PROVIDER AUDIT
## AVATAR AI — INDEPENDENT ARCHITECTURE REVIEW 001

**Fecha de Auditoría:** 27 de Septiembre de 2026  
**Auditor:** Independent Architecture Auditor (Antigravity Agent)  
**Target Module:** `core/llm_provider.py` (575 líneas)  
**Estado:** COMPLETED  

---

### 1. Resumen de Adaptadores y Gestión de Proveedores

`LLMProvider` (`core/llm_provider.py`) gestiona la conexión multimodelo de Avatar AI con proveedores de IA. Soporta:
1. `GeminiAdapter` (`L62`): Integración oficial con la API Google GenAI (`gemini-2.5-flash`, `gemini-2.5-pro`).
2. `OpenAICompatibleAdapter` (`L218`): Integración con OpenAI, DeepSeek, Groq, Together AI, vLLM.
3. `OllamaAdapter` (`L405`): Adaptador para modelos locales (Llama 3, Qwen 2.5, DeepSeek-Coder).
4. `ProviderManager` (`L459`): Gestor de enrutamiento y health-checks de adaptadores.

---

### 2. Negociación de Capacidades y Proveedor Activo

- **Cargar Configuración:** `config.json` especifica el proveedor activo (`active_provider: "gemini"`).
- **Health Checks:** `check_all_health()` verifica la disponibilidad de API Keys y endpoints HTTP.
- **Enrutamiento:** Si el proveedor activo carece de `native_tool_calling`, el motor de orquestación conmuta al modo de estructuración de texto plano (`StructuredActionRecoveryLayer`).

---

### 3. Evaluación de Fallback y Degradación Semántica

#### Riesgo Auditado:
*¿Puede un fallo de proveedor ser convertido en un "éxito aparente"?*

#### Hallazgos en el Código:
1. **Manejo de Excepciones en `GeminiAdapter.generate_response_with_tools()` (`L126-215`):**
   Si ocurre un error HTTP 400 (ej. `API_KEY_INVALID`) o HTTP 429 / 500, el adaptador lanza o retorna un bloque de error estructurado con la clave `"error"`.
2. **Propagación al Orquestador (`orchestrator.py:315`):**
   El orquestador intercepta el diccionario con clave `"error"`. Se imprime una advertencia y se registra la falla en la historia.
3. **Mecanismo Anti-Degradación:**
   El orquestador **NO marca la tarea como `COMPLETED`** cuando el proveedor falla. En su lugar, el bucle ReAct incrementa el contador de reintentos o invoca la conmutación a un proveedor secundario si está configurado.

---

### 4. Clasificación Epistemológica del Proveedor

> **ESTADO OBJETIVO:**  
> **`VERIFIED`**  
>  
> **JUSTIFICACIÓN:**  
> La API Key de Gemini está configurada activamente en `.env` / `config.json` y el adaptador responde exitosamente a consultas reales HTTP 200 OK. La suite `test_provider_manager.py` aprueba 100% de los tests.
