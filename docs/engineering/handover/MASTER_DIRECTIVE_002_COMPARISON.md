# Master Directive 002 — dictamen de comparación

Fecha: 2026-09-30. Rama: `cursor/u1-contencion-5763`.  
Texto comparado: `docs/engineering/handover/MASTER_DIRECTIVE_002.md`
(copia íntegra de los apartados 0 a 22, archivada en U0).
No se modificó código de ejecución.

Documentos vigentes que siguen mandando hasta que Mauro acepte una unidad:

- `STATUS.md` — estado corto.
- `AVATAR_IMPLEMENTATION_ROADMAP.md` — R0–R7.
- `AVATAR_ERROR_AND_RISK_REGISTER.md` — qué duele.
- `CURSOR_MASTER_CONTEXT_PROMPT.md` — cómo arranca un agente.
- `AVATAR_ARCHITECTURE_TARGET.md` — un orquestador, efectos solo por `ActChokepoint`.

La suite hermética vigente al cierre de la noche fue 691 passed, 2 skipped
(Linux, sin navegador real ni escritorio Windows). Eso no demuestra las
capacidades de esta directriz de extremo a extremo en el PC de Mauro.

## Organización documental

No se reescribió ningún maestro anterior. La directriz entra como complemento:

| Pieza | Rol |
|---|---|
| `MASTER_DIRECTIVE_002.md` | Texto propuesto. No es cola de implementación. |
| Este archivo | Matriz, conflictos, mapa y plan. |
| Roadmap R0–R7 | Fases ya aceptadas. R7 sigue bloqueado sin ADR. |

## Entregable A — Matriz

Leyenda de estado en código: IMPLEMENTED, INTEGRATED, VERIFIED, PARTIAL, UNVERIFIED, NOT_IMPLEMENTED, BLOCKED.  
«VERIFIED» aquí significa prueba en la suite o lectura de código con camino real. No significa prueba en el Windows de Mauro.

