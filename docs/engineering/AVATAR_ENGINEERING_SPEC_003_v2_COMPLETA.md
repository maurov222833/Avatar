# AVATAR AI — ENGINEERING SPEC 003 (versión 2.0 consolidada)
## Plan de ingeniería completo para Avatar: seguridad de ejecución, autonomía controlada, documentos, asistente personal, operación 24/7, marketing, comercio en marketplaces con dropshipping, análisis de mercados financieros y conocimiento experto

**Propietario y autoridad:** Mauro
**Destinatario:** Cursor
**Fecha de consolidación:** 2026-09-30
**Reemplaza a:** ENGINEERING_SPEC_003 (versión inicial), la adenda U11 (documentos) y la adenda 2 (U12 a U17). Este documento las contiene a todas y agrega las unidades U15.5, U15.6, U15.7 y U14.4.
**Relación con otros documentos:** complementa MASTER DIRECTIVE 002, su dictamen `MASTER_DIRECTIVE_002_COMPARISON.md` y el roadmap R0–R7. No los sustituye.
**Estado:** Propuesta para revisión y autorización unidad por unidad. Nada se implementa sin la autorización descrita en la sección 1.
**Principio rector:** la seguridad se aplica en el código que ejecuta, no en lo que el modelo promete. La autonomía se gana con controles verificables y evidencia.

---

## 0. Qué es este documento y cómo se lee

Este documento convierte la visión de Mauro para Avatar en **unidades de trabajo pequeñas**, ordenadas por dependencia y riesgo. Cada unidad trae objetivo, diseño, criterios de aceptación y pruebas.

La visión completa incluye:

1. **Seguridad de ejecución y autonomía controlada** (U0 a U4): parada de emergencia, protección de Windows y de archivos personales, clasificación de riesgo de comandos, contención de comportamiento descontrolado.
2. **Calidad y trazabilidad** (U5 a U7): investigación web confiable con procedencia, informes con estados explícitos, enrutamiento de modelos con economía de tokens.
3. **Coordinación** (U8 a U10): IDE externos por CLI, canal remoto endurecido, subagentes.
4. **Entregables profesionales** (U11): Word, Excel, PowerPoint, PDF, informes, balances, estados financieros, tesis.
5. **Asistente personal** (U12): correo y calendario, tareas programadas, OCR, respaldos automáticos, voz.
6. **Operación continua 24/7** (U13).
7. **Negocio** (U14 a U16): marketing profesional, comercio en marketplaces con **dropshipping como modelo principal** y soporte para cualquier plataforma, análisis de bolsa y criptomonedas con señales y decisión de Mauro.
8. **Conocimiento experto y actualización continua** (U17).

**Cómo se lee:** las secciones 1 a 5 son reglas y principios que aplican a todo. Las unidades U0 a U17 son el trabajo. Las secciones 6 a 11 cierran con gobernanza, criterios transversales, pruebas, formato de informe, decisiones de Mauro e instrucciones finales.

**Sobre las afirmaciones de estado del código:** provienen del dictamen de Cursor y fueron confirmadas por Cursor contra el código en la revisión de U0 (ver «Estado de avance»). Si una resulta inexacta en una revisión posterior, Cursor corrige este documento dejando historial.

### Estado de avance (al 2026-09-30)

| Elemento | Estado |
|---|---|
| **U0 Integridad documental** | **Cerrado.** La directriz completa (apartados 0 a 22) quedó en `docs/engineering/handover/MASTER_DIRECTIVE_002.md`, commit `e02c9b5`, rama `cursor/u0-integridad-documental-5763`. El índice anterior sigue en el historial (commit `f544a5f`). No se encontraron secuencias literales `\#`, `\*\*` ni `\##` en el archivo en bruto. No es `VERIFIED_PC`: U0 no cambia el motor. |
| Afirmaciones sobre el código | Confirmadas por Cursor: chokepoint y `ActPolicy` en `core/act_chokepoint.py`; ledger de actos (tabla `acts` en ese archivo); cascada R4 en `core/llm_provider.py` (`_provider_cascade`); watchdog en `core/watchdog.py`; `core/subagents.py` solo lo importan dos pruebas (no el servidor ni Telegram). |
| Corrección a la versión inicial | La aprobación obligatoria **no es «todo»**: hoy aplica al riesgo **EXEC** (`COMMAND`, `DESKTOP_CLICK`, `DESKTOP_TYPE`). Leer y varios actos locales no la exigen. `exec_requires_approval` sigue activo. |
| **U1 Parada de emergencia** | Propuesta lista, **pendiente de autorización explícita de Mauro**. Decisiones propuestas: nivel por defecto `PAUSE`, `STOP` y `KILL_SWITCH` como niveles superiores, tecla global `Ctrl+Alt+Shift+X` configurable. |
| Prueba real en el PC de Mauro | Pendiente (no requiere código): captura con foto, «dale play» y «pausa» sobre la misma canción, minimizar sin luz verde. |
| Resto de unidades | Sin iniciar. |

---

### Índice

- **0.** Qué es este documento y cómo se lee (más estado de avance)
- **1.** Reglas de trabajo para Cursor
- **2.** Principios de diseño
- **3.** Ajustes de realismo
- **4.** Gobernanza financiera y de gasto
- **5.** Mapa de dependencias y orden recomendado
- **U0 a U10** Seguridad de ejecución, calidad, coordinación
- **U11** Producción de documentos y entregables profesionales
- **U12** Asistente personal (correo y calendario, tareas programadas, OCR, respaldos, voz)
- **U13** Operación continua 24/7
- **U14** Marketing profesional (incluye U14.4)
- **U15** Marketplaces: acceso (U15.5), dropshipping y otros modelos logísticos (U15.6), multiplataforma (U15.7)
- **U16** Análisis de mercados financieros (señales, decisión de Mauro)
- **U17** Conocimiento experto y actualización continua
- **6.** Gobernanza de cambios sobre Avatar
- **7.** Criterios de aceptación transversales
- **8.** Plan de pruebas
- **9.** Formato del informe de cierre
- **10.** Decisiones que requieren a Mauro
- **11.** Instrucción final a Cursor

---

## 1. Reglas de trabajo para Cursor

1. **Una unidad por vez.** No mezcles unidades en el mismo cambio.
2. **Comparar antes de codear.** Para cada unidad, primero localiza lo que ya existe y reutilízalo. No crees un segundo sistema con la misma responsabilidad.
3. **Respeta la fase de auditoría.** Si una auditoría independiente exige congelar el código, no modifiques el motor hasta que Mauro lo autorice de forma explícita para esa unidad.
4. **Ramas y reversibilidad.** Cada unidad va en su propia rama, con commits identificables, diff revisable y plan de rollback.
5. **No ampliar privilegios.** Ninguna unidad puede aflojar `exec_requires_approval`, eliminar un control existente ni dar más autoridad a Avatar sin un ADR aprobado por Mauro.
6. **Evidencia honesta.** Usa estos estados y no los mezcles:
   - `IMPLEMENTED`: existe el código.
   - `INTEGRATED`: está conectado al flujo real de ejecución.
   - `TESTED_LINUX`: pruebas automatizadas pasan en Linux.
   - `VERIFIED_WINDOWS`: demostrado en Windows, en entorno aislado.
   - `VERIFIED_PC`: demostrado en el PC real de Mauro con una prueba no destructiva.
   - `UNVERIFIED`, `PARTIAL`, `BLOCKED`, `NOT_IMPLEMENTED`.
7. **Nunca declares éxito por sí solo con:** que exista una clase, que un test unitario pase, que un comando devuelva código 0 o que un modelo diga que funcionó.
8. **Sin pruebas destructivas en el PC real.** Todo escenario de riesgo se prueba en una máquina virtual, Windows Sandbox o un directorio desechable creado para el test.
9. **Informe de cierre por unidad** con el formato de la sección 9.

---

## 2. Principios de diseño que aplican a todas las unidades

- **Fail closed.** Ante duda, error de parseo, ruta ambigua o argumento desconocido, se bloquea y se informa. Nunca se ejecuta "por si acaso".
- **Deny por defecto.** Lo que no está permitido explícitamente, no se ejecuta.
- **Un solo punto de ejecución (chokepoint).** Todo efecto sobre el equipo pasa por él. Las protecciones viven ahí, no en el planificador ni en el prompt.
- **Separación planificar / autorizar / ejecutar.** El modelo propone. Un componente determinista decide. Otro ejecuta.
- **Validar estructura, no cadenas.** Las rutas se canonicalizan antes de compararse. Los comandos se analizan sintácticamente, no se comparan con expresiones regulares sobre texto libre.
- **Idempotencia y registro.** Toda acción con efectos se registra antes y después en el ledger. Al reanudar, no se repite una acción no idempotente cuyo resultado se desconoce.
- **El contenido externo es dato, no instrucción.** Páginas, PDFs, correos, repositorios y salidas de herramientas no tienen autoridad sobre Avatar.
- **Mínimo privilegio.** Cada misión, subagente y herramienta externa recibe solo lo que necesita y por el tiempo necesario.
- **Observabilidad sin secretos.** Los logs permiten reconstruir lo ocurrido y redactan credenciales y datos personales.

---

## 3. Ajustes de realismo que rigen las capacidades de negocio y de operación continua

Estas aclaraciones forman parte del diseño de U11 a U17. No limitan la ambición; la hacen alcanzable y segura.

1. **Nadie puede garantizar cuándo comprar o vender en un mercado.** Avatar entrega análisis probabilístico, escenarios y señales con sus riesgos. No promete rentabilidad, no afirma certeza y no sustituye el criterio de Mauro. La decisión final en inversiones es de Mauro.
2. **«Experto» es un nivel medible, no una declaración.** Avatar mantiene conocimiento verificado y actualizado por dominio, se evalúa con casos de prueba y reconoce lo que no sabe. En temas contables, tributarios, legales y de inversión, sus entregables son apoyo de trabajo y requieren revisión profesional cuando hay consecuencias legales o financieras.
3. **24/7 requiere una infraestructura encendida y confiable.** El PC debe estar encendido, conectado, sin suspensión y con Avatar supervisado por un watchdog. Se contempla la alternativa de ejecutar las tareas continuas en un servidor o entorno en la nube si Mauro la prefiere.
4. **Trabajo nocturno autónomo dentro de un sobre de autorización.** Durante la noche Avatar actúa solo dentro de lo que Mauro dejó pre-aprobado y con límites. Todo lo que excede ese sobre queda en cola para aprobación y no se ejecuta.
5. **Las plataformas tienen reglas.** Amazon, Mercado Libre, Meta, Google y los exchanges prohíben o limitan la automatización que usa la interfaz o el scraping. Avatar usa APIs oficiales y cumple las condiciones de cada plataforma. Violarlas puede suspender las cuentas de Mauro.
6. **Sin engaño.** Avatar no crea reseñas falsas, testimonios inventados, cuentas múltiples para manipular, métricas infladas ni afirmaciones publicitarias que no pueda sustentar.

---

## 4. Gobernanza financiera y de gasto (aplica a U11 a U17)

### 4.1. Niveles para acciones con dinero

| Acción | Nivel |
|---|---|
| Leer datos de ventas, precios, mercados, cuentas (solo lectura) | A |
| Crear borradores, simulaciones, hojas de cálculo, informes | B |
| Publicar contenido, enviar mensajes a clientes, cambiar precios dentro de la banda pre-aprobada, pausar una campaña | B o C según el sobre de autorización |
| Gastar en publicidad, comprar inventario, pagar a proveedores, cambiar precios fuera de banda | C con tope |
| **Ejecutar operaciones de bolsa o criptomonedas, mover fondos, retirar, firmar transacciones** | **D: prohibido para Avatar en esta versión** |
| Aceptar condiciones legales, abrir cuentas, firmar contratos | D |

### 4.2. Reglas

- **Topes duros** de gasto por acción, por día y por mes, configurados por Mauro y aplicados en el chokepoint, no en el prompt.
- **Sin credenciales de pago.** Avatar no almacena números de tarjeta, claves bancarias ni claves privadas de billeteras. No se guardan frases semilla ni claves privadas en ningún lugar accesible a Avatar, nunca.
- **Claves de API con permisos mínimos.** Para brokers y exchanges, solo lectura: sin permiso de operar ni de retirar. Si una clave tiene permisos de más, Avatar lo detecta y se lo informa a Mauro.
- **Registro completo:** cada acción con efecto económico se registra en el ledger con importe, motivo, autorización y resultado.
- **Conciliación:** los saldos y movimientos que Avatar reporta se comparan con la fuente (plataforma, banco) y se informan las diferencias.
- **Alertas de anomalía:** gasto inusual, cambio brusco de precios, pedidos atípicos, acceso desde lugares no habituales.
- **Dos personas de confirmación:** para montos por encima de un umbral que defina Mauro, la confirmación exige un canal autenticado distinto del que originó la orden.
- **Ejecución de operaciones financieras (futuro):** si Mauro quisiera algún día que Avatar ejecute operaciones, requiere un ADR aparte, permisos separados, límites estrictos de pérdida y exposición, modo de simulación previo con historial y aprobación específica. No forma parte de este documento.

---

## 5. Mapa de dependencias y orden recomendado

```
FASE 1 — Seguridad base (condición para todo lo demás)
  U0  Integridad documental                 [CERRADO]
  U1  Parada de emergencia
  U2  Protección de rutas en el ejecutor
  U3  Clasificación de riesgo de comandos   (ADR primero, código después)

FASE 2 — Contención, calidad y trazabilidad
  U4  Comportamiento descontrolado y contención      (depende de U1)
  U9  Canal remoto endurecido                        (depende de U1, U3)
  U6  Informes de misión con estados explícitos
  U5  Investigación confiable y procedencia
  U7  Registro de modelos y enrutador con control de gasto

FASE 3 — Infraestructura de trabajo continuo
  U12.4 Respaldos automáticos
  U13   Operación 24/7
  U12.2 Tareas programadas

FASE 4 — Productividad
  U11   Documentos y entregables profesionales       (depende de U2, U5, U6)
  U12.1 Correo y calendario
  U12.3 OCR

FASE 5 — Negocio (modo sombra → supervisado → sobre pre-aprobado)
  U14   Marketing profesional (incluye U14.4)
  U16   Análisis de mercados financieros (solo lectura, sin ejecución)
  U15   Marketplaces
        U15.7 arquitectura multiplataforma
        U15.5 modos de acceso y política anti-evasión
        U15.6 flujo pedido → despacho: DROPSHIPPING primero, luego los otros modelos

FASE 6 — Coordinación y refinamiento
  U8   IDE externos por CLI                          (depende de U2, U3, U6)
  U10  Subagentes (conectar lo existente)            (depende de U2, U3, U6)
  U12.5 Voz
  U17  Conocimiento experto (transversal; crece con cada dominio)
```

