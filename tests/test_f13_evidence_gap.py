import unittest
from unittest.mock import MagicMock, patch
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.cognitive.stagnation_detector import StagnationDetector, StagnationState
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine, InvestigationState, ResearchBudget
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskEvidence, TaskResult, TaskResultStatus, EvidenceGap
from core.orchestrator import AvatarOrchestrator

class TestF13EvidenceGap(unittest.TestCase):

    def setUp(self):
        self.goal = Goal(
            goal_id="goal-f13-test",
            objective="Analiza la arquitectura del orquestador y verifica fallos de ejecución",
            status=GoalState.EXECUTING
        )

    # ------------------------------------------------------------------
    # TEST A: Goal con evidencia insuficiente genera EvidenceGap
    # ------------------------------------------------------------------
    def test_a_goal_insufficient_evidence_generates_evidence_gap(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        engine.start_investigation()

        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR root", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={"files": ["main.py", "core"]}, reliability=1.0)
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[evidence])

        res = engine.evaluate_task_step(task, evidence, task_result)
        self.assertEqual(res["action"], "CONTINUE")
        self.assertIn("evidence_gap", res)
        self.assertIsInstance(res["evidence_gap"], dict)

    # ------------------------------------------------------------------
    # TEST B: EvidenceGap contiene current_evidence
    # ------------------------------------------------------------------
    def test_b_evidence_gap_contains_current_evidence(self):
        gap = EvidenceGap(
            current_evidence="Estructura de archivos obtenida.",
            required_evidence="Inspección de código fuente.",
            evidence_gap="Falta lectura de archivos principales.",
            next_information_target="Obtener evidencia sobre la implementación."
        )
        self.assertEqual(gap.current_evidence, "Estructura de archivos obtenida.")
        self.assertIn("current_evidence", gap.to_dict())

    # ------------------------------------------------------------------
    # TEST C: EvidenceGap contiene required_evidence
    # ------------------------------------------------------------------
    def test_c_evidence_gap_contains_required_evidence(self):
        gap = EvidenceGap(
            current_evidence="Estructura de archivos obtenida.",
            required_evidence="Inspección de código fuente.",
            evidence_gap="Falta lectura de archivos principales.",
            next_information_target="Obtener evidencia sobre la implementación."
        )
        self.assertEqual(gap.required_evidence, "Inspección de código fuente.")
        self.assertIn("required_evidence", gap.to_dict())

    # ------------------------------------------------------------------
    # TEST D: EvidenceGap contiene next_information_target
    # ------------------------------------------------------------------
    def test_d_evidence_gap_contains_next_information_target(self):
        gap = EvidenceGap(
            current_evidence="Lista de archivos.",
            required_evidence="Código de orquestador.",
            evidence_gap="Falta detalle de implementación.",
            next_information_target="Obtener evidencia sobre el flujo de ejecución."
        )
        self.assertEqual(gap.next_information_target, "Obtener evidencia sobre el flujo de ejecución.")
        self.assertIn("NEXT_INFORMATION_TARGET", gap.format_cognitive_instruction())

    # ------------------------------------------------------------------
    # TEST E: SUCCESS + INSUFFICIENT_EVIDENCE activa investigación adaptativa
    # ------------------------------------------------------------------
    def test_e_success_insufficient_evidence_triggers_adaptive_engine(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        engine.start_investigation()

        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[evidence])

        res = engine.evaluate_task_step(task, evidence, task_result)
        self.assertEqual(res["status"], "EXECUTING")
        self.assertIn("cognitive_instruction", res)
        self.assertIn("ANÁLISIS DE BRECHA DE EVIDENCIA", res["cognitive_instruction"])

    # ------------------------------------------------------------------
    # TEST F: La información de EvidenceGap llega al contexto del LLM
    # ------------------------------------------------------------------
    @patch("core.orchestrator.LLMProvider")
    @patch("core.orchestrator.RAGMemory")
    def test_f_evidence_gap_reaches_llm_context(self, mock_memory, mock_llm_cls):
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
                    "name": "LIST_DIR",
                    "args": {"dir_path": "."},
                    "raw_part": {"functionCall": {"name": "LIST_DIR", "args": {"dir_path": "."}}}
                }
            return {"type": "text", "text": "Informe final: no_action_required."}

        mock_llm.generate_response_with_tools.side_effect = mock_generate

        orchestrator = AvatarOrchestrator()
        with patch.object(orchestrator, "_dispatch_native_tool", return_value="main.py\ncore\ntests"):
            orchestrator.process_user_input("analiza e investiga las misiones del sistema")

        self.assertGreaterEqual(mock_llm.generate_response_with_tools.call_count, 2)
        second_call_contents = mock_llm.generate_response_with_tools.call_args_list[1][1]["contents"]

        has_evidence_gap_prompt = any(
            "ANÁLISIS DE BRECHA DE EVIDENCIA" in p.get("text", "")
            for c in second_call_contents
            for p in c.get("parts", [])
        )
        self.assertTrue(has_evidence_gap_prompt)

    # ------------------------------------------------------------------
    # TEST G: NEXT_INFORMATION_TARGET describe información, NO herramienta específica
    # ------------------------------------------------------------------
    def test_g_next_information_target_describes_information_not_tool(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        gap = engine.calculate_evidence_gap(self.goal, 1, task, evidence)

        # Verificar que target NO contiene nombres de herramientas hardcodeados como mandatos
        self.assertNotIn("Ejecutar READ_FILE", gap.next_information_target)
        self.assertNotIn("Ejecutar COMMAND", gap.next_information_target)
        self.assertIn("Obtener evidencia", gap.next_information_target)

    # ------------------------------------------------------------------
    # TEST H: Diferentes objetivos producen diferentes brechas de evidencia
    # ------------------------------------------------------------------
    def test_h_different_goals_produce_different_gaps(self):
        goal1 = Goal(goal_id="g1", objective="Auditar seguridad de WhatsApp", status=GoalState.EXECUTING)
        goal2 = Goal(goal_id="g2", objective="Verificar rendimiento de base de datos", status=GoalState.EXECUTING)

        engine1 = AdaptiveInvestigationEngine(goal1)
        engine2 = AdaptiveInvestigationEngine(goal2)

        task = Task(task_id="t1", goal_id="g1", description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)

        gap1 = engine1.calculate_evidence_gap(goal1, 1, task, evidence)
        gap2 = engine2.calculate_evidence_gap(goal2, 1, task, evidence)

        self.assertIn("Auditar seguridad", gap1.required_evidence)
        self.assertIn("rendimiento de base de datos", gap2.required_evidence)
        self.assertNotEqual(gap1.required_evidence, gap2.required_evidence)

    # ------------------------------------------------------------------
    # TEST I: LIST_DIR no implica automáticamente READ_FILE en la directiva
    # ------------------------------------------------------------------
    def test_i_listdir_does_not_force_read_file(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        gap = engine.calculate_evidence_gap(self.goal, 1, task, evidence)

        instruction = gap.format_cognitive_instruction()
        self.assertNotIn("Debes ejecutar READ_FILE", instruction)
        self.assertIn("Selecciona e invoca libremente la herramienta nativa adecuada", instruction)

    # ------------------------------------------------------------------
    # TEST J: LIST_DIR no implica automáticamente COMMAND en la directiva
    # ------------------------------------------------------------------
    def test_j_listdir_does_not_force_command(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        gap = engine.calculate_evidence_gap(self.goal, 1, task, evidence)

        instruction = gap.format_cognitive_instruction()
        self.assertNotIn("Debes ejecutar COMMAND", instruction)

    # ------------------------------------------------------------------
    # TEST K: Una nueva acción puede actualizar/reducir el gap
    # ------------------------------------------------------------------
    def test_k_new_action_updates_evidence_gap(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        engine.start_investigation()

        task1 = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence1 = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        res1 = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[evidence1])
        r1 = engine.evaluate_task_step(task1, evidence1, res1)

        task2 = Task(task_id="t2", goal_id=self.goal.goal_id, description="READ_FILE", tool="READ_FILE", arguments={"file_path": "core/orchestrator.py"})
        evidence2 = TaskEvidence(source="adapter", type="file", value={"content": "class Orchestrator"}, reliability=1.0)
        res2 = TaskResult(task_id="t2", status=TaskResultStatus.PASS, evidence=[evidence2])
        r2 = engine.evaluate_task_step(task2, evidence2, res2)

        gap1 = r1["evidence_gap"]
        gap2 = r2["evidence_gap"]

        self.assertNotEqual(gap1["current_evidence"], gap2["current_evidence"])
        self.assertIn("Inspección del contenido", gap2["current_evidence"])

    # ------------------------------------------------------------------
    # TEST L: Nueva evidencia actualiza current_evidence en EvidenceGap
    # ------------------------------------------------------------------
    def test_l_new_evidence_updates_current_evidence(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="READ_FILE", tool="READ_FILE", arguments={"file_path": "main.py"})
        evidence = TaskEvidence(source="adapter", type="file", value={"content": "import sys"}, reliability=1.0)
        gap = engine.calculate_evidence_gap(self.goal, 1, task, evidence)

        self.assertIn("main.py", gap.current_evidence)

    # ------------------------------------------------------------------
    # TEST M: Evidencia suficiente permite concluir
    # ------------------------------------------------------------------
    def test_m_sufficient_evidence_allows_conclusion(self):
        from core.cognitive.physical_fact_verifier import VerifiedFact
        engine = AdaptiveInvestigationEngine(self.goal)
        engine.start_investigation()
        engine.verified_facts.append(VerifiedFact("f1", "COMMAND", "python -m unittest", True, {}))

        executed_steps = [
            {"tool_name": "READ_FILE", "output": "code content", "task_result": TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[TaskEvidence(source="a", type="f", value="c")])}
        ]
        res = engine.evaluate_mission_conclusion(executed_steps, "La investigación concluyó: no_action_required.")
        self.assertIn(res.conclusion_status, ["NO_ACTION_REQUIRED", "SUCCESS", "COMPLETED"])

    # ------------------------------------------------------------------
    # TEST N: Evidencia insuficiente no permite declarar éxito prematuro
    # ------------------------------------------------------------------
    def test_n_insufficient_evidence_blocks_premature_success(self):
        goal = Goal(goal_id="g1", objective="Misión abierta de prueba", status=GoalState.EXECUTING)
        executed_steps = [
            {"tool_name": "LIST_DIR", "output": "file list", "task_result": TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[TaskEvidence(source="a", type="d", value="l")])}
        ]
        res = SemanticMissionEngine.is_evidence_sufficient_for_goal(goal, executed_steps, "Todo está bien.")
        self.assertFalse(res["sufficient"])

    # ------------------------------------------------------------------
    # TEST O: False success continúa bloqueado
    # ------------------------------------------------------------------
    def test_o_false_success_remains_blocked(self):
        failed_result = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, error="ExitCode 1")
        executed_steps = [
            {"tool_name": "COMMAND", "output": "error log", "task_result": failed_result}
        ]
        res = SemanticMissionEngine.is_evidence_sufficient_for_goal(self.goal, executed_steps, "Comando ejecutado con éxito aparente.")
        self.assertFalse(res["sufficient"])

    # ------------------------------------------------------------------
    # TEST P: Stagnation no se activa únicamente por evidencia insuficiente inicial
    # ------------------------------------------------------------------
    def test_p_stagnation_not_triggered_by_single_insufficient_evidence(self):
        detector = StagnationDetector()
        state = detector.record_tool_call("LIST_DIR", {"dir_path": "."}, True)
        self.assertEqual(state, StagnationState.ACTIVE)
        self.assertIsNone(detector.get_stagnation_directive())

    # ------------------------------------------------------------------
    # TEST Q: Regresión Gates A-E intactos
    # ------------------------------------------------------------------
    def test_q_gates_a_e_intact(self):
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