| Requisito | Documento anterior | Estado documental | Código | Evidencia | Brecha | Riesgo | Prioridad | Acción |
|---|---|---|---|---|---|---|---|---|
| Efectos solo por un chokepoint | Arquitectura objetivo; R1 | EXISTING | INTEGRATED, VERIFIED en suite | `core/act_chokepoint.py` `ACT_TYPES`, `perform` | El modelo no es la política | Alto si se abre un bypass | — | Conservar |
| Orden clara sin re-preguntar lo ya autorizado | Físico: minimizar / play / captura sin luz verde repetida | EXPANSION | PARTIAL | Atajos Telegram en `bridges/telegram_bridge.py`; EXEC sigue pidiendo aprobación | Un «corrige el proyecto» que lance PowerShell sigue en Nivel EXEC | Molestia vs daño | P1 | No apagar `exec_requires_approval` |
| Escritorio: observar, capturar, minimizar, maximizar, mostrar escritorio | `PHYSICAL_PC_ASSISTANT` (repo de revisión); STATUS | EXISTING | INTEGRATED; UNVERIFIED en el PC real | `SCREEN_CAPTURE`, `DESKTOP_OBSERVE`, `DESKTOP_HOTKEY` allowlist Win+↓/↑/D | Falta la prueba Telegram de Mauro | Medio | P0 del dueño | Probar en el PC |
| Cerrar ventana / Alt+Tab / clic / tecleo libre | MD002 §2.2 y §4.1; tabla física | EXPANSION | PARTIAL | `DESKTOP_CLICK` y `DESKTOP_TYPE` son EXEC. Alt+F4 y Alt+Tab salieron de la allowlist en `192c333` | MD002 pide poder cerrar «cuando esté autorizado», no como atajo permanente | Alto si vuelve a ser permanente | — | Dejarlos detrás de EXEC |
| No interferir con el foco ni el mouse sin misión | MD002 §4 | NEW | NOT_IMPLEMENTED | `tools/desktop_hotkey.py` enfoca el navegador al minimizar. No hay detector de «Mauro está usando el PC» | Un atajo autorizado igual roba el foco | Medio | P2 | Diseñar antes de codificar |
| Parada de emergencia con prioridad sobre el plan | MD002 §4.3 | NEW | NOT_IMPLEMENTED | Abort de recuperación en `core/cognitive/recovery_policy.py` no es un botón de Mauro. Failsafe de pyautogui vuelve a estar activo | Una misión visual no tiene freno único | Alto | P0 de diseño | Decisión de canal (Telegram y/o local) |
| Contención por clics repetidos o ventana equivocada | MD002 §4.3 | NEW | PARTIAL | Anti-bucle en `recovery_engine.py`; `computer_control.py` aborta si no encuentra la ventana | No vigila el mouse ni el foco de forma continua | Alto | P1 | Reusar el anti-bucle; no crear otro motor |
| Protección de Windows en el ejecutor | MD002 §3.1 y §3.5 | EXPANSION | PARTIAL | `WRITE_FILE` bloquea metadata git (`_touches_git_dir`). `COMMAND` es EXEC, no una denylist de `System32` ni del registro | Una orden aprobada o un allowlist mal escrito puede tocar el sistema | Alto | P0 técnico, cuando Mauro acepte la unidad | Denylist canónica en el ejecutor, con tests. No en el prompt |
| Archivos personales y alcance de misión | MD002 §3.2–3.3; U1 workspace | EXPANSION | PARTIAL | `ActPolicy.allowed_workspace_root` para algunas escrituras locales | No hay denylist de Fotos/Documentos distinta del workspace | Alto | P1 | Misma unidad que la denylist |
| Acciones destructivas con respaldo y autorización específica | MD002 §3.4 y §5.3 nivel D | EXPANSION | PARTIAL | EXEC pide aprobación. No hay paso obligatorio de backup ni de «elemento exacto» | Una aprobación genérica puede cubrir un borrado amplio | Alto | P1 | No implementar borrado nuevo |
| Investigación web como datos, no como órdenes | F-06; `UNTRUSTED_INPUT_ACTS` | EXISTING | INTEGRATED, PARTIAL | `WEB_SEARCH`, `FETCH_URL`, `BROWSER_OBSERVE` contaminan el contexto. Luego EXEC / LOCAL_WRITE / EXTERNAL piden aprobación | No clasifica fuente oficial vs copia. No hay informe estructurado de investigación | Medio | P2 | No guardar hallazgos crudos como reglas |
| RAG con procedencia y estados de validación | E-16 abierto | EXPANSION | PARTIAL | `core/rag_memory.py` `search_knowledge` por intersección de palabras. `save_knowledge` no guarda fuente ni estado | Una frase externa puede quedar como conocimiento | Medio | P2 | No es la fase siguiente. No duplicar otro RAG |
| Misión con plan, evidencia, reanudación sin repetir lo no idempotente | Fases 1–2, F-14, D-7, R4 presupuesto | EXISTING | INTEGRATED, PARTIAL | `checkpoint_engine.py` trata UNKNOWN como no idempotente. `resume_engine`, `watchdog.py`, techo de actos | El bucle de chat no es el diagrama UNDERSTAND→REPORT de la §8. El watchdog no está en el Programador de tareas | Medio | — | Conservar. Scheduler de Windows sigue opcional |
| Verificación física, no éxito por texto del modelo | Arquitectura objetivo; F-11 | EXISTING | PARTIAL | Observadores del chokepoint; `ComputerControl` tiene estados OBSERVE/VERIFY | Varios resultados de navegador marcan `verified` si `success` | Medio | P1 | No declarar VERIFIED de escritorio sin el PC |
| Logger, secretos redactados, ledger de actos | R2; E-01; E-10 | EXISTING | INTEGRATED, VERIFIED en suite | `core/logging_util.py`, `core/redaction.py`, tabla `acts` | Consola si el logger no arranca. No hay informe de misión con los estados de la §18 | Bajo | P2 | Conservar |
| Cascada de proveedores, techo por hora | R4 | EXISTING | INTEGRATED, VERIFIED en suite | `core/llm_provider.py`, `core/provider_usage.py` | No hay inventario dinámico de modelos ni precios | Bajo | — | No sustituir R4 por un catálogo inventado |
| Elegir modelo en la UI de Cursor y cambiar al agotar cuota sin perder la misión | MD002 §10.5–10.7 | NEW | NOT_IMPLEMENTED | La cascada cambia de proveedor de Avatar, no el modelo del IDE. No hace clic en el selector de Cursor | Automatizar el selector puede violar límites del proveedor | Alto si se automatiza la UI | BLOCKED | No implementar el clic en el selector |
| No gastar de más sin autorización | R4 techo; MD002 §10.5 | EXISTING + EXPANSION | PARTIAL | `max_calls_per_hour` opcional, por defecto vacío | No hay precio ni bloqueo de ampliación de plan | Medio | P2 | Dejar el techo opt-in |
| Subagentes con alcance menor que Avatar | MD002 §11; R6 | CONFLICT con «crear la flota» | NOT_INTEGRATED | `core/subagents.py` no lo importa el server ni Telegram. Lo usa una prueba de superficies | Crear PlannerAgent/CoderAgent duplicaría el orquestador y heredaría permisos de más | Alto | — | No crear agentes nuevos |
| IDE externos y revisión del diff | MD002 §9 | NEW | NOT_IMPLEMENTED | No hay coordinador de Cursor/VS Code/Antigravity dentro de Avatar | Un agente externo con el escritorio sería otro bypass | Alto | BLOCKED | Decisión de Mauro antes de diseñar |
| Telegram y WhatsApp con la misma autoridad | R1, R5, F-18, F-19 | EXISTING | INTEGRATED; prueba en vivo UNVERIFIED | Allowlist numérica, `chokepoint.perform`, WhatsApp con política | El estado remoto de la §12.4 no es un panel completo. Falta la prueba del dueño | Alto si la allowlist se vacía y auto-enrola al primer privado | P0 del dueño | Probar captura, play, minimizar |
| Auto-evolución sin ampliarse privilegios | MD002 §19; R7 | EXISTING | PARTIAL | `exec_requires_approval` sigue en verdadero por defecto. Modelo-B (mismo proceso) sigue abierto a propósito | Un proceso local puede saltarse el chokepoint si ya corre dentro de Avatar | Alto, aceptado | BLOCKED | R7 solo con ADR |
| Parar al exceder pasos, coste o reintentos | R4 actos; recovery | EXISTING | PARTIAL | `max_acts_per_mission`; anti-bucle de recuperación; techo de llamadas | No hay reloj único de misión ni presupuesto de tokens del IDE | Medio | P2 | No añadir otro contador hasta definir cuál manda |

