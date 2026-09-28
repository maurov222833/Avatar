# EVIDENCE TRUST MODEL 001

## 1. Principio Fundamental de Confianza

En Avatar AI, la confianza en que una capacidad del sistema ha sido verificada **nunca debe basarse en afirmaciones textuales (claims)** de un LLM ni en objetos de evidencia instanciados por invocadores no confiables (`untrusted callers`).

## 2. Definiciones de Frontera

- **Claim (Nivel 0):** Afirmación generada por el LLM o un componente de control sobre el éxito de una tarea. *No posee valor epistémico por sí mismo.*
- **Observation (Nivel 1):** Datos brutos devueltos por una herramienta del sistema (`Tool Result`). *Sujeto a manipulación o interpretación errónea.*
- **Verified Fact (Nivel 2):** Hecho físico verificado de forma determinista mediante inspección del sistema operativo u operativo (`PhysicalFactVerifier`).
- **Evidence (Nivel 3):** Estructura inmutable con procedencia (`Provenance`) atada a una misión, tarea y ejecución específica.
- **Capability Verified (Nivel 4):** Estado epistemológico autoritativo determinado exclusivamente por el `CapabilityEvidenceRegistry` al validar que la evidencia satisface todos los requisitos formales.
- **Mission Completed (Nivel 5):** Resolución autoritativa dictada por el `MissionCompletionGate`.

## 3. Separación de Evidencia de Producción y Evidencia de Pruebas

- **Test Synthetic Evidence:** Creada exclusivamente para pruebas unitarias o de integración en el entorno de testing (`tests/`). No puede ser utilizada para certificar capacidades en el entorno de producción.
- **Production Physical Evidence:** Generada exclusivamente por el pipeline de verificación autoritativo (`PhysicalFactVerifier` + `AuthorizedEvidenceBuilder`).
