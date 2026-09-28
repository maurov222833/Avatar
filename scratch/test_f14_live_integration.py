import sys
import os

sys.path.insert(0, os.path.abspath("b:/PROYECTOS ANTIGRAVITY/Avatar"))

from core.orchestrator import AvatarOrchestrator

def run_live_f14_test():
    orc = AvatarOrchestrator()
    prompt = "Analiza el estado actual de Avatar AI, identifica una debilidad real relacionada con su capacidad de ingeniería autónoma y determina cómo debería resolverse."
    
    print("==================================================")
    print("FASE 14 — PRUEBA DE INTEGRACIÓN MULTI-TURNO REAL")
    print(f"PROMPT: {prompt}")
    print("==================================================\n")
    
    response = orc.process_user_input(prompt, max_steps=5)
    print("\n--- RESPUESTA FINAL DE AVATAR ---")
    print(response[:1500])
    print("==================================================")

if __name__ == "__main__":
    run_live_f14_test()
