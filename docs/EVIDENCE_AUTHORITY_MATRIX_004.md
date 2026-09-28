# EVIDENCE AUTHORITY MATRIX 004

| COMPONENT | CAN OBSERVE | CAN VERIFY | CAN CREATE EVIDENCE | CAN DECLARE PHYSICAL | CAN SET VERIFIED | CAN COMPLETE MISSION |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **LLM** | NO | NO | NO | NO | NO | NO |
| **Tool** | YES | NO | NO | NO | NO | NO |
| **Orchestrator** | YES | YES | YES | PARTIAL | NO | NO |
| **PhysicalFactVerifier** | YES | YES | YES | YES | NO | NO |
| **CapabilityEvidenceRegistry**| NO | NO | NO | NO | YES | NO |
| **MissionCompletionGate** | NO | NO | NO | NO | NO | YES |
| **StateEngine** | NO | NO | NO | NO | NO | NO |
| **Tests / Mocks** | YES | NO | SYNTHETIC | SYNTHETIC | NO | NO |
| **External Caller** | NO | NO | NO | NO | NO | NO |

### Reglas Epistemológicas Fundamentales
1. `MODEL_CLAIM != FACT`: El modelo nunca puede certificar hechos.
2. `TOOL_SUCCESS != PHYSICAL_FACT`: El retorno exitoso de una función no garantiza la persistencia real del estado sin observación.
3. `PHYSICAL_FACT != CAPABILITY_VERIFIED`: Un hecho puntual no eleva una capacidad si no cumple la cobertura requerida.
4. `CAPABILITY_VERIFIED != MISSION_COMPLETED`: El cierre de misión requiere cumplir los objetivos específicos bajo la auditoría de `MissionCompletionGate`.
