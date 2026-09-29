# CURSOR — Handover práctico del proyecto Avatar

## 1. Abrir el repositorio exacto

1. Instala Cursor en Windows y ábrelo.
2. **File → Open Folder** → `B:\PROYECTOS ANTIGRAVITY\Avatar` (esa carpeta, no la
   padre `PROYECTOS ANTIGRAVITY`, que es otro repo —NEXUM—).
3. Confirma raíz: debes ver `core/`, `server.py`, `tests/`, `.git`, `README.md`.
4. Terminal integrado → `git status` (limpio esperado), `git log --oneline -4`
   (debe mostrar `4dc7514` arriba), `git branch` (`main`).
5. Comandos verificados: `python -m pytest tests/ -q --tb=line -p no:cacheprovider`
   (~2 min, 497 passed); `python server.py` (FastAPI :8000). No hay CI ni linter.

## 2. Modelos y cuenta

El catálogo del dueño (Grok/Claude/GPT/Gemini/Muse Spark) cambia; no lo fijes en
código. Para efectos locales usa el modelo que prefieras; el runtime de Avatar usa
sus propios proveedores (`config.json`, no tus credenciales de Cursor). Nunca pegues
API keys en prompts, reportes ni commits.

## 3. MCP, Skills, Hooks, Cloud Agents

Revisa cada integración antes de activarla (pueden ejecutar código). Para este repo:
no instales nada sin leerlo primero; los scripts de `scratch/` NO son producción.
**Cloud Agents no tocan tu escritorio**: WhatsApp/Telegram Playwright, Task Scheduler
y la DB local solo funcionan con agentes LOCALES. No ejecutes dos agentes sobre el
mismo árbol a la vez (uno edita, el otro espera).

## 4. Reglas de trabajo y secretos

- Rama `main`, commits pequeños con `git diff` revisado; nunca commitees `.env`,
  `config.json`, `memory/`, `token.txt` (gitignore los cubre; verifica con
  `git status` y escanea patrones `gsk_|AIza` antes de commitear).
- Empieza en solo-lectura; verifica baseline (suite verde) antes de implementar.
- Puertas de calidad: reproducir síntoma → test dedicado → suite verde → evidencia
  (ledger/log). Prohibido: mocks que afirman éxito, truncar errores, marcar fixed
  sin reproducir.
- Sensibles/externos/irreversibles (mensajes reales, credenciales, borrados,
  dependencias, red fuera de localhost): autorización explícita del dueño.

## 5. Dónde está cada cosa (ver `AVATAR_PROJECT_DEEP_AUDIT.md` §3-4)

Orquestador `core/orchestrator.py`, chokepoint `core/act_chokepoint.py`,
autoridad `core/cognitive/`, estado `core/state_db.py`, proveedores
`core/llm_provider.py`, puentes `bridges/`, GUI `server.py+gui/`, roadmap
`AVATAR_IMPLEMENTATION_ROADMAP.md` (este handover), errores
`AVATAR_ERROR_AND_RISK_REGISTER.md`.
