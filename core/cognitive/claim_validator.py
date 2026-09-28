import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from core.cognitive.physical_fact_verifier import VerifiedFact
from core.cognitive.capability_registry import CapabilityEvidenceRegistry, CapabilityStatus
from core.cognitive.mission_completion_gate import MissionCompletionGate, MissionStatus

@dataclass
class ClaimValidationResult:
    original_text: str
    sanitized_text: str
    detected_claims: List[Dict[str, Any]]
    unverified_claims: List[Dict[str, Any]]
    verified_claims: List[Dict[str, Any]]

class ClaimValidator:
    """
    Validador de Afirmaciones del LLM para Avatar AI (Forensic Repair 002).
    Diferencia inequívocamente entre MODEL_CLAIM y VERIFIED_FACT.
    Intercepta afirmaciones sobre creación/modificación de archivos, estados de capacidad
    (CAPABILITY = VERIFIED) y estados de misión (MISSION_STATUS = COMPLETED).
    Demanda respaldo en CapabilityEvidenceRegistry y MissionCompletionGate.
    """

    @staticmethod
    def extract_engineering_claims(llm_text: str) -> List[Dict[str, Any]]:
        claims = []
        if not llm_text:
            return claims

        # 1. Buscar patrones de creación de archivos
        patterns_creation = [
            r'(?:se creó|he creado|se ha creado|creó|creando|crear|se decidió crear|creación de)(?:\s+(?:el|un|una|la|nueva|nuevo)?\s*(?:archivo|suite|test|prueba|fichero)?)*\s+[`"]?([a-zA-Z0-9_\-\/\.\\\:]+\.(?:py|txt|json|md|sh|ps1))[`"]?',
            r'[`"]?([a-zA-Z0-9_\-\/\.\\\:]+\.(?:py|txt|json|md|sh|ps1))[`"]?\s+(?:fue creado|ha sido creado|se ha creado)'
        ]

        for pat in patterns_creation:
            for match in re.finditer(pat, llm_text, re.IGNORECASE):
                path = match.group(1).strip()
                claims.append({
                    "claim_type": "FILE_CREATION",
                    "target_path": path,
                    "target": path,
                    "matched_text": match.group(0)
                })

        # 2. Buscar patrones de modificación de archivos
        patterns_modification = [
            r'(?:se modificó|he modificado|se ha modificado|modificó|modificar el archivo)\s+[`"]?([a-zA-Z0-9_\-\/\.\\\:]+\.(?:py|txt|json|md|sh|ps1))[`"]?'
        ]

        for pat in patterns_modification:
            for match in re.finditer(pat, llm_text, re.IGNORECASE):
                path = match.group(1).strip()
                claims.append({
                    "claim_type": "FILE_MODIFICATION",
                    "target_path": path,
                    "target": path,
                    "matched_text": match.group(0)
                })

        # 3. Buscar patrones de afirmaciones de estado de capacidad (ej: "CAPABILITY_WHATSAPP: VERIFIED", "WhatsApp: VERIFIED")
        patterns_capability = [
            r'(?:CAPABILITY_|CAPABILITY\s*[\:\=]?\s*)([a-zA-Z0-9_\-]+)\s*[\:\=]\s*(?:VERIFIED|VERIFICADA|VERIFICADO)',
            r'([a-zA-Z0-9_\-]+)\s*:\s*VERIFIED'
        ]

        for pat in patterns_capability:
            for match in re.finditer(pat, llm_text, re.IGNORECASE):
                cap_id = match.group(1).strip()
                # Filtrar palabras clave genéricas
                if cap_id.upper() not in ["STATUS", "AUDIT_STATUS", "MASTER_MISSION_STATUS", "REGRESSION_STATUS", "STATE"]:
                    claims.append({
                        "claim_type": "CAPABILITY_VERIFIED",
                        "target_capability": cap_id,
                        "target": cap_id,
                        "matched_text": match.group(0)
                    })

        # 4. Buscar patrones de estado de misión completada
        patterns_mission = [
            r'(?:MASTER_MISSION_STATUS|MISSION_STATUS|AUDIT_STATUS)\s*=\s*(?:COMPLETED|COMPLETED_WITH_VERIFIED_EVIDENCE)',
            r'STATUS\s*=\s*COMPLETED'
        ]

        for pat in patterns_mission:
            for match in re.finditer(pat, llm_text, re.IGNORECASE):
                claims.append({
                    "claim_type": "MISSION_COMPLETED",
                    "target": "MISSION",
                    "matched_text": match.group(0)
                })

        return claims

    @staticmethod
    def validate_llm_claims(
        llm_text: str,
        verified_facts: List[VerifiedFact],
        capability_registry: Optional[CapabilityEvidenceRegistry] = None,
        critical_gaps: int = 0,
        blocking_findings: int = 0,
        state_db=None,
        mission_id: str = ""
    ) -> ClaimValidationResult:
        detected_claims = ClaimValidator.extract_engineering_claims(llm_text)
        verified_claims = []
        unverified_claims = []
        sanitized_text = llm_text

        # Rastrear rutas de archivos verificados físicamente
        verified_paths = set()
        for fact in verified_facts:
            if fact.verified and fact.target:
                normalized = fact.target.replace("\\", "/").lower()
                verified_paths.add(normalized)

        for claim in detected_claims:
            claim_type = claim["claim_type"]

            if claim_type in ["FILE_CREATION", "FILE_MODIFICATION"]:
                target = claim["target_path"].replace("\\", "/").lower()
                is_verified = any(target in v_path or v_path in target for v_path in verified_paths)
                if is_verified:
                    verified_claims.append(claim)
                else:
                    unverified_claims.append(claim)

            elif claim_type == "CAPABILITY_VERIFIED":
                cap_id = claim.get("target_capability", "").upper()
                # Normalizar alias comunes (ej: WhatsApp -> CAP_WHATSAPP_AUTO_REPLY)
                if not cap_id.startswith("CAP_"):
                    if "WHATSAPP" in cap_id:
                        cap_id = "CAP_WHATSAPP_AUTO_REPLY"
                    elif "BROWSER" in cap_id or "PLAYWRIGHT" in cap_id:
                        cap_id = "CAP_PLAYWRIGHT_BROWSER"
                    elif "DESKTOP" in cap_id or "VISION" in cap_id:
                        cap_id = "CAP_DESKTOP_VISION"
                    elif "STATE" in cap_id:
                        cap_id = "CAP_STATE_ENGINE"
                    elif "CHECKPOINT" in cap_id:
                        cap_id = "CAP_CHECKPOINT_RESUME"

                status = capability_registry.get_capability_status(cap_id) if capability_registry else CapabilityStatus.NOT_IMPLEMENTED
                if status == CapabilityStatus.VERIFIED:
                    verified_claims.append(claim)
                else:
                    unverified_claims.append(claim)

            elif claim_type == "MISSION_COMPLETED":
                # D-7: an LLM assertion of completion is never self-certifying. A mission
                # claim is only credible when the deterministic gate, evaluated against the
                # persisted requirements and current evidence, says the mission may complete.
                gate_allows = False
                if state_db and mission_id:
                    try:
                        from core.cognitive.mission_completion_gate import (
                            MissionCompletionGate,
                            read_mission_requirements,
                        )
                        from core.cognitive.capability_registry import CapabilityEvidenceRegistry
                        # D-5: the gate must see the mission's *persisted* requirements, not
                        # an empty list supplied here, or a claim would be judged against a
                        # weaker requirement set than the one the mission actually has.
                        required, declared = read_mission_requirements(state_db, mission_id)
                        gate_result = MissionCompletionGate.evaluate_mission_completion(
                            mission_id=mission_id,
                            required_capabilities=required,
                            critical_gaps=critical_gaps,
                            blocking_findings=blocking_findings,
                            capability_registry=capability_registry or CapabilityEvidenceRegistry(state_db=state_db),
                            state_db=state_db,
                            requirements_declared=declared,
                        )
                        gate_allows = bool(gate_result.can_complete)
                    except Exception:
                        gate_allows = False
                if gate_allows:
                    verified_claims.append(claim)
                else:
                    unverified_claims.append(claim)

        if unverified_claims:
            annotations = []
            for unv in unverified_claims:
                ctype = unv["claim_type"]
                mtext = unv["matched_text"]
                if ctype in ["FILE_CREATION", "FILE_MODIFICATION"]:
                    annotations.append(
                        f"\n> ⚠️ **[AUDITORÍA DE EVIDENCIA FÍSICA - AFIRMACIÓN NO VERIFICADA]**: "
                        f"El sistema detectó la afirmación: *\"{mtext}\"*, pero **NO** existe evidencia física "
                        f"de la ejecución de la herramienta correspondiente en el disco (`FILE_EXISTS = False`)."
                    )
                elif ctype == "CAPABILITY_VERIFIED":
                    annotations.append(
                        f"\n> ⚠️ **[AUDITORÍA DE AUTORIDAD EPISTÉMICA - AFIRMACIÓN DE CAPACIDAD DEGRADADA]**: "
                        f"El sistema detectó la afirmación *\"{mtext}\"*, pero se degradó a **`UNVERIFIED_CLAIM`** porque NO existe evidencia física operacional registrada en `CapabilityEvidenceRegistry`."
                    )
                elif ctype == "MISSION_COMPLETED":
                    annotations.append(
                        f"\n> ⚠️ **[AUDITORÍA DE AUTORIDAD EPISTÉMICA - ESTADO DE MISIÓN DEGRADADO]**: "
                        f"El sistema detectó la afirmación *\"{mtext}\"*, pero el `MissionCompletionGate` degradó el estado de la misión porque existen brechas críticas ({critical_gaps}) o hallazgos bloqueantes ({blocking_findings}) pendientes de resolución."
                    )

            sanitized_text = sanitized_text + "\n" + "\n".join(annotations)

        return ClaimValidationResult(
            original_text=llm_text,
            sanitized_text=sanitized_text,
            detected_claims=detected_claims,
            unverified_claims=unverified_claims,
            verified_claims=verified_claims
        )
