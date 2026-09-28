import sys
import os
import json
import time
import traceback

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))
from core.orchestrator import AvatarOrchestrator
from core.llm_provider import LLMProvider

def execute_gate_g():
    print("==========================================")
    print("AVATAR AI — GATE G EXECUTION INITIATION")
    print("==========================================")
    
    # 1. Configurar proveedor explícito Gemini sin fallback
    llm = LLMProvider("config.json")
    llm.config["default_provider"] = "gemini"
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(llm.config, f, indent=2)
        
    orchestrator = AvatarOrchestrator()
    orchestrator.llm.config["default_provider"] = "gemini"
    
    # 2. Misión abierta exacta
    mission_prompt = (
        "Realiza una evaluación de ingeniería del estado actual de Avatar como sistema autónomo. "
        "Investiga su arquitectura, implementación, pruebas y flujo operativo. Identifica si existe una debilidad real "
        "que afecte su capacidad de desarrollo autónomo. Si encuentras una debilidad real y suficientemente demostrada, "
        "determina qué debería hacerse, implementa la corrección necesaria y verifica el resultado. Si no encuentras una "
        "debilidad suficientemente demostrada, no modifiques código simplemente para producir actividad. En ambos casos, "
        "justifica tu conclusión mediante evidencia reproducible y realiza regresión completa."
    )
    
    print(f"\n[GATE G MISSION PROMPT]:\n{mission_prompt}\n")
    print("Iniciando orquestador autónomo de Avatar...")
    
    start_time = time.time()
    try:
        response = orchestrator.process_user_input(user_input=mission_prompt, max_steps=15)
        elapsed = time.time() - start_time
        print(f"\n==========================================")
        print(f"MISIÓN COMPLETADA EN {round(elapsed, 2)}s")
        print("==========================================")
        print("\n[RESPUESTA FINAL DE AVATAR]:\n")
        print(response)
        
        with open("scratch/gate_g_final_response.txt", "w", encoding="utf-8") as f:
            f.write(response)
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n==========================================")
        print(f"ERROR EN MISIÓN GATE G TRAS {round(elapsed, 2)}s")
        print("==========================================")
        print(f"Excepción: {str(e)}")
        traceback.print_exc()
        with open("scratch/gate_g_error.txt", "w", encoding="utf-8") as f:
            f.write(f"Exception: {str(e)}\n{traceback.format_exc()}")

if __name__ == "__main__":
    execute_gate_g()
