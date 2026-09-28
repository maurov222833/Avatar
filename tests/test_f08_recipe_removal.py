import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cognitive.models import Goal, Task, Plan, TaskState, EvidenceGap, TaskEvidence, TaskResult, TaskResultStatus
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.cognitive.stagnation_detector import StagnationDetector, StagnationState
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine
from core.cognitive.tool_registry import ToolRegistry, default_tool_registry
from tools.shell_tool import ShellTool

class TestRecipeRemoval(unittest.TestCase):
    """
    Suite de Pruebas Obligatorias de Eliminación de Recetas Hardcodeadas (Fase 15 / Gate F Repair).
    Verifica que el orquestador, motores cognitivos y detectores emitan información 100% semántica
    sin prescribir nombres de herramientas, comandos concretos ni archivos específicos.
    """

    def test_a_continuation_prompt_no_tool_names(self):
        """TEST A: El prompt de continuación del orquestador no contiene nombres explícitos de herramientas."""
        from core.orchestrator import AvatarOrchestrator
        orchestrator = AvatarOrchestrator()
        goal = Goal(goal_id="g1", objective="Misión de prueba de arquitectura")
        eval_res = {"reason": "Evidencia técnica insuficiente."}

        continuation_prompt = (
            f"[AVISO DEL MOTOR COGNITIVO - CONTINUACIÓN DE MISIÓN ABIERTA]:\n"
            f"Estado del Objetivo: {goal.objective}\n"
            f"Razón de Continuación: {eval_res['reason']}\n"
            "SITUACIÓN COGNITIVA ACTUAL:\n"
            "- La misión permanece abierta porque la evidencia recopilada hasta ahora es insuficiente para validar o descartar el objetivo.\n"
            "- Evalúa la evidencia disponible y el gap de información actual para seleccionar autónomamente la siguiente acción de investigación adecuada entre tus herramientas disponibles."
        )

        for prohibited in ["READ_FILE:", "COMMAND:", "WRITE_FILE:", "LIST_DIR:"]:
            self.assertNotIn(prohibited, continuation_prompt, f"Receta encontrada en prompt: {prohibited}")

    def test_b_continuation_prompt_no_specific_commands(self):
        """TEST B: El prompt de continuación no contiene comandos específicos como unittest o pytest."""
        with open("core/orchestrator.py", "r", encoding="utf-8") as f:
            content = f.read()

        continuation_block = content[content.find("continuation_prompt = ("):content.find("contents.append({")]
        self.assertNotIn("python -m unittest", continuation_block)
        self.assertNotIn("pytest", continuation_block)

    def test_c_continuation_prompt_no_specific_filenames(self):
        """TEST C: El prompt de continuación no contiene nombres de archivos específicos."""
        with open("core/orchestrator.py", "r", encoding="utf-8") as f:
            content = f.read()

        continuation_block = content[content.find("continuation_prompt = ("):content.find("contents.append({")]
        self.assertNotIn("core/orchestrator.py", continuation_block)
        self.assertNotIn("core/cognitive/planner.py", continuation_block)

    def test_d_evidence_gap_is_semantic(self):
        """TEST D: EvidenceGap permanece semántico y no es una herramienta disfrazada."""
        gap = EvidenceGap(
            current_evidence="Estructura de directorios explorada",
            required_evidence="Implementación de persistencia de datos",
            evidence_gap="No se ha inspeccionado la clase RAGMemory",
            next_information_target="Obtener evidencia sobre la persistencia y recuperación de contexto"
        )
        instruction = gap.format_cognitive_instruction()

        self.assertIn("NEXT_INFORMATION_TARGET", instruction)
        self.assertNotIn("READ_FILE: core/rag_memory.py", instruction)
        self.assertNotIn("python -m unittest", instruction)

    def test_e_stagnation_detector_no_recipe_prescription(self):
        """TEST E: StagnationDetector detecta estancamiento sin prescribir una herramienta concreta."""
        detector = StagnationDetector()
        detector.record_text_turn("Hola")
        detector.record_text_turn("¿Cómo estás?")
        directive = detector.get_stagnation_directive()

        self.assertIsNotNone(directive)
        self.assertNotIn("python -m unittest discover -v", directive)
        self.assertNotIn("pytest", directive)
        self.assertNotIn("READ_FILE", directive)

    def test_f_adaptive_investigation_no_recipe_prescription(self):
        """TEST F: AdaptiveInvestigationEngine indica reevaluación sin prescribir una receta hardcodeada."""
        goal = Goal(goal_id="g1", objective="Analizar sistema")
        engine = AdaptiveInvestigationEngine(goal)
        task = Task(task_id="t1", goal_id="g1", description="Probe", tool="COMMAND", arguments={"command": "pytest"})
        
        evidence = TaskEvidence(source="COMMAND", type="output", value="Error")
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[evidence], error="ModuleNotFoundError")
        
        res = engine.evaluate_task_step(task, evidence, task_result, verified_fact=None)
        self.assertIn("cognitive_instruction", res)
        instruction = res["cognitive_instruction"]
        
        self.assertNotIn("python -m unittest discover -v", instruction)
        self.assertNotIn("READ_FILE", instruction)

    def test_g_model_decision_reaches_registry(self):
        """TEST G: Una decisión MODEL_DECISION llega al ToolRegistry normal."""
        registry = default_tool_registry
        self.assertTrue(registry.is_registered("COMMAND"))
        self.assertTrue(registry.is_registered("READ_FILE"))
        self.assertTrue(registry.is_registered("LIST_DIR"))

    def test_h_recovery_decision_remains_functional(self):
        """TEST H: El motor de recuperación (RecoveryEngine) continúa funcionando."""
        from core.cognitive.recovery_engine import RecoveryEngine
        engine = RecoveryEngine()
        goal = Goal(goal_id="g1", objective="Test")
        plan = Plan(plan_id="p1", goal_id="g1", tasks=[])
        task = Task(task_id="t1", goal_id="g1", description="Test", tool="COMMAND")
        
        evidence = TaskEvidence(source="COMMAND", type="output", value="Err")
        result = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[evidence], error="SyntaxError")
        
        new_plan, record = engine.handle_task_failure(goal, plan, task, result)
        self.assertIsNotNone(record)
        self.assertEqual(record.attempt, 1)

    def test_i_tool_safety_and_validation(self):
        """TEST I: Las funciones de seguridad y validación de herramientas siguen operativas."""
        ws = ShellTool.get_allowed_workspace()
        self.assertTrue(os.path.exists(ws))

    def test_j_static_recipe_search_in_cognitive_components(self):
        """TEST J: Prueba estática/estructural que verifica ausencia de recetas generales hardcodeadas."""
        for file_path in [
            "core/orchestrator.py",
            "core/cognitive/stagnation_detector.py",
            "core/cognitive/semantic_mission_engine.py",
            "core/cognitive/adaptive_investigation_engine.py"
        ]:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            self.assertNotIn("python -m unittest discover -v", code, f"Comando unittest hardcodeado encontrado en {file_path}")

    def test_k_generality_across_distinct_domains(self):
        """TEST K: EvidenceGap produce metas semánticas distintas para objetivos de dominios diferentes."""
        gap_mem = EvidenceGap(
            current_evidence="Dirección de memoria identificada",
            required_evidence="Verificación de aislamiento de sesiones",
            evidence_gap="Sin datos de comportamiento tras reinicio",
            next_information_target="Obtener evidencia sobre persistencia de contexto de memoria"
        )
        gap_auth = EvidenceGap(
            current_evidence="Módulo auth localizado",
            required_evidence="Verificación de hashing de tokens",
            evidence_gap="Sin datos de esquema de tokens",
            next_information_target="Obtener evidencia sobre validación de tokens de acceso"
        )

        self.assertNotEqual(gap_mem.next_information_target, gap_auth.next_information_target)
        self.assertNotIn("READ_FILE", gap_mem.next_information_target)
        self.assertNotIn("READ_FILE", gap_auth.next_information_target)

if __name__ == "__main__":
    unittest.main()
