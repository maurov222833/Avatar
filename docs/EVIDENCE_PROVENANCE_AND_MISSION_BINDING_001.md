# EVIDENCE PROVENANCE AND MISSION BINDING SPECIFICATION 001

## 1. Problema de Vinculación de Misión (Mission Binding)
En las versiones anteriores, `CapabilityEvidence` no contenía vinculación explícita con `mission_id` y `task_id`.
Esto permitía que:
1. Una evidencia recolectada en una misión previa pudiera persistir y satisfacer requisitos de misiones posteriores de forma espuria.
2. Evidencia generada en tareas desacopladas pudiera confundirse con el objetivo actual.

## 2. Definición del Esquema Reforzado
El esquema estricto de evidencia debe incorporar:
- `mission_id`: Identificador unívoco de la misión activa.
- `task_id`: Identificador de la subtarea ejecutada.
- `verifier_signature`: Identificador y hash de verificación física emitido por `PhysicalFactVerifier`.

## 3. Reglas de Validación
1. **Anti-Replay**: Una evidencia cuyo `mission_id` no coincida con la misión en ejecución debe ser rechazada por el `MissionCompletionGate`.
2. **Anti-Auto-Certification**: Ningún componente que no sea un `PhysicalFactVerifier` autorizado puede emitir una estampa de evidencia física válida.
