# U18 — Comparación con el código

Fecha: 2026-10-01. Adenda 3 de la Spec 003. Sin código nuevo de motor.
Estados usados: `IMPLEMENTED`, `INTEGRATED`, `TESTED_LINUX`, `VERIFIED_WINDOWS`, `VERIFIED_PC`, `UNVERIFIED`, `PARTIAL`, `BLOCKED`, `NOT_IMPLEMENTED`.

Nada de esta tabla es `VERIFIED_PC`. No se probó contra un repositorio real de Mauro.

## Qué se reutiliza

| Pieza de U18 | Dónde vive hoy | Estado | Límite |
|---|---|---|---|
| Parada por encima del director | `core/halt.py`, `/pause` `/stop` `/kill` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX`. `/pause` también `VERIFIED_PC` | La parada vive en el proceso de Avatar. Un CLI de Cursor lanzado aparte no la ve hasta que el director lo cancele. |
| Todo efecto por el chokepoint | `core/act_chokepoint.py` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | El IDE no hereda permisos. Un proceso `agent` con `--force` se salta esta puerta. No se usará. |
| Riesgo A–D de cada acción | `core/command_risk.py`, `core/grants.py` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Los niveles D0–D3 de la adenda son otra capa (decisiones de ingeniería). No sustituyen A–D. |
| Rutas prohibidas | `core/path_guard.py` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Junctions, 8.3 y UNC siguen `UNVERIFIED` en Windows. |
| Estado que no inventa el modelo | `core/mission_transition.py`, `core/mission_report.py` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Los estados de `DevMission` no existen. No se renombran los estados ya persistidos. |
| Adaptador de IDE | `core/external_dev.py`, `SimulatedDevAgent` | `IMPLEMENTED + TESTED_LINUX` | Escribe un archivo de prueba. No simula S1–S14. No habla con Cursor. |
| Revisión de alcance del diff | `review_diff` en el mismo archivo | `PARTIAL` | Solo mira rutas. No mira pruebas debilitadas, hardcode ni secretos. |
| Subagente con alcance | `AvatarOrchestrator.run_scoped_act` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Una escritura acotada. No es un revisor independiente ni una flota. |
| Contención de bucles de actos | `core/containment.py` | `IMPLEMENTED + TESTED_LINUX`, apagada | Cuenta actos iguales de Avatar. No ve el bucle de un IDE externo. |
| Gasto de proveedores de Avatar | `core/model_inventory.py`, ledger de uso | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | No ve la factura de Cursor. Un tope de U7 no frena `agent`. |
| Sobre nocturno | `core/night_mode.py`, `NightEnvelope` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX`, apagado | Cola de actos A/B. No es el `DevEnvelope` de desarrollo (ramas, WP, silencio, parada). |
| Canal de aviso | `core/remote_guard.py`, Telegram y WhatsApp | `IMPLEMENTED + INTEGRATED + TESTED_LINUX`. Telegram `VERIFIED_PC` en tres pasos | No hay heartbeat de dirección ni informe de regreso. |
| Fichas con vencimiento | `core/expertise.py` | `IMPLEMENTED + TESTED_LINUX` | Sirve de patrón para lecciones que caducan. No está unido a la memoria del servidor. |
| Proveniencia | `memory/provenance.jsonl` | `IMPLEMENTED + INTEGRATED + TESTED_LINUX` | Una orden dentro de una página contamina el turno. No cubre un comentario malicioso dentro del repo dirigido. |
| Ledger de actos | tabla `acts` | `IMPLEMENTED + INTEGRATED` | No guarda Stall Report ni DEC. |

## Qué falta