## Entregable B — Requisitos nuevos

No estaban cubiertos de forma suficiente. No se implementan en este dictamen.

1. Parada de emergencia invocable por Mauro, con prioridad sobre el plan y sin matar Windows.
2. Denylist de rutas críticas de Windows (sistema, registro, arranque, seguridad) aplicada en el ejecutor, con ruta canónica y rechazo de enlaces.
3. Detector de interferencia: no mover mouse ni robar foco si la misión no lo pidió.
4. Contención operativa ante repetición visual (no solo ante error de herramienta).
5. Informe de investigación con fuente, fecha, corroboración e incertidumbre. Separar dato crudo de decisión de proyecto.
6. Metadatos de procedencia en la memoria (fuente, fecha, estado de validación, misión).
7. Inventario de modelos marcado como desconocido cuando no se pueda comprobar. Sin precios inventados.
8. Informe de misión con los estados de la §18 (`COMPLETED_VERIFIED`, `BLOCKED`, etc.).
9. Consulta remota de misión activa, último acto confirmado y pendiente de aprobación.

## Entregable C — Conflictos

### C1. Atajos permanentes frente a «cerrar ventanas cuando esté autorizado»

La tabla física autoriza, sin repetir luz verde, solo minimizar, mostrar el escritorio y maximizar. La directriz §2.2 permite cerrar una ventana cuando la misión lo autoriza. La §4.1 prohíbe cerrar o cambiar el foco sin justificación.

