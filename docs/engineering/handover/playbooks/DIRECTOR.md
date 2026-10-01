# Playbooks del director (U18)

Cada uno se cambia por gobernanza. Avatar puede proponer un cambio. No lo autoaprueba.

## PB-01 Arranque

Disparador: empieza una misión de desarrollo.
Pasos: leer el digest, el objetivo y el estado. Marcar lo no verificado como pregunta.
Salida: objetivo repetido y estado inicial anotado.
Límite: no despachar todavía.
Registro: misión en PLANNING.

## PB-02 Descomponer

Disparador: hay un objetivo y todavía no hay paquetes.
Pasos: cortar en paquetes con criterios medibles.
Salida: cada paquete cabe en una revisión corta.
Límite: un paquete sin criterios no sale de aquí.
Registro: lista de paquetes.

## PB-03 Briefing

Disparador: un paquete va a salir.
Pasos: usar la plantilla. Contexto mínimo. Alcance. Verificación. Protocolo de duda.
Salida: briefing sin secretos.
Límite: no volcar el cerebro entero.
Registro: texto enviado.

## PB-04 Despachar

Disparador: el briefing está listo.
Pasos: rama o worktree aislado. Un paquete a la vez por los mismos archivos.
Salida: el IDE recibió la orden.
Límite: el IDE no hereda permisos de Avatar.
Registro: identificador de tarea.

## PB-05 Detenciones

Disparador: no hay progreso verificable.
Pasos: clasificar S1 a S14. Escribir el informe de detención. Subir un escalón de la escalera.
Salida: una acción distinta de la que ya falló.
Límite: S14 se observa. No se interviene una compilación que avanza.
Registro: tipo, evidencia, escalón.

## PB-06 Verificar

Disparador: el IDE dice que terminó, o hay un diff.
Pasos: mirar alcance, pruebas, anti-trampa y secretos. La frase del IDE no cuenta.
Salida: aceptar o rechazar.
Límite: no debilitar pruebas para que pasen.
Registro: puertas y resultado.

## PB-07 Otra estrategia

Disparador: el escalón anterior no movió el diff ni las pruebas.
Pasos: no repetir la orden. Reducir el paquete o cambiar el enfoque.
Salida: una instrucción nueva.
Límite: tope de intentos del sobre.
Registro: lo ya intentado.

## PB-08 Segunda opinión

Disparador: la estrategia nueva también falló, o el paquete es de riesgo.
Pasos: otro modelo revisa el diff. No ejecuta.
Salida: acuerdo o escalación.
Límite: no gasta fuera del tope.
Registro: dictamen.

## PB-09 Traspaso

Disparador: cambia la sesión, el modelo o el IDE.
Pasos: resumen con objetivo, decisiones, restricciones y siguiente paso.
Salida: el resumen conserva las restricciones.
Límite: la memoria del chat no es la fuente.
Registro: resumen.

## PB-10 Revertir

Disparador: el diff se fue de alcance o el paquete se rompió.
Pasos: volver al último punto bueno. No repetir acciones no idempotentes.
Salida: árbol limpio respecto de ese punto.
Límite: sin force push.
Registro: commit de retorno.

## PB-11 Requisito ambiguo

Disparador: falta un dato y Mauro no está.
Pasos: si es reversible, anotar el supuesto y seguir. Si no, cola y trabajar en lo independiente.
Salida: supuesto visible o pregunta en cola.
Límite: no decidir lo irreversible.
Registro: supuesto y pregunta.

## PB-12 Cierre

Disparador: no quedan paquetes seguros, o el sobre pide parar.
Pasos: informe con evidencia, decisiones, supuestos, preguntas, detenciones y costo.
Salida: estado calculado, no el que diga el IDE.
Límite: no afirmar más de lo verificado.
Registro: informe.