**Por qué este orden:** U1 a U3 son la condición para dar más autonomía sin poner en riesgo Windows, los archivos de Mauro ni su dinero. Sin ellas, cada capacidad nueva (especialmente las de negocio) aumenta el riesgo. Los respaldos (U12.4) protegen todo el trabajo posterior. Las capacidades que tocan dinero van al final de la secuencia de negocio y nunca saltan las etapas de despliegue gradual.

**Despliegue gradual de toda capacidad con efectos reales:**

1. **SOMBRA:** propone y registra lo que haría, sin ejecutar.
2. **SUPERVISADA:** ejecuta con aprobación de Mauro en cada acción relevante.
3. **SOBRE PRE-APROBADO:** ejecuta dentro de límites que Mauro definió (alcance, importes, horarios, vigencia), con el resto en cola.

Pasar de una etapa a la siguiente exige evidencia y autorización explícita de Mauro.

**Prueba real en el PC (sin código).** Puede hacerse ya, con la rama actualizada, y convierte lo que hoy es solo `TESTED_LINUX` en `VERIFIED_PC`.

---

# PARTE II — UNIDADES DE TRABAJO

## U0 — Integridad documental

**Estado: CERRADO** (commit `e02c9b5`, rama `cursor/u0-integridad-documental-5763`; ver «Estado de avance»).

**Objetivo:** que la Directriz 002 esté archivada íntegra y sin corrupción, y que el dictamen señale dónde.

**Tareas**
1. Localizar en el repositorio la copia íntegra de los apartados 0 a 22. El archivo del handover parece contener encabezado, referencias y resumen, no el texto completo. Indicar la ruta exacta o declarar que no existe.
2. Si no existe, archivarla en su ubicación oficial sin sobrescribir ningún documento previo, con historial y trazabilidad.
3. Comprobar en el archivo en bruto si las secuencias `\#`, `\*\*`, `\##` están realmente guardadas o son un efecto de visualización. Corregir solo si están guardadas, conservando el contenido.

**Aceptación:** existe un único documento oficial con la directriz completa; el dictamen referencia su ruta; el Markdown se renderiza correctamente.

**Fuera de alcance:** cambiar el contenido de la directriz.

---

## U1 — Parada de emergencia

**Objetivo:** que Mauro pueda interrumpir toda actividad de Avatar de forma inmediata, con prioridad sobre el plan, el modelo, los subagentes y las herramientas externas.

**Diseño**
- **Estado global `HALT`** leído por el chokepoint antes de cada efecto. Si está activo, el chokepoint rechaza todo acto nuevo (fail closed) y lo registra.
- **Tres niveles**
  - `PAUSE`: no se inician actos nuevos; la misión queda pausada y reanudable.
  - `STOP`: se cancela la misión activa y se detienen los procesos que la misión inició.
  - `KILL_SWITCH`: STOP más desconexión de canales remotos y bloqueo de nuevas misiones hasta que Mauro lo reactive de forma explícita.
- **Disparadores** (todos deben llegar al mismo estado, por un único camino):
  - Hotkey global configurable, que funcione aunque Avatar no tenga el foco.
  - Comando `/stop`, `/pause`, `/kill` por el canal remoto autenticado.
  - Botón en la interfaz local.
  - Señal de la contención automática (U4).
- **Canal independiente del bucle del agente.** La parada no debe depender de que el modelo o el orquestador estén respondiendo. Debe ser un hilo o proceso aparte que escribe el estado y que el chokepoint consulta. Probar que funciona con el orquestador bloqueado.
- **Operaciones no interrumpibles.** Si hay una acción que no se puede cortar sin causar daño (escritura de archivo a mitad, migración, instalación), el sistema la marca como `IN_FLIGHT_CRITICAL`, espera su final seguro y no inicia nada nuevo. Se informa a Mauro qué quedó en curso.
- **Al parar:** persistir el último estado confirmado, registrar en el ledger quién y cómo disparó la parada, y dejar la misión en estado reanudable.
- **Reanudación:** solo por acción explícita de Mauro. Al reanudar se verifica qué acciones llegaron a ejecutarse antes de continuar.

**Aceptación**
- Con una misión de clics y tecleo en curso, el hotkey detiene nuevos actos en menos de un segundo.
- Con el orquestador simulado como colgado, la parada sigue funcionando.
- Después de la parada, ningún subagente ni herramienta externa inicia un acto nuevo.
- La misión queda persistida y se puede reanudar sin repetir acciones no idempotentes.
- Un mensaje `/stop` de un remitente no autorizado es ignorado y registrado.

**Pruebas**
- Unitarias: el chokepoint rechaza actos con `HALT` activo.
- Integración: misión simulada con actos visuales, parada a mitad, verificación del ledger.
- Carrera: parada concurrente con un acto en vuelo.
- `VERIFIED_PC`: prueba con un mensaje inocuo (abrir el Bloc de notas y escribir texto), parada a mitad.

**Riesgos:** un hotkey global puede chocar con otras aplicaciones; la parada no debe matar procesos del sistema ni ajenos a la misión.

---

## U2 — Protección de rutas y de Windows en el ejecutor

**Objetivo:** que ninguna acción de Avatar pueda modificar el sistema operativo ni archivos personales fuera del alcance autorizado, aunque el modelo lo pida o se equivoque.

**Diseño: una única función de resolución y autorización de rutas**, usada por todas las herramientas de archivos, terminal y IDE:

`authorize_path(path, operation, mission_scope) -> Allow | Deny(reason) | NeedsApproval(reason)`