Resolución propuesta, ya reflejada en `192c333`: Alt+F4 y Alt+Tab no son atajos permanentes. Cerrar una ventana puede existir como acto EXEC, pedido de forma explícita. No se restaura el atajo salvo una frase nueva de Mauro que lo pida.

### C2. «No preguntes por cada paso» frente a EXEC

La §5.1 y §5.4 piden ejecutar la lectura, la búsqueda y la corrección dentro del proyecto sin confirmaciones redundantes. El código pide aprobación para `COMMAND`, `DESKTOP_CLICK` y `DESKTOP_TYPE`.

Resolución propuesta: no poner `exec_requires_approval` en falso. La lectura dentro del workspace ya es directa. Ampliar la allowlist de comandos solo con líneas exactas, cuando Mauro nombre esas líneas. Una orden de «arregla Avatar» no autoriza PowerShell libre ni salir del proyecto.

### C3. Subagentes de la §11 frente al módulo actual

La directriz describe una flota (Planner, Researcher, Coder, Tester, Security, Reviewer). El módulo `core/subagents.py` es un boceto que producción no llama. R6 decidió conservarlo por una prueba, no cablearlo.

Resolución propuesta: no crear esa flota. Si más adelante hay delegación, el subagente no hereda el chokepoint completo y el orquestador sigue siendo el único que ejecuta efectos.

### C4. Selector de modelos del IDE frente a la cascada R4

La §10.7 pide abrir la UI de Cursor y cambiar el modelo. R4 ya cambia de proveedor de Avatar cuando uno falla, con techo de llamadas. Automatizar el selector puede saltarse cuotas y facturación. La propia §10.5 y §10.7 lo prohíben.

Resolución propuesta: la cascada R4 permanece. No se implementa el clic en el selector. Si no hay modelo, la misión se guarda y se informa.

### C5. Baseline de 497 tests frente a la suite actual

El prompt maestro histórico esperaba 497 passed. La suite creció con las fases posteriores. Volver a 497 sería borrar pruebas.

Resolución: el número histórico se reporta, no se maquilla. El estado vivo es el de `STATUS.md`.

### C6. Verificador fuera de proceso (R7) frente a más autonomía

La directriz pide más iniciativa dentro de la misión. No pide apagar el Modelo-B. La arquitectura sigue diciendo que un verificador externo solo nace con ADR.

Resolución: R7 sigue bloqueado. Más autonomía de escritorio no sustituye ese ADR.

## Entregable D — Mapa de integración

Reutilizar, no duplicar:

| Capacidad de la directriz | Módulo que ya manda | No crear |
|---|---|---|
| Permisos y ejecución | `ActChokepoint` + `ActPolicy` | Un segundo motor de autoridad |
| Escritorio y visión | `tools/computer_control.py`, `core/ui_inspector.py`, `tools/screen_tool.py` | Otro `mouse_tool` (el archivo actual está vacío) |
| Música y pestañas del navegador real | `tools/audio_tool.py` | Usar Playwright como si fuera el Chrome del usuario |
| Misiones, reanudación, no repetir efectos | `checkpoint_engine.py`, `resume_engine.py`, `watchdog.py` | Otro planificador de misiones |
| Investigación | `tools/web_tool.py` + contaminación F-06 | Un researcher que escriba reglas en la memoria |
| Memoria | `core/rag_memory.py` | Una segunda base hasta cerrar E-16 con diseño |
| Modelos de Avatar | `core/llm_provider.py`, `core/provider_usage.py` | Catálogo de precios inventado |
| Canal remoto | `bridges/telegram_bridge.py`, `bridges/whatsapp_bridge.py` | Otro listener sin allowlist |
| Logs | `core/logging_util.py`, `core/redaction.py` | Prints nuevos de diagnóstico |
| Subagentes | Ninguno en producción | La flota de la §11 |

`tools/mouse_tool.py` está vacío. No es una capacidad. El clic real, si se usa, entra por `ComputerControl` y sale como `DESKTOP_CLICK` (EXEC).

## Entregable E — Arquitectura complementaria

