import os

with open("core/cognitive/capability_registry.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

target = '''    def register_evidence(
        self,
        capability_id: str,
        evidence: CapabilityEvidence
    ) -> str:
        """
        Registra evidencia f?sica para una capacidad y eval?a si satisface el estado VERIFIED.
        """
        rec = self.state_db.get_capability_record(capability_id)
        if not rec:
            rec = {
                "capability_id": capability_id,
                "capability_name": capability_id,
                "required_evidence": [evidence.evidence_type],
                "required_tests": [],
                "physical_verification_required": evidence.physical_evidence,
                "verification_status": CapabilityStatus.NOT_IMPLEMENTED,
                "evidence_ids": [],
                "limitations": [],
                "dependencies": [],
                "last_verified_at": ""
            }

        if evidence.evidence_id not in rec["evidence_ids"]:
            rec["evidence_ids"].append(evidence.evidence_id)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec["last_verified_at"] = now

        # Evaluar cambio de estado determinista
        if evidence.verification_result:
            if evidence.physical_evidence:
                # Comprobar si se han cumplido los tipos de evidencia requeridos
                rec["verification_status"] = CapabilityStatus.VERIFIED
            else:
                # Test unitario o simulado sin infraestructura real
                if rec["verification_status"] not in [CapabilityStatus.VERIFIED]:
                    rec["verification_status"] = CapabilityStatus.PARTIAL
                    if "Requiere infraestructura f?sica real en vivo" not in rec["limitations"]:
                        rec["limitations"].append("Requiere infraestructura f?sica real en vivo")
        else:
            if rec["verification_status"] != CapabilityStatus.VERIFIED:
                rec["verification_status"] = CapabilityStatus.NOT_IMPLEMENTED

        self.state_db.save_capability_record(rec)
        return rec["verification_status"]'''

replacement = '''    def register_evidence(
        self,
        capability_id: str,
        evidence: CapabilityEvidence
    ) -> str:
        """
        Registra evidencia física para una capacidad y evalúa de forma determinista si satisface VERIFIED.
        REGLA EPISTÉMICA DE COBERTURA COMPLETA (Consolidación 002):
        Una capacidad SOLO asciende a CapabilityStatus.VERIFIED si Y SOLO SI TODOS los tipos de evidencia
        requeridos en rec['required_evidence'] han sido físicamente verificados.
        Si falta algún tipo requerido o si physical_evidence == False, la capacidad degrada a PARTIAL.
        """
        rec = self.state_db.get_capability_record(capability_id)
        if not rec:
            rec = {
                "capability_id": capability_id,
                "capability_name": capability_id,
                "required_evidence": [getattr(evidence.evidence_type, "value", str(evidence.evidence_type))],
                "required_tests": [],
                "physical_verification_required": evidence.physical_evidence,
                "verification_status": CapabilityStatus.NOT_IMPLEMENTED,
                "evidence_ids": [],
                "limitations": [],
                "dependencies": [],
                "last_verified_at": ""
            }

        ev_type = getattr(evidence.evidence_type, "value", str(evidence.evidence_type))
        ev_entry = {
            "id": evidence.evidence_id,
            "type": ev_type,
            "physical": bool(evidence.physical_evidence),
            "verified": bool(evidence.verification_result)
        }

        # Normalizar evidence_ids
        raw_evs = rec.get("evidence_ids", [])
        normalized_evs = []
        already_present = False
        for item in raw_evs:
            if isinstance(item, dict):
                if item.get("id") == evidence.evidence_id:
                    normalized_evs.append(ev_entry)
                    already_present = True
                else:
                    normalized_evs.append(item)
            elif isinstance(item, str):
                if item == evidence.evidence_id:
                    normalized_evs.append(ev_entry)
                    already_present = True
                else:
                    normalized_evs.append({"id": item, "type": ev_type, "physical": bool(evidence.physical_evidence), "verified": bool(evidence.verification_result)})

        if not already_present:
            normalized_evs.append(ev_entry)
        rec["evidence_ids"] = normalized_evs

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec["last_verified_at"] = now

        # EVALUACIÓN DETERMINISTA DE COBERTURA COMPLETA DE EVIDENCIA
        required_types = set(rec.get("required_evidence", []))

        present_verified_physical_types = set()
        for item in rec["evidence_ids"]:
            if isinstance(item, dict):
                if item.get("verified") and item.get("physical"):
                    present_verified_physical_types.add(item.get("type"))

        if required_types:
            missing_types = required_types - present_verified_physical_types
            if not missing_types:
                rec["verification_status"] = CapabilityStatus.VERIFIED
                rec["limitations"] = [l for l in rec.get("limitations", []) if not l.startswith("Falta evidencia física requerida")]
            else:
                rec["verification_status"] = CapabilityStatus.PARTIAL
                lim_msg = f"Falta evidencia física requerida: {', '.join(sorted(missing_types))}"
                if lim_msg not in rec.get("limitations", []):
                    rec["limitations"].append(lim_msg)
        else:
            if evidence.verification_result and evidence.physical_evidence:
                rec["verification_status"] = CapabilityStatus.VERIFIED
            else:
                rec["verification_status"] = CapabilityStatus.PARTIAL

        self.state_db.save_capability_record(rec)
        return rec["verification_status"]'''

# Execute string search and replace
start_str = "    def register_evidence("
end_str = "        return rec[\"verification_status\"]"
start_pos = text.find(start_str)
end_pos = text.find(end_str, start_pos) + len(end_str)

if start_pos != -1 and end_pos != -1:
    new_text = text[:start_pos] + replacement + text[end_pos:]
    with open("core/cognitive/capability_registry.py", "w", encoding="utf-8") as f:
        f.write(new_text)
    print("core/cognitive/capability_registry.py updated cleanly!")
else:
    print("Could not locate start/end bounds in capability_registry.py", start_pos, end_pos)
