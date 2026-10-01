# Comparación Spec 003 v2 (U11–U17) contra el código

Fecha: 2026-09-30  
Estado de este documento: comparación histórica del 2026-09-30, sin cambios de motor en esa fecha. El estado vigente de U1 a U18 es `SPEC_003_CIERRE.md`. Las filas `NOT_IMPLEMENTED` de abajo no se usan como tablero actual.  
Estados usados: los de la sección 1 del spec (`IMPLEMENTED`, `INTEGRATED`, `TESTED_LINUX`, `VERIFIED_WINDOWS`, `VERIFIED_PC`, `UNVERIFIED`, `PARTIAL`, `BLOCKED`, `NOT_IMPLEMENTED`).

La versión consolidada sustituye a la spec inicial y a las adendas. El orden de la sección 5 se mantiene: U1, U2 y el ADR de U3 van antes que documentos, asistente, 24/7 y negocio.

## Qué se reutiliza

| Pieza existente | Dónde | Sirve para |
|---|---|---|
| Chokepoint y `ActPolicy` | `core/act_chokepoint.py` | Todo efecto futuro (documentos fuera del workspace, pagos, publicación, APIs) tiene que pasar por aquí. Hoy no conoce marketplaces ni brokers. |
| Ledger de actos | tabla `acts` | Registro de efectos. No guarda importes de negocio: eso no existe. |
| Watchdog | `core/watchdog.py` | U13 puede reutilizar el latido del proceso. No es un modo noche ni un tope de gasto. |
| WhatsApp 24/7 | `whatsapp_24x7.py` | Supervisor de un canal, no un planificador de tareas de negocio. |
| OCR local | `core/ui_inspector.py` (`LocalOCREngine`), `pytesseract` en `requirements.lock` | Leer texto en capturas de pantalla. No es un pipeline de facturas o PDF. |
| RAG por intersección de palabras | `core/word_rag.py` | Base débil de U5/U17. Sin estados de procedencia ni caducidad. |
| Redacción de logs | `core/redaction.py` | Útil para U11.7 y U12.1. No clasifica documentos confidenciales. |

No hay `python-docx`, `openpyxl`, `python-pptx` ni un motor de PDF de oficina en las dependencias del proyecto. No hay conector de correo, calendario, exchange ni marketplace.

## Unidades nuevas

| Unidad | Estado | Qué falta | Bloqueo |
|---|---|---|---|
| U11 Documentos | `NOT_IMPLEMENTED` | Generación programática, verificación por tipo, escritura atómica en `outputs/` | U2, U5, U6 y la decisión de herramientas (sección 10) |
| U12.1 Correo y calendario | `NOT_IMPLEMENTED` | OAuth de solo lectura y borradores | Cuentas y plantillas que defina Mauro |
| U12.2 Tareas programadas | `PARTIAL` | El watchdog no es un scheduler con vigencia. El Programador de tareas de Windows sigue sin instalarse | Decisión de infraestructura (PC o servidor) |
| U12.3 OCR de documentos | `PARTIAL` | OCR de pantalla sí; facturas, PDF y confianza por campo no | Motor local y decisión de no sacar documentos financieros |
| U12.4 Respaldos | `NOT_IMPLEMENTED` | Copias versionadas que una misión no pueda borrar | Dónde guardarlas (decisión de Mauro) |
| U12.5 Voz | `NOT_IMPLEMENTED` | Transcripción con confirmación aparte para riesgo alto | Dispositivo y modo de activación |
| U13 Operación 24/7 | `PARTIAL` | Hay supervisor de proceso. No hay sobre nocturno, informe diario ni tope de gasto | U1, porque el `KILL_SWITCH` todavía no existe |
| U14 Marketing | `NOT_IMPLEMENTED` | Estudio, métricas por código, pruebas de demanda | U5, U6, U7 y topes de gasto |
| U15 Marketplaces | `NOT_IMPLEMENTED` | Modelo canónico, conectores, máquina de estados de pedidos | U1–U3, cuentas de vendedor, lectura de condiciones por plataforma |
| U16 Mercados financieros | `NOT_IMPLEMENTED` | Señales y backtest. No hay cliente de broker, y no debe haber ejecución | Claves de solo lectura y perfil de riesgo |
| U17 Conocimiento experto | `PARTIAL` | Solo el RAG actual. Sin playbooks, caducidad ni evaluaciones por dominio | U5 |

