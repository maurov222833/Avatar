import os

with open("core/cognitive/capability_registry.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

target = '''        # Evaluar cambio de estado determinista
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
                rec["verification_status"] = CapabilityStatus.NOT_IMPLEMENTED'''

replacement = '''        # Formatear entrada de evidencia estructurada
        ev_entry = {
            "id": evidence.evidence_id,
            "type": evidence.evidence_type,
            "physical": bool(evidence.physical_evidence),
            "verified": bool(evidence.verification_result)
        }

        # Registrar entrada en evidence_ids evitando duplicados
        existing_evs = rec.get("evidence_ids", [])
        already_present = False
        for item in existing_evs:
            if isinstance(item, dict) and item.get("id") == evidence.evidence_id:
                item.update(ev_entry)
                already_present = True
                break
            elif isinstance(item, str) and item == evidence.evidence_id:
                already_present = True
                break

        if not already_present:
            existing_evs.append(ev_entry)
        rec["evidence_ids"] = existing_evs

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec["last_verified_at"] = now

        # EVALUACIÓN DETERMINISTA DE COBERTURA COMPLETA DE EVIDENCIA (Consolidación 002)
        required_types = set(rec.get("required_evidence", []))

        # Recopilar tipos de evidencia físicamente verificados
        present_verified_physical_types = set()
        for item in rec["evidence_ids"]:
            if isinstance(item, dict):
                if item.get("verified") and item.get("physical"):
                    present_verified_physical_types.add(item.get("type"))
            elif isinstance(item, str):
                if evidence.verification_result and evidence.physical_evidence:
                    present_verified_physical_types.add(evidence.evidence_type)

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
                rec["verification_status"] = CapabilityStatus.PARTIAL'''

# Execute search and replace ignoring non-ascii artifacts in target
target_start = '        # Evaluar cambio de estado determinista'
target_end = 'rec["verification_status"] = CapabilityStatus.NOT_IMPLEMENTED'

idx_start = text.find(target_start)
idx_end = text.find(target_end, idx_start) + len(target_end)

if idx_start != -1 and idx_end != -1:
    new_text = text[:idx_start] + replacement + text[idx_end:]
    with open("core/cognitive/capability_registry.py", "w", encoding="utf-8") as f:
        f.write(new_text)
    print("capability_registry.py hardened successfully!")
else:
    print("Target NOT found in capability_registry.py!", idx_start, idx_end)
