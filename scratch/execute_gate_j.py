import sys
import os
import json
import time
import traceback

sys.path.insert(0, os.path.abspath("."))
from core.orchestrator import AvatarOrchestrator
from core.llm_provider import LLMProvider

def execute_gate_j():
    print("==========================================")
    print("AVATAR AI — GATE J EXECUTION INITIATION")
    print("==========================================")
    
    # 1. Configurar proveedor explícito Gemini sin fallback
    llm = LLMProvider("config.json")
    llm.config["default_provider"] = "gemini"
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(llm.config, f, indent=2)
        
    orchestrator = AvatarOrchestrator()
    orchestrator.llm.config["default_provider"] = "gemini"
    
    # 2. Misión abierta de ingeniería de Gate J
    mission_prompt = (
        "Realiza una evaluación técnica de resiliencia y recuperación de Avatar ante fallos. "
        "Investiga la arquitectura del proyecto, ejecuta diagnósticos de pruebas, analiza qué ocurre ante errores "
        "o fallos de entorno, comprueba si el motor de recuperación (RecoveryEngine) y el detector de estancamiento "
        "(StagnationDetector) funcionan según lo especificado sin caer en bucles repetitivos de comandos, "
        "y emite un dictamen final justificado con evidencia física reproducible de regresión completa."
    )
    
    print(f"\n[GATE J MISSION PROMPT]:\n{mission_prompt}\n")
    print("Iniciando orquestador autónomo de Avatar...")
    
    start_time = time.time()
    try:
        response = orchestrator.process_user_input(user_input=mission_prompt, max_steps=15)
        elapsed = time.time() - start_time
        print(f"\n==========================================")
        print(f"MISIÓN GATE J COMPLETADA EN {round(elapsed, 2)}s")
        print("==========================================")
        print("\n[RESPUESTA FINAL DE AVATAR]:\n")
        print(response)
        
        with open("scratch/gate_j_final_response.txt", "w", encoding="utf-8") as f:
            f.write(response)
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n==========================================")
        print(f"ERROR EN MISIÓN GATE J TRAS {round(elapsed, 2)}s")
        print("==========================================")
        print(f"Excepción: {str(e)}")
        traceback.print_exc()
        with open("scratch/gate_j_error.txt", "w", encoding="utf-8") as f:
            f.write(f"Exception: {str(e)}\n{traceback.format_exc()}")

if __name__ == "__main__":
    execute_gate_j()
