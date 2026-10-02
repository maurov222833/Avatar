# Cierre Spec 003 — U1 a U18

Matriz revisada el 2026-10-02. Rama `cursor/spec-003-u1-u17-5763`.
El 2026-09-30 Mauro confirmó en su PC la captura, «dale play» y «pausa» sobre la misma canción, y `/pause` a mitad de un acto inocuo. Eso es `VERIFIED_PC` de esos tres pasos. El resto, en Windows y en el PC, es `UNVERIFIED`.

La suite de este árbol en Linux (`python -m unittest discover -s tests -q`) es `TESTED_LINUX`. No sustituye la prueba en el PC. Ninguna fila de abajo usa un estado suelto: el entorno va en su columna.

`exec_requires_approval` sigue activo. No hay claves de pago, ni frases semilla, ni llamadas a Amazon, Mercado Libre o un broker.

## Por unidad

| Unidad | Estado | Entorno (Linux / Windows / PC) | Dónde | Qué no quedó |
|---|---|---|---|---|
| U1 Parada | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `VERIFIED_PC` solo el `/pause` (2026-09-30). | `core/halt.py`. `/pause` pausa y el segundo `/pause` quita la pausa. Un hilo aparte lee el archivo de disparo aunque el orquestador esté colgado. Una `WRITE_FILE` en curso se nombra, termina, y un acto nuevo no arranca. | La tecla global no se instala y su latencia en el PC no está medida. Ese hilo no arranca solo al abrir Avatar. `/stop` y `/kill` no se apagan con `/pause`. |
| U2 Rutas | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `core/path_guard.py` en escrituras y en comandos que nombran una ruta prohibida. Niega `C:Windows` sin barra, `C:/Windows/...`, y un nombre con punto o espacio final. Antes de pisar un archivo guarda una copia en la papelera de la misión. | Un junction real de Windows no se creó aquí. El 8.3 y el UNC se niegan por el texto, no por NTFS. El tope en bytes no tiene cifra en la spec. |
| U3 Comandos | `IMPLEMENTED + INTEGRATED`. ADR aprobados condicionalmente, no cerrados | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `core/command_risk.py`. C entendido (`git push`, `curl`, `echo`, install sin fijar) se separa de `UNUNDERSTOOD`. Lo ofuscado es `PROHIBITED`. `pip`/`npm install` son C salvo un archivo con hashes. Una lectura de ruta protegida deja de ser A. Apagar `exec_requires_approval` no deja correr lo no entendido. `>`, `>>` y `\|` son `UNUNDERSTOOD` / `REDIRECT` o `COMPOSITION`. Out-File, Set-Content y tee son `UNUNDERSTOOD` / `OUTPUT_SINK`. | Sin AST. `>` ya está cerrado. La revisión del análisis estructural, antes del primer `allow_level_c` y antes del modo noche, sigue pendiente. Los ADR no están cerrados. |
| U4 Contención | `IMPLEMENTED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `core/containment.py`. El orquestador la enciende solo si `security.containment_enabled` es verdadero | Apagada por defecto para no pausar el PC a los cinco actos iguales sin que Mauro lo active. |
| U5 Procedencia | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | Cada página o búsqueda deja una línea en `memory/provenance.jsonl`. Una orden dentro del texto contamina el turno. | No promociona sola nada a memoria permanente. |
| U6 Informes | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | Si el turno ejecutó actos, la respuesta cierra con `Estado de la misión:` calculado desde la evidencia. | Una charla sin actos no lleva esa línea. |
| U7 Modelos | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | Un proveedor listado en `providers.paid_upgrade` no entra como reemplazo. | El precio real sigue `UNKNOWN` si no se comprobó. |
| U8 IDE | `IMPLEMENTED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `core/external_dev.py`, adaptador simulado | Ningún IDE real. Falta la lista que autorice Mauro. |
| U9 Canal | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `VERIFIED_PC` en captura, play/pausa y `/pause` (2026-09-30). | `core/remote_guard.py` en Telegram y en WhatsApp. El `/pause` autorizado pausa y el segundo lo quita. Un ajeno no cambia el estado. | En el PC solo están comprobados captura, play/pausa y `/pause` por Telegram. Falta comprobar WhatsApp en el teléfono, el reinicio a mitad y la pantalla bloqueada. |
| U10 Subagentes | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `AvatarOrchestrator.run_scoped_act`. Una escritura con `scope` pasa por ahí. | El servidor no arranca una flota de subagentes. |
| U11 Documentos | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `write_mission_deliverable` escribe por el chokepoint, avisa el descuadre y no pisa un original. | No hay Word ni Excel recalculando. No es un dictamen contable. |
| U12 Asistente | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `backup_tree` registra la carpeta. Una misión no la borra. El watchdog la copia solo si `backup_source` y `backup_dest` están puestos. | Sin OAuth, sin correo real, sin micrófono. El correo sigue en borrador. |
| U13 Noche | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `security.night_mode` apagado por defecto. Si se enciende, C, D y lo visual quedan en `NIGHT_QUEUED` y el watchdog no reanuda. | No está encendido en el PC. No detecta solo que Windows está bloqueado. |
| U14 Marketing | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | Una reseña marcada como inventada se niega en el chokepoint. | No publica ni gasta en anuncios. |
| U15 Marketplaces | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | Un `access_mode` prohibido se niega en el chokepoint. El margen estricto separa costo, comisión, envío, impuesto, devoluciones y publicidad. Si falta el impuesto, el veredicto es `INCOMPLETO`. | Sin API real. Ninguna tarifa de país se leyó del sitio oficial. Una hipótesis no es tarifa. |
| U16 Mercados | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | Una URL o un comando que nombra `/order`, `/withdraw`, `/transfer` o `/trade` se niega. | No hay cliente de broker. |
| U17 Conocimiento | `IMPLEMENTED + INTEGRATED` | Linux: `TESTED_LINUX`. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `core/expertise.py` y `expertise.json` leído por `RAGMemory.search_knowledge`. Una ficha vencida no sale. | El modelo no escribe fichas solo. No es búsqueda vectorial. |
| U18 Director | `IMPLEMENTED` | Linux: `TESTED_LINUX` en el simulador. Windows: `UNVERIFIED`. PC: `UNVERIFIED`. | `core/dev_director.py`, `FakeDevAgent` en `core/external_dev.py`. Detenciones S1–S14, verificador, `plan_packages`, decisiones D0–D3, sobre de ausencia y parada por `KILL_SWITCH`. Cada verificación guarda `PASS` o `REJECT` solo de las puertas que corrieron. El briefing enviado queda en la misión y uno con secreto no se guarda. Un diff que toca parada, chokepoint, secretos o gasto no se acepta. `begin` no despacha. `run_next` sigue con el siguiente paquete en una carpeta aparte, anota la lista sin inventar criterios y cierra si no queda trabajo seguro. Si hay una compilación en curso, no abre otra tarea. Un paquete rechazado por trampa, falso hecho, secreto o módulo crítico no se vuelve a despachar. No abre `main`. El servidor no lo llama. | Ningún IDE real. No fusiona a `main`. La carta de Mauro sigue sin redactarse. La segunda opinión no se llama hasta que el software esté por terminarse. La calibración se queda en E0. Un desvío de alcance borra solo archivos nuevos dentro de la carpeta y no llama a git. Un traspaso no hereda un «terminado» dicho por el paquete y conserva el objetivo aunque el resumen cambie. El informe de cierre repite ese objetivo. Un caso sin veredicto de Mauro no es regla. |