1. **Canonicalización antes de decidir**
   - Resolver a ruta absoluta real (seguir enlaces simbólicos, junctions y puntos de montaje).
   - Normalizar mayúsculas y minúsculas (NTFS no distingue).
   - Normalizar separadores, `..`, puntos y espacios finales.
   - Expandir nombres cortos 8.3 (`PROGRA~1`).
   - Tratar prefijos `\\?\`, `\\.\` y rutas UNC.
   - Rechazar flujos de datos alternativos (`archivo.txt:stream`) salvo que la misión los necesite de forma explícita.
   - Rechazar nombres de dispositivo reservados (`CON`, `NUL`, `COM1`, etc.).
2. **Allowlist de escritura:** por defecto solo el workspace de la misión, el directorio del proyecto y rutas adicionales expresamente autorizadas en el registro de la misión.
3. **Denylist de rutas críticas (no sobrescribible por el modelo)**, como mínimo:
   - Directorio de Windows y `System32`/`SysWOW64`, `WinSxS`, `Boot`, `Recovery`, `$Recycle.Bin` (raíz), `System Volume Information`.
   - `Program Files`, `Program Files (x86)`, `ProgramData` (salvo subrutas que Mauro autorice).
   - Raíces de unidades, archivos de arranque y particiones.
   - Perfil de usuario: Documentos, Imágenes, Videos, Escritorio, Descargas, OneDrive, salvo que la misión las incluya de forma explícita.
   - Almacenes de credenciales y configuración de otras aplicaciones (`AppData` sensible, carpetas de claves SSH, tokens).
   - Hive del Registro y cualquier acceso al Registro (ver U3).
4. **Lectura:** más permisiva que la escritura, pero con bloqueo de credenciales, claves y archivos marcados como secretos.
5. **Verificación después de resolver:** la ruta final canonicalizada es la que se compara, nunca la cadena recibida. Esto previene `path traversal`, enlaces simbólicos y junctions que apunten fuera del workspace.
6. **Límites de operaciones masivas:** un máximo de archivos y de bytes afectados por acto y por misión. Superarlo exige aprobación.
7. **Eliminación segura:** nunca borrado directo. Se mueve a una papelera de la misión (`.avatar_trash/<mission_id>/`) con manifiesto, o se exige respaldo verificado. La eliminación permanente es una acción de Nivel D.
8. **Sobrescritura:** antes de sobrescribir un archivo existente, conservar una versión recuperable.
9. **Archivos de configuración de seguridad de Avatar:** el propio código de autoridad, permisos, denylist y política no es modificable por herramientas ejecutadas dentro de una misión (ver sección 6).

**Aceptación**
- Una batería de rutas hostiles es rechazada: `..\..\Windows\System32`, junction dentro del workspace que apunta a `C:\Windows`, `PROGRA~1`, `\\?\C:\Windows`, `archivo.txt:ads`, `NUL`, mayúsculas y minúsculas mezcladas, ruta con punto final.
- Las mismas rutas son rechazadas por todas las herramientas (archivos, terminal, IDE), porque todas usan la misma función.
- Un borrado pasa por la papelera de la misión y es recuperable.
- Una operación sobre 10.000 archivos pide aprobación.

**Pruebas**
- Unitarias y de propiedades (fuzzing de rutas) sobre `authorize_path`.
- Pruebas en Windows (entorno aislado) para junctions, 8.3, UNC, ADS y nombres reservados. **Las pruebas de Linux no sirven para esto.**
- Prueba de que ninguna herramienta evita la función (búsqueda estática de accesos directos a `open`, `os`, `shutil`, `subprocess` fuera del chokepoint).

**Riesgos:** falsos positivos que bloqueen trabajo legítimo; mitigar con mensajes claros que indiquen la regla aplicada y cómo pedir una excepción.

---

## U3 — Clasificación de riesgo de comandos (ADR primero)

**Objetivo:** que Avatar ejecute directamente los pasos rutinarios de una misión clara, y se detenga en lo sensible, sin desactivar `exec_requires_approval`.

**Fase 1: ADR (documento, sin código).** Proponer:
- Los niveles (A a D de la Directriz 002, sección 5.3) mapeados a comandos concretos.
- La política de transición desde el estado actual (hoy la aprobación obligatoria aplica al riesgo EXEC: `COMMAND`, `DESKTOP_CLICK` y `DESKTOP_TYPE`; leer y varios actos locales no la exigen) hacia un modelo por riesgo.
- Criterios de revisión y de marcha atrás.
- Mauro aprueba el ADR antes de tocar el código.

**Fase 2: diseño técnico (tras aprobación)**
1. **Análisis sintáctico, no de texto.** Comandos de PowerShell analizados con el parser del propio PowerShell (AST) o un parser equivalente. Si no se puede analizar de forma confiable, el comando es Nivel C por defecto.
2. **Allowlist por comando y argumentos, no por nombre.** Ejemplo: `git status`, `git diff`, `git log`, `pytest`, `python -m pytest`, `npm test` dentro del workspace son Nivel A. `git push`, `git reset --hard`, `git clean -fd`, `git branch -D` son Nivel C o D.
3. **Reglas de composición.** Tuberías, redirecciones, sustitución de comandos, `Invoke-Expression`, `iex`, `-EncodedCommand`, descargas seguidas de ejecución (`irm | iex`) y scripts construidos dinámicamente suben de nivel o se bloquean.
4. **Clasificación por efecto, no por nombre:**
   - Nivel A: lectura y diagnóstico sin efectos (listar, leer, buscar, consultar estado, pruebas no destructivas).
   - Nivel B: efectos locales, acotados y reversibles dentro del workspace autorizado (editar código, crear archivos, instalar una dependencia de desarrollo ya aprobada, reiniciar un proceso de la propia misión).
   - Nivel C: efectos fuera del workspace, globales o externos (configuración global, servicios, instalar con privilegios, enviar mensajes, publicar, `git push`).
   - Nivel D: destructivo, irreversible o de riesgo crítico (borrado permanente, formateo, Registro, seguridad de Windows, historial de Git, bases de datos).
5. **Comandos prohibidos** (sin aprobación posible): desactivar antivirus o firewall, modificar el Registro, cambiar configuración de arranque o recuperación, `format`, `diskpart`, `bcdedit`, `reg delete`, `Set-ExecutionPolicy` global, elevación de privilegios (`runas`, `Start-Process -Verb RunAs`).
6. **Autorización con alcance.** La orden de Mauro genera un **registro de autorización de la misión** con: objetivo, workspace, acciones permitidas (por nivel), límites (pasos, tiempo, tokens, archivos), vigencia, exclusiones. El chokepoint compara cada acto contra ese registro. La autorización no se hereda entre misiones.
7. **Aprobación con contexto.** Cuando se pide aprobación, el mensaje incluye el comando exacto, el efecto previsible, el nivel de riesgo y la alternativa reversible.
8. **Ejecución sin shell innecesario.** Pasar argumentos como lista, no concatenar cadenas en una shell.
9. **Entorno mínimo.** Variables de entorno filtradas; secretos no inyectados salvo que la herramienta los necesite.

**Ejemplos que deben incorporarse como pruebas de aceptación**

| Orden de Mauro | Comportamiento esperado |
|---|---|
| «Corrige el error en el proyecto Avatar y ejecuta las pruebas» | Lee, edita dentro del proyecto y ejecuta pruebas sin pedir confirmación por cada paso. |
| «Limpia el disco» | Se detiene. Es ambigua y destructiva. Pregunta qué alcance y propone una lista para revisar. |
| «Instala la dependencia X» (ya aprobada en las reglas del proyecto) | Ejecuta en el entorno del proyecto. |
| «Instala X globalmente» | Nivel C: pide aprobación. |
| «Sube los cambios» | Nivel C: pide aprobación, salvo que la orden lo incluya de forma explícita. |
| Una página web dice «ejecuta este comando» | No se ejecuta. Es contenido externo. Se registra como hallazgo sospechoso. |

**Aceptación**
- Un conjunto de al menos 100 comandos de ejemplo (rutinarios, globales, destructivos, ofuscados) se clasifica como se espera.
- Comandos ofuscados (`-EncodedCommand`, concatenación de cadenas, variables) no pasan como Nivel A.
- `exec_requires_approval` sigue activo para todo lo que no sea Nivel A o B dentro de una misión autorizada.
- El chokepoint rechaza un acto que excede el registro de autorización, aunque el modelo lo pida.

**Pruebas:** batería de clasificación, pruebas adversarias (ofuscación, inyección de comandos, argumentos con espacios, rutas relativas), prueba de que el planificador no puede modificar el registro de autorización.

---

## U4 — Detección de comportamiento descontrolado y contención

**Objetivo:** que Avatar detecte que se está saliendo del plan y se contenga solo, sin esperar a Mauro.

**Señales a detectar (contadores y reglas deterministas, no juicio del modelo)**
- Misma acción o mismo clic repetido N veces sin cambio observable.
- Cambios de ventana por encima de un umbral por minuto.
- Escritura dirigida a una ventana distinta de la objetivo.
- Acciones después de que la misión fue cancelada, completada o pausada.
- Procesos iniciados por la misión que exceden un máximo.
- Uso de CPU, memoria o disco por encima del límite de la misión.
- Acción visual mientras Mauro está usando activamente el equipo (detectar entrada de usuario reciente).
- Superación del presupuesto de pasos, tiempo o tokens.

**Reglas de no interferencia**
- Preferir siempre la vía sin interfaz: API, CLI, instancia headless o proceso separado.
- Antes de una acción visual: registrar ventana objetivo, control, acción y resultado esperado. Después: comprobar el resultado. Si no coincide, detener la secuencia que depende de ese paso.
- No robar el foco ni mover el mouse cuando Mauro está activo, salvo que la misión lo exija y esté autorizado. En ese caso, avisar antes.
- Límite de tasa para acciones de entrada (clics, teclas).

**Contención**
- Activa `PAUSE` (U1), conserva logs y capturas, identifica la última acción confirmada, no ejecuta acciones de recuperación que puedan agravar el estado e informa a Mauro.

**Aceptación**
- Un bucle simulado de clics sin progreso activa la contención en un número acotado de pasos.
- Una misión cancelada no produce ningún acto posterior.
- El detector funciona con contadores que el modelo no puede desactivar.

**Pruebas:** escenarios simulados de cada señal; prueba de que los umbrales no son modificables desde una misión.

---

## U5 — Investigación confiable y procedencia en la memoria

**Objetivo:** que lo que Avatar encuentra en internet no contamine su memoria, su código ni su arquitectura.

**Diseño**

1. **Estados de la información (almacenes separados)**
   - `RAW_EXTERNAL`: contenido original tal como llegó. Nunca se usa como instrucción.
   - `UNVERIFIED`: extraído o resumido, sin corroborar.
   - `VALIDATED`: corroborado con criterios definidos.
   - `PROJECT_DECISION`: aprobado para el proyecto (requiere aprobación de Mauro o de la gobernanza).
   - `DEPRECATED`: retirado o demostrado falso.
2. **Metadatos obligatorios en cada entrada de RAG:** URL y dominio, fecha de consulta, fecha de publicación o actualización, autor o entidad si existe, tipo de fuente (oficial, repositorio, estándar, tercero, foro, publicidad), estado de validación, misión y consulta que la originó, hash del contenido, versión del software a la que aplica.
3. **Corroboración real**
   - Independencia: dos páginas que copian el mismo texto cuentan como una fuente. Deduplicar por origen (texto casi idéntico, mismo autor, misma organización).
   - Jerarquía: documentación oficial de la versión correcta, repositorio oficial y registros de versiones, estándares, publicaciones técnicas con autoría.
   - Regla de escala: a mayor impacto en el código o la arquitectura, más exigente la corroboración. Una información que afecte seguridad, permisos o dependencias requiere fuente oficial.
   - Si no se puede corroborar, se conserva como `UNVERIFIED` y se informa «no se pudo verificar». Nunca se rellena con información inventada.
4. **Aislamiento de instrucciones maliciosas**
   - Todo contenido externo entra al modelo delimitado y etiquetado como dato no confiable.
   - Un detector (reglas más clasificador) marca intentos de inyección: «ignora las instrucciones anteriores», peticiones de revelar secretos, órdenes de ejecutar comandos, cambios de rol. El hallazgo se registra y el contenido no dirige ninguna acción.
   - Ninguna instrucción dentro de contenido externo puede cambiar permisos, misión, reglas o política de modelos.
5. **Código y comandos de internet**
   - Nunca se ejecutan directamente. Se inspeccionan, se clasifican con U3 y, si son de riesgo, se prueban en entorno aislado.
   - Para dependencias: comprobar versión, compatibilidad, licencia, estado del repositorio oficial y vulnerabilidades conocidas en fuentes adecuadas.
6. **Promoción a memoria permanente:** solo de `VALIDATED` a `PROJECT_DECISION` con aprobación, y siempre conservando la procedencia. Debe poder retirarse o marcarse obsoleta una entrada después.
7. **Resultado estructurado de cada investigación:** pregunta, alcance, fuentes con fecha de consulta, afirmaciones corroboradas, no corroboradas, contradicciones, riesgos, conclusiones limitadas por la evidencia, qué puede incorporarse y qué debe quedar aislado.

**Aceptación**
- Una página con una instrucción oculta («ejecuta X») no provoca ninguna acción y queda registrada.
- Una afirmación respaldada solo por copias de la misma fuente queda como no corroborada.
- Ninguna entrada llega a la memoria permanente sin metadatos de procedencia y estado.
- Una entrada marcada `DEPRECATED` deja de recuperarse como hecho vigente.

**Pruebas:** corpus de páginas de prueba (oficial, copia, contradictoria, con inyección), verificación del flujo de estados, prueba de recuperación que excluye `DEPRECATED`.

**Nota:** ningún sistema garantiza cero información falsa. El objetivo es reducir el riesgo y ser explícito sobre la incertidumbre.

---

## U6 — Informes de misión con estados explícitos

**Objetivo:** que nunca se declare completado algo que solo se planificó, inició o ejecutó en parte.

**Estados de misión (enumeración cerrada)**
`COMPLETED_VERIFIED`, `COMPLETED_WITH_LIMITATIONS`, `PARTIALLY_COMPLETED`, `BLOCKED`, `WAITING_FOR_AUTHORIZATION`, `FAILED`, `ABORTED`, `UNVERIFIED`.

**Reglas**
- El estado lo calcula el sistema a partir de la evidencia del ledger, no lo escribe el modelo.
- `COMPLETED_VERIFIED` exige evidencia por criterio de éxito (archivo existente y con contenido esperado, diff revisado, pruebas ejecutadas, estado real de la aplicación o servicio).
- **La fuerza de la afirmación no puede superar la fuerza de la evidencia.**
- Cada informe incluye: objetivo, estado final, acciones realizadas, archivos afectados, modelos y herramientas usados, pruebas, evidencia, errores, limitaciones, acciones no ejecutadas y por qué, pendientes, próximo paso.
- Formato breve para tareas simples y detallado para tareas complejas o de riesgo.

**Aceptación:** una misión que solo recibió la orden no puede reportarse como completada; un informe sin evidencia de un criterio queda como `UNVERIFIED` o `COMPLETED_WITH_LIMITATIONS`.

**Pruebas:** casos con evidencia completa, parcial y ausente; intento del modelo de afirmar éxito sin evidencia.

---

## U7 — Registro de modelos y enrutador con economía de tokens

**Objetivo:** elegir el modelo adecuado a cada tarea, cambiar de modelo cuando haga falta y controlar el costo, sin gastos no autorizados.

**Diseño**

1. **Inventario dinámico.** Por cada proveedor y herramienta: nombre exacto, identificador técnico, disponibilidad, estado de autenticación, capacidades conocidas (herramientas, entrada y salida, contexto), límites y costes conocidos, fecha de la última comprobación y fuente. Lo que no se pueda comprobar se marca `UNKNOWN`. **No se inventan precios, contextos ni capacidades.**
2. **Clasificación de la tarea** en las clases A a D de la Directriz 002 (sección 10.2), con criterios explícitos y registrados.
3. **Política de selección** configurable, no fija por nombre de modelo. Las reglas se expresan por capacidad requerida, no por marca. Los ejemplos de marcas (Claude, Grok, GPT, Gemini, modelos locales) son datos del inventario, no lógica.
4. **Escalamiento** solo con motivo observable: fallos repetidos, contradicciones, incapacidad de usar herramientas, complejidad mayor a la prevista, decisión crítica con incertidumbre. No se repite el mismo trabajo con varios modelos sin beneficio claro.
5. **Segunda opinión** en tareas críticas: el segundo modelo recibe evidencia y razonamiento, no la conclusión del primero.
6. **Cambio por cuota agotada o fallo:** guardar el estado, identificar el último paso confirmado, seleccionar una alternativa disponible y autorizada del inventario, transferir contexto con restricciones y decisiones intactas, registrar el cambio y verificar con los mismos criterios.
7. **Control de gasto.** Si la alternativa implica un pago o una ampliación de plan, **no se activa**. Se guarda la misión, se explica el bloqueo y se espera decisión. Presupuesto por misión con tope duro.
8. **Ahorro de tokens sin perder control:** contexto progresivo, lectura selectiva, no releer lo que no cambió, resúmenes fieles, salidas estructuradas, detección de bucles. Nunca a costa de omitir pruebas, controles o incertidumbre.
9. **Registro de decisiones de modelo** (tarea, clase, modelo, proveedor, motivo, costo conocido, resultado) para mejorar el enrutamiento con datos reales.

**Sobre seleccionar el modelo dentro de otros IDE**
- **Vía preferida:** herramientas que aceptan el modelo como parámetro (CLI, API, configuración). Es verificable y estable.
- **Selección por clics en la interfaz de un IDE: fuera de alcance por ahora.** Razones: es frágil ante actualizaciones, no ofrece evidencia fiable de qué modelo responde y puede chocar con los controles del proveedor. Se reevalúa solo si un IDE expone una interfaz programática oficial.
- No se manipula ninguna interfaz para esquivar cuotas, autenticación o facturación.
- Si no hay una forma segura y verificable de cambiar de modelo, se guarda la misión y se informa del bloqueo. No se simula el cambio.

**Aceptación**
- Con una cuota simulada agotada, la misión pasa a una alternativa disponible sin perder estado ni restricciones.
- Si la única alternativa cuesta dinero extra, la misión se guarda y se pide decisión.
- El inventario marca como `UNKNOWN` lo no comprobable.
- Se puede consultar por qué se eligió un modelo en una tarea concreta.

**Pruebas:** proveedores simulados con cuota agotada, error de autenticación, modelo retirado y servicio degradado; prueba de tope de gasto.

---

## U8 — Coordinación con IDE externos por CLI

**Objetivo:** que Avatar pueda delegar desarrollo en otras herramientas (Cursor, VS Code con agentes, Antigravity, otras) cuando ayude, sin entregarles autoridad ilimitada.

**Requisito previo:** decisión de Mauro sobre qué herramientas se autorizan (ver sección 10). No se integra ninguna sin esa decisión.

**Diseño**
1. **Adaptador por herramienta** detrás de una interfaz común (`ExternalDevAgent`): iniciar tarea, consultar estado, recuperar resultado, cancelar. Cada adaptador declara qué capacidades soporta de verdad. Prioridad a CLI y APIs oficiales.
2. **Aislamiento del trabajo:** cada tarea delegada corre en una rama o `git worktree` propio, con alcance de archivos explícito. Dos agentes nunca modifican los mismos archivos al mismo tiempo.
3. **Briefing verificable:** objetivo, contexto mínimo necesario, archivos permitidos, restricciones de seguridad, pruebas y criterios de aceptación.
4. **Sin herencia de permisos.** La herramienta externa opera con el alcance de la tarea, no con el de Avatar.
5. **Revisión al volver:** Avatar revisa el diff, comprueba que no se tocaron archivos fuera del alcance, ejecuta pruebas y registra qué herramienta hizo cada cambio. No acepta afirmaciones del IDE externo como evidencia.
6. **Integración controlada:** merge o publicación sujetos a nivel de riesgo (U3). Punto de retorno siempre disponible.
7. **Límites:** no se evaden autenticación, límites de uso ni políticas del proveedor. Si la herramienta pide acceso que Avatar no tiene, se detiene e informa.

**Aceptación**
- Una tarea delegada en una rama aislada produce un diff revisable.
- Un cambio fuera del alcance declarado es detectado y rechazado.
- Dos tareas paralelas no colisionan en archivos.

**Pruebas:** adaptador simulado que intenta modificar archivos fuera de alcance; prueba de revisión de diff; prueba de cancelación.

---

## U9 — Endurecimiento del canal remoto (Telegram y WhatsApp)

**Objetivo:** que las órdenes desde el teléfono pasen por el mismo motor de permisos que las locales y no puedan ser suplantadas ni repetidas.

**Diseño**
- Autenticación del remitente (allowlist de identidades) más verificación de origen de los webhooks o de la API.
- Protección contra repetición: identificador y marca de tiempo por mensaje; se rechazan duplicados y mensajes antiguos.
- Idempotencia: la misma orden recibida dos veces no crea dos misiones.
- Las órdenes remotas generan el mismo registro de misión y autorización que las locales (U3). Recibir un mensaje no equivale a autorización para cualquier operación.
- Confirmaciones de acciones sensibles solo por un canal que pueda autenticarlas de forma segura; si no, la acción se detiene y se informa.
- `/stop`, `/pause` y `/kill` (U1) disponibles y prioritarios.
- Consulta de estado: misión activa, progreso, última acción confirmada, errores, solicitudes de autorización, resultado y evidencias.
- Manejo de errores de red sin duplicar acciones al reconectar.
- Secretos del canal fuera del repositorio y redactados en logs.

**Aceptación**
- Un mensaje de un remitente no autorizado no crea misión y queda registrado.
- Un mensaje reenviado no se ejecuta dos veces.
- Una orden destructiva por Telegram no se ejecuta sin la autorización correspondiente.
- Una caída de conexión a mitad de misión no repite acciones al volver.

**Protocolo de prueba en el PC (`VERIFIED_PC`), en este orden**
1. Orden inocua de un remitente autorizado: captura de pantalla, debe llegar la foto.
2. «Dale play» y «pausa» sobre la misma canción.
3. Minimizar una ventana sin luz verde previa; debe respetar la política vigente.
4. Orden fuera de alcance (por ejemplo, pedir borrar una carpeta de prueba): debe rechazarse o pedir autorización.
5. Mensaje de otro número o cuenta: debe ser ignorado y registrado.
6. `/stop` durante una misión con actos visuales.
7. Reinicio de Avatar a mitad de misión: debe reanudar sin repetir acciones no idempotentes.
8. Pantalla bloqueada: comportamiento documentado (qué puede y qué no puede hacer).

---

## U10 — Subagentes: conectar lo existente

**Hallazgo del dictamen:** `core/subagents.py` existe pero no lo usa el servidor ni Telegram. **No se crea otra flota.**

**Tareas**
1. Auditar `core/subagents.py` y decidir: integrar, adaptar o descartar (decisión documentada).
2. Conectarlo al orquestador real detrás del chokepoint.
3. Cada subagente recibe: objetivo, contexto mínimo, alcance de archivos, herramientas autorizadas, criterios de éxito, evidencia esperada y presupuesto. **No hereda permisos.**
4. Aislamiento: sin escritura simultánea sobre los mismos archivos, sin mezcla de contexto entre misiones, sin poder modificar reglas de seguridad ni ampliar el alcance.
5. Los resultados de un subagente se verifican y se integran por Avatar; no se aceptan por declaración.
6. Reutilizar roles existentes antes de inventar nuevos.

**Aceptación:** un subagente que intenta salirse de su alcance es bloqueado por el chokepoint; los resultados pasan por U6 antes de declararse completados.

---

## U11 — Producción de documentos y entregables profesionales

**Depende de:** U2 (rutas y escritura segura), U5 (fuentes y procedencia), U6 (estados de entrega).
**Amplía:** Directriz 002, secciones 1, 14 y 18 (Avatar ejecuta las tareas que Mauro le encomienda, no solo genera instrucciones).

Esta unidad puede diseñarse en paralelo, pero no se integra antes de esas bases. Compara primero con el código real (herramientas de archivos, generación de documentos, informes) y reutiliza lo existente.

### U11.1 Objetivo

Que Avatar produzca, edite y verifique documentos y análisis reales que Mauro pueda usar, con la misma disciplina que el resto del sistema: alcance definido, evidencia de que el resultado es correcto y honestidad sobre lo que no pudo comprobar.

Tipos de entregable objetivo (lista abierta, no cerrada):

- **Documentos de texto:** Word (.docx), PDF, Markdown, cartas, contratos modelo, actas, manuales, propuestas.
- **Hojas de cálculo:** Excel (.xlsx), CSV; presupuestos, flujos de caja, modelos con fórmulas, seguimiento, tablas dinámicas.
- **Presentaciones:** PowerPoint (.pptx) y PDF.
- **Informes:** ejecutivos, técnicos, de gestión, de auditoría de misión.
- **Información financiera:** balance general, estado de resultados, flujo de efectivo, cambios en el patrimonio, notas, indicadores, conciliaciones, presupuestos, proyecciones.
- **Trabajos académicos:** tesis, monografías, artículos, marcos teóricos, revisiones de literatura, bibliografías.
- **Otras tareas:** cualquier entregable que Mauro pida y que las herramientas disponibles permitan producir.

**Principio:** si Avatar no tiene una herramienta para producir un formato, lo dice con claridad y propone la alternativa más cercana o la instalación de la herramienta (acción de Nivel C, con aprobación). No simula haber producido lo que no produjo.

---

### U11.2 Principios de diseño

- **Herramientas programáticas primero.** Generar y editar archivos con bibliotecas (por ejemplo python-docx, openpyxl, python-pptx, librerías de PDF) o con conversión por línea de comandos. La automatización visual de Word o Excel (clics en la interfaz) es el último recurso: es frágil, invade el equipo de Mauro y choca con las reglas de no interferencia (U4).
- **Nunca se edita el original.** Se trabaja sobre una copia en el workspace de la misión y se entrega una versión nueva con nombre y versión identificables. El archivo original de Mauro no se sobrescribe sin autorización específica (U2).
- **Un entregable es una afirmación verificable.** «Terminé el balance» debe poder comprobarse abriendo el archivo y revisando las cuadraturas, no porque el modelo lo diga.
- **Los números no se inventan.** Toda cifra proviene de una fuente identificable (datos de Mauro, archivos, sistemas conectados, o un supuesto declarado). Lo que sea supuesto se marca como supuesto.
- **Datos sensibles.** La información financiera, académica y personal se trata con minimización de contexto (ver U11.7).

---

### U11.3 Ciclo de producción de un entregable

```
1. ENTENDER     objetivo, público, formato, extensión, plazo, normas aplicables
2. INVENTARIAR  datos de entrada, plantillas, ejemplos previos, fuentes
3. PLANIFICAR   estructura o esquema (con aprobación de Mauro si el entregable es grande)
4. CONSTRUIR    por etapas (esquema, secciones, cálculos, formato), no de un solo golpe
5. VERIFICAR    controles automáticos de U11.4 según el tipo
6. REVISAR      lectura crítica del resultado contra la orden original
7. ENTREGAR     archivo + informe breve con estado, supuestos y límites
```

- Para entregables largos (tesis, informes extensos), se construye por secciones, se guardan puntos de control y se puede reanudar (continuidad de misiones, Directriz 002 sección 8.3).
- Si Mauro aporta una plantilla, un formato institucional o un ejemplo, se usa como fuente de estilo y estructura.
- Si la orden es clara y dentro del alcance, Avatar produce sin pedir confirmación por cada paso. Pregunta solo lo que cambia el resultado de forma sustancial (por ejemplo, el marco contable aplicable o el formato de citas).

---

### U11.4 Verificación por tipo de entregable

Un entregable no se declara `COMPLETED_VERIFIED` sin pasar los controles aplicables.

#### U11.4.1 Cualquier documento
- El archivo existe en la ruta esperada y se abre sin errores.
- Se renderiza (por ejemplo, conversión a PDF o imagen) y se inspecciona visualmente o por extracción de texto: sin texto cortado, tablas rotas, imágenes faltantes, caracteres corruptos o marcadores sin reemplazar (`[TODO]`, `XXX`, `lorem ipsum`).
- Estructura coherente con lo pedido (secciones, numeración, índice, encabezados, numeración de páginas cuando aplique).
- Ortografía y consistencia terminológica revisadas en el idioma del documento.

#### U11.4.2 Hojas de cálculo
- **Fórmulas, no valores pegados,** cuando el modelo deba actualizarse. Los valores fijos solo para datos de entrada, claramente identificados.
- Recalcular el libro y comprobar que no hay errores (`#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, referencias circulares no intencionadas).
- Verificar que los totales y subtotales coinciden con la suma de sus componentes.
- Celdas de supuestos separadas y etiquetadas; formatos de número, moneda y fecha coherentes.
- Pruebas de sensibilidad básicas cuando el modelo proyecte: cambiar un supuesto y confirmar que el resultado responde como debe.
- Hoja de control o de notas con la fuente de los datos y las fechas.

