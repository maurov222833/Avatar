import sys
import os

sys.path.insert(0, os.path.abspath("b:/PROYECTOS ANTIGRAVITY/Avatar"))

from core.orchestrator import AvatarOrchestrator

def run_behavioral_audit():
    orc = AvatarOrchestrator()
    
    print("\n==================================================", flush=True)
    print("MISIÓN A — PROCESAMIENTO CON AVATAR ORCHESTRATOR", flush=True)
    prompt_a = "Analiza el estado actual de Avatar AI, identifica una debilidad real relacionada con su capacidad de ingeniería autónoma y determina cómo debería resolverse."
    print(f"PROMPT A: {prompt_a}\n", flush=True)
    
    res_a = orc.process_user_input(prompt_a, max_steps=5)
    print("\n--- RESULTADO FINAL MISIÓN A ---", flush=True)
    print(res_a, flush=True)
    print("==================================================\n", flush=True)
    
    print("\n==================================================", flush=True)
    print("MISIÓN B — PROCESAMIENTO CON AVATAR ORCHESTRATOR", flush=True)
    prompt_b = "Audita la arquitectura de memoria persistente y recuperación de tareas en Avatar AI, identifica un riesgo potencial de consistencia de estado y determina la solución técnica recomendada."
    print(f"PROMPT B: {prompt_b}\n", flush=True)
    
    res_b = orc.process_user_input(prompt_b, max_steps=5)
    print("\n--- RESULTADO FINAL MISIÓN B ---", flush=True)
    print(res_b, flush=True)
    print("==================================================\n", flush=True)

if __name__ == "__main__":
    run_behavioral_audit()
