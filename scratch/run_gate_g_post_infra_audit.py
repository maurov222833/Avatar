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

def run_post_infra_gate_g_audit():
    mission_text = (
        "Realiza una evaluación de ingeniería del estado actual de Avatar como sistema autónomo. "
        "Investiga su arquitectura, implementación, pruebas y comportamiento operativo. "
        "Determina si existe una debilidad real que afecte una capacidad importante del sistema. "
        "No asumas que necesariamente existe una debilidad. "
        "Si encuentras una debilidad real y suficientemente demostrada, decide autónomamente si requiere intervención. "
        "Si la requiere, diseña e implementa una corrección adecuada y verifica físicamente que resuelve el problema sin introducir regresiones. "
        "Si no encuentras una debilidad suficientemente demostrada, no modifiques código y explica qué evidencia justifica esa decisión. "
        "Toda conclusión debe estar respaldada por evidencia reproducible."
    )

    print("=" * 100)
    print("AVATAR AI — AUDITORÍA FORENSE INDEPENDIENTE GATE G POST-INFRAESTRUCTURA")
    print(f"MISIÓN ABIERTA DE INGENIERÍA:\n{mission_text}")
    print("=" * 100)

    orchestrator = AvatarOrchestrator()

    start_time = time.time()
    response = orchestrator.process_user_input(mission_text, max_steps=15)
    elapsed = time.time() - start_time

    print("=" * 100)
    print(f"EJECUCIÓN COMPLETADA EN {elapsed:.2f} SEGUNDOS")
    print("RESPUESTA FINAL DE AVATAR:")
    print("=" * 100)
    print(response)
    print("=" * 100)

if __name__ == "__main__":
    run_post_infra_gate_g_audit()
