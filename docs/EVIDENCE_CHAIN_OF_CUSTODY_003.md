# EVIDENCE CHAIN OF CUSTODY 003

## 1. Cadena Objetivo de Custodiamiento
MISSION
↓
TASK
↓
ACTION
↓
EXECUTION
↓
TOOL
↓
TOOL RESULT
↓
OBSERVATION
↓
VERIFIER (`PhysicalFactVerifier`)
↓
VERIFIED FACT
↓
EVIDENCE (`CapabilityEvidence`)
↓
CAPABILITY REGISTRY (`CapabilityEvidenceRegistry`)
↓
MISSION GATE (`MissionCompletionGate`)
↓
FINAL STATE

## 2. Análisis de Transiciones Críticas
1. **TOOL RESULT → OBSERVATION**: Confiable si el output viene directo de la ejecución del sistema operativo o librería sandbox.
2. **OBSERVATION → VERIFIER**: Actualmente validada mediante reglas heurísticas en `PhysicalFactVerifier`, pero vulnerable si se inyectan mocks o datos sintéticos sin firma criptográfica.
3. **EVIDENCE → CAPABILITY REGISTRY**: El Registry confía en los booleanos `physical_evidence` y `verification_result` del objeto `CapabilityEvidence` sin requerir que provengan del canal autenticado del verifcador. Esto constituye la vulnerabilidad principal mapeada en la Auditoría 004.
