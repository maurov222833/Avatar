# EVIDENCE PROVENANCE MODEL 001

## 1. Identificadores de Procedencia (Provenance IDs)

Para garantizar la inmutabilidad y evitar ataques de *replay* entre misiones o tareas, cada objeto de evidencia debe estar vinculado de manera criptográfica o estructurada a través de los siguientes identificadores obligatorios:

1. **mission_id:** Identificador único de la misión en curso.
2. **task_id:** Identificador único de la tarea dentro de la misión.
3. **execution_id:** Identificador de la ejecución o intento específico.
4. **observation_id:** Identificador único de la observación cruda.
5. **verification_id:** Identificador del hecho verificado (`VerifiedFact`).
6. **evidence_id:** Identificador único inmutable de la evidencia generada.
7. **capability_id:** Identificador de la capacidad asociada.

## 2. Reglas de Inmutabilidad y Supervivencia

- **Unicidad:** Cada `evidence_id` debe ser único en todo el ciclo de vida del sistema.
- **Inmutabilidad:** Una vez generada y firmada/autorizada por el pipeline, ningún campo de procedencia puede ser modificado.
- **Supervivencia a Recovery:** Los identificadores de procedencia deben persistirse en el almacenamiento (`StateEngine`) para asegurar que un reinicio o reanudación (`resume`) no invalide el control de replay, pero requerirán validación temporal.
