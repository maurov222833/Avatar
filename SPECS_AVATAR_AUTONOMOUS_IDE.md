# 📑 PLAN MAESTRO DE AUTONOMÍA Y ESPECIFICACIÓN TÉCNICA: PROYECTO AVATAR

**Para:** AGENTE PRINCIPAL AVATAR (AVATAR ENGINE)  
**De:** ANTIGRAVITY DEEP MIND PAIR-PROGRAMMER  
**Objetivo:** Guía de auto-desarrollo, evolución de arquitectura y réplica completa de capacidades IDE de Antigravity.

---

## 🏛️ 1. VISIÓN GENERAL Y ARQUITECTURA DEL SISTEMA

Avatar es un **Entorno de Desarrollo Soberano y Sistema de Agentes Autónomos** diseñado para operar en la PC de Mauro de forma 100% independiente, privada y configurable.

### Arquitectura de 4 Capas:
1. **Capa 1 - Interfaz IDE / GUI (Antigravity Workspace):**
   - Sidebar de proyectos, historial y tareas programadas.
   - Canvas de conversación estilo Chat IDE.
   - **Visor de Código en Tiempo Real (Live Code Viewer & Diff Editor).**
   - Terminal PowerShell Integrada en tiempo real.
2. **Capa 2 - Orquestador y Supervisor (Core Engine):**
   - Bucle de Razonamiento ReAct (Pensar -> Seleccionar Herramienta -> Verificar -> Responder).
   - Modo de Confirmación Humana para acciones críticas en PowerShell.
3. **Capa 3 - Enjambre de Subagentes Especializados (Swarm):**
   - `CoderAgent`: Arquitectura de software, refactorización y generación de código limpio.
   - `TesterAgent`: Ejecución de pruebas unitarias y diagnóstico de errores en terminal.
   - `SysAdminAgent`: Manejo de entorno, git y PowerShell.
   - `AntigravityProxyAgent`: Agente avatar para desarrollo desatendido de noche o desde remoto.
4. **Capa 4 - Motores de Inteligencia Híbridos (Local & Cloud):**
   - Google Gemini API (`gemini-3.5-flash-lite` / `gemini-3.6-flash`).
   - OpenAI ChatGPT API (`gpt-4o-mini` / `gpt-4o`).
   - Ollama Local Server (`qwen2.5-coder` / `deepseek-coder` 100% offline).

---

## 🎨 2. ESPECIFICACIÓN DE LA INTERFAZ IDE Y VISUALIZACIÓN DE CÓDIGO EN TIEMPO REAL

Para que Avatar adquiera la capacidad de mostrar el código mientras lo edita (igual que Antigravity), debe implementar los siguientes componentes en su frontend (`gui/`):

### A. Visor de Código en Tiempo Real (Live Code Viewer / Diff Editor)
- **Ubicación:** Panel central o dividible (Split Panel 50/50 entre Chat y Editor).
- **Lógica de Ejecución:**
  1. Cuando Avatar decida usar la herramienta `WRITE_FILE`, en lugar de solo mostrar texto en el chat, enviará un evento en vivo a la GUI.
  2. La GUI abrirá el **Editor de Código en Vivo (Monaco Editor / CodeMirror)** mostrando el archivo objetivo.
  3. El usuario verá cómo se escriben las líneas de código en tiempo real con resaltado de sintaxis (Python, HTML, JS, C++, PowerShell, JSON).
  4. En modificaciones de archivos existentes, se activará el **Modo Diff** (Líneas verdes = agregadas, Líneas rojas = eliminadas).

### B. Barra de Estado de Herramientas y Agentes
- Mostrar en vivo qué sub-agente está ejecutando la tarea (ej. `[CoderAgent trabajando en server.py...]`).
- Barra de progreso de compilación y ejecución de tests.

---

## 🤖 3. PROTOCOLO DE AUTO-DESARROLLO (INSTRUCCIONES PARA AVATAR)

Avatar debe seguir estos pasos para autocompletar su propio desarrollo:

### Paso 1: Inspeccionar la Estructura Actual
Avatar debe utilizar sus herramientas `READ_FILE` y `LIST_DIR` en la carpeta `b:\PROYECTOS ANTIGRAVITY\Avatar\` para revisar:
- `server.py`: Servidor de API FastAPI.
- `core/orchestrator.py`: Bucle de razonamiento.
- `core/subagents.py`: Definición de subagentes.
- `gui/index.html`, `gui/app.js`, `gui/style.css`: Interfaz de usuario.

### Paso 2: Integrar el Visor de Código en Tiempo Real (Live Code Stream)
Avatar debe actualizar `gui/index.html` y `gui/app.js` para añadir la librería **Monaco Editor** (`https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.js`):
1. Crear un contenedor `<div id="editor-container"></div>` junto al canvas de chat.
2. Cada vez que Avatar ejecute un `WRITE_FILE` o `READ_FILE`, cargará el código en el Monaco Editor en vivo.

### Paso 3: Conectar el Enjambre de Subagentes
Avatar debe habilitar en `server.py` los endpoints `/api/subagents/delegate` para permitir lanzar tareas en segundo plano (ej. un subagente corriendo tests unitarios mientras el agente principal conversa con Mauro).

### Paso 4: Mantener la Soberanía y Seguridad
Avatar nunca debe eliminar el **Modo de Confirmación Humana** para comandos destructivos en la PC.

---

## 🛠️ 4. RESUMEN DE COMANDOS Y REGLAS DE ORO PARA AVATAR

1. **Nombre del Agente:** AVATAR AI ENGINE.
2. **Usuario Principal:** Mauro.
3. **Plataforma Base:** Google Antigravity Workspace (`b:\PROYECTOS ANTIGRAVITY\Avatar`).
4. **Regla Suprema:** Comunicar progresos de forma clara, amigable, sin alucinaciones y con total transparencia técnica.

---
*Documento preparado por Antigravity DeepMind para el auto-desarrollo del Proyecto Avatar.*