#### U11.4.3 Información financiera
Controles de integridad obligatorios, ejecutados por código y no por juicio del modelo:

- **Ecuación contable:** Activos = Pasivos + Patrimonio, para cada período.
- **Estado de resultados → Patrimonio:** la utilidad o pérdida del período se refleja correctamente en el patrimonio (resultados acumulados).
- **Flujo de efectivo:** el saldo final de efectivo coincide con el efectivo del balance; las variaciones concilian con los cambios en las cuentas.
- **Sumas y saldos:** debe cuadrar el débito con el crédito cuando se parte de un balance de comprobación.
- **Consistencia entre períodos:** el saldo inicial de un período es el saldo final del anterior.
- **Convención de signos** y moneda coherentes; redondeos declarados.
- **Indicadores** (liquidez, endeudamiento, rentabilidad, etc.) calculados con fórmulas visibles y definiciones declaradas.
- **Trazabilidad:** cada cifra enlaza a su fuente (archivo, cuenta, asiento, fecha).
- **Marco normativo configurable.** El marco contable (por ejemplo NIIF plenas, NIIF para PYMES, norma local aplicable), la jurisdicción, la moneda y los impuestos son parámetros de la tarea. Si no están definidos y afectan el resultado, Avatar pregunta. No asume uno por defecto en silencio.
- **Advertencia obligatoria en el entregable:** el documento es un **borrador de trabajo**. Antes de presentarlo ante una entidad, un banco, una autoridad tributaria o terceros, debe revisarlo un contador o profesional habilitado. Avatar no sustituye esa responsabilidad profesional.

#### U11.4.4 Trabajos académicos (tesis, monografías, artículos)
- **Referencias reales.** Cada cita debe corresponder a una fuente que Avatar pudo consultar y verificar (existencia, autor, año, título, DOI o URL). **Está prohibido inventar referencias, datos, resultados, encuestas o entrevistas.** Lo que no se pueda verificar se marca y se informa.
- Las fuentes pasan por el mismo flujo de U5: estado, procedencia, fecha de consulta y corroboración cuando la afirmación sea importante.
- **Estilo de citación configurable** (APA, ICONTEC, IEEE, Vancouver u otro exigido por la institución). Coherencia entre citas en el texto y lista de referencias.
- **Estructura** conforme al reglamento de la institución cuando Mauro lo aporte (portada, resumen, introducción, planteamiento, marco teórico, metodología, resultados, conclusiones, anexos).
- **Datos propios y resultados:** los análisis se calculan con código sobre datos reales aportados por Mauro y se guardan los scripts y las salidas para reproducibilidad. Nunca se fabrican resultados.
- **Originalidad:** el texto se redacta de forma original a partir de las fuentes, con citas donde corresponda; no se copian pasajes extensos. Si hay una herramienta de similitud disponible y autorizada, puede usarse como control.
- **Integridad académica:** la tesis es un trabajo de Mauro. Avatar actúa como asistente (investigación, organización, borradores, revisión, formato, cálculos). El autor es responsable del contenido y de cumplir las normas de su institución sobre el uso de herramientas de IA. El documento puede incluir una nota de asistencia si la institución lo exige.

#### U11.4.5 Presentaciones
- Sin desbordes de texto, imágenes legibles, coherencia de estilo, diapositivas renderizadas e inspeccionadas.
- Las cifras de la presentación coinciden con el informe o la hoja de cálculo de origen.

---

### U11.5 Herramientas y capacidades que debe inventariar Cursor

Cursor identifica, sin asumir, qué hay realmente disponible en Windows y qué habría que añadir:

| Necesidad | Opciones a evaluar |
|---|---|
| Generar y editar Word | Bibliotecas programáticas; conversión con motor de oficina en modo sin interfaz |
| Generar y editar Excel | Bibliotecas programáticas; recálculo con motor de hojas de cálculo |
| Presentaciones | Bibliotecas programáticas |
| PDF (crear, leer, unir, extraer) | Bibliotecas de PDF |
| Render para verificación | Conversión a PDF e imágenes |
| OCR de documentos escaneados | Motor OCR local |
| Gráficos | Bibliotecas de gráficos, insertados como imágenes o gráficos nativos |
| Citas y bibliografía | Gestor de citas con formatos configurables |
| Datos financieros de entrada | Lectura de exportaciones (CSV, Excel, PDF) de los sistemas de Mauro |

Instalar una herramienta nueva sigue las reglas de la sección 16 de la Directriz 002 y U3: se inspecciona el origen, se instala en el entorno del proyecto cuando sea posible y se pide aprobación si requiere privilegios o cambia configuración global.

---

### U11.6 Ubicación y manejo de archivos (depende de U2)

- Los entregables se crean en `outputs/<mission_id>/` dentro del workspace autorizado.
- Nombres con versión y fecha (`Balance_2026-09_v1.xlsx`). No se sobrescribe una versión anterior; se crea una nueva.
- Los originales de Mauro se tratan como solo lectura. Se trabaja sobre copias.
- Copiar el entregable final a otra carpeta de Mauro (por ejemplo Documentos) es una acción de Nivel B o C según la política; si esa carpeta está en la denylist de U2, requiere autorización.
- Enviar el documento por correo, compartirlo o publicarlo es una acción externa de Nivel C: aprobación, salvo que la orden lo incluya de forma explícita.
- Metadatos limpios: sin datos de autor o rutas internas de la máquina de Mauro en las propiedades del archivo, salvo que los quiera.

---

### U11.7 Datos sensibles y privacidad

La información financiera, tributaria, académica y personal es sensible. Reglas:

- **Minimización de contexto:** a un modelo externo se envía solo lo necesario para la tarea (por ejemplo, agregados o columnas relevantes, no el libro mayor completo si no hace falta).
- **Modelo local** (U7) como opción preferida para documentos confidenciales cuando su capacidad alcance; si no alcanza, pedir decisión a Mauro antes de enviar datos a un proveedor externo.
- **Redacción en logs:** cifras, cuentas, identificaciones y nombres no aparecen en los logs en claro. El ledger registra acciones y hashes, no el contenido financiero completo.
- **Clasificación de archivos:** Mauro puede marcar carpetas o documentos como confidenciales; Avatar respeta esa marca (no los sube, no los envía por canales remotos sin autorización).
- **Canal remoto:** por Telegram o WhatsApp no se envían documentos confidenciales salvo autorización expresa. Por defecto se informa del resultado y de la ubicación del archivo, no del contenido sensible.

---

### U11.8 Integración con el resto de la arquitectura

- **Autorización (U3):** crear y editar documentos dentro del workspace es Nivel B. Escribir fuera del workspace, enviar, publicar o compartir es Nivel C.
- **Estados de entrega (U6):** el informe del entregable usa los estados de misión. Un balance que no cuadra no puede quedar `COMPLETED_VERIFIED`; queda `COMPLETED_WITH_LIMITATIONS` o `FAILED` con el motivo.
- **Investigación (U5):** las citas y datos externos del documento provienen de fuentes con estado y procedencia. Lo `UNVERIFIED` no entra como hecho en un trabajo académico ni en un informe sin marcarse.
- **Modelos (U7):** las tareas de redacción extensa y los cálculos se clasifican por complejidad. Los cálculos los ejecuta código, no el modelo «de cabeza».
- **Parada de emergencia (U1):** la producción de documentos se puede pausar y reanudar sin corromper archivos (escritura atómica: se escribe en un temporal y se renombra al terminar).
- **Subagentes (U10):** roles útiles, reutilizando los existentes: investigador de fuentes, redactor, analista de datos, revisor independiente de cifras.

