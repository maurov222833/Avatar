# Decisión: las dos specs pedidas no se recuperan

**Cierre 2026-10-02.** Mauro las adjuntó. Quedaron en `docs/engineering/` con los bytes recibidos, sin edición. El índice y `SPEC_HASHES.txt` apuntan a esos archivos. Lo que sigue es el registro de la búsqueda del 2026-10-01, no el estado vigente.

Fecha: 2026-10-01. La dijo Mauro: ya no los encuentra.

Nombres cerrados, sin hash y sin texto rehecho:

- `AVATAR_ENGINEERING_SPEC_003_v2_COMPLETA.md`
- `AVATAR_SPEC_003_ADDENDUM_3_U18_DIRECTOR_DE_DESARROLLO.md`

Se buscaron en el repo, en el historial de git, en esta sesión, en las carpetas del PC, en `Avatar_Project_Complete.zip` y en los chats de OpenCode. Solo había menciones. No se fabrican para ocupar el hueco.

## Qué manda a partir de ahora

1. `docs/engineering/handover/MASTER_DIRECTIVE_002.md`
2. `docs/engineering/handover/ENGINEERING_SPEC_003.md`
3. `docs/engineering/handover/SPEC_003_V2_GAP.md`
4. `docs/engineering/handover/U18_0_PREPARACION.md`
5. `docs/engineering/handover/U18_COMPARACION.md`

`ENGINEERING_SPEC_003.md` es el registro del plan, no una copia de la v2 perdida. La comparación U11–U17 está en `SPEC_003_V2_GAP.md`. La preparación del director de desarrollo está en los dos archivos U18.

## Cuando falte una frase

Si una tarea necesita una regla que solo estaba en el texto perdido, se para esa tarea y se le pregunta a Mauro esa decisión. No se rellena el documento entero de memoria. El resto del trabajo sigue con los cinco archivos de arriba.

## Efecto en el funcionamiento

Ningún módulo de `core/`, `bin/` ni `tests/` lee esos dos nombres. Lo ya programado —parada, chokepoint, plantillas, margen en el simulador, director en el simulador— sigue igual.

Lo que puede fallar es un trabajo nuevo. `ENGINEERING_SPEC_003.md` registró el orden y no copió la v2 entera. Si una cifra, un criterio de aceptación o una prohibición quedó solo en el archivo perdido, el código nuevo puede omitirla. En ese caso se pregunta esa frase. La instalación en el PC, la verificación en Windows y las cuentas siguen dependiendo de Mauro, no de esos dos archivos.
