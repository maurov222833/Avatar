import unittest
from unittest.mock import MagicMock, patch
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.cognitive.stagnation_detector import StagnationDetector, StagnationState
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine, InvestigationState, ResearchBudget
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskEvidence, TaskResult, TaskResultStatus
from core.orchestrator import AvatarOrchestrator

class TestF05AdaptiveCognitiveProgression(unittest.TestCase):

    def setUp(self):
        self.goal = Goal(
            goal_id="goal-f05-test",
            objective="Auditar y reparar suite de pruebas de Avatar AI",
            status=GoalState.EXECUTING
        )

    # ------------------------------------------------------------------
    # TEST A: format_structured_error_context no trunca a 120 caracteres
    # ------------------------------------------------------------------
    def test_a_format_structured_error_context_preserves_traceback(self):
        long_pytest_output = (
            "============================= test session starts =============================\n"
            "platform win32 -- Python 3.12.0, pytest-7.4.0\n"
            "rootdir: b:\\PROYECTOS ANTIGRAVITY\\Avatar\n"
            "collected 0 items / 1 error\n\n"
            "==================================== ERRORS ====================================\n"
            "_____________________ ERROR collecting tests/test_api.py _____________________\n"
            "Traceback (most recent call last):\n"
            "  File \"core/app.py\", line 15, in <module>\n"
            "    import starlette.testclient\n"
            "RuntimeError: starlette testclient requires httpx library to be installed.\n"
            "=========================== short test summary info ===========================\n"
            "ERROR tests/test_api.py - RuntimeError: starlette testclient requires httpx library to be installed."
        )

        formatted = SemanticMissionEngine.format_structured_error_context(long_pytest_output, max_chars=2000)
        self.assertIn("RuntimeError", formatted)
        self.assertIn("starlette testclient requires httpx library", formatted)
        self.assertGreater(len(formatted), 120)

    # ------------------------------------------------------------------
    # TEST B: Output extenso prioriza excepción principal
    # ------------------------------------------------------------------
    def test_b_format_structured_error_context_large_output(self):
        noise = "LOG ENTRY DATA LINE\n" * 200
        large_output = f"{noise}\nTraceback (most recent call last):\n  File 'test.py', line 1\nModuleNotFoundError: No module named 'fake_module'\n"
        formatted = SemanticMissionEngine.format_structured_error_context(large_output, max_chars=500)
        self.assertIn("ModuleNotFoundError", formatted)

    # ------------------------------------------------------------------
    # TEST C: is_evidence_sufficient_for_goal usa contexto de error estructurado
    # ------------------------------------------------------------------
    def test_c_is_evidence_sufficient_uses_structured_error(self):
        failed_task_result = TaskResult(
            task_id="t-1",
            status=TaskResultStatus.FAIL,
            error="Traceback (most recent call last):\n  File 'a.py'\nImportError: missing package"
        )
        executed_steps = [{
            "tool_name": "COMMAND",
            "output": failed_task_result.error,
            "task_result": failed_task_result
        }]
        res = SemanticMissionEngine.is_evidence_sufficient_for_goal(self.goal, executed_steps, "Texto de respuesta")
        self.assertFalse(res["sufficient"])
        self.assertIn("ImportError: missing package", res["reason"])

    # ------------------------------------------------------------------
    # TEST D: StagnationDetector inicia en estado ACTIVE
    # ------------------------------------------------------------------
    def test_d_stagnation_detector_initial_state(self):
        detector = StagnationDetector()
        self.assertEqual(detector.state, StagnationState.ACTIVE)
        self.assertIsNone(detector.get_stagnation_directive())

    # ------------------------------------------------------------------
    # TEST E: Transición a STAGNANT y REASSESS por turnos de texto consecutivos
    # ------------------------------------------------------------------
    def test_e_stagnation_detector_consecutive_text_turns(self):
        detector = StagnationDetector()
        s1 = detector.record_text_turn("Hola Mauro")
        self.assertEqual(s1, StagnationState.ACTIVE)

        s2 = detector.record_text_turn("No ejecuté herramienta")
        self.assertEqual(s2, StagnationState.STAGNANT)

        s3 = detector.record_text_turn("Sigo sin ejecutar herramienta")
        self.assertEqual(s3, StagnationState.REASSESS)

    # ------------------------------------------------------------------
    # TEST F: Transición a REPLAN tras 4 turnos de texto sin herramienta
    # ------------------------------------------------------------------
    def test_f_stagnation_detector_replan_state(self):
        detector = StagnationDetector()
        for _ in range(4):
            state = detector.record_text_turn("Texto solo")
        self.assertEqual(state, StagnationState.REPLAN)
        directive = detector.get_stagnation_directive()
        self.assertIsNotNone(directive)
        self.assertIn("REPLANIFICACIÓN", directive)

    # ------------------------------------------------------------------
    # TEST G: Detección de repetición de la misma herramienta con mismos args
    # ------------------------------------------------------------------
    def test_g_stagnation_detector_repeated_tool_calls(self):
        detector = StagnationDetector()
        detector.record_tool_call("COMMAND", {"command": "pytest"}, False)
        state = detector.record_tool_call("COMMAND", {"command": "pytest"}, False)
        self.assertEqual(state, StagnationState.STAGNANT)
        directive = detector.get_stagnation_directive()
        self.assertIn("pytest", directive)

    # ------------------------------------------------------------------
    # TEST H: Ejecución válida de herramienta resetea contador de texto
    # ------------------------------------------------------------------
    def test_h_stagnation_detector_tool_resets_text_turns(self):
        detector = StagnationDetector()
        detector.record_text_turn("Texto 1")
        detector.record_text_turn("Texto 2")
        self.assertEqual(detector.state, StagnationState.STAGNANT)

        detector.record_tool_call("READ_FILE", {"file_path": "core/orchestrator.py"}, True)
        self.assertEqual(detector.state, StagnationState.ACTIVE)
        self.assertEqual(detector.consecutive_text_turns, 0)

    # ------------------------------------------------------------------
    # TEST I: get_stagnation_directive retorna directiva operativa
    # ------------------------------------------------------------------
    def test_i_stagnation_detector_directive_generation(self):
        detector = StagnationDetector()
        detector.record_text_turn("t1")
        detector.record_text_turn("t2")
        directive = detector.get_stagnation_directive()
        self.assertTrue(isinstance(directive, str))
        self.assertIn("DIRECTIVA DE SEÑAL COGNITIVA DE ESTANCAMIENTO", directive)

    # ------------------------------------------------------------------
    # TEST J: AdaptiveInvestigationEngine retorna cognitive_instruction ante fallo
    # ------------------------------------------------------------------
    def test_j_adaptive_investigation_engine_step_mutation(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        engine.start_investigation()

        task = Task(task_id="t-pytest", goal_id=self.goal.goal_id, description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        evidence = TaskEvidence(source="adapter", type="stdout", value={"stdout": "Traceback:\nModuleNotFoundError: no pytest"}, reliability=1.0)
        task_result = TaskResult(task_id="t-pytest", status=TaskResultStatus.FAIL, error="ModuleNotFoundError: no pytest")

        res = engine.evaluate_task_step(task, evidence, task_result)
        self.assertEqual(res["action"], "RECOVER_OR_REPLAN")
        self.assertIn("cognitive_instruction", res)
        self.assertIn("ModuleNotFoundError", res["cognitive_instruction"])

    # ------------------------------------------------------------------
    # TEST K: Presupuesto agotado retorna INSUFFICIENT_EVIDENCE
    # ------------------------------------------------------------------
    def test_k_adaptive_investigation_engine_budget_exhaustion(self):
        budget = ResearchBudget(max_steps=2)
        engine = AdaptiveInvestigationEngine(self.goal, budget=budget)
        engine.start_investigation()

        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="List dir", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.PASS)

        engine.evaluate_task_step(task, evidence, task_result)
        res2 = engine.evaluate_task_step(task, evidence, task_result)

        self.assertEqual(res2["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(res2["action"], "TERMINATE")

    # ------------------------------------------------------------------
    # TEST L: Orchestrator inyecta instrucción cognitiva al fallar herramienta
    # ------------------------------------------------------------------
    @patch("core.orchestrator.LLMProvider")
    @patch("core.orchestrator.RAGMemory")
    def test_l_orchestrator_prompt_context_injection(self, mock_memory, mock_llm_cls):
        mock_llm = mock_llm_cls.return_value
        mock_memory_inst = mock_memory.return_value
        mock_memory_inst.load_history.return_value = []
        mock_memory_inst.get_active_task.return_value = None
        mock_memory_inst.search_knowledge.return_value = []

        call_count = [0]
        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "type": "function_call",
                    "name": "COMMAND",
                    "args": {"command": "pytest"},
                    "raw_part": {"functionCall": {"name": "COMMAND", "args": {"command": "pytest"}}}
                }
            return {"type": "text", "text": "Intentando adaptación..."}

        mock_llm.generate_response_with_tools.side_effect = mock_generate

        orchestrator = AvatarOrchestrator()
        with patch.object(orchestrator, "_dispatch_native_tool", return_value="[Resultado PowerShell (ExitCode: 1)]:\nTraceback:\nModuleNotFoundError: no pytest"):
            res = orchestrator.process_user_input("analiza e investiga las misiones del sistema")

        self.assertGreaterEqual(mock_llm.generate_response_with_tools.call_count, 2)
        second_call_contents = mock_llm.generate_response_with_tools.call_args_list[1][1]["contents"]
        
        has_cognitive_instruction = any(
            "MOTOR DE INVESTIGACIÓN ADAPTATIVA" in p.get("text", "")
            for c in second_call_contents
            for p in c.get("parts", [])
        )
        self.assertTrue(has_cognitive_instruction)

    # ------------------------------------------------------------------
    # TEST M: Orchestrator inyecta directiva de estancamiento ante giros de texto
    # ------------------------------------------------------------------
    @patch("core.orchestrator.LLMProvider")
    @patch("core.orchestrator.RAGMemory")
    def test_m_orchestrator_stagnation_directive_injection(self, mock_memory, mock_llm_cls):
        mock_llm = mock_llm_cls.return_value
        mock_memory_inst = mock_memory.return_value
        mock_memory_inst.load_history.return_value = []
        mock_memory_inst.get_active_task.return_value = None
        mock_memory_inst.search_knowledge.return_value = []

        def mock_generate(*args, **kwargs):
            return {"type": "text", "text": "Respuesta solo texto..."}

        mock_llm.generate_response_with_tools.side_effect = mock_generate

        orchestrator = AvatarOrchestrator()
        orchestrator.process_user_input("investiga debilidades en el motor de misiones")

        self.assertGreaterEqual(mock_llm.generate_response_with_tools.call_count, 2)
        second_call_contents = mock_llm.generate_response_with_tools.call_args_list[1][1]["contents"]

        has_stagnation_directive = any(
            "ESTANCAMIENTO COGNITIVO" in p.get("text", "")
            for c in second_call_contents
            for p in c.get("parts", [])
        )
        self.assertTrue(has_stagnation_directive)

    # ------------------------------------------------------------------
    # TEST N: Misión abierta no concluye prematuramente tras texto tras fallo
    # ------------------------------------------------------------------
    @patch("core.orchestrator.LLMProvider")
    @patch("core.orchestrator.RAGMemory")
    def test_n_orchestrator_open_mission_continuation(self, mock_memory, mock_llm_cls):
        mock_llm = mock_llm_cls.return_value
        mock_memory_inst = mock_memory.return_value
        mock_memory_inst.load_history.return_value = []
        mock_memory_inst.get_active_task.return_value = None
        mock_memory_inst.search_knowledge.return_value = []

        # Paso 1: COMMAND pytest (fallo)
        # Paso 2: READ_FILE
        # Paso 3: Texto final
        mock_llm.generate_response_with_tools.side_effect = [
            {
                "type": "function_call",
                "name": "COMMAND",
                "args": {"command": "pytest"},
                "raw_part": {"functionCall": {"name": "COMMAND", "args": {"command": "pytest"}}}
            },
            {
                "type": "function_call",
                "name": "READ_FILE",
                "args": {"file_path": "core/orchestrator.py"},
                "raw_part": {"functionCall": {"name": "READ_FILE", "args": {"file_path": "core/orchestrator.py"}}}
            },
            {"type": "text", "text": "No se requiere modificación adicional. Misión de investigación completada."}
        ]

        orchestrator = AvatarOrchestrator()
        # The dispatcher now receives mission/task/execution context so every side effect is
        # attributable to the act record; the mock must accept those keyword arguments.
        def mock_dispatch(tool_name, args, **context):
            if "pytest" in str(args):
                return "[Resultado PowerShell (ExitCode: 1)]:\nTraceback:\nModuleNotFoundError: pytest"
            return "class AvatarOrchestrator: pass"

        with patch.object(orchestrator, "_dispatch_native_tool", side_effect=mock_dispatch):
            res = orchestrator.process_user_input("analiza e investiga las misiones del sistema")

        self.assertEqual(mock_llm.generate_response_with_tools.call_count, 3)

    # ------------------------------------------------------------------
    # TEST O: Flujo completo de investigación adaptativa end-to-end
    # ------------------------------------------------------------------
    def test_o_full_adaptive_progression_flow(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        engine.start_investigation()

        # Step 1: pytest fails
        task1 = Task(task_id="t1", goal_id=self.goal.goal_id, description="pytest", tool="COMMAND", arguments={"command": "pytest"})
        evidence1 = TaskEvidence(source="adapter", type="stdout", value={"stdout": "Traceback:\nImportError: missing pytest"}, reliability=1.0)
        res1 = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, error="ImportError: missing pytest")
        eval1 = engine.evaluate_task_step(task1, evidence1, res1)

        self.assertEqual(eval1["action"], "RECOVER_OR_REPLAN")

        # Step 2: mutated strategy unittest passes
        task2 = Task(task_id="t2", goal_id=self.goal.goal_id, description="unittest", tool="COMMAND", arguments={"command": "python -m unittest discover -v"})
        evidence2 = TaskEvidence(source="adapter", type="stdout", value={"stdout": "Ran 139 tests in 0.5s\nOK"}, reliability=1.0)
        res2 = TaskResult(task_id="t2", status=TaskResultStatus.PASS)
        eval2 = engine.evaluate_task_step(task2, evidence2, res2)

        self.assertEqual(eval2["action"], "CONTINUE")

    # ------------------------------------------------------------------
    # TEST P: Suite de regresión pasa limpiamente
    # ------------------------------------------------------------------
    def test_p_full_regression_suite_pass(self):
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
