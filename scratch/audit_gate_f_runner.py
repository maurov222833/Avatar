import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import AvatarOrchestrator
from core.cognitive.semantic_mission_engine import SemanticMissionEngine
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.cognitive.claim_validator import ClaimValidator
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine, InvestigationState
from core.cognitive.stagnation_detector import StagnationDetector, StagnationState
from core.cognitive.structured_action_recovery import StructuredActionRecoveryLayer

def run_detailed_audit():
    mission_text = (
        "Analiza el sistema de memoria persistente y recuperación de tareas de Avatar. "
        "Determina si existe un riesgo real de pérdida, contaminación o inconsistencia de contexto entre misiones. "
        "Investiga la arquitectura, las implementaciones y las pruebas disponibles. "
        "Si encuentras una debilidad real y suficientemente demostrada, determina qué debería me hacerse y verifica mediante evidencia si la solución existente ya la resuelve o si requiere intervención. "
        "Si no encuentras una debilidad suficientemente demostrada, concluye que no hay acción justificada. "
        "Fundamenta toda conclusión con evidencia reproducible."
    )

    print("=" * 100)
    print("AVATAR AI — AUDITORÍA FINAL GATE F: EJECUCIÓN DE MISIÓN CON CAPTURA DE TRAZA COGNITIVA COMPLETA")
    print("PROMPT:")
    print(mission_text)
    print("=" * 100)

    orchestrator = AvatarOrchestrator()
    
    # We will log cognitive trace per step
    trace_log = []

    # Original process_user_input logic with instrumentation
    # Let's run process_user_input and capture output
    start_time = time.time()
    
    # Run the actual orchestrator method
    result_text = orchestrator.process_user_input(mission_text, max_steps=15)
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 100)
    print(f"EJECUCIÓN FINALIZADA EN {elapsed:.2f} SEGUNDOS")
    print("RESPUESTA FINAL DEVUELTA POR AVATAR:")
    print("=" * 100)
    print(result_text)
    print("=" * 100)

if __name__ == "__main__":
    run_detailed_audit()
