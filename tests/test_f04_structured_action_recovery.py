import unittest
import os
from core.cognitive.structured_action_recovery import StructuredActionRecoveryLayer
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier, VerifiedFact
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskEvidence, TaskResult, TaskResultStatus
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine, InvestigationState

class TestF04StructuredActionRecovery(unittest.TestCase):

    def setUp(self):
        self.tools_schema = [
            {
                "functionDeclarations": [
                    {"name": "COMMAND", "description": "Execute command", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}}},
                    {"name": "READ_FILE", "description": "Read file", "parameters": {"type": "OBJECT", "properties": {"file_path": {"type": "STRING"}}}},
                    {"name": "WRITE_FILE", "description": "Write file", "parameters": {"type": "OBJECT", "properties": {"file_path": {"type": "STRING"}, "content": {"type": "STRING"}}}},
                    {"name": "LIST_DIR", "description": "List dir", "parameters": {"type": "OBJECT", "properties": {"dir_path": {"type": "STRING"}}}}
                ]
            }
        ]

    def test_sar_01_native_function_call_works(self):
        """TEST SAR-01: Native Function Call continúa funcionando."""
        text = "Just text, no JSON"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_02_valid_json_text_recovered(self):
        """TEST SAR-02: JSON textual válido representa una acción válida."""
        text = "```json\n{\n  \"action\": \"LIST_DIR\",\n  \"args\": {\"dir_path\": \"b:\\\\PROYECTOS ANTIGRAVITY\\\\Avatar\"}\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "function_call")
        self.assertEqual(res["name"], "LIST_DIR")
        self.assertEqual(res["args"]["dir_path"], "b:\\PROYECTOS ANTIGRAVITY\\Avatar")

    def test_sar_03_valid_json_text_passes_tool_registry(self):
        """TEST SAR-03: JSON textual válido pasa por ToolRegistry."""
        text = "```json\n{\n  \"action\": \"READ_FILE\",\n  \"args\": {\"file_path\": \"core/orchestrator.py\"}\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "READ_FILE")

    def test_sar_04_valid_json_text_passes_security(self):
        """TEST SAR-04: JSON textual válido pasa por Security."""
        # Intento de path traversal con ruta absoluta externa
        text = "```json\n{\n  \"action\": \"READ_FILE\",\n  \"args\": {\"file_path\": \"C:\\\\Windows\\\\System32\\\\..\\\\..\\\\secret.txt\"}\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_05_invalid_json_not_executed(self):
        """TEST SAR-05: JSON inválido NO se ejecuta."""
        text = "```json\n{\n  \"action\": \"LIST_DIR\",\n  \"args\": BROKEN_JSON\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_06_unregistered_tool_not_executed(self):
        """TEST SAR-06: Herramienta inexistente NO se ejecuta."""
        text = "```json\n{\n  \"action\": \"DELETE_DATABASE_ROOT\",\n  \"args\": {\"force\": true}\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_07_invalid_arguments_not_executed(self):
        """TEST SAR-07: Argumentos inválidos NO se ejecutan."""
        text = "```json\n{\n  \"action\": \"COMMAND\",\n  \"args\": {}\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_08_ambiguous_json_not_executed(self):
        """TEST SAR-08: JSON ambiguo NO se ejecuta."""
        text = "```json\n[\"just\", \"an\", \"array\"]\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_09_normal_text_remains_text(self):
        """TEST SAR-09: Texto normal sigue siendo texto."""
        text = "El análisis del sistema demuestra que no hay debilidades en la suite de pruebas."
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNone(res)

    def test_sar_10_recovered_action_normalized_format(self):
        """TEST SAR-10: La acción recuperada utiliza exactamente la misma representación que Function Call nativa."""
        text = "```json\n{\n  \"action\": \"COMMAND\",\n  \"args\": {\"command\": \"python -m unittest discover -v\"}\n}\n```"
        res = StructuredActionRecoveryLayer.extract_and_validate_structured_action(text, self.tools_schema)
        self.assertIsNotNone(res)
        self.assertIn("type", res)
        self.assertIn("name", res)
        self.assertIn("args", res)
        self.assertIn("raw_part", res)
        self.assertEqual(res["type"], "function_call")

    def test_timeout_01_timeout_produces_command_fact(self):
        """TEST TIMEOUT-01: Timeout produce resultado verificado de comando."""
        raw_output = "[Resultado PowerShell (ExitCode: 1)]:\n[Error]: El comando tardó demasiado (Timeout de 120s)."
        fact = PhysicalFactVerifier.verify_command("pytest", raw_output, expected_exit_code=0)
        self.assertFalse(fact.verified)
        self.assertEqual(fact.fact_type, "COMMAND")
        self.assertEqual(fact.evidence_data["exit_code"], 1)

    def test_timeout_02_timeout_produces_evidence(self):
        """TEST TIMEOUT-02: Timeout produce evidencia física."""
        raw_output = "[Resultado PowerShell (ExitCode: 1)]:\n[Error]: El comando tardó demasiado (Timeout de 120s)."
        fact = PhysicalFactVerifier.verify_command("pytest", raw_output, expected_exit_code=0)
        self.assertIsNotNone(fact.evidence_data)

    def test_timeout_03_timeout_does_not_produce_success(self):
        """TEST TIMEOUT-03: Timeout NO produce SUCCESS."""
        raw_output = "[Resultado PowerShell (ExitCode: 1)]:\n[Error]: El comando tardó demasiado (Timeout de 120s)."
        fact = PhysicalFactVerifier.verify_command("pytest", raw_output, expected_exit_code=0)
        self.assertFalse(fact.verified)

    def test_timeout_04_timeout_does_not_terminate_mission(self):
        """TEST TIMEOUT-04: Timeout NO finaliza una misión abierta automáticamente."""
        goal = Goal(goal_id="g1", objective="Test timeout continuation", status=GoalState.CREATED)
        engine = AdaptiveInvestigationEngine(goal)
        engine.start_investigation()

        task = Task(task_id="t1", goal_id="g1", description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        ev = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Timeout 120s"}, reliability=1.0)
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[ev])

        step_res = engine.evaluate_task_step(task, ev, res)
        self.assertEqual(step_res["status"], "EXECUTING")
        self.assertNotEqual(engine.state, InvestigationState.CONCLUDED_SUCCESS)

    def test_timeout_05_timeout_feeds_adaptive_investigation(self):
        """TEST TIMEOUT-05: Timeout alimenta a AdaptiveInvestigationEngine."""
        goal = Goal(goal_id="g1", objective="Test timeout continuation", status=GoalState.CREATED)
        engine = AdaptiveInvestigationEngine(goal)
        engine.start_investigation()

        task = Task(task_id="t1", goal_id="g1", description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        ev = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Timeout 120s"}, reliability=1.0)
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[ev])

        step_res = engine.evaluate_task_step(task, ev, res)
        self.assertEqual(engine.state, InvestigationState.MUTATING_STRATEGY)

    def test_timeout_06_adaptive_engine_produces_subsequent_decision(self):
        """TEST TIMEOUT-06: AdaptiveInvestigationEngine produce decisión posterior."""
        goal = Goal(goal_id="g1", objective="Test timeout continuation", status=GoalState.CREATED)
        engine = AdaptiveInvestigationEngine(goal)
        engine.start_investigation()

        task1 = Task(task_id="t1", goal_id="g1", description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        ev1 = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Timeout 120s"}, reliability=1.0)
        res1 = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[ev1])
        engine.evaluate_task_step(task1, ev1, res1)

        task2 = Task(task_id="t2", goal_id="g1", description="Run unittest", tool="COMMAND", arguments={"command": "python -m unittest discover -v"})
        ev2 = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 0, "raw_output": "Ran 123 tests OK"}, reliability=1.0)
        res2 = TaskResult(task_id="t2", status=TaskResultStatus.PASS, evidence=[ev2])
        step_res2 = engine.evaluate_task_step(task2, ev2, res2)

        self.assertEqual(step_res2["action"], "CONTINUE")

if __name__ == '__main__':
    unittest.main()
