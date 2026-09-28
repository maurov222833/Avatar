import unittest
from core.orchestrator import AvatarOrchestrator
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType

class TestForensicRepair001(unittest.TestCase):
    def setUp(self):
        self.orchestrator = AvatarOrchestrator()

    def test_001_audit_prose_examples_no_command(self):
        user_input = "Audita reglas como:\n- pytest → unittest\n- pytest →)"
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertIn(interaction_type, [InteractionType.OPEN_ENGINEERING_MISSION, InteractionType.INFORMATIVE_QUERY])
        
        # Verificar que _parse_multi_task_specs NO intercepte o sea omitido
        multi_specs = None
        if interaction_type == InteractionType.DIRECT_ACTION:
            multi_specs = self.orchestrator._parse_multi_task_specs(user_input)
        self.assertIsNone(multi_specs, "Prosa de auditoría con flechas no debe generar tareas multi-spec.")

    def test_002_explicit_direct_action(self):
        user_input = "Ejecuta pytest."
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.DIRECT_ACTION)

    def test_003_open_engineering_mission(self):
        user_input = "Investiga por qué pytest falla."
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.OPEN_ENGINEERING_MISSION)

    def test_004_informative_query(self):
        user_input = "¿Qué es pytest?"
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.INFORMATIVE_QUERY)

    def test_005_analysis_query(self):
        user_input = "Analiza si el proyecto utiliza pytest."
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.OPEN_ENGINEERING_MISSION)

    def test_006_explicit_multi_command_direct_action(self):
        user_input = "Ejecuta:\npytest\npython -m unittest"
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.DIRECT_ACTION)
        specs = self.orchestrator._parse_multi_task_specs(user_input)
        self.assertIsNotNone(specs)
        self.assertGreaterEqual(len(specs), 2)

    def test_007_negative_forensic_constraint(self):
        user_input = "No ejecutes nada.\nAnaliza:\npytest\ngit status\npython -m unittest"
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertIn(interaction_type, [InteractionType.OPEN_ENGINEERING_MISSION, InteractionType.INFORMATIVE_QUERY])
        self.assertNotEqual(interaction_type, InteractionType.DIRECT_ACTION)

    def test_008_audit_example_block(self):
        user_input = "Audita el siguiente ejemplo:\n- echo TEST\n- pytest\n- git status"
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertIn(interaction_type, [InteractionType.OPEN_ENGINEERING_MISSION, InteractionType.INFORMATIVE_QUERY])
        self.assertNotEqual(interaction_type, InteractionType.DIRECT_ACTION)

    def test_009_open_mission_no_direct_parser_interception(self):
        user_input = "Analiza la arquitectura actual de Avatar y determina si existe una debilidad real."
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.OPEN_ENGINEERING_MISSION)
        has_json_block = "```json" in user_input and "[" in user_input
        self.assertFalse(interaction_type == InteractionType.DIRECT_ACTION or has_json_block)

    def test_010_direct_action_multi_task_legacy_support(self):
        user_input = "Ejecuta:\necho TASK1\necho TASK2"
        interaction_type = SemanticMissionEngine.classify_interaction(user_input)
        self.assertEqual(interaction_type, InteractionType.DIRECT_ACTION)
        specs = self.orchestrator._parse_multi_task_specs(user_input)
        self.assertIsNotNone(specs)
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["arguments"]["command"], "echo TASK1")
        self.assertEqual(specs[1]["arguments"]["command"], "echo TASK2")

if __name__ == "__main__":
    unittest.main()
