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
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.cognitive.claim_validator import ClaimValidator
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine
from core.cognitive.stagnation_detector import StagnationDetector, StagnationState
from core.cognitive.structured_action_recovery import StructuredActionRecoveryLayer

def run_traced_mission():
    mission_text = (
        "Analiza el sistema de memoria persistente y recuperación de tareas de Avatar. "
        "Determina si existe un riesgo real de pérdida, contaminación o inconsistencia de contexto entre misiones. "
        "Investiga la arquitectura, las implementaciones y las pruebas disponibles. "
        "Si encuentras una debilidad real y suficientemente demostrada, determina qué debería hacerse y verifica mediante evidencia si la solución existente ya la resuelve o si requiere intervención. "
        "Si no encuentras una debilidad suficientemente demostrada, concluye que no hay acción justificada. "
        "Fundamenta toda conclusión con evidencia reproducible."
    )

    print("====================================================================================================")
    print("AVATAR AI — AUDITORÍA GATE F: MISIÓN CON RASTREO COGNITIVO INTERNO DETALLADO")
    print("PROMPT DE MISIÓN:")
    print(mission_text)
    print("====================================================================================================\n")

    orchestrator = AvatarOrchestrator()
    
    # We will wrap or run process_user_input and observe step logs
    res = orchestrator.process_user_input(mission_text, max_steps=15)
    
    print("\n====================================================================================================")
    print("RESPUESTA FINAL FINALIZADA:")
    print("====================================================================================================")
    print(res)

if __name__ == "__main__":
    run_traced_mission()