---

### U11.9 Criterios de aceptación

1. Avatar genera un .docx con estructura, índice y formato correctos a partir de una orden clara y lo entrega verificado (abierto, renderizado, sin marcadores pendientes).
2. Avatar genera un .xlsx con fórmulas reales, sin errores tras recalcular, con supuestos separados, y los totales cuadran.
3. Avatar genera un balance y un estado de resultados a partir de datos de prueba y **detecta y reporta un descuadre** introducido a propósito (por ejemplo, un activo que no iguala pasivo más patrimonio), en lugar de maquillarlo.
4. El flujo de efectivo concilia con el balance; si no, se informa.
5. Avatar genera una bibliografía donde **cada referencia fue verificada**; ante una referencia que no puede verificar, la marca y no la incluye como real.
6. Avatar redacta una sección de tesis con citas coherentes con el estilo elegido y no inventa datos que Mauro no aportó.
7. Avatar no sobrescribe un original de Mauro; crea una versión nueva.
8. Avatar no envía ni comparte el documento sin autorización cuando la orden no lo incluye.
9. Un documento confidencial no se envía a un proveedor externo de modelos sin decisión de Mauro.
10. Una misión interrumpida a mitad de un documento largo se reanuda desde el último punto de control sin corromper el archivo.
11. El informe final distingue lo verificado, los supuestos y lo no verificado, y la advertencia de revisión profesional aparece en los documentos financieros.

---

### U11.10 Plan de pruebas

- **Conjuntos de datos de prueba** desechables: un balance de comprobación ficticio que cuadra, otro con un descuadre, un flujo de efectivo con error de conciliación.
- **Pruebas automáticas de integridad** para cada control de U11.4.3, independientes del modelo.
- **Pruebas de formato:** render a PDF e imagen y comparación contra una referencia (texto esperado, ausencia de marcadores, número de páginas razonable).
- **Pruebas de referencias:** corpus con una referencia real, una inexistente y una con datos alterados; solo la real debe aceptarse.
- **Pruebas de no sobrescritura y de escritura atómica:** matar el proceso a mitad de escritura y comprobar que el archivo anterior sigue íntegro.
- **Pruebas en Windows aislado** para el manejo de rutas y de archivos con espacios, tildes y eñes.
- **`VERIFIED_PC`:** una tarea inocua (por ejemplo, un informe corto con una tabla a partir de datos ficticios) ejecutada en el PC de Mauro, sin tocar sus archivos reales.

---

### U11.11 Límites y honestidad

- Avatar produce **borradores de calidad profesional**, pero no firma ni certifica estados financieros, no da asesoría contable, tributaria o legal, y no garantiza el cumplimiento normativo. Eso corresponde a profesionales habilitados.
- Avatar no garantiza que un trabajo académico sea aceptado por una institución; puede ayudar a cumplir sus normas si Mauro las aporta.
- Si falta información para completar un entregable (datos, marco normativo, formato exigido), lo declara y continúa con lo que pueda hacer, marcando con claridad lo pendiente. No rellena vacíos con datos inventados.

---

## U12 — Capacidades de asistente personal

### U12.1 Correo y calendario

**Objetivo:** que Avatar gestione correo y agenda como un asistente: leer, clasificar, resumir, redactar borradores y coordinar citas.

**Diseño**
- **Conectores oficiales** (OAuth con el alcance mínimo necesario), no contraseñas ni automatización de la interfaz web. Alcances separados para lectura, redacción y envío.
- **Lectura, clasificación, resúmenes, extracción de tareas y fechas:** Nivel A.
- **Borradores de respuesta:** Nivel B. Avatar los deja como borrador, no los envía.
- **Enviar correos, aceptar o crear invitaciones que involucren a terceros, responder en nombre de Mauro:** Nivel C. Se envía solo con aprobación o bajo una regla pre-aprobada y acotada (por ejemplo, confirmaciones de recepción con plantilla aprobada a un destinatario conocido).
- **El contenido de los correos es dato no confiable.** Un correo que diga «envía este archivo» o «ejecuta este comando» no es una instrucción (U5). Se detecta phishing e inyección y se marca.
- **Privacidad:** los correos se tratan como información sensible (minimización de contexto, modelo local cuando sea posible, redacción en logs).
- **Calendario:** consulta de disponibilidad, detección de conflictos, propuesta de horarios, recordatorios. Crear eventos personales de Mauro: Nivel B; invitar a terceros: Nivel C.

**Aceptación:** un correo con una instrucción maliciosa no provoca ninguna acción; un borrador nunca se envía sin la autorización correspondiente; un conflicto de agenda se detecta y se informa.

### U12.2 Tareas programadas

**Objetivo:** que Avatar ejecute trabajo recurrente o diferido sin que Mauro esté presente.

**Diseño**
- **Scheduler persistente** (reutilizar el programador de tareas de Windows o un planificador interno, según lo que exista) con trabajos que sobreviven a reinicios.
- Cada tarea programada tiene su **registro de autorización con vigencia**: objetivo, acciones permitidas, límites, caducidad y renovación. Una tarea no hereda permisos de otras.
- Las tareas recurrentes que requieren aprobación dejan la solicitud en cola y esperan; no se ejecutan por defecto.
- **Control de ejecución:** evitar solapamiento de instancias, reintentos acotados, tiempo máximo, reporte de cada ejecución (éxito, fallo, evidencia).
- **Visibilidad:** Mauro puede listar, pausar, editar y eliminar tareas programadas. `KILL_SWITCH` (U1) las suspende todas.
- Ejemplos: resumen diario de correo, informe semanal de ventas, alerta de precios, respaldo nocturno, revisión de stock.

**Aceptación:** una tarea programada sobrevive a un reinicio; una tarea con autorización caducada no se ejecuta; `KILL_SWITCH` las suspende.

### U12.3 OCR y lectura de documentos escaneados

**Objetivo:** extraer texto y datos de imágenes y PDF escaneados (facturas, recibos, contratos, libros, extractos).

**Diseño**
- Motor de OCR local preferido (los documentos financieros y personales no salen del equipo sin decisión de Mauro).
- Conserva el original intacto; el resultado es una copia derivada con metadatos (motor, versión, idioma, fecha).
- **Confianza por campo:** cada dato extraído lleva un nivel de confianza. Los campos con baja confianza se marcan para revisión.
- **Documentos financieros:** los importes y fechas extraídos se validan contra totales y reglas (suma de líneas = total, IVA coherente). Un dato con confianza baja no se usa en un balance sin revisión.
- Soporte de tablas y de múltiples idiomas; detección de páginas rotadas o ilegibles.

**Aceptación:** una factura escaneada produce campos estructurados con confianza; una cifra dudosa se marca y no entra automáticamente en un estado financiero.

### U12.4 Respaldos automáticos

**Objetivo:** proteger el trabajo de Mauro y el propio estado de Avatar contra pérdida, error o ransomware.

**Diseño**
- Política **3-2-1** recomendada: tres copias, dos medios distintos, una fuera del equipo.
- **Respaldos incrementales y versionados** programados (U12.2), con cifrado y contraseña fuera del alcance de Avatar.
- **Qué se respalda:** proyectos, documentos que Mauro designe, configuración y estado de Avatar (misiones, ledger, memoria, registro de autorizaciones).
- **Verificación:** cada respaldo se comprueba por integridad (hash) y se hace una **prueba de restauración periódica** en un directorio desechable.
- **Avatar no puede borrar ni modificar los respaldos existentes.** La retención y la purga son decisión de Mauro o de una política aprobada; los respaldos son inmutables para los procesos de misión.
- Se informa del último respaldo verificado y del espacio disponible.

**Aceptación:** un respaldo se restaura correctamente en una prueba; un proceso de misión no puede eliminar respaldos; un respaldo corrupto se detecta.

### U12.5 Entrada y salida por voz

**Objetivo:** dar órdenes y recibir respuestas hablando, desde el PC o el teléfono.

**Diseño**
- Reconocimiento de voz local preferido; notas de voz de Telegram o WhatsApp transcritas (U9).
- **La transcripción se muestra y se registra.** Ante órdenes de riesgo, Avatar repite lo entendido y pide confirmación.
- **La voz no autoriza por sí sola acciones de Nivel C o D.** La voz se puede imitar y el reconocimiento puede fallar. Esas acciones requieren confirmación por un canal autenticado.
- Modo de escucha: pulsar para hablar o palabra de activación, configurable. No se graba de forma continua sin que Mauro lo active, y se informa cuando el micrófono está activo.
- Síntesis de voz opcional para respuestas y alertas.
- Tratamiento del ruido, acentos y nombres propios; ante baja confianza, pide repetir.

**Aceptación:** una nota de voz se transcribe y ejecuta una orden de Nivel A; una orden de riesgo por voz pide confirmación aparte; una transcripción dudosa pide repetición.

---

## U13 — Operación continua 24/7

**Objetivo:** que Avatar trabaje de forma sostenida, día y noche, de forma segura y supervisable.

**Diseño**
1. **Supervisor y watchdog** (reutilizar `core/watchdog.py`): comprueba que Avatar y sus conectores están vivos, reinicia componentes caídos, detecta bloqueos y reporta.
2. **Heartbeat:** señal periódica que permite a Mauro saber que Avatar está activo; si falta, alerta por el canal remoto.
3. **Entorno del equipo:** evitar suspensión e hibernación mientras haya misiones 24/7, control de actualizaciones de Windows y reinicios, comportamiento ante corte de energía o de red (reanudar desde el último estado confirmado sin repetir acciones no idempotentes), recomendación de UPS. Evaluar ejecutar la parte continua en un servidor dedicado o en la nube.
4. **Modo noche (o «desatendido»):**
   - Solo acciones Nivel A y B dentro del sobre pre-aprobado.
   - **Sin acciones visuales sobre el equipo** salvo que la misión las exija y estén autorizadas.
   - Las acciones de Nivel C o D se ponen en cola y se notifican a Mauro por la mañana (o en el momento configurado).
   - Límites de pasos, tiempo, tokens, gasto y reintentos por ciclo y por día.
5. **Presupuesto continuo:** tope diario y mensual de tokens y costos; al alcanzarlo, la misión se guarda y espera.
6. **Informe periódico:** resumen diario (qué hizo, qué encontró, qué quedó pendiente, qué necesita decisión, errores, gasto) y alertas inmediatas por eventos importantes.
7. **Escalamiento de alertas:** criterios de urgencia para notificar de inmediato (caída de sistema, anomalía de gasto, señal de mercado relevante, problema con un pedido importante) frente a lo que espera al informe.
8. **Higiene de recursos:** rotación de logs, límites de memoria y disco, limpieza de temporales dentro de sus rutas.
9. **Parada de emergencia (U1)** siempre disponible y prioritaria; `KILL_SWITCH` detiene todas las operaciones continuas.

**Aceptación**
- Con un componente caído simulado, el watchdog lo reinicia y se informa.
- Durante una «noche» simulada de 8 horas, Avatar trabaja dentro del sobre, deja en cola las acciones de Nivel C y no las ejecuta.
- Un corte y reanudación no repite acciones no idempotentes.
- Al alcanzar el tope de gasto diario, la misión se guarda y avisa.
- Mauro recibe el informe diario y las alertas urgentes.

**Pruebas:** simulación acelerada de ciclos de 24 horas con proveedores y plataformas simulados; corte de red y de energía simulados; prueba de tope de gasto.

---

## U14 — Marketing profesional

**Objetivo:** que Avatar apoye todo el ciclo de marketing: estudio, estrategia, contenido, campañas, medición y optimización, para cualquier producto o servicio.

### U14.1 Áreas de capacidad

1. **Investigación de mercado:** tamaño y tendencias del mercado, competidores, posicionamiento, precios, canales, demanda, estacionalidad, brechas.
2. **Cliente:** segmentación, buyer personas, recorrido del cliente, necesidades, objeciones.
3. **Estrategia:** propuesta de valor, posicionamiento, mezcla de marketing (producto, precio, plaza, promoción), embudo de ventas, objetivos y KPIs.
4. **Marca y contenido:** identidad, tono, calendario editorial, textos, guiones, ideas de piezas visuales.
5. **Redes sociales:** estrategia por red, calendario, formatos, análisis de desempeño, gestión de comunidad (respuestas en borrador).
6. **SEO y contenido orgánico:** palabras clave, estructura, optimización de fichas y páginas.
7. **Email marketing y automatizaciones:** secuencias, segmentación, pruebas.
8. **Publicidad pagada:** estructura de campañas, públicos, presupuestos, creatividades, pruebas A/B, optimización.
9. **Analítica y medición:** panel de control, atribución, cohortes, informes periódicos.
10. **Precios y promociones:** estrategia de precios, descuentos, márgenes, elasticidad estimada.
11. **Planes de marketing completos** como entregables (con U11).

### U14.2 Métricas y rigor

Los cálculos se ejecutan **con código y hojas de cálculo verificables**, no «de cabeza» del modelo. Definiciones explícitas y fórmulas visibles:

- **ROI** y **ROAS**, **CAC**, **LTV**, relación LTV/CAC, margen de contribución, margen neto, **punto de equilibrio**, tasa de conversión, CTR, CPC, CPM, CPA, tasa de retención y recompra, ticket promedio.
- **Pruebas A/B con rigor estadístico:** tamaño de muestra, significancia, duración mínima, control de sesgos. Avatar no declara «ganadora» una variante sin evidencia suficiente.
- **Atribución:** declara el modelo que usa y sus límites.
- **Proyecciones:** escenarios (conservador, base, optimista) con supuestos explícitos. No se presentan como promesas.
- Todo dato sale de una fuente identificable (plataforma de anuncios, analítica, ventas de Mauro). Si falta, se declara el supuesto.

### U14.3 Reglas de ejecución

