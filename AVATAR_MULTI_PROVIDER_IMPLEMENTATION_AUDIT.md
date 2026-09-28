# AVATAR AI — AUDITORÍA PREVIA A LA IMPLEMENTACIÓN MULTI-PROVIDER

**FECHA:** 27 DE SEPTIEMBRE DE 2026  
**PROYECTO:** B:\PROYECTOS ANTIGRAVITY\Avatar  
**ROL:** INGENIERO DE INFRAESTRUCTURA LLM Y AUDITOR FORENSE  

---

## 1. INTRODUCCIÓN Y ARQUITECTURA OBJETIVO

El propósito de esta misión es consolidar una infraestructura de proveedores de Inteligencia Artificial agnóstica, robusta y profesional en **Avatar AI**.

La arquitectura objetivo garantiza que el **Cerebro Cognitivo de Avatar** (`Planner`, `Replanner`, `RecoveryEngine`, `Verifier`, `EvidenceGap`, `SemanticMissionEngine`) permanezca 100% independiente del proveedor o modelo seleccionado:

```text
USER / INTERFACE (GUI / CLI / Telegram)
          ↓
  AVATAR COGNITIVE ENGINE (Sin acoplamiento a LLM específico)
          ↓
  PROVIDER MANAGER / ROUTER (Manager central con adaptadores modularizados)
          ↓
┌──────────────────────────────────────────────────────────┐
│ GEMINI     │ OPENAI   │ GROQ      │ OLLAMA    │ LM STUDIO │
└──────────────────────────────────────────────────────────┘
          ↓
  MODELO SELECCIONADO Y VALIDADO (Capabilities & Health Checked)
          ↓
  FUNCTION CALLING / TEXT / MULTI-TURN
          ↓
  MISMO PIPELINE COGNITIVO & VERIFICADOR DE HECHOS FÍSICOS
```

---

## 2. AUDITORÍA FÍSICA DE PROVEEDORES EXISTENTES

### 2.1 Matriz Detallada por Proveedor

| Proveedor | Archivo de Adaptador | Endpoint API | Autenticación | Modelos Soportados | Texto | Function Calling | Multi-Turn | Streaming | JSON Schema | Visión | Estado Actual | Problemas Identificados | Riesgo | Trabajo Requerido |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- | :---: | :--- |
| **Google Gemini** | `core/llm_provider.py` | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | Query Param `?key={GEMINI_API_KEY}` | `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.5-flash-lite` | SÍ | SÍ (Nativo) | SÍ | NO | SÍ | NO | **VERIFIED** | Bloqueo `HTTP 429` en Tier Gratuito por ráfagas sin backoff exponencial. | Medio | Implementar Backoff Exponencial y Rate Limiting inteligente; modularizar en `GeminiAdapter`. |
| **OpenAI** | `core/llm_provider.py` | `https://api.openai.com/v1/chat/completions` | Header `Authorization: Bearer {OPENAI_API_KEY}` | `gpt-4o-mini`, `gpt-4o` | SÍ | SÍ (Traducción `tools`) | SÍ | NO | SÍ | SÍ | **PARTIAL** | Falta clave activa en `.env` para pruebas reales end-to-end. | Bajo | Crear `OpenAIAdapter` desacoplado con validación de credenciales. |
| **Groq Cloud** | `core/llm_provider.py` | `https://api.groq.com/openai/v1/chat/completions` | Header `Authorization: Bearer {GROQ_API_KEY}` | `qwen-2.5-coder-32b`, `llama-3.3-70b-versatile` | SÍ | SÍ (Compatible OpenAI) | SÍ | NO | SÍ | NO | **PARTIAL** | Requiere clave `GROQ_API_KEY` configurada en `.env`. | Bajo | Crear `GroqAdapter` aprovechando su tasa ultra rápida (14,400 req/día gratis). |
| **GitHub Models** | `core/llm_provider.py` | `https://models.inference.ai.azure.com/chat/completions` | Header `Authorization: Bearer {GITHUB_TOKEN}` | `gpt-4o`, `Phi-3.5-mini-instruct` | SÍ | SÍ (Compatible OpenAI) | SÍ | NO | SÍ | SÍ | **PARTIAL** | Servicio sujeto a límites de cuota de Azure Inference / GitHub API. | Medio | Crear `GitHubModelsAdapter` con detección de disponibilidad. |
| **Ollama Local** | `core/llm_provider.py` | `http://localhost:11434/api/chat` & `/v1/chat/completions` | Ninguna (Localhost) | `qwen2.5-coder:1.5b`, `qwen2.5-coder:7b` | SÍ | NO (Solo texto plano por defecto) | SÍ | NO | SÍ | NO | **PARTIAL** | Modelos pequeños locales no emiten estructuras `function_call` nativas sin parser. | Medio | Crear `OllamaAdapter` integrado con `StructuredActionRecoveryLayer` para fallback de herramientas. |
| **LM Studio Local**| `core/llm_provider.py` | `http://localhost:1234/v1/chat/completions` | Ninguna (Localhost) | `local-model` | SÍ | SÍ (Segun GGUF cargado) | SÍ | NO | SÍ | NO | **UNAVAILABLE** | Servidor local inactivo si LM Studio no está ejecutándose en puerto 1234. | Bajo | Crear `LMStudioAdapter` con Verificación de Salud (Health Check) en inicio. |

