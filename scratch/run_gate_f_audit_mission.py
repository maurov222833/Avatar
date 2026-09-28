import os
import sys
import json
import time

# Ensure UTF-8 output encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import AvatarOrchestrator

def run_audit_mission():
    mission_text = (
        "Analiza el sistema de memoria persistente y recuperación de tareas de Avatar. "
        "Determina si existe un riesgo real de pérdida, contaminación o inconsistencia de contexto entre misiones. "
        "Investiga la arquitectura, las implementaciones y las pruebas disponibles. "
        "Si encuentras una debilidad real y suficientemente demostrada, determina qué debería hacerse y verifica mediante evidencia si la solución existente ya la resuelve o si requiere intervención. "
        "Si no encuentras una debilidad suficientemente demostrada, concluye que no hay acción justificada. "
        "Fundamenta toda conclusión con evidencia reproducible."
    )

    print("=" * 80)
    print("AVATAR AI — AUDITORÍA FINAL GATE F (EJECUCIÓN DE MISIÓN INDEPENDIENTE)")
    print(f"PROMPT DE MISIÓN: {mission_text}")
    print("=" * 80)

    orchestrator = AvatarOrchestrator()
    
    # We will run orchestrator process_user_input and capture output while printing live execution logs
    start_time = time.time()
    response = orchestrator.process_user_input(mission_text, max_steps=15)
    elapsed = time.time() - start_time

    print("=" * 80)
    print(f"MISIÓN COMPLETADA EN {elapsed:.2f}s")
    print("RESPUESTA FINAL DE AVATAR:")
    print("-" * 40)
    print(response)
    print("=" * 80)

if __name__ == "__main__":
    run_audit_mission()
