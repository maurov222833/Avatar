# EVIDENCE IMPLEMENTATION PLAN 001

## 1. Plan de Implementación por Etapas (Futuro)

### STEP 1: Evidence Provenance Binding
- Añadir campos obligatorios (`mission_id`, `task_id`, `execution_id`) a la estructura de evidencia.
- **Archivos afectados:** `core/cognitive/capability_registry.py`.

### STEP 2: Authorized Verification Boundary
- Restringir la instanciación de `CapabilityEvidence` mediante un factory o builder controlado exclusivamente por `PhysicalFactVerifier`.
- **Archivos afectados:** `core/cognitive/physical_fact_verifier.py`, `core/cognitive/capability_registry.py`.

### STEP 3: Replay Protection & Mission Isolation
- Validar en el Registry que la evidencia pertenezca al `mission_id` y `task_id` activo.
- **Archivos afectados:** `core/cognitive/capability_registry.py`.

### STEP 4: Temporal Validity & TTL
- Incorporar marca temporal de frescura para evitar el uso de evidencias obsoletas.
- **Archivos afectados:** `core/cognitive/capability_registry.py`.

### STEP 5: Registry Authority Correction
- Asegurar que el Registry actúe únicamente como evaluador de hechos autorizados.
- **Archivos afectados:** `core/cognitive/capability_registry.py`.

---

## 2. Entregables Generados en esta Misión de Diseño
1. `docs/AUTHORITY_CONSOLIDATION_005_REPORT.md`
2. `docs/EVIDENCE_TRUST_MODEL_001.md`
3. `docs/EVIDENCE_AUTHORITY_MODEL_001.md`
4. `docs/EVIDENCE_PROVENANCE_MODEL_001.md`
5. `docs/EVIDENCE_THREAT_MODEL_001.md`
6. `docs/EVIDENCE_IMPLEMENTATION_PLAN_001.md`

**Veredicto Final de la Misión:** `AUTHORITY_MODEL_DEFINED`