## Correcciones del 2026-10-02

En la misma suite de Linux, y solo ahí (`TESTED_LINUX`; Windows `UNVERIFIED`; PC `UNVERIFIED`): la apertura de WhatsApp pasa por `perform()` y no usa `shell=True`; la intención queda `REQUESTED` antes del ejecutor y, si el proceso cae, el acto sigue `INTERRUPTED` / `UNVERIFIED` sin reejecutarse solo; el puente acepta un único chat configurado, con coincidencia exacta, rechaza grupos, y el nivel C o mayor espera un identificador numérico de Telegram; los hijos de prueba no heredan el token real y llevan la guarda de red; la captura de prueba va a `memory_dir()` del pin y no pulsa clics ni teclas salvo `AVATAR_ALLOW_REAL_INPUT=1`; la certificación concurrente ya no pierde la evidencia; la prueba del QR borra su directorio al salir.

## Informe OpenCode 9 (2026-10-02, commit `aca3278`)

La suite en Windows no pasó: 565 pruebas, 2 fallos, 50 errores, 2 omitidas, salida 1. La fase 3 sigue `TESTED_LINUX`. Windows y PC de esas correcciones siguen `UNVERIFIED`.

La base viva no cambió de tamaño (1482752, wal 1899352, shm 32768) y la clave siguió en 32 bytes. `memory\screen_observation.png` no cambió de hora ni de tamaño. Una captura de la suite fue a `%TEMP%\avatar_test_*\memory\` y esa carpeta ya no está. Los enlaces `salto_fuera` y `enlace_fuera` no estaban; no se borró nada. `C:\Windows` sigue. La tarea `AvatarWhatsApp247` apareció Disabled; no se tocó.

El respaldo `avatar_sandbox\respaldo_memory`, leído en una copia, tiene filas parecidas a pruebas: 73 misiones, 337 actos, 46 de memoria. Eso es suciedad anterior al pin. No se restauró la base.

## Informe OpenCode 10 (2026-10-02, commit `ee8b568`)

Otra corrida en Windows: 798 pruebas, 1 error, 2 omitidas, salida 1. La fase 3 sigue `TESTED_LINUX`. Windows y PC de esas correcciones siguen `UNVERIFIED`.

Desaparecieron los 50 errores de import y los 2 fallos de escritorio del informe 9. La base viva, el wal, el shm, la clave de 32 bytes y `memory\screen_observation.png` no cambiaron de tamaño ni de hora. El error que queda es el fixture del navegador: no pudo abrir el puerto 8765 porque lo tenía en escucha `Cursor.exe` (PID 8180). Esa clase no llegó a ejecutarse. No es un fallo de aserción del arreglo.

## Riesgo que queda

La parada vive en el proceso. Otro código que llame a una herramienta saltándose el chokepoint no la ve. La tecla global y las pruebas de rutas en Windows siguen pendientes. La prueba corta de Telegram en el PC ya la cerró Mauro el 2026-09-30.

## Siguiente paso

El 2026-10-01 quedaron cerradas las puertas de `GATES_CERRADAS.md`: IDE real apagado, carta sin respuestas, tecla sin instalar, analizador = clasificador actual, WhatsApp aparcado, fusión a `main` en cola, segunda opinión sin gasto y sin llamada. Esa segunda opinión se activa cuando el software esté por terminarse, no antes. La contención automática y el modo noche siguen apagados. No hay cuentas de tienda ni de broker. Lo que queda fuera de este equipo es la prueba en el PC de Windows.
