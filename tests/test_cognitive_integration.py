import unittest
import os
from core.orchestrator import AvatarOrchestrator
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.verifier import Verifier
from core.cognitive.models import TaskResultStatus, TaskState
from tools.shell_tool import ShellTool
from tools.file_tool import FileTool

class TestCognitivePipelineIntegration(unittest.TestCase):

    def setUp(self):
        self.orchestrator = AvatarOrchestrator()

    def test_e2e_001_multi_task_execution_flow(self):
        """TEST-E2E-001: Flujo completo multi-tarea determinista a través de process_user_input()."""
        user_input = (
            "1. Tarea 1: echo TEST_E2E_OUTPUT_1\n"
            "2. Tarea 2: echo TEST_E2E_OUTPUT_2"
        )
        user_input = "avatar-exec:\n" + user_input
        self.orchestrator.chokepoint.policy.exec_requires_approval = False
        response = self.orchestrator.process_user_input(user_input)
        self.assertIn("Ejecución Multi-Tarea Continua Completada", response)
        self.assertIn("TEST_E2E_OUTPUT_1", response)
        self.assertIn("TEST_E2E_OUTPUT_2", response)
        self.assertIn("- **Tareas Exitosas:** 2/2", response)

    def test_e2e_002_verifier_sole_authority(self):
        """TEST-E2E-002: El Verifier evalúa correctamente éxito y rechaza la ausencia de criterios."""
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nSUCCESS_PATTERN_CHECK"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        
        # Con criterio de salida correcto -> PASS
        result_pass = Verifier.verify("task-e2e-1", evidence, {"expected_stdout_contains": "SUCCESS_PATTERN_CHECK"})
        self.assertEqual(result_pass.status, TaskResultStatus.PASS)

        # Con criterio de salida ausente -> FAIL
        result_fail = Verifier.verify("task-e2e-2", evidence, {"expected_stdout_contains": "NON_EXISTENT_PATTERN"})
        self.assertEqual(result_fail.status, TaskResultStatus.FAIL)

    def test_e2e_003_workspace_security_boundary(self):
        """TEST-E2E-003: Bloqueo de seguridad al intentar operar fuera del workspace permitido."""
        outside_path = "C:\\Windows\\System32\\calc.exe"
        read_res = FileTool.read_file(outside_path)
        self.assertIn("[Seguridad]", read_res)

        cmd_res = ShellTool.execute_command("dir", cwd="C:\\Windows")
        self.assertIn("[Seguridad]", cmd_res)

if __name__ == "__main__":
    unittest.main()
