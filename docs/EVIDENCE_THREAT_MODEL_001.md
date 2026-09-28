# EVIDENCE THREAT MODEL 001

## 1. Matriz de Amenazas y Mitigaciones Diseñadas

| ID | Amenaza | Ataque | Defensa Actual | Brecha Actual | Defensa Propuesta | Propietario de Autoridad |
|----|---------|--------|----------------|---------------|-------------------|--------------------------|
| T1 | Fake physical flag | Caller instancia `CapabilityEvidence(physical_evidence=True)` | Ninguna | Invocador no confiable puede auto-certificar | `AuthorizedEvidenceBuilder` construido solo por `PhysicalFactVerifier` | Fact Authority |
| T2 | Synthetic evidence injection | Inyección de objetos falsos en tests | Ninguna | Contaminación entre test y producción | Separación estricta de namespaces y factory de test | Test Authority |
| T3 | Cross-mission replay | Reutilizar evidencia de Mission A en Mission B | Ninguna | Falta binding por `mission_id` | Validación estricta de `mission_id` en Registry | Capability Authority |
| T4 | Cross-task replay | Reutilizar evidencia de Task A en Task B | Ninguna | Falta binding por `task_id` | Validación estricta de `task_id` en Registry | Capability Authority |
| T5 | Cross-capability replay | Usar evidencia de Cap A para certificar Cap B | Ninguna | Falta binding estricto por `capability_id` | Validación estricta de `capability_id` | Capability Authority |
| T6 | Stale evidence | Usar evidencia antigua tras cambio en el mundo | Ninguna | Ausencia de modelo temporal / TTL | TTL y control de vigencia temporal | Fact Authority |
| T7 | Evidence substitution | Reemplazar hashes válidos por hashes manipulados | Hash SHA-256 parcial | Falta firma o inmutabilidad de origen | Inmutabilidad garantizada por Provenance Model | Provenance Authority |
| T8 | LLM claim injection | LLM afirma que completó una tarea | `ClaimValidator` | El LLM puede engañar al orquestador | Requerir `VerifiedFact` obligatorio | Fact Authority |
| T9 | Tool success inflation | Herramienta retorna éxito sin efecto real | Ninguna | Éxito lógico != Éxito físico | Auditoría física obligatoria post-ejecución | Fact Authority |
| T10| Recovery state poisoning | Restaurar estado VERIFIED desde BD corrupta | Ninguna | `StateEngine` confía en lo almacenado | Re-verificación de procedencia al reanudar | Persistence & Fact Authority |
| T11| Test/prod contamination | Objetos de prueba usados en producción | Ninguna | Sin distinción de origen en dataclass | Flag explícito de entorno de ejecución | Environment Boundary |
| T12| Unauthorized caller | Invocación directa a métodos internos de registro | Ninguna | Clases accesibles globalmente | Encapsulamiento y firma de métodos de registro | Authority Boundary |
