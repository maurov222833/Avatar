# U18.0 — Preparación, sin código

Fecha: 2026-10-01. No modifica el motor ni las políticas de aprobación.
Comparación con el código: `U18_COMPARACION.md`.

## 1. Qué control ofrece Cursor de verdad

Fuentes leídas el 2026-10-01: documentación de Cursor en `cursor.com/docs/cli/headless`, `cursor.com/docs/cli/using`, `cursor.com/docs/cli/reference/parameters` y `cursor.com/docs/hooks`. No se ejecutó el CLI contra ningún repositorio de Mauro.

### Preferencia 1 — interfaz programática

Existe el CLI `agent`.

- Instalación documentada: `curl https://cursor.com/install -fsS | bash` en macOS, Linux y WSL. En Windows: `irm 'https://cursor.com/install?win32=true' | iex`.
- Modo sin interfaz: `agent -p` (también `--print`). Sirve para scripts. La salida puede ser `text`, `json` o `stream-json`.
- Acepta un prompt, un directorio (`--workspace`) y un modelo (`--model`). Hay `agent models` para listar modelos de la cuenta.
- Modos documentados: agente (por defecto), `--mode=plan`, `--mode=ask` (lectura, sin editar).
- Worktree: `-w` / `--worktree` crea uno bajo `~/.cursor/worktrees/`. `--worktree-base` elige la base.
- Autenticación: `agent login` o la variable `CURSOR_API_KEY`.
- Sandbox documentado: `--sandbox enabled` o `disabled`.

Esto es la vía que U18 debe usar cuando Mauro autorice un IDE real. El progreso verificable es el código de salida, la salida JSON y el diff de git. No la frase final del agente.

**No se usará `--force` ni `--yolo`.** La documentación los describe como permiso para modificar archivos sin confirmación. Chocan con la aprobación de EXEC y con la detención S1.

**No está comprobado en este equipo:** si el binario `agent` está instalado en el PC de Mauro, si su cuenta tiene cuota, ni el costo por ejecución. Eso queda `UNVERIFIED` hasta que él lo confirme. Este entorno no lo lanza.

### Preferencia 2 — archivos que el IDE lee

Documentados y utilizables:

- `AGENTS.md` en la raíz del repositorio, y también en subdirectorios. El CLI lo lee.
- `.cursor/rules/*.mdc` para reglas con alcance por archivos.
- `.cursorrules` es formato viejo. No se usará como sitio nuevo.
- Hooks en `.cursor/hooks.json` (proyecto) o `~/.cursor/hooks.json` (usuario). Eventos documentados que importan aquí: `beforeShellExecution`, `afterShellExecution`, `beforeReadFile`, `afterFileEdit`, `stop`, `preCompact`, `subagentStart`, `subagentStop`. Un hook puede permitir o denegar un comando. El código de salida 2 deniega.

Los hooks no son un detector de detenciones. No dicen «el agente se quedó pensando». Si el script del hook falla, el comportamiento de respaldo no se da por seguro en esta nota: hay que leerlo en la versión instalada antes de confiar en él. Un hook tampoco sustituye al chokepoint de Avatar.

El cerebro del proyecto (sección 2) es contexto para el director. El briefing de un paquete es la orden. No se vuelca el cerebro entero en `AGENTS.md`.

### Preferencia 3 — ventana gráfica

No hay una API estable para pulsar la ventana de Cursor. Cloud Agents (`cursor.com/agents`) son otro producto, con su propia cola y su propia factura. No son un mando local que Avatar pueda llamar hoy.

Automatizar clics sobre el IDE queda como último recurso, frágil ante una actualización, y una prueba en Linux no la valida en Windows. U18.2 no parte de ahí.

### Lo que Cursor no ofrece

- No hay una señal oficial de «estoy detenido por la causa S4» o «S5». Avatar tiene que inferirlo del proceso, del git y de las pruebas.
- El agente puede decir que terminó sin haberlo hecho. Eso es S9. La frase no es evidencia.
- El selector visual de modelo no es un mando. El modelo va por `--model`.
- El CLI gasta la cuenta de Cursor. El libro de gasto de Avatar no lo ve.

## 2. Dónde vive el cerebro

Un cerebro por repositorio dirigido, dentro de ese repositorio, versionado en git.

Ruta oficial propuesta: `docs/brain/`.

Si el repositorio ya tiene una carpeta de documentación viva, no se abre una segunda. En Avatar esa carpeta ya es `docs/engineering/handover/`. Si Mauro elige Avatar como piloto, los archivos que falten se agregan ahí y se apunta a los que ya existen (`ENGINEERING_SPEC_003.md`, `SPEC_003_CIERRE.md`, `STATUS.md`). No se copia su contenido.

Archivos, y una sola fuente por tema:

