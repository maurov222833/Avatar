import sys
import os
import json
import requests

sys.path.insert(0, os.path.abspath("b:/PROYECTOS ANTIGRAVITY/Avatar"))

from core.orchestrator import AvatarOrchestrator, AVATAR_TOOLS_SCHEMA
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine
from core.cognitive.stagnation_detector import StagnationDetector
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.cognitive.structured_action_recovery import StructuredActionRecoveryLayer

def query_gemini_api(api_key, system_prompt, contents, tools):
    fallback_models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
    
    for model in fallback_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
            "tools": tools
        }
        try:
            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                return model, res.status_code, res.json(), payload
            elif res.status_code in [503, 429]:
                print(f"[Model Retry {res.status_code}]: {model} -> trying next fallback...")
                continue
            else:
                print(f"[Model HTTP Error {res.status_code}]: {model} -> {res.text[:200]}")
        except Exception as e:
            print(f"[Model Exception]: {model} -> {e}")
    return None, 500, {}, {}

def run_f07_audit():
    prompt = "Analiza el estado actual de Avatar AI, identifica una debilidad real relacionada con su capacidad de ingeniería autónoma y determina cómo debería resolverse."
    
    print("==================================================")
    print("F-07 FORENSIC DECISION BOUNDARY AUDIT — REPRODUCCIÓN")
    print(f"PROMPT: {prompt}")
    print("==================================================\n")

    orc = AvatarOrchestrator()
    interaction_type = SemanticMissionEngine.classify_interaction(prompt)
    current_goal = CognitiveAdapter.create_goal(prompt)
    current_goal.metadata["interaction_type"] = interaction_type.value

    investigation_engine = AdaptiveInvestigationEngine(current_goal)
    investigation_engine.start_investigation()

    contents = []

    current_system_prompt = orc.system_prompt
    if interaction_type == InteractionType.OPEN_ENGINEERING_MISSION:
        current_system_prompt += (
            f"\n\n[MISION DE INGENIERIA AUTONOMA ABIERTA EN CURSO - Goal ID: {current_goal.goal_id}]:\n"
            "Estás ejecutando una MISIÓN ABIERTA DE INGENIERÍA. Tu objetivo es investigar la arquitectura y pruebas de forma adaptativa. "
            "NUNCA te detengas o des por concluida la misión tras ejecutar únicamente un LIST_DIR o READ_FILE inicial. "
            "Debes formular hipótesis, inspeccionar archivos clave, ejecutar pruebas si es necesario y recopilar evidencia técnica "
            "comprobable antes de emitir tu dictamen final o decidir si modificar código."
        )

    contents.append({"role": "user", "parts": [{"text": prompt}]})

    api_key = orc.llm._get_api_key("gemini")

    # --- CICLO 1 ---
    print(">>> CICLO 1: LLM GENERATION <<<")
    model_c1, status_c1, data_c1, payload_c1 = query_gemini_api(api_key, current_system_prompt, contents, AVATAR_TOOLS_SCHEMA)
    print(f"[CICLO 1 REQUEST MODEL]: {model_c1}")
    print(f"[CICLO 1 HTTP STATUS]: {status_c1}")

    c1_parts = data_c1.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    c1_func = None
    c1_raw_part = None
    c1_text = None
    for p in c1_parts:
        if "functionCall" in p:
            c1_func = p["functionCall"]
            c1_raw_part = p
            break
        elif "text" in p:
            c1_text = p["text"]

    if not c1_func and c1_text:
        rec = StructuredActionRecoveryLayer.extract_and_validate_structured_action(c1_text, AVATAR_TOOLS_SCHEMA)
        if rec:
            c1_func = {"name": rec["name"], "args": rec["args"]}
            c1_raw_part = {"text": c1_text}
            print(f"[CICLO 1 RECOVERED FROM TEXT]: {c1_func['name']} args {c1_func['args']}")

    if not c1_func:
        print("[-] Ciclo 1 no devolvió functionCall nativo ni recuperable.")
        return

    tool_name_c1 = c1_func["name"]
    args_c1 = c1_func.get("args", {})
    print(f"[CICLO 1 TOOL CALL DETECTADO]: {tool_name_c1} con args {args_c1}")

    # Ejecutar herramienta 1
    tool_output_c1 = orc._dispatch_native_tool(tool_name_c1, args_c1)
    print(f"[CICLO 1 OUTPUT (primeros 300 chars)]:\n{tool_output_c1[:300]}...")

    task1 = CognitiveAdapter.create_task(goal_id=current_goal.goal_id, tool=tool_name_c1, arguments=args_c1)
    evidence1 = CognitiveAdapter.create_evidence_from_tool_output(tool_name_c1, tool_output_c1)
    task_result1 = CognitiveAdapter.build_task_result(task1.task_id, evidence1)
    verified_fact1 = PhysicalFactVerifier.verify_command(f"{tool_name_c1}", tool_output_c1)

    inv_step_res1 = investigation_engine.evaluate_task_step(task1, evidence1, task_result1, verified_fact1)

    # Construir contenido para Ciclo 2
    contents.append({
        "role": "model",
        "parts": [c1_raw_part]
    })
    contents.append({
        "role": "function",
        "parts": [{
            "functionResponse": {
                "name": tool_name_c1,
                "response": {"output": tool_output_c1}
            }
        }]
    })

    if inv_step_res1 and isinstance(inv_step_res1, dict) and "cognitive_instruction" in inv_step_res1:
        cog_inst = inv_step_res1["cognitive_instruction"]
        contents.append({
            "role": "user",
            "parts": [{"text": cog_inst}]
        })

    print("\n==================================================")
    print(">>> CICLO 2: ANÁLISIS FORENSE DEL PAYLOAD Y RESPUESTA <<<")
    print("==================================================")
    
    print("\n--- ESTRUCTURA DE CONTENTS ENVIADA EN CICLO 2 ---")
    for idx, msg in enumerate(contents):
        role = msg.get("role")
        parts = msg.get("parts", [])
        print(f"Mensaje {idx} [rol: '{role}']:")
        for p in parts:
            if "text" in p:
                print(f"  - text: {p['text'][:250]}...")
            elif "functionCall" in p:
                print(f"  - functionCall: {p['functionCall']['name']} args={p['functionCall'].get('args')}")
            elif "functionResponse" in p:
                print(f"  - functionResponse: {p['functionResponse']['name']} output_len={len(str(p['functionResponse']['response']['output']))}")
            else:
                print(f"  - part: {p}")

    print("\n--- LLAMADA HTTP A PROVIDER EN CICLO 2 ---")
    model_c2, status_c2, data_c2, payload_c2 = query_gemini_api(api_key, current_system_prompt, contents, AVATAR_TOOLS_SCHEMA)
    print(f"[CICLO 2 REQUEST MODEL]: {model_c2}")
    print(f"[CICLO 2 HTTP STATUS CODE]: {status_c2}")
    
    print("\n--- RAW RESPONSE DEL PROVIDER EN CICLO 2 ---")
    print(json.dumps(data_c2, indent=2, ensure_ascii=False))

    # Verificar PARSED response
    c2_parts = data_c2.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    c2_func = None
    c2_text = None
    for p in c2_parts:
        if "functionCall" in p:
            c2_func = p["functionCall"]
        elif "text" in p:
            c2_text = p["text"]

    print("\n--- PARSED RESPONSE EN CICLO 2 ---")
    if c2_func:
        print(f"FUNCTION CALL SELECCIONADO: {c2_func['name']} con args {c2_func.get('args')}")
    elif c2_text:
        print(f"RESPUESTA TEXTUAL: {c2_text}")
    else:
        print("RESPUESTA VACÍA O SIN CONTENIDO RECONOCIDO")

    # --- PRUEBA CONTRAFACTUAL ---
    print("\n==================================================")
    print(">>> PRUEBA CONTRAFACTUAL <<<")
    print("==================================================")
    print("Verificando si el pipeline podía ejecutar READ_FILE:")
    try:
        sample_read = orc._dispatch_native_tool("READ_FILE", {"file_path": "core/orchestrator.py"})
        print(f"[OK] READ_FILE funcional. Salida leída: {len(sample_read)} caracteres.")
        print("Resultado Contrafactual: SÍ, el pipeline habría ejecutado READ_FILE correctamente sin romper.")
    except Exception as e:
        print(f"[-] Error en prueba contrafactual: {e}")

if __name__ == "__main__":
    run_f07_audit()
