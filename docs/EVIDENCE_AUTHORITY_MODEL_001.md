# EVIDENCE AUTHORITY MODEL 001

## 1. Separación de Autoridades

Para evitar la auto-certificación por parte de invocadores no confiables, el sistema define tres autoridades estrictamente separadas:

### Authority A: Fact Authority (Autoridad de Hechos)
- **Componente:** `PhysicalFactVerifier`
- **Responsabilidad:** Inspeccionar el sistema operativo y el sistema de archivos de forma determinista y convertir observaciones en `VerifiedFact`. Ningún otro componente puede declarar que un hecho físico ocurrió.

### Authority B: Capability Authority (Autoridad de Capacidades)
- **Componente:** `CapabilityEvidenceRegistry`
- **Responsabilidad:** Evaluar si un conjunto de hechos verificados y autorizados satisface los requisitos formales de una capacidad. No puede verificar hechos por sí mismo; solo evalúa cobertura.

### Authority C: Mission Authority (Autoridad de Misión)
- **Componente:** `MissionCompletionGate`
- **Responsabilidad:** Determinar si las condiciones y objetivos de una misión están satisfechos en función de las capacidades y hechos verificados.

---

## 2. Grafo de Autoridad Objetivo

```
[Tool / External Input] (UNTRUSTED)
         ↓
[PhysicalFactVerifier] (FACT AUTHORITY) → Genera VerifiedFact
         ↓
[AuthorizedEvidenceBuilder] (EVIDENCE AUTHORITY) → Genera Evidence con Provenance
         ↓
[CapabilityEvidenceRegistry] (CAPABILITY AUTHORITY) → Determina CapabilityStatus.VERIFIED
         ↓
[MissionCompletionGate] (MISSION AUTHORITY) → Determina Mission Completed
         ↓
[StateEngine] (PERSISTENCE AUTHORITY) → Persiste en SQLite WAL
```