| Archivo | Fuente única de |
|---|---|
| `PROJECT_BRIEF.md` | Qué es, para quién, objetivos, no-objetivos |
| `ARCHITECTURE.md` | Módulos y contratos |
| `DECISIONS/` | ADR con estado: vigente, propuesta, descartada |
| `CONVENTIONS.md` | Estilo, ramas, commits |
| `STACK_AND_ENV.md` | Cómo instalar, correr y probar |
| `VERIFY_COMMANDS.md` | Comandos canónicos del verificador |
| `ROADMAP.md` | Prioridades |
| `BACKLOG.md` | Trabajo pendiente y dependencias |
| `STATE.md` | Qué se hizo, qué sigue, bloqueos. Se actualiza tras cada paquete |
| `KNOWN_ISSUES.md` | Deuda y trampas |
| `SECURITY_RULES.md` | Lo que no se toca |
| `GLOSSARY.md` | Términos |
| `DIGEST.md` | Una página. Es lo único que se carga siempre |

Cada hecho lleva una de tres marcas: **verificado**, **decisión aprobada** o **hipótesis**. Los cambios en `DECISIONS/` y `SECURITY_RULES.md` los aprueba Mauro. Avatar propone.

Hoy ninguno de esos archivos está aprobado como cerebro. Esta tabla es la estructura, no el contenido.

## 3. Banco de preguntas

Se hacen en bloques cortos. Avatar redacta la carta solo después de las respuestas, y Mauro la aprueba. Una respuesta no se inventa.

**A. El proyecto**

1. ¿Qué problema resuelve y para quién?
2. ¿Qué significa que esté terminado o bien hecho?
3. ¿Qué no debe hacer el proyecto?
4. ¿Cuáles son las tres prioridades actuales, en orden?

**B. Calidad y estilo**

5. Entre velocidad, calidad, costo y simplicidad, ¿en qué orden van?
6. ¿Qué pruebas espera: mínimas, por módulo, o una cobertura concreta?
7. ¿Qué estilo debe seguir el código? ¿Hay un archivo que le guste como ejemplo?
8. ¿En qué idioma van los comentarios, la documentación y los commits?
9. ¿Cuánta deuda técnica tolera y cuándo hay que pagarla?

**C. Tecnología**

10. ¿Qué lenguajes y herramientas son obligatorios o preferidos?
11. ¿Qué está prohibido usar?
12. ¿Cómo se decide una dependencia nueva? ¿Qué licencias rechaza?

**D. Proceso**

13. ¿Qué política de ramas, commits y revisión prefiere?
14. ¿Cuándo se fusiona a la rama principal y quién lo decide?
15. ¿Cómo se publica y quién autoriza?

**E. Decisiones**

16. ¿Qué puede decidir Avatar sin consultarle?
17. ¿Qué debe consultarle siempre?
18. Si usted no responde, ¿Avatar usa un default reversible, espera, o pasa a otra tarea?
19. ¿Qué es inaceptable aunque usted esté ausente?

**F. Riesgo, costo y comunicación**

20. ¿Cuál es el tope por sesión, por día y por mes?
21. ¿Por qué canal y con qué urgencia quiere que lo contacten?
22. ¿Qué horarios son de silencio?
23. ¿Cuánto detalle quiere en el informe de regreso?
24. ¿Qué le ha hecho perder tiempo con una IA de desarrollo?
25. ¿Qué le haría confiar más y qué le haría confiar menos?

La carta no existe todavía. No hay etapa E1 hasta que el cerebro y la carta estén aprobados.

## 4. Borrador de cerebro del piloto

El piloto no está elegido. No redacto un cerebro de un repositorio real, y no uso Avatar como si ya fuera el piloto: si lo fuera, el chokepoint, la parada, los permisos, la denylist, la persistencia, los secretos, el canal remoto y el enrutador de gasto quedan fuera de cualquier paquete autónomo.

Cuando Mauro nombre el piloto, el primer borrador será un `DIGEST.md` de una página con tres clases de líneas: lo comprobado en el árbol, lo que es decisión suya y lo que queda como pregunta. Nada de eso se despacha a un IDE.

La biblioteca de ejemplos tampoco se siembra aquí. Hacen falta de 15 a 25 casos con su veredicto. Sin ese veredicto, un caso no se usa como regla.

## 5. Decisiones que siguen en Mauro

1. Proyecto piloto.
2. Cuándo y cada cuánto es la entrevista.
3. Casos iniciales de la biblioteca, aportados o validados por él.
4. Qué delega en D0, D1 y D2, y qué no delegará nunca.
5. Parámetros del sobre de ausencia.
6. Si Avatar podrá fusionar a la rama principal alguna vez.
7. Qué código puede salir a un modelo externo.
8. Números para pasar de E1 a E4, o los sugeridos de la adenda (85 % en 20 decisiones, 10 paquetes, 3 detenciones recuperadas, 5 ausencias cortas).
9. Canal y prioridad de alertas.
10. IDE autorizados. Hoy el único adaptador es el simulado.
11. Autorización de cada sub-unidad de código, empezando por U18.1 si quiere modelo de datos.

U18.0 queda cerrado como documento. El motor sigue igual.