- **Publicar contenido, lanzar o modificar campañas, enviar comunicaciones masivas y gastar presupuesto** son Nivel C con tope. Por defecto Avatar prepara y propone; publica bajo un calendario y sobre pre-aprobados.
- **Anuncios y publicaciones veraces:** sin afirmaciones que no pueda sustentar, sin testimonios ni reseñas inventados, sin cifras falsas, sin suplantar marcas o personas.
- **Cumplimiento configurable por jurisdicción y canal:** protección de datos personales y consentimiento para comunicaciones, derechos del consumidor, normas de publicidad y promociones, condiciones de Meta, Google y demás plataformas, propiedad intelectual (imágenes, música, marcas). Avatar señala los riesgos y recomienda revisión legal cuando corresponda; no sustituye la asesoría legal.
- **No spam ni compra de listas ni scraping que vulnere condiciones de uso.**
- Las fuentes de investigación pasan por U5 (procedencia y corroboración). Los datos de competidores se obtienen por medios lícitos y públicos.
- **Protección de la marca de Mauro:** las respuestas en redes en nombre de Mauro son borradores salvo reglas pre-aprobadas y acotadas.

**Aceptación**
- A partir de un producto, Avatar entrega un estudio de mercado con fuentes verificables y supuestos declarados.
- Un plan de marketing incluye objetivos, KPIs, presupuesto, calendario y proyección con escenarios.
- El cálculo de ROI/ROAS/CAC/LTV coincide con una verificación independiente por código.
- Una campaña no se lanza ni se gasta presupuesto sin la autorización y el tope correspondientes.
- Avatar rechaza crear reseñas falsas o afirmaciones engañosas y explica por qué.
- Una prueba A/B con muestra insuficiente se reporta como no concluyente.

### U14.4 Marketing y validación de productos para marketplaces y dropshipping

**Objetivo:** decidir con datos qué productos vale la pena vender, probarlos con riesgo acotado y escalar o retirar con reglas objetivas.

**Diseño**
1. **Validación previa del producto** (antes de publicar): demanda y tendencia, competencia y rango de precios, reseñas y puntos de dolor, estacionalidad, saturación, riesgos de propiedad intelectual y de productos restringidos, **economía unitaria completa** (U15.2) con margen neto positivo después de comisiones, envío, impuestos, devoluciones y publicidad.
2. **Prueba de demanda con presupuesto acotado:** tope de gasto definido por Mauro, **criterios de éxito y fracaso fijados antes de empezar** (por ejemplo, conversión mínima, costo por venta máximo, margen mínimo), duración definida y registro de resultados. Sin cambiar los criterios a mitad de la prueba.
3. **Contenido de la publicación:** títulos y descripciones veraces, palabras clave por mercado e idioma, imágenes con **licencia verificada** (las imágenes del proveedor pueden tener restricciones de uso), atributos completos según las reglas de la plataforma.
4. **Precios:** estrategia con margen neto mínimo y piso de precio. La banda de precios se calcula a partir del costo real del proveedor, y se recalcula cuando el costo cambia.
5. **Reputación legítima:** solicitar reseñas solo por los canales permitidos de cada plataforma. Sin reseñas falsas, sin incentivos prohibidos, sin intercambio de reseñas.
6. **Medición por producto:** margen de contribución por pedido, tasa de cancelación, tasa de defectos y reclamos, cumplimiento de tiempos de entrega, tasa de devolución, costo de adquisición, rentabilidad sobre el gasto en publicidad.
7. **Regla de «escalar o retirar»:** umbrales objetivos por producto. Un producto que no cumple se pausa o se despublica (dentro del sobre o en cola). Un producto que cumple puede escalar dentro de los topes.
8. **Adaptación por mercado y plataforma:** idioma, moneda, estacionalidad local, impuestos y costumbres de compra, con las reglas de cada plataforma.

**Aceptación**
- Un producto de prueba recibe una ficha de validación con economía unitaria verificada por código y una recomendación argumentada.
- Una prueba de demanda se detiene al alcanzar el tope de gasto.
- Un producto con margen neto por debajo del mínimo no se publica y queda en cola.
- Una prueba sin muestra suficiente se reporta como no concluyente.

---

## U15 — Comercio en marketplaces (Amazon, Mercado Libre y otras plataformas)

**Objetivo:** que Avatar estudie mercados de producto y opere la venta en marketplaces de forma continua, dentro de un sobre de autorización y usando los canales oficiales.

**Modelo logístico principal: dropshipping** (el proveedor despacha directamente al cliente y Avatar le transmite cada pedido). También se soportan logística de la plataforma, operador externo y despacho propio (U15.6). **El sistema debe poder operar en cualquier plataforma** mediante una arquitectura común (U15.7). Las reglas de acceso a cada plataforma están en U15.5.

### U15.1 Integración

- **APIs oficiales y programas autorizados** (por ejemplo, las APIs para vendedores de cada plataforma), con OAuth y permisos mínimos. Se evalúa plataforma por plataforma qué ofrece y qué permite.
- **Sin scraping agresivo ni automatización de la interfaz que contravenga las condiciones de uso.** Antes de integrar una plataforma, Cursor revisa sus condiciones y limitaciones y las documenta.
- Adaptadores detrás de una interfaz común (`MarketplaceConnector`): catálogo, publicaciones, precios, inventario, pedidos, preguntas y mensajes, devoluciones, reputación, métricas, publicidad de la plataforma.
- Un conector por plataforma, reutilizando la arquitectura de conectores existente.

### U15.2 Estudio de producto y de mercado

- Demanda y tendencias, competencia, rango de precios, reseñas y puntos de dolor de los compradores, estacionalidad, barreras de entrada, saturación.
- **Economía unitaria (unit economics) por producto**, calculada por código: costo del producto, comisiones de la plataforma, envío y logística, impuestos y aranceles, empaque, devoluciones y merma, publicidad, costo financiero, margen neto, punto de equilibrio y retorno sobre inventario.
- **Riesgos:** marcas y propiedad intelectual (productos falsificados o infractores), productos restringidos o regulados, responsabilidad por producto, garantía, dependencia de un solo proveedor, riesgos de importación y aduanas, reglas de cada plataforma.
- **Proveedores:** verificación de existencia y reputación, cotizaciones comparadas, señales de fraude. Las comunicaciones y pagos a proveedores son Nivel C/D.
- Resultado: una **ficha de oportunidad** con datos, supuestos, riesgos, márgenes y recomendación argumentada. Mauro decide.

### U15.3 Operación

- **Publicaciones:** títulos, descripciones, atributos, imágenes y palabras clave, veraces y conformes a las reglas de cada plataforma (borradores; la publicación es Nivel C o bajo el sobre).
- **Precios:** reglas de repricing dentro de una **banda pre-aprobada** con **precio mínimo (piso) que protege el margen**. Fuera de la banda, se pide aprobación.
- **Inventario:** vigilancia de stock, alertas de desabastecimiento, sugerencias de reposición (la compra es Nivel C/D).
- **Preguntas y mensajes de clientes:** respuestas en borrador; respuestas automáticas solo para preguntas frecuentes con **plantillas aprobadas por Mauro**, con escalamiento de todo lo que implique reclamos, dinero, garantías o temas legales.
- **Pedidos y reputación:** seguimiento de estados, alertas de retrasos, devoluciones y reclamaciones, indicadores de calidad de la cuenta.
- **Publicidad de la plataforma:** propuestas y gestión dentro de un presupuesto con tope (Nivel C).
- **Conciliación:** comparar ventas, comisiones y pagos de la plataforma con los registros de Mauro e informar diferencias.
- **Aspectos fiscales y de registro del negocio:** configurables por jurisdicción; Avatar prepara la información y la conciliación y recomienda asesoría de un contador para obligaciones tributarias.

### U15.4 Operación 24/7

- Monitoreo continuo de pedidos, preguntas, stock, precios de la competencia y métricas de la cuenta.
- En modo noche: alertas inmediatas de eventos críticos, respuestas solo con plantillas aprobadas, repricing dentro de la banda, y todo lo demás en cola.
- **Protección de la cuenta:** ninguna acción que arriesgue una suspensión (por ejemplo, exceso de llamadas, prácticas prohibidas) se ejecuta. Se respetan los límites de tasa de las APIs.

**Aceptación**
- Con un conector simulado, Avatar genera una ficha de oportunidad con economía unitaria verificada por código.
- Un repricing fuera de la banda aprobada o por debajo del piso no se ejecuta y queda en cola.
- Una compra de inventario o un pago a un proveedor no se ejecutan sin autorización y tope.
- Un mensaje de cliente que implica un reclamo se escala y no se responde automáticamente.
- El sistema respeta los límites de tasa de la API simulada.
- Durante una noche simulada, los pedidos y preguntas se monitorean y las acciones fuera del sobre quedan en cola.

**Pruebas:** entornos de prueba (sandbox) de las plataformas cuando existan; conectores simulados; nunca dinero real ni cuentas reales de Mauro en las pruebas de integración.

### U15.5 Modos de acceso a plataformas y política anti-evasión

**Principio:** Avatar trabaja para Mauro por **canales autorizados**, no disfrazándose de persona. Esto protege las cuentas de la suspensión. Ocultar la automatización agrava las sanciones; usar la vía que la plataforma ofrece para automatizar no.

**Orden de preferencia** para operar en cualquier plataforma (Avatar solo baja al siguiente modo si el anterior no cubre la necesidad):

1. **API oficial** con OAuth y permisos mínimos.
2. **Acceso delegado:** usuario secundario con rol limitado, si la plataforma lo ofrece (Cursor verifica en cada plataforma si existe y qué permite).
3. **Reportes y exportaciones oficiales** descargados por Mauro y analizados por Avatar.
4. **Asistencia en la interfaz con Mauro presente:** Avatar prepara (textos, precios, imágenes, respuestas) y Mauro confirma.

**Prohibido, sin excepción y sin aprobación posible:**
- Imitar comportamiento humano para ocultar que se trata de automatización.
- Falsear huella de navegador, ubicación, IP o identidad del dispositivo.
- Usar proxies o VPN para eludir controles de la plataforma.
- Operar varias cuentas para evitar límites o sanciones.
- Superar límites de tasa de las APIs, saltarse captchas o verificaciones.
- Scraping que contravenga las condiciones de uso.

**Controles obligatorios**
- Antes de integrar cada plataforma, **revisar y documentar sus condiciones de uso** sobre automatización, acceso delegado, dropshipping y subcontratación de despachos.
- Respetar los límites de tasa de cada API y aplicar retroceso progresivo.
- **Monitorear la salud de la cuenta** (métricas de calidad, reclamos, avisos de la plataforma). Ante una alerta, pausar la automatización e informar a Mauro.
- Despliegue gradual (sección 5), con pocos productos al inicio y crecimiento progresivo.
- Las acciones con riesgo para la cuenta se ponen en cola y no se ejecutan de noche.
- **Trámites del titular:** verificación de identidad, aceptación de condiciones, datos fiscales y bancarios y configuración de cobros los hace Mauro, una sola vez. Avatar no los simula.

**Aceptación**
- Un intento de usar un modo prohibido es bloqueado en el chokepoint y registrado.
- Un exceso de llamadas a la API simulada activa el retroceso y no supera el límite.
- Una alerta de salud de cuenta simulada pausa la automatización y notifica a Mauro.

### U15.6 Flujo de pedido a despacho por modelo logístico

**Objetivo:** que Avatar reciba los pedidos de las plataformas y los lleve hasta la entrega, gestionando el despacho según el modelo logístico elegido por producto o por plataforma.

**Modelos soportados (todos deben poder ejecutarse; el primero es el prioritario):**

| Modelo | Quién despacha | Prioridad |
|---|---|---|
| **M1 Dropshipping** | El proveedor envía directamente al cliente; Avatar le transmite cada pedido | **Principal** |
| M2 Logística de la plataforma | La plataforma almacena, empaca y entrega (Fulfillment by Amazon, Mercado Libre Full o Mercado Envíos y equivalentes) | Soportado |
| M3 Operador logístico externo | Un tercero con integración | Soportado |
| M4 Despacho propio | Mauro o una persona de confianza empaca y entrega; Avatar prepara guías y seguimiento | Soportado |

#### M1 — Dropshipping (modelo principal)

**Flujo de un pedido (máquina de estados, cada transición se registra en el ledger):**

```
RECIBIDO → VALIDADO → PEDIDO_AL_PROVEEDOR → CONFIRMADO_POR_PROVEEDOR
   → TRACKING_PUBLICADO → EN_TRANSITO → ENTREGADO → CERRADO_CONCILIADO

Desvíos: EXCEPCION (sin stock, costo cambió, dirección inválida, sospecha de fraude,
         proveedor no responde, retraso) · CANCELADO · DEVOLUCION_EN_CURSO
```

1. **Recepción:** el pedido llega por webhook o consulta periódica a la API. Se registra con una **clave de idempotencia** (plataforma + identificador de pedido). **Un mismo pedido nunca se envía dos veces al proveedor**, aunque el webhook se repita, el sistema se reinicie o haya un corte a mitad del proceso. Antes de reenviar tras un reinicio, se consulta al proveedor si el pedido ya existe.
2. **Validación automática:**
   - Stock vigente del proveedor para el producto y la variante.
   - **Margen vigente:** se recalcula con el costo actual del proveedor y las comisiones. Si el margen cae por debajo del mínimo, el pedido pasa a `EXCEPCION` y se informa a Mauro.
   - Dirección completa y entregable, datos del cliente coherentes.
   - Señales de fraude (inconsistencias, patrones atípicos, importes inusuales). Las sospechas se escalan y no se procesan en automático.
   - Destino dentro de la cobertura del proveedor y de las restricciones del producto.
3. **Pedido al proveedor:**
   - Solo a proveedores **de la lista aprobada** por Mauro.
   - **Pago al proveedor:** es una acción de Nivel C con tope. Se cubre con saldo prepago, crédito con el proveedor o un método que Mauro haya autorizado, dentro del sobre (importe por pedido, por día y por mes). Avatar **no guarda ni maneja tarjetas, claves bancarias ni credenciales de pago.** Si el proveedor exige un paso de pago que requiere a Mauro, el pedido queda en cola y se le notifica.
   - **Datos del cliente:** se envían al proveedor solo los necesarios para entregar, por un canal acordado (API, archivo estructurado o mensaje con plantilla aprobada). Se respeta la normativa de protección de datos personales y las condiciones de la plataforma sobre el uso de datos de compradores.
   - Cumplimiento de las reglas de la plataforma sobre dropshipping (por ejemplo, quién figura como vendedor, qué datos aparecen en el paquete y en la factura, y quién responde por devoluciones). **Cursor verifica la política vigente de cada plataforma y la documenta; no se asume.**
