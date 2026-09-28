import os
import sys
import json
import time

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import AvatarOrchestrator

def run_post_phase15_audit():
    mission_text = (
        "Analiza el sistema de memoria persistente y recuperación de tareas de Avatar. "
        "Determina si existe algún riesgo real de pérdida, contaminación o inconsistencia de contexto entre misiones. "
        "Investiga la implementación y las pruebas disponibles. "
        "Si encuentras una debilidad suficientemente demostrada, determina qué debería hacerse y verifica si la implementación actual ya la resuelve. "
        "Si no encuentras una debilidad suficientemente demostrada, explica por qué la evidencia disponible no justifica una intervención."
    )

    print("=" * 100)
    print("AVATAR AI — AUDITORÍA FORENSE INDEPENDIENTE GATE F POST-FASE 15")
    print(f"MISIÓN ABIERTA: {mission_text}")
    print("=" * 100)

    orchestrator = AvatarOrchestrator()
    
    start_time = time.time()
    response = orchestrator.process_user_input(mission_text, max_steps=15)
    elapsed = time.time() - start_time

    print("=" * 100)
    print(f"EJECUCIÓN FINALIZADA EN {elapsed:.2f} SEGUNDOS")
    print("RESPUESTA FINAL DE AVATAR:")
    print("=" * 100)
    print(response)
    print("=" * 100)

if __name__ == "__main__":
    run_post_phase15_audit()