La directriz cabe en la arquitectura que ya está dibujada. El modelo propone; el chokepoint dispone.

```text
Mauro (PC o Telegram/WhatsApp allowlist)
        |
        v
Orquestador  -- plan, misión, presupuesto, parada
        |
        v
ActChokepoint -- denylist de rutas, EXEC, contaminación, ledger
        |
        +-- archivos / terminal (workspace + denylist Windows)
        +-- escritorio (observar, captura, hotkeys de la lista, clic/tecleo con EXEC)
        +-- web (dato no confiable; no entra solo a la memoria permanente)
        +-- proveedores (cascada R4; sin selector de IDE)
```

Parada de emergencia, si se aprueba, es una entrada del orquestador que corta actos nuevos. No es un `taskkill` de Windows.

## Entregable F — Plan por unidades

Ninguna unidad empieza sola. Orden sugerido, seguridad antes que autonomía aparente:

| Unidad | Depende de | Riesgo si se hace mal | Aceptación mínima |
|---|---|---|---|
| 0. Prueba Telegram del dueño | Rama actual en el PC | Declarar el canal listo sin foto ni play | Captura llega como foto; «dale play»/«pausa» misma canción; minimizar sin luz verde |
| 1. Denylist de rutas críticas en el ejecutor | Decisión de la lista exacta | Bloquear el proyecto o dejar pasar `System32` por un enlace | Tests de ruta canónica, symlink y junction simulado; `WRITE_FILE` y argumentos de `COMMAND` |
| 2. Parada de emergencia | Decisión del canal | Parar a medias y seguir haciendo clic | Una señal de Mauro impide el siguiente acto visual y queda en el ledger |
| 3. Procedencia mínima en RAG | Unidad 1 no es prerrequisito, pero no se adelanta a 1–2 | Guardar la web como regla | Un `FETCH_URL` no aparece como conocimiento permanente sin estado `unverified` |
| 4. Informe de misión con estado explícito | Ledger ya existente | Un texto del modelo marcado `COMPLETED_VERIFIED` | El estado sale del ledger, no del párrafo final |

Fuera de esta lista hasta nuevo aviso: flota de subagentes, clic en el selector de modelos, IDE externos, R7, instalar el Programador de tareas, devolver Alt+F4 como atajo permanente.

## Entregable G — Informe de estado

**Ya existe y está en el flujo real:** un orquestador, chokepoint con ledger, allowlist de Telegram, captura y audio por acto, hotkeys de minimizar/maximizar/escritorio, logger JSON, cascada y techo de proveedores, watchdog en proceso, reanudación con checkpoints, contaminación de la web.

**Verificado en suite Linux, no en el PC:** lo anterior, más 691 passed / 2 skipped. La prueba de Telegram en la máquina de Mauro sigue pendiente.

**Existe y no está integrado:** `core/subagents.py`. `tools/mouse_tool.py` está vacío.

**Parcial:** protección de rutas (solo git), investigación web (busca y marca no confiable, no corrobora), RAG por palabras, presupuesto de misión, escritorio (clic/tecleo piden aprobación; no hay conciencia de interferencia).

**Falta:** parada de emergencia, denylist de Windows, inventario dinámico de modelos, coordinación de IDE externos, informe de misión con los estados de la §18, metadatos de validación en la memoria.

**Bloqueado:** R7 sin ADR. Selector de modelos del IDE: no se debe automatizar. Programador de tareas de Windows: decisión del dueño, no se instala desde aquí.

**Decisión de Mauro antes de codear:**

1. Aceptar este dictamen como complemento, sin reemplazar R0–R7.
2. Elegir la primera unidad, si quiere alguna: denylist de Windows, o parada de emergencia. La prueba de Telegram no requiere código nuevo.
3. Confirmar que Alt+F4 y Alt+Tab siguen fuera de los atajos permanentes. La directriz no los pide como permanentes.

**Puede empezar bajo las reglas ya vigentes, sin esta directriz:** corregir un test rojo, o un hueco que el registro de riesgos y el roadmap ya tengan aceptado. Esta directriz no abre esa puerta por sí sola.