| Requisito | Estado |
|---|---|
| `DevMission`, `WorkPackage`, cola de preguntas, registro DEC | `IMPLEMENTED + TESTED_LINUX` en `core/dev_director.py`. No está unido al servidor. |
| `Planner`, `BriefingBuilder`, playbooks PB-01 a PB-12 versionados | `PARTIAL`. `begin` aplica PB-01 y no despacha. `run_next` salta lo ya aceptado, despacha un paquete y, si no queda trabajo seguro, cierra con PB-12. No elige el piloto ni redacta el cerebro. El servidor no lo arranca. |
| `Dispatcher` sobre un IDE real | `NOT_IMPLEMENTED`. El despacho prueba `FakeDevAgent`. |
| `FakeDevAgent` con modos S1–S14 | `IMPLEMENTED + TESTED_LINUX` |
| `Monitor` y `StallDetector` | `IMPLEMENTED + TESTED_LINUX` sobre la observación del simulador |
| `Verifier` con puertas 1 a 10 y anti-trampa | `PARTIAL`. Alcance, pruebas observadas, anti-trampa, secretos, sintaxis de los `.py` escritos dentro del alcance, y licencia solo si el paquete nombra las que rechaza. La segunda opinión de otro modelo sigue `NOT_IMPLEMENTED`: gastaría y el tope del CLI sigue `UNKNOWN`. |
| `DecisionEngine` D0–D3 | `IMPLEMENTED + TESTED_LINUX`. D2 queda en cola. D3 se bloquea. |
| Escalera de intervención | `IMPLEMENTED + TESTED_LINUX`. No repite la orden fallida. |
| `DevEnvelope`, parada automática de desarrollo, informe Anexo E | `IMPLEMENTED + TESTED_LINUX` en el simulador. No está encendido en el PC. |
| Cerebro del proyecto aprobado, carta de Mauro, biblioteca de 15–25 casos | `NOT_IMPLEMENTED`. La estructura propuesta está en `U18_0_PREPARACION.md`. |
| Métricas de calibración E1–E4 | `PARTIAL`. `calibration_stage` cuenta el umbral sugerido y se queda en `E0`. No sube de etapa: la carta no está aprobada y la escala E1–E4 no está en el repo. |

## Conflictos

1. **`--force` y `--yolo` del CLI de Cursor.** La documentación oficial los describe como permiso para cambiar archivos sin confirmación. Eso choca con `exec_requires_approval` y con S1. El director no los pasará. Un comando de nivel C o D sigue yendo a la cola.
2. **Dos sistemas de estados.** U6 calcula `COMPLETED_VERIFIED` y vecinos desde actos de Avatar. U18 añade estados de `DevMission`. Convivirán. El modelo no escribe ninguno de los dos.
3. **Dos sobres.** `NightEnvelope` no se estira para cubrir ramas, merges y paquetes de trabajo. `DevEnvelope` será otro objeto, cuando se autorice U18.8, y el modo noche sigue apagado.
4. **Dos cajas de gasto.** Cursor cobra por su cuenta. U7 no lo ve. Hasta que Mauro fije un tope, el gasto del CLI queda `UNKNOWN` y el director no lo lanza.
5. **Dirigir a Avatar.** Los componentes críticos (autoridad, permisos, chokepoint, denylist, parada, persistencia, secretos, canal remoto, enrutador de gasto) no se aceptan si el diff los toca. El director los nombra en el briefing. `verify_package` devuelve `CRITICAL` y el paquete no pasa a aceptado. No borra el archivo.
6. **GUI de Cursor.** Automatizar la ventana del IDE es el último recurso de la sección 10. Es frágil y en Linux no valida Windows. No es el camino de U18.2.

## Bloqueos

- Mauro no ha elegido el proyecto piloto (decisión 1 de la sección 17).
- No hay carta de ingeniería. Sin ella, D0 y D1 no tienen contenido.
- No hay IDE real autorizado. U8 sigue en el simulador.
- No hay presupuesto para el CLI de Cursor.
- El código del simulador ya no espera un permiso por sub-unidad. Siguen fuera: IDE real, fusión a `main`, gasto del CLI y la carta de Mauro.
