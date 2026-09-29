# AVATAR — Empieza aquí (Cursor)

Repo: `B:\PROYECTOS ANTIGRAVITY\Avatar` (git propio, `main`). No lo copies ni lo
muevas; no es NEXUM.

## Orden de lectura

1. `CURSOR_MASTER_CONTEXT_PROMPT.md` — pégalo como primer mensaje.
2. `AVATAR_PROJECT_DEEP_AUDIT.md` — estado verificado con evidencia.
3. `AVATAR_ARCHITECTURE_TARGET.md` — a dónde va el sistema.
4. `AVATAR_ERROR_AND_RISK_REGISTER.md` — qué duele y su estado.
5. `AVATAR_IMPLEMENTATION_ROADMAP.md` — fases R0-R7 (empieza por R1).
6. `CURSOR_PROJECT_HANDOVER.md` — operación diaria, secretos, calidad.

## Primeras tareas (solo lectura)

1. `git status` + `git log --oneline -4` y confirma árbol limpio.
2. Corre la suite y confirma 497 passed.
3. Traza `POST /api/chat` → `process_user_input` → `chokepoint.perform` → ledger.
4. Lee `bridges/telegram_bridge.py:111,122` (bypass abierto) y propone R1 sin
   implementarlo aún.

No implementes nada amplio hasta validar el baseline y entender el roadmap.