## Plataformas (revisión del 2026-09-30, no es asesoría legal)

No se diseñó ningún adaptador. Lo que no se leyó queda `UNKNOWN`.

**Mercado Libre.** La documentación de desarrolladores describe OAuth 2.0, tokens de acceso de corta duración y refresh token. La página de buenas prácticas pide usar la API, no hacer web crawling, respetar el error 429 y no enviar mensajes automáticos repetitivos de postventa (la propia documentación dice que se bloquean). Desde el 18 de marzo de 2026, la documentación de automatización de precios indica que un ítem con esa automatización activa rechaza cambios de precio por el endpoint general de ítems. Fuentes consultadas: `developers.mercadolibre.com.ve` (buenas prácticas, automatizaciones de precios, autenticación). La política de dropshipping del país donde Mauro vendería no se leyó en esta pasada: `UNKNOWN`. No se asume que una plantilla de seguimiento esté permitida.

**Amazon.** La vía oficial de vendedores es Selling Partner API (SP-API), con registro de desarrollador, autorización del vendedor, sandbox, política de uso aceptable y política de protección de datos. La política de uso aceptable prohíbe evadir cuotas con varias cuentas. Fuentes: documentación SP-API y Acceptable Use Policy / Data Protection Policy enlazadas desde ahí. La política de dropshipping de la cuenta de vendedor (distinta de la de desarrollador) y el marketplace concreto (por ejemplo Estados Unidos, México o Colombia) quedan `UNKNOWN` hasta leerlos.

Cualquier otra plataforma está `NO_EVALUADA`.

## Choque de nombres

En el historial del repositorio, «U1» ya significa otra cosa: la contención de canales y de EXEC de septiembre de 2026 (`docs/engineering/u1_contencion/`). La U1 de esta spec es la parada de emergencia y **no está hecha**. No se reutiliza ese informe como cierre de la parada.

## Conflictos, sin cambiar código

1. **La tecla de U1 sigue siendo una propuesta.** La tabla de avance la nombra; la sección 10 exige autorización. No se implementa.
2. **Modo noche frente a atajos del dueño.** U13 dice que de noche no hay actos visuales salvo misión autorizada. Los atajos de minimizar, maximizar y mostrar escritorio son órdenes explícitas por Telegram, no autonomía nocturna. No se amplían ni se quitan en este paso.
3. **Programador de Windows.** U12.2 permite reutilizarlo. La decisión previa del proyecto es no instalarlo hasta que Mauro elija PC encendido o servidor. No se instala.
4. **Mensajes automáticos y Mercado Libre.** U15.6 habla de plantillas aprobadas. La documentación de buenas prácticas consultada dice que los mensajes automáticos repetitivos de postventa se bloquean. Hasta leer la política del país de Mauro, el diseño no envía esos mensajes.
5. **Pagos y operaciones.** La sección 4 prohíbe que Avatar ejecute bolsa, cripto, retiros o guarde tarjetas y frases semilla. Eso coincide con no aflojar `exec_requires_approval`. No hay que añadir endpoints de trading para “dejarlos apagados”.
6. **Negocio antes de seguridad.** Empezar U14, U15 o U16 ahora contradice la sección 5. Esas unidades quedan registradas y sin iniciar.

## Siguiente paso

U1, cuando Mauro la autorice, con nivel por defecto `PAUSE` y la tecla que él confirme. Hasta entonces no hay diff de motor.
