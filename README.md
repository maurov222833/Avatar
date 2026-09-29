# ⚡ PROYECTO AVATAR AI: SISTEMA DE AGENTE SOBERANO DE ALTO NIVEL

**Avatar AI** es un entorno de desarrollo autónomo e IDE de agentes de Inteligencia Artificial independiente y local en la PC de Mauro (`b:\PROYECTOS ANTIGRAVITY\Avatar`).

---

## 🏛️ ARQUITECTURA DE MÓDULOS DE ÉLITE

```
                        ┌──────────────────────────────────────────┐
                        │          AVATAR SUPREME CORE             │
                        └────────────────────┬─────────────────────┘
                                             │
      ┌────────────────┬─────────────────────┼─────────────────────┬────────────────┐
      ▼                ▼                     ▼                     ▼                ▼
 [AutoLoop ReAct] [Memoria RAG]     [Deep Research Web]    [Telegram Daemon] [Monaco IDE]
 (core/autoloop)  (core/rag_memory) (tools/web_tool)       (bridges/telegram)(gui/index.html)
```

1. **Bucle Autónomo ReAct (AutoLoop Engine - `core/autoloop.py`):**
   - Motor de autocorrección para ejecutar tareas multi-paso en PowerShell/Python sin quedarse bloqueado.

2. **Memoria RAG y Conocimiento Acumulativo (`core/rag_memory.py` + `memory/knowledge_base.json`):**
   - Registra de forma continua todas las lecciones aprendidas, comandos, configuraciones y contextos de proyectos de Mauro.

3. **Motor de Investigación Web (Deep Research Engine - `tools/web_tool.py`):**
   - Búsqueda web en tiempo real (`WEB_SEARCH`) y lectura de páginas web/documentación (`FETCH_URL`).

4. **Protocolo de Razonamiento Supremo e Aislamiento de Pensamiento (`tools/reasoning_engine.py`):**
   - Razonamiento en Árbol de Pensamiento (`pensamiento_superior`) procesado en segundo plano y filtrado automáticamente para ofrecer respuestas 100% limpias al usuario.

5. **Pasarela de Comunicación Remota 24/7 (`bridges/telegram_bridge.py`):**
   - Bot de Telegram de demonio en segundo plano (`@Avatar_soberano_bot`) activado automáticamente con la interfaz visual.

6. **Visor de Código en Tiempo Real (Monaco Editor - `gui/app.js`):**
   - Pantalla dividida integrada a la derecha de la GUI para desplegar el código en vivo.

7. **Ejecución Silenciosa Sin Ventanas Negras:**
   - Lanzador optimizado `Avatar AI.lnk` utilizando `pythonw.exe` y reconfiguración UTF-8 de consola.

---

## 🚀 INICIO RÁPIDO EN WINDOWS

- **Desde el Escritorio:** Doble clic en **`Avatar AI`** (`Avatar AI.lnk`).
- **Control Remoto:** Telegram -> `@Avatar_soberano_bot` (Token configurado en `config.json`).

## Dependencias

```text
pip install -r requirements.txt
playwright install chromium
```

En Windows, para la GUI (`main_gui.py`) y automatización de escritorio:

```text
pip install -r requirements-desktop.txt
```

Para correr la suite:

```text
pip install -r requirements-dev.txt
pytest
```

La raíz de datos (`config.json`, `memory/`) es `AVATAR_HOME` o, si no está definida, la carpeta del repo.
