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

class TraceAuditor:
    def __init__(self):
        self.steps = []
        self.orchestrator = AvatarOrchestrator()

    def run_audit(self, mission_text: str):
        # We hook into process_user_input logic or trace its execution step by step
        print(f"Starting audit for mission:\n{mission_text}\n")
        
        # We can observe the exact steps recorded in executed_tools_summary or hook into the loop
        start_time = time.time()
        res = self.orchestrator.process_user_input(mission_text, max_steps=15)
        elapsed = time.time() - start_time
        
        return res

if __name__ == "__main__":
    auditor = TraceAuditor()
    mission = (
        "Analiza el sistema de memoria persistente y recuperación de tareas de Avatar. "
        "Determina si existe un riesgo real de pérdida, contaminación o inconsistencia de contexto entre misiones. "
        "Investiga la arquitectura, las implementaciones y las pruebas disponibles. "
        "Si encuentras una debilidad real y suficientemente demostrada, determina qué debería hacerse y verifica mediante evidencia si la solución existente ya la resuelve o si requiere intervención. "
        "Si no encuentras una debilidad suficientemente demostrada, concluye que no hay acción justificada. "
        "Fundamenta toda conclusión con evidencia reproducible."
    )
    res = auditor.run_audit(mission)
    print("FINISHED AUDIT RUN.")
