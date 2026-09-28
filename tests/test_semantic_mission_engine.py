import unittest
import os
from core.cognitive.models import Goal, GoalState, TaskState, TaskResultStatus, TaskEvidence, TaskResult
from core.cognitive.adapter import CognitiveAdapter
from core.cognitive.verifier import Verifier
from core.cognitive.semantic_mission_engine import SemanticMissionEngine, InteractionType
from core.cognitive.recovery_engine import RecoveryEngine
from core.cognitive.recovery_policy import RecoveryStrategy

class TestSemanticMissionEngine(unittest.TestCase):

    def test_001_normal_conversation(self):
        """TEST 1: Conversación normal se clasifica como CONVERSATION_NORMAL y no activa misión."""
        prompts = [
            "Hola Avatar, ¿cómo estás?",
            "Avatar estas ahí?",
            "Estas listo para trabajar conmigo",
            "Hola",
            "Buenos días Avatar"
        ]
        for prompt in prompts:
            itype = SemanticMissionEngine.classify_interaction(prompt)
            self.assertEqual(itype, InteractionType.CONVERSATION_NORMAL, f"Fallo en prompt: {prompt}")

    def test_002_direct_action(self):
        """TEST 2: Acción directa pasa por el pipeline cognitivo completo."""
        prompt = "Ejecuta echo AVATAR_DIRECT_ACTION_OK"
        itype = SemanticMissionEngine.classify_interaction(prompt)
        self.assertEqual(itype, InteractionType.DIRECT_ACTION)

        goal = CognitiveAdapter.create_goal(prompt)
        task = CognitiveAdapter.create_task(goal.goal_id, "COMMAND", {"command": "echo AVATAR_DIRECT_ACTION_OK"})
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nAVATAR_DIRECT_ACTION_OK"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        res = Verifier.verify(task.task_id, evidence, {"expected_stdout_contains": "AVATAR_DIRECT_ACTION_OK"})
        self.assertEqual(res.status, TaskResultStatus.PASS)

    def test_003_open_mission_creation(self):
        """TEST 3: Misión abierta se clasifica correctamente y genera un Goal formal."""
        prompt = "Investiga si existe una debilidad real en tu proceso de recuperación. No se te proporciona archivo, defecto ni solución."
        itype = SemanticMissionEngine.classify_interaction(prompt)
        self.assertEqual(itype, InteractionType.OPEN_ENGINEERING_MISSION)

        goal = CognitiveAdapter.create_goal(prompt)
        self.assertEqual(goal.status, GoalState.CREATED)
        self.assertIsNotNone(goal.goal_id)

    def test_004_no_completion_after_list_dir(self):
        """TEST 4: LIST_DIR como única herramienta NO finaliza una misión abierta."""
        goal = CognitiveAdapter.create_goal("Analiza la arquitectura del proyecto")
        raw_output = "core\ntests\ntools"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("LIST_DIR", raw_output)
        task_res = CognitiveAdapter.build_task_result("t-ld", evidence)

        executed_steps = [{
            "tool_name": "LIST_DIR",
            "output": raw_output,
            "task_result": task_res
        }]

        eval_res = SemanticMissionEngine.is_evidence_sufficient_for_goal(goal, executed_steps, "He listado el directorio.")
        self.assertFalse(eval_res["sufficient"])
        self.assertIn("Only directory listing", eval_res["reason"])

    def test_005_adaptive_investigation(self):
        """TEST 5: La investigación adaptativa exige herramientas adicionales tras la primera exploración."""
        goal = CognitiveAdapter.create_goal("Investiga fallos en el orquestador")
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nfile1.py\nfile2.py"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("LIST_DIR", raw_output)
        task_res = CognitiveAdapter.build_task_result("t-1", evidence)

        executed_steps = [{
            "tool_name": "LIST_DIR",
            "output": raw_output,
            "task_result": task_res
        }]

        eval_res = SemanticMissionEngine.is_evidence_sufficient_for_goal(goal, executed_steps, "Directorio inspeccionado.")
        self.assertFalse(eval_res["sufficient"])
        self.assertEqual(eval_res["status"], GoalState.EXECUTING)

    def test_006_insufficient_evidence_produces_no_pass(self):
        """TEST 6: Evidencia insuficiente o fallo de herramienta produce STATUS no exitoso."""
        goal = CognitiveAdapter.create_goal("Prueba de evidencia fallida")
        raw_output = "[Resultado PowerShell (ExitCode: 1)]:\nstderr:\nError fatal en módulo"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        task_res = CognitiveAdapter.build_task_result("t-err", evidence)

        executed_steps = [{
            "tool_name": "COMMAND",
            "output": raw_output,
            "task_result": task_res
        }]

        eval_res = SemanticMissionEngine.is_evidence_sufficient_for_goal(goal, executed_steps, "Intento fallido.")
        self.assertFalse(eval_res["sufficient"])
        self.assertFalse(task_res.status.is_success())

    def test_007_recovery_during_investigation(self):
        """TEST 7: Fallo durante la investigación activa el Motor de Recuperación."""
        goal = CognitiveAdapter.create_goal("Prueba de recuperación en investigación")
        task = CognitiveAdapter.create_task(goal.goal_id, "COMMAND", {"command": "python script_inexistente.py"})
        raw_output = "[Resultado PowerShell (ExitCode: 1)]:\nstderr:\nFileNotFoundError"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        task_res = CognitiveAdapter.build_task_result(task.task_id, evidence)

        recovery_engine = RecoveryEngine()
        plan = CognitiveAdapter.create_single_task_plan(goal, task)
        new_plan, rec_record = recovery_engine.handle_task_failure(goal, plan, task, task_res, evidence)

        self.assertIsNotNone(rec_record)
        self.assertIn(rec_record.strategy, [RecoveryStrategy.RETRY_SAME, RecoveryStrategy.RETRY_MODIFIED, RecoveryStrategy.REPLAN, RecoveryStrategy.ABORT])

    def test_008_no_action_required(self):
        """TEST 8: Misión donde no existe defecto concluye NO_ACTION_REQUIRED respaldada por evidencia."""
        goal = CognitiveAdapter.create_goal("Audita si existe una falla en el módulo X")
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\n98 tests OK"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        task_res = CognitiveAdapter.build_task_result("t-ok", evidence)

        executed_steps = [{
            "tool_name": "COMMAND",
            "output": raw_output,
            "task_result": task_res
        }]

        llm_report = "Se investigaron los componentes y se verificó que NO_ACTION_REQUIRED. No existe debilidad real."
        eval_res = SemanticMissionEngine.is_evidence_sufficient_for_goal(goal, executed_steps, llm_report)

        self.assertTrue(eval_res["sufficient"])
        self.assertEqual(eval_res["conclusion"], "NO_ACTION_REQUIRED")
        self.assertEqual(eval_res["status"], GoalState.COMPLETED)

    def test_009_false_success_prevention(self):
        """TEST 9: ExitCode 0 con patrón no encontrado produce FAIL determinista."""
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nSalida normal sin patrón esperada"
        evidence = CognitiveAdapter.create_evidence_from_tool_output("COMMAND", raw_output)
        res = Verifier.verify("t-false-success", evidence, {"expected_stdout_contains": "PATRON_INEXISTENTE_CRITICO"})

        self.assertEqual(res.status, TaskResultStatus.FAIL)
        self.assertFalse(res.status.is_success())

if __name__ == "__main__":
    unittest.main()