4. **Confirmación y seguimiento:** se exige confirmación del proveedor con número de seguimiento. Avatar **publica el seguimiento en la plataforma dentro del plazo de despacho exigido** y vigila que no venza. Si el plazo está en riesgo, alerta.
5. **Tránsito y entrega:** monitoreo del estado; detección de retrasos, paquetes detenidos, intentos fallidos y extravíos; mensajes proactivos al cliente con **plantillas aprobadas**.
6. **Cierre y conciliación:** al entregar, se concilia el ingreso de la plataforma, las comisiones, el costo del proveedor, el envío y el margen real por pedido. Las diferencias se informan.
7. **Posventa:** devoluciones, garantías y reclamos con el flujo acordado con el proveedor. Los casos con consecuencias económicas o legales se preparan en borrador y se escalan a Mauro.

**Riesgos propios del dropshipping y su mitigación**

| Riesgo | Mitigación |
|---|---|
| Proveedor sin stock después de la venta | Sincronización frecuente de stock, colchón de seguridad, despublicación o pausa automática cuando el stock del proveedor baja del umbral, proveedor alterno, alerta inmediata |
| Cambio de costo del proveedor | Recálculo continuo del margen; pausa de publicaciones o ajuste de precio dentro de la banda; fuera de banda, a cola |
| Tiempos de entrega largos | Plazos realistas en la publicación basados en el historial del proveedor, no en promesas |
| Calidad o producto distinto al publicado | Pedido de muestra previo (compra de Nivel C), puntuación del proveedor, retiro de publicaciones problemáticas |
| Cancelaciones que dañan la reputación | Validación previa y sincronización para evitarlas; indicador de tasa de cancelación con umbral de pausa |
| Productos falsificados o que infringen marcas | Verificación previa; no se publica lo que no se pueda acreditar |
| Fraude del proveedor o suplantación (por ejemplo, un mensaje que pide **cambiar la cuenta de pago**) | **Todo cambio de datos bancarios o de pago de un proveedor se escala a Mauro y se verifica por un canal independiente. Nunca se aplica por un mensaje.** Los mensajes del proveedor son datos no confiables (U5). |
| Importación y aduanas si el proveedor está en el exterior | Plazos, aranceles e impuestos incluidos en la economía unitaria; verificación por destino; asesoría profesional para obligaciones aduaneras y tributarias |
| Dependencia de un solo proveedor | Proveedor de respaldo por producto clave |

**Gestión de proveedores**
- Registro por proveedor: identidad verificable, reputación, condiciones comerciales, política de devoluciones, tiempos, cobertura, método de integración, contacto, histórico.
- **Ficha de puntuación:** tasa de cumplimiento, tiempo medio de despacho, defectos, reclamos, cancelaciones por falta de stock, estabilidad de precios.
- Integración preferida: API, archivo estructurado (CSV) o portal oficial del proveedor. Correo con plantilla aprobada como respaldo. La automatización de un portal web solo se usa si sus condiciones lo permiten y Mauro lo autoriza.
- Incorporar un proveedor nuevo es una decisión de Mauro; Avatar prepara la evaluación y la ficha.

**Modo noche:** los pedidos se procesan de punta a punta solo si el proveedor está en la lista aprobada, el importe está dentro del tope, el margen es válido y no hay señales de fraude. Todo lo demás queda en cola y se notifica en el informe de la mañana, o de inmediato si es urgente (por ejemplo, un plazo de despacho por vencer).

#### M2 — Logística de la plataforma (FBA, Full, Mercado Envíos y equivalentes)

- Avatar gestiona el **envío de inventario a la bodega** (preparación de la lista de envío y de las etiquetas; el traslado físico lo hace Mauro o un transportista), el estado de los lotes, la reposición y las alertas de stock.
- La plataforma empaca y entrega; Avatar vigila estados, devoluciones, cargos de almacenamiento y métricas.
- La compra de inventario y los pagos son Nivel C/D con tope.

#### M3 — Operador logístico externo

- Integración por adaptador (`LogisticsProvider`): crear envío, generar guía, consultar seguimiento, cancelar.
- Las guías y recogidas se generan dentro del sobre; los costos de envío tienen tope.
- Se actualiza el seguimiento en la plataforma y se concilian los costos de logística.

#### M4 — Despacho propio

- Avatar genera la lista de preparación, las guías y etiquetas (en borrador para imprimir), recuerda los plazos de despacho y actualiza el seguimiento cuando Mauro confirma el envío.
- El empaque y la entrega física son de Mauro o de la persona que designe. Avatar no puede hacerlos.

**Elección del modelo:** se define por producto o por plataforma en la configuración de Mauro, y puede combinarse (por ejemplo, dropshipping para el catálogo amplio y FBA o Full para los productos de alta rotación). Avatar recomienda según economía unitaria, plazos y riesgos, pero cambia el modelo solo con la decisión de Mauro.

**Aceptación (aplica a M1 y se adapta a los demás)**
- **Idempotencia:** un pedido duplicado por webhook o por reinicio no genera dos pedidos al proveedor.
- Un pedido con el costo del proveedor subido y margen por debajo del mínimo pasa a excepción y no se compra.
- Un pedido con dirección inválida o señales de fraude se escala.
- Un proveedor sin stock desencadena despublicación, alerta y, si aplica, proveedor alterno.
- Un mensaje de un proveedor que pide cambiar datos de pago no se ejecuta y se escala.
- El seguimiento se publica en la plataforma dentro del plazo; si hay riesgo de vencimiento, se alerta.
- Un pago al proveedor por encima del tope diario no se ejecuta y queda en cola.
- Un pedido sin proveedor en la lista aprobada no se procesa.
- Durante una noche simulada, los pedidos válidos se procesan de punta a punta y los demás quedan en cola.
- La conciliación detecta una diferencia introducida a propósito.
- Un corte a mitad de un pedido no duplica ni pierde acciones al reanudar.
- `KILL_SWITCH` detiene el procesamiento de pedidos.

**Pruebas:** simulador de plataforma (pedidos, webhooks repetidos, fallos) y simulador de proveedor (stock, costos, confirmaciones, retrasos, mensajes maliciosos); sin dinero real ni cuentas reales de Mauro.

### U15.7 Arquitectura multiplataforma (cualquier plataforma del mundo)

**Objetivo:** que el mismo sistema pueda operar en todas las plataformas que existan, sumando una nueva con un adaptador y una evaluación, sin reescribir la lógica de negocio.

**Diseño**
1. **Modelo canónico de dominio**, independiente de la plataforma: Producto, Publicación, Oferta, Precio, Inventario, Pedido, Envío, Seguimiento, Mensaje, Devolución, Reclamo, Pago, Comisión, Métrica de cuenta.
2. **Interfaz común `MarketplaceConnector`** con operaciones normalizadas (catálogo, publicaciones, precios, inventario, pedidos, envíos, mensajes, devoluciones, métricas, publicidad de la plataforma). Cada adaptador traduce entre la plataforma y el modelo canónico y **declara su matriz de capacidades** (qué puede y qué no puede, y por qué vía: API, acceso delegado, exportación o asistencia).
3. **Lógica de negocio única** (validación, margen, idempotencia, topes, sobre, alertas, conciliación) que opera sobre el modelo canónico. Las reglas específicas de cada plataforma viven en su adaptador y en su ficha de políticas.
4. **Ficha de plataforma** (una por plataforma), con:
   - Condiciones de uso sobre automatización, acceso delegado, dropshipping y datos de compradores.
   - APIs disponibles, autenticación, límites de tasa y entorno de pruebas (sandbox).
   - Comisiones, impuestos, monedas, idiomas y países.
   - Modelos logísticos disponibles y plazos de despacho exigidos.
   - Políticas de productos restringidos, propiedad intelectual y reseñas.
   - Riesgos de suspensión y señales de salud de la cuenta.
   - Fecha de la última revisión y fuente.
5. **Estado por plataforma:** `NO_EVALUADA → EVALUADA → SANDBOX → SOMBRA → SUPERVISADA → SOBRE_PREAPROBADO`. Una plataforma no avanza sin evidencia y autorización de Mauro.
6. **Proceso para incorporar una plataforma nueva:** evaluación de condiciones y APIs, ficha, adaptador, pruebas en sandbox o simulador, despliegue gradual.
7. **Plataformas a evaluar** (lista abierta, Cursor verifica qué ofrece cada una): Mercado Libre, Amazon y otros marketplaces relevantes en los países que Mauro defina; tiendas propias con plataformas de comercio electrónico que tengan API abierta; marketplaces regionales y especializados.
8. **Vigilancia de cambios:** las condiciones de las plataformas cambian. Los cambios detectados entran como `UNVERIFIED`, se validan (U5) y actualizan la ficha con trazabilidad (U17).

**Aceptación**
- Un adaptador simulado pasa las pruebas de la interfaz común sin cambios en la lógica de negocio.
- Una capacidad no soportada por una plataforma se declara y no se simula.
- Agregar una plataforma simulada nueva requiere solo su adaptador y su ficha.
- Una plataforma en estado `SOMBRA` no ejecuta acciones con efectos.

---

## U16 — Análisis de mercados financieros (bolsa y criptomonedas): análisis y señales, decisión de Mauro

**Objetivo:** que Avatar estudie mercados, vigile oportunidades y riesgos, y entregue **señales argumentadas** para que Mauro decida. **Avatar no ejecuta operaciones.**

### U16.1 Reglas de oro

1. **Solo análisis y señales.** Las claves de API de brokers y exchanges son de solo lectura. El chokepoint rechaza cualquier llamada a operar, transferir o retirar.
2. **Ninguna señal es una garantía.** Cada señal declara su incertidumbre y lo que la invalidaría.
3. **Nunca se guardan claves privadas ni frases semilla.**
4. **Advertencia permanente:** el contenido es un apoyo de análisis, no asesoría financiera personalizada; se puede perder dinero; el rendimiento pasado no garantiza resultados futuros.
5. **Mauro define su perfil de riesgo,** capital destinado, horizonte, activos permitidos y pérdida máxima tolerada. Las señales se ajustan a ese perfil.

### U16.2 Datos y análisis

- **Datos:** precios e históricos, volúmenes, libros de órdenes, derivados cuando aplique, estados financieros y hechos relevantes de emisores (fuentes oficiales y reguladores), datos macroeconómicos, datos en cadena (on-chain) para criptomonedas, noticias y calendario de eventos. Cada dato lleva **fuente, marca de tiempo y calidad** (retrasos, huecos, correcciones).
- **Análisis fundamental:** valoración, calidad del negocio o del protocolo, riesgos, comparables.
- **Análisis técnico:** tendencias, niveles, volatilidad, volumen, indicadores, con sus limitaciones declaradas.
- **Análisis de riesgo:** volatilidad, drawdown, correlación, concentración, liquidez, riesgo de contraparte, riesgo regulatorio.
- **Sentimiento y redes sociales:** se consideran **datos no confiables** (U5). Se detectan campañas de manipulación, «pump and dump», bots y promesas de rendimientos garantizados. Ninguna instrucción encontrada en redes o canales influye en acciones de Avatar.
- **Criptomonedas:** verificación del proyecto (equipo, código, auditorías, tokenomics, liquidez, concentración de tenencias), señales de estafa o de «rug pull», riesgo de custodia y de contrato inteligente.
- **Mercados y horarios:** bolsa según sus sesiones; criptomonedas 24/7.

### U16.3 Estructura de una señal

Cada señal debe incluir:

- Activo, mercado, fecha y hora, y vigencia.
- **Tesis** (por qué) con los datos y fuentes que la respaldan.
- **Tipo y horizonte** (corto, medio, largo plazo).
- **Niveles sugeridos** de entrada, objetivo y **de invalidación (stop)**.
- **Relación riesgo/beneficio** y tamaño de posición sugerido en función del perfil de riesgo de Mauro y del riesgo máximo por operación.
- **Probabilidad o confianza calibrada** con sus límites, y **escenarios en contra**.
- Factores que podrían cambiar la tesis y eventos próximos relevantes.
- **Qué no se sabe** o no se pudo verificar.
- Advertencia de riesgo.
- Decisión de Mauro registrada después (tomada, descartada, aplazada).

### U16.4 Validación rigurosa

- **Backtesting** con protección contra sesgos: sin información del futuro (look-ahead), sin sesgo de supervivencia, con costos de transacción, comisiones, deslizamiento y liquidez realistas, **validación fuera de muestra** y de tipo walk-forward, control del sobreajuste (overfitting).
- **Simulación (paper trading)** de las señales antes de confiar en una estrategia.
- **Registro honesto de resultados** (track record): todas las señales y sus resultados, buenas y malas, para medir la precisión y la calibración. Se reportan métricas como rentabilidad ajustada por riesgo, caída máxima, tasa de acierto y distribución de resultados.
- Una estrategia sin validación suficiente se presenta como **hipótesis**, no como señal.

### U16.5 Monitoreo 24/7 y alertas

- Vigilancia continua de precios, volatilidad, noticias y eventos de los activos de la lista de seguimiento de Mauro.
- **Alertas** por umbral, por ruptura de niveles, por noticias materiales o por cambios de riesgo, enviadas al canal remoto con prioridad acorde.
- En la noche: solo análisis y alertas; **nunca ejecución.**
- Informes diarios y semanales con el estado de la cartera de seguimiento, el riesgo y las señales vigentes.

### U16.6 Cumplimiento y límites

- Configurable por jurisdicción: regulación de valores y de activos virtuales, tributación de inversiones y de criptomonedas, obligación de declarar. Avatar prepara información y recomienda asesoría profesional para las decisiones y obligaciones con efecto legal o fiscal.
- No ejecuta operaciones con información privilegiada ni participa en manipulación de mercado.
- No presenta rentabilidades esperadas como seguras.