---

## 3. HALLAZGOS Y OPORTUNIDADES DE MEJORA DE INFRAESTRUCTURA

1. **Gestión de Secretos (.env / config.json):**
   - Las API keys se buscan actualmente primero en `.env` y luego en `config.json`.
   - El endpoint `/api/config/update` de `server.py` permite guardar claves de Gemini, OpenAI, Groq, GitHub u Ollama URL, pero la interfaz gráfica (`gui/index.html`) carecía de campos para ingresar `GROQ_API_KEY` y `GITHUB_TOKEN`.

2. **Acoplamiento Directo o Fallbacks Involuntarios:**
   - Se verificó que `AvatarOrchestrator` utiliza `self.llm` de forma consistente.
   - En versiones preliminares existía la posibilidad de que si un proveedor fallaba por 429 o falta de clave, se generara un aviso plano sin opción de cambio rápido.

3. **Arquitectura del Router (`LLMProvider`):**
   - Actualmente `LLMProvider` concentra la lógica de Gemini, OpenAI, Groq, GitHub, Ollama y LM Studio en una sola clase monolítica en `core/llm_provider.py`.
   - **Oportunidad de Refactorización Limpia:** Crear un patrón de administración modular (`ProviderManager` / `BaseAdapter` / `ProviderCapabilities` / `ProviderHealth`) sin alterar la interfaz pública utilizada por el orquestador (`generate_response`, `generate_response_with_tools`, `load_config`, `get_active_provider`).

---

## 4. PLAN DE TRABAJO Y SIGUIENTES FASES

1. **Fase 1 — Provider Manager Modular:**
   - Crear clases de estructura `ProviderCapabilities` y `ProviderHealth`.
   - Implementar adaptadores especializados por proveedor bajo una interfaz común (`BaseAdapter`).
   - Mantener compatibilidad 100% con `LLMProvider` para no alterar el motor cognitivo.

2. **Fase 2 — Interfaz y Gestión de Credenciales:**
   - Actualizar `gui/index.html` y `gui/app.js` para incluir inputs de `GROQ_API_KEY` y `GITHUB_TOKEN` en la modal de configuración.
   - Actualizar el menú CLI (`interface/cli.py`) para reflejar todos los proveedores con sus estados de salud.

3. **Fase 3 — Pruebas Unitarias y Regresión:**
   - Mantener el total de pruebas unitarias existentes pasando (201/201 PASS).
   - Añadir pruebas unitarias dedicadas para la matriz de capacidades y comprobación de salud de proveedores.
