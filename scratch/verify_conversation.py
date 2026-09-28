import sys
import os

avatar_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if avatar_root not in sys.path:
    sys.path.insert(0, avatar_root)

from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.orchestrator import AvatarOrchestrator

def main():
    prompts = [
        "Avatar estas ahí?",
        "Estas listo para trabajar conmigo",
        "Hola Avatar",
        "Ejecuta echo TEST_ACTION"
    ]
    
    print("=== PROMPT CLASSIFICATION TEST ===")
    for p in prompts:
        itype = SemanticMissionEngine.classify_interaction(p)
        print(f"Prompt: '{p}' -> InteractionType: {itype.value}")

if __name__ == "__main__":
    main()