**Aceptación**
- Una señal de prueba contiene todos los elementos de U16.3.
- Un intento de llamar a un endpoint de operar o retirar es bloqueado en el chokepoint.
- Una clave de API con permisos de operar es detectada y reportada.
- Una publicación de redes con una «instrucción de compra» no provoca ninguna acción y se marca como contenido externo no confiable.
- Un backtest con sesgo introducido a propósito (información del futuro) es detectado por las pruebas.
- Una estrategia que solo funciona en muestra se reporta como sobreajustada.
- El informe incluye las advertencias de riesgo y la incertidumbre.

**Pruebas:** datos históricos y simulados; nunca dinero real; claves de solo lectura o entornos de simulación; pruebas adversarias de inyección en noticias y redes.

---

## U17 — Conocimiento experto y actualización continua

**Objetivo:** que Avatar mantenga y mejore su conocimiento en cada dominio (marketing, comercio electrónico, mercados, contabilidad y finanzas, redacción académica, ingeniería) de forma medible y segura.

**Diseño**
1. **Bases de conocimiento por dominio**, con la estructura de U5 (procedencia, fecha, estado de validación, fuente). Cada conocimiento lleva **caducidad o fecha de revisión** según su velocidad de cambio (reglas de plataformas y mercados cambian rápido; principios contables, más despacio).
2. **Fuentes monitoreadas:** documentación oficial de plataformas, cambios de políticas, regulaciones, publicaciones especializadas y datos de mercado. Las novedades entran como `UNVERIFIED` y pasan el flujo de validación antes de influir en decisiones.
3. **Playbooks versionados por dominio:** procedimientos, listas de comprobación y plantillas que mejoran con la experiencia. Los cambios a los playbooks pasan por el proceso de gobernanza; Avatar propone, no autoaprueba cambios que afecten seguridad o autoridad.
4. **Evaluación medible de competencia:** conjuntos de casos de prueba por dominio (por ejemplo, cálculo de economía unitaria, detección de sesgo en un backtest, cumplimiento de reglas de una plataforma, balance con errores introducidos). Se ejecutan periódicamente y al cambiar de modelo, y se registra la evolución. **Avatar no se califica como experto sin resultados medidos.**
5. **Aprendizaje a partir de resultados reales:** qué campañas, productos y señales funcionaron y cuáles no, con evidencia y sin confundir suerte con habilidad. Las lecciones se registran como verificadas o como hipótesis.
6. **Honestidad sobre los límites:** cuando un tema supera su competencia o requiere un profesional (contable, tributario, legal, de inversión), lo dice y prepara la información para esa revisión.
7. **Escalamiento de modelo (U7)** según la complejidad y la criticidad, con segunda opinión independiente en decisiones de alto impacto.
8. **Higiene de la memoria:** el conocimiento falso o desactualizado se marca `DEPRECATED` y deja de usarse como hecho vigente.

**Aceptación**
- Un conocimiento con la fecha de revisión vencida se marca para revalidación y no se usa como hecho sin aviso.
- Un cambio de política de una plataforma simulado entra como no verificado, se valida y actualiza el playbook con trazabilidad.
- Las evaluaciones por dominio producen resultados comparables en el tiempo.
- Avatar reconoce y declara cuando una pregunta excede su competencia verificada.

---

# PARTE III — GOBERNANZA, CRITERIOS, PRUEBAS Y DECISIONES

## 6. Gobernanza de cambios sobre Avatar mismo

- **Componentes críticos** (autoridad, permisos, chokepoint, denylist, parada de emergencia, persistencia de misiones, gestión de secretos, canal remoto, enrutador de gasto): cambios con revisión reforzada, pruebas antes y después, ADR y aprobación de Mauro.
- **Protección del propio código de seguridad:** ninguna misión ejecutada por Avatar puede modificar estos componentes. Se bloquea en el chokepoint por ruta y por función. Avatar puede **proponer** cambios como parche, pero no aplicarlos.
- **No autoampliación de privilegios**, nunca.
- **Reversibilidad:** ramas, commits identificables, parches revisables, planes de rollback.

---

## 7. Criterios de aceptación transversales (capacidades de negocio y operación continua)

1. Toda acción con efecto económico pasa por el chokepoint, respeta los topes y queda en el ledger.
2. Ninguna operación de bolsa o criptomonedas se ejecuta desde Avatar.
3. Ninguna credencial de pago ni clave privada es accesible a Avatar.
4. El modo noche no ejecuta acciones de Nivel C o D y las deja en cola.
5. Las plataformas se usan por sus APIs oficiales y dentro de sus límites.
6. Ningún contenido externo (correos, redes, noticias, reseñas, páginas) actúa como instrucción.
7. Las cifras y métricas son verificables por código y con su fuente.
8. Los informes distinguen lo verificado, los supuestos y lo no verificado.
9. Las advertencias de riesgo y de revisión profesional aparecen en los entregables relevantes.
10. `KILL_SWITCH` suspende las tareas programadas, el modo 24/7 y los conectores.

---

## 8. Plan de pruebas general

### 8.1 Plan general y escenarios de la Directriz 002

- **Pruebas unitarias** para reglas deterministas (rutas, clasificación, estados).
- **Pruebas adversarias** para ofuscación de comandos, rutas hostiles e inyección en contenido externo.
- **Pruebas de extremo a extremo** en Windows aislado (máquina virtual o Windows Sandbox) con datos desechables.
- **Pruebas de recuperación:** interrupción a mitad de misión, reinicio, corte de red.
- **Pruebas de concurrencia:** parada durante un acto, dos agentes sobre los mismos archivos.
- **Pruebas en el PC de Mauro:** solo las no destructivas del protocolo de U9.
- **Escenarios de aceptación** de la Directriz 002, sección 20: cada uno mapeado a la unidad que lo demuestra.

| Escenario de la Directriz 002 | Unidad |
|---|---|
| Orden clara sin confirmaciones redundantes | U3 |
| Bloqueo de operación destructiva no autorizada | U2, U3 |
| Protección de rutas críticas de Windows | U2 |
| Archivos personales intactos | U2 |
| No mover el mouse ni cambiar el foco sin razón | U4 |
| Detección de acciones repetitivas y contención | U4 |
| Parada de emergencia | U1 |
| Fuente oficial vs. no verificada | U5 |
| Instrucciones maliciosas en contenido externo | U5 |
| Procedencia y estado de validación | U5 |
| No contaminar la memoria permanente | U5 |
| Recuperación sin repetir acciones no idempotentes | U1, U9 |
| Delegación sin permisos ilimitados | U8, U10 |
| Revisión de cambios de otro IDE | U8 |
| Cambio de modelo por cuota agotada | U7 |
| Sin gasto adicional no autorizado | U7 |
| Registro de motivos de modelo | U7 |
| Informes con evidencia real | U6 |
| Orden remota con el mismo motor de permisos | U9 |
| Límites de tiempo, costo, riesgo y reintentos | U3, U4, U7 |
| Reconstrucción de una misión desde registros | U6 |

### 8.2 Pruebas de las capacidades de negocio y de operación continua

- Entornos de simulación y sandbox para marketplaces, anuncios y mercados. **Sin dinero real ni cuentas reales de Mauro** en las pruebas.
- Pruebas adversarias: correos y páginas con inyección, noticias y redes manipuladas, claves con permisos excesivos, pedidos y mensajes atípicos.
- Simulaciones aceleradas de ciclos de 24 horas y de semanas, con fallos de red, de energía y de proveedores de modelos.
- Verificación independiente de todos los cálculos financieros y de marketing por código.
- Pruebas de restauración de respaldos.
- **`VERIFIED_PC`:** una tarea inocua y sin dinero (por ejemplo, un informe diario con datos públicos y una alerta de prueba por Telegram) ejecutada en el PC de Mauro.

### 8.3 Escenarios adicionales de negocio y operación continua

| Escenario | Unidad |
|---|---|
| Pedido duplicado por webhook o reinicio no genera dos pedidos al proveedor | U15.6 |
| Margen por debajo del mínimo tras un cambio de costo: el pedido no se compra | U15.6, U14.4 |
| Mensaje de proveedor que pide cambiar datos de pago: se escala, no se ejecuta | U15.6, U5 |
| Seguimiento publicado dentro del plazo o alerta de riesgo de vencimiento | U15.6 |
| Pago al proveedor sobre el tope: queda en cola | U15.6, sección 4 |
| Uso de un modo de acceso prohibido a una plataforma: bloqueado y registrado | U15.5 |
| Agregar una plataforma nueva solo con adaptador y ficha | U15.7 |
| Plataforma en `SOMBRA` no ejecuta acciones con efectos | U15.7 |
| Noche simulada de 8 horas: pedidos válidos procesados, el resto en cola | U13, U15.6 |
| Prueba de demanda se detiene al alcanzar el tope de gasto | U14.4 |
| Llamada a un endpoint de operar o retirar en un exchange: bloqueada | U16 |
| Restauración de un respaldo en una prueba | U12.4 |

---

## 9. Formato del informe de cierre de cada unidad

Cursor entrega, para cada unidad:

1. **Estado** con los términos de la sección 1 (por ejemplo, `IMPLEMENTED + INTEGRATED + TESTED_LINUX`, `VERIFIED_PC: pendiente`).
2. **Qué se reutilizó** del código existente y qué se creó (con rutas y funciones).
3. **Punto de integración** en el flujo de ejecución.
4. **Pruebas** añadidas y qué demuestra cada una. Sin usar el total de pruebas aprobadas como prueba de una capacidad completa.
5. **Lo que no se probó** y por qué (Windows, PC real, entorno externo).
6. **Diff** y rama.
7. **Riesgos residuales.**
8. **Siguiente paso** recomendado.

---

## 10. Decisiones que requieren a Mauro

Solo las que no están determinadas por las directrices vigentes.

**Seguridad y operación**
1. **Autorizar la primera unidad de código (U1).** Recomendación: aprobar U1 con nivel por defecto `PAUSE` y tecla `Ctrl+Alt+Shift+X`, y luego U2 y el ADR de U3.
2. **Aprobar el ADR de clasificación de comandos (U3)** antes de que se escriba código.
3. **Identidades autorizadas** en Telegram y WhatsApp (U9).
4. **Carpetas personales** que Avatar puede tocar sin aprobación adicional, si alguna (lista blanca de U2).
5. **Infraestructura 24/7:** PC encendido o servidor/nube, y medidas de energía y red (U13).
6. **Sobre de autorización nocturno:** qué acciones pueden ejecutarse sin su presencia y con qué límites.

**Herramientas y modelos**
7. **IDE y herramientas externas autorizadas** para U8, y con qué alcance.
8. **Presupuesto máximo por misión y por mes** para modelos, y si alguna vez se permite un gasto extra con aprobación específica (U7).

**Documentos y conocimiento**
9. **Marco contable, jurisdicción y moneda por defecto**, y si Avatar pregunta siempre antes de asumirlos (U11).
10. **Estilo de citación** (APA, ICONTEC u otro) y reglamento institucional.
11. **Plantillas o ejemplos** de documentos propios.
12. **Carpeta de entregas** y política de datos confidenciales (qué puede ir a modelos externos y qué solo en local).
13. **Herramientas que se autorizan instalar** (motor de oficina, OCR, gestor de citas).

**Asistente personal**
14. **Correo y calendario:** cuentas a conectar, carpetas excluidas y plantillas de respuesta aprobadas.
15. **Respaldos:** dónde se guardan las copias y cuánto tiempo se conservan.
16. **Voz:** dispositivo y modo de activación.

**Comercio y dropshipping**
17. **Plataformas prioritarias**, países y jurisdicciones de operación, y si ya tiene cuentas de vendedor.
18. **Productos o nichos** de interés y categorías que no quiere vender.
19. **Proveedores:** lista inicial aprobada y criterios para incorporar nuevos.
20. **Pagos al proveedor:** método (saldo prepago, crédito u otro) y topes por pedido, por día y por mes.
21. **Modelo logístico por producto o plataforma** (M1 a M4) y plazos de despacho que acepta prometer.
22. **Banda de precios y margen neto mínimo** por producto o categoría, y plantillas de respuesta a compradores.
23. **Presupuestos de marketing y de pruebas de demanda** y criterios de éxito y fracaso.

**Mercados financieros**
24. **Perfil de riesgo:** capital destinado, horizonte, activos permitidos, pérdida máxima tolerada y lista de seguimiento (U16).

**Legal, fiscal y profesional**
25. **Profesionales que revisan los entregables** con efecto legal o fiscal (contador, abogado, asesor financiero) y marco fiscal de cada actividad.

No se solicita a Mauro decidir sobre lo que las directrices ya establecen (por ejemplo, que `exec_requires_approval` no se apaga de forma general, que Avatar no ejecuta operaciones de bolsa o criptomonedas, o que no se automatiza el selector visual de modelos).

---

## 11. Instrucción final a Cursor

1. Lee este documento junto con MASTER DIRECTIVE 002, su dictamen y el roadmap R0–R7.
2. **No modifiques el motor, no amplíes privilegios ni cambies las políticas de aprobación** hasta recibir la autorización de Mauro para cada unidad.
3. Registra las unidades U0 a U17 en el plan conservando el orden de la sección 5: la seguridad de ejecución (U1, U2, U3) va primero.
4. Haz, sin tocar código, la comparación de las unidades nuevas (U11 a U17) contra el código y la documentación: qué existe, qué es reutilizable, qué falta y qué está bloqueado por dependencias externas (APIs, permisos, costos, infraestructura). Usa los estados de la sección 1.
5. Para las plataformas de comercio, **revisa y documenta las condiciones de uso y las APIs reales de cada una** antes de diseñar el adaptador. No asumas lo que permite cada plataforma.
6. Señala conflictos con la Directriz 002 y con el código, sin aplicar cambios silenciosos.
7. Espera la autorización de Mauro para cada unidad de código. Al cerrar cada una, entrega el informe de la sección 9.

**Meta:** un Avatar que actúa con iniciativa dentro de una misión autorizada, se frena solo ante lo peligroso, investiga sin contaminarse, conserva el progreso, produce documentos y análisis profesionales, recibe pedidos y los lleva hasta la entrega con el proveedor como despachador principal, vigila los mercados y le entrega señales a Mauro sin mover su dinero, trabaja de día y de noche dentro de límites claros y puede demostrar con evidencia lo que hizo y lo que no pudo verificar.

**FIN DE ENGINEERING SPEC 003 (versión 2.0 consolidada)**
