import sys
import os

# Ensure Avatar root is in sys.path
avatar_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if avatar_root not in sys.path:
    sys.path.insert(0, avatar_root)

from core.orchestrator import AvatarOrchestrator

def main():
    print("Testing AvatarOrchestrator Multi-Task Autonomous Execution...")
    orchestrator = AvatarOrchestrator()

    prompt = (
        "Ejecuta las siguientes tareas de forma continua y autónoma:\n"
        "1. echo AVATAR_REAL_TASK_1_OK\n"
        "2. echo AVATAR_REAL_TASK_2_OK\n"
        "3. echo AVATAR_REAL_TASK_3_OK\n"
    )

    result = orchestrator.process_user_input(prompt)
    print("--- RESULT FROM ORCHESTRATOR ---")
    print(result)
    print("--------------------------------")

    assert "AVATAR_REAL_TASK_1_OK" in result, "Task 1 output missing!"
    assert "AVATAR_REAL_TASK_2_OK" in result, "Task 2 output missing!"
    assert "AVATAR_REAL_TASK_3_OK" in result, "Task 3 output missing!"

    print("SUCCESS: AvatarOrchestrator executed all 3 tasks continuously in a single interaction!")

if __name__ == "__main__":
    main()
