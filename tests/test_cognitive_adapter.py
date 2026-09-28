import unittest
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.models import (
    Goal,
    GoalState,
    Task,
    TaskState,
    TaskEvidence,
    TaskResultStatus,
)

class TestCognitiveAdapter(unittest.TestCase):

    def test_cg_001_create_goal(self):
        """TEST-CG-001: Creación de Goal."""
        goal = CognitiveAdapter.create_goal("Test objective")
        self.assertIsNotNone(goal.goal_id)
        self.assertEqual(goal.objective, "Test objective")
        self.assertEqual(goal.status, GoalState.CREATED)

    def test_cg_002_create_task(self):
        """TEST-CG-002: Creación de Task."""
        goal = CognitiveAdapter.create_goal("Test goal")
        task = CognitiveAdapter.create_task(goal.goal_id, "COMMAND", {"command": "echo test"})
        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.goal_id, goal.goal_id)
        self.assertEqual(task.tool, "COMMAND")
        self.assertEqual(task.state, TaskState.CREATED)

    def test_cg_003_valid_single_task_plan(self):
        """TEST-CG-003: Plan válido de una tarea."""
        goal = CognitiveAdapter.create_goal("Single task goal")
        task = CognitiveAdapter.create_task(goal.goal_id, "COMMAND", {"command": "echo test"})
        plan = CognitiveAdapter.create_single_task_plan(goal, task)
        self.assertEqual(len(plan.tasks), 1)
        self.assertEqual(plan.goal_id, goal.goal_id)

    def test_cg_004_invalid_plan_rejected(self):
        """TEST-CG-004: Plan inválido rechazado."""
        goal = CognitiveAdapter.create_goal("Invalid plan goal")
        task = CognitiveAdapter.create_task(
            goal.goal_id, "COMMAND", {"command": "echo test"}, dependencies=["non_existent_task"]
        )
        with self.assertRaises(ValueError):
            CognitiveAdapter.create_single_task_plan(goal, task)

    def test_cg_005_convert_tool_output_to_evidence(self):
        """TEST-CG-005: Conversión de resultado real a Evidence."""
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nAVATAR_COGNITIVE_OK"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.source, "COMMAND")
        self.assertEqual(evidence.value["exit_code"], 0)
        self.assertEqual(evidence.value["stdout"], "AVATAR_COGNITIVE_OK")

    def test_cg_006_pass_result_with_valid_evidence(self):
        """TEST-CG-006: Resultado PASS con evidencia válida."""
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nAVATAR_COGNITIVE_OK"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        result = CognitiveAdapter.build_task_result("t-001", evidence)
        self.assertEqual(result.status, TaskResultStatus.PASS)
        self.assertTrue(result.status.is_success())
        self.assertEqual(len(result.evidence), 1)

    def test_cg_007_fail_result_with_error_evidence(self):
        """TEST-CG-007: Resultado FAIL con evidencia de error."""
        raw_output = "[Resultado PowerShell (ExitCode: 1)]:\nstderr:\nCommand not found"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        result = CognitiveAdapter.build_task_result("t-002", evidence)
        self.assertEqual(result.status, TaskResultStatus.FAIL)
        self.assertFalse(result.status.is_success())

    def test_cg_008_unknown_result_without_evidence(self):
        """TEST-CG-008: Resultado UNKNOWN sin evidencia."""
        result = CognitiveAdapter.build_task_result("t-003", evidence=None, forced_status=TaskResultStatus.UNKNOWN)
        self.assertEqual(result.status, TaskResultStatus.UNKNOWN)
        self.assertFalse(result.status.is_success())

    def test_cg_009_no_evidence_result_without_evidence(self):
        """TEST-CG-009: Resultado NO_EVIDENCE sin evidencia."""
        result = CognitiveAdapter.build_task_result("t-004", evidence=None)
        self.assertEqual(result.status, TaskResultStatus.NO_EVIDENCE)
        self.assertFalse(result.status.is_success())

    def test_cg_010_llm_text_cannot_produce_pass(self):
        """TEST-CG-010: Texto del LLM no puede convertirse directamente en PASS."""
        llm_text = "He ejecutado el comando exitosamente."
        result = CognitiveAdapter.build_result_from_llm_text_attempt("t-005", llm_text)
        self.assertNotEqual(result.status, TaskResultStatus.PASS)
        self.assertEqual(result.status, TaskResultStatus.NO_EVIDENCE)
        self.assertFalse(result.status.is_success())

if __name__ == "__main__":
    unittest.main()
