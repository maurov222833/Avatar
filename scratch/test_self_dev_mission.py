import sys
import os

avatar_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if avatar_root not in sys.path:
    sys.path.insert(0, avatar_root)

from core.orchestrator import AvatarOrchestrator

def main():
    print("Testing Avatar E2E Autonomous Self-Development Mission...")
    orchestrator = AvatarOrchestrator()

    # Self-development mission containing inspect, write code, run test, verify output
    test_target_file = os.path.join(avatar_root, "scratch", "demo_module.py")
    test_file = os.path.join(avatar_root, "scratch", "test_demo_module.py")

    prompt = f"""Ejecuta autónomamente la siguiente misión de autodesarrollo:
1. WRITE_FILE: {test_target_file} ||| def add(a, b):\n    return a + b\n
2. WRITE_FILE: {test_file} ||| import unittest\nfrom scratch.demo_module import add\nclass TestDemo(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\nif __name__ == '__main__':\n    unittest.main()\n
3. COMMAND: C:\\Users\\Mauro\\AppData\\Local\\Programs\\Python\\Python312\\python.exe scratch/test_demo_module.py
"""

    result = orchestrator.process_user_input(prompt)
    print("--- SELF-DEVELOPMENT MISSION RESULT ---")
    print(result)
    print("---------------------------------------")

    assert "COMPLETED" in result or "OK" in result or "Ran 1 test" in result, "Self-development mission failed!"
    print("SUCCESS: Avatar successfully executed autonomous self-development mission!")

if __name__ == "__main__":
    main()
