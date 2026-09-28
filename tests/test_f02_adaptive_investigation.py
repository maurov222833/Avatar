import unittest
import os
from core.cognitive.models import Goal, GoalState, Task, TaskState, TaskEvidence, TaskResult, TaskResultStatus
from core.cognitive.adaptive_investigation_engine import (
    AdaptiveInvestigationEngine,
    InvestigationState,
    Hypothesis,
    HypothesisStatus,
    ResearchBudget
)

class TestF02AdaptiveInvestigation(unittest.TestCase):

    def setUp(self):
        self.goal = Goal(goal_id="goal-f02-test", objective="Auditar autonomía y pruebas del sistema", status=GoalState.CREATED)
        self.engine = AdaptiveInvestigationEngine(self.goal)

    def test_f02_01_unexpected_result_does_not_terminate(self):
        """TEST F02-01: Resultado inesperado no termina automáticamente la misión."""
        self.engine.start_investigation()
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        evidence = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Error pytest"}, reliability=1.0)
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[evidence])

        res = self.engine.evaluate_task_step(task, evidence, task_result)
        self.assertNotEqual(self.engine.state, InvestigationState.CONCLUDED_SUCCESS)
        self.assertEqual(res["status"], "EXECUTING")
        self.assertEqual(res["action"], "RECOVER_OR_REPLAN")

    def test_f02_02_tool_failure_triggers_evaluation(self):
        """TEST F02-02: Herramienta fallida provoca evaluación."""
        self.engine.start_investigation()
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        evidence = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Error pytest"}, reliability=1.0)
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[evidence])

        res = self.engine.evaluate_task_step(task, evidence, task_result)
        self.assertIn("recovery_plan", res)

    def test_f02_03_hypothesis_can_be_generated(self):
        """TEST F02-03: Hipótesis puede generarse."""
        hyp = self.engine.propose_hypothesis("Pytest falla por dependencia en scratch", proposed_tool="COMMAND")
        self.assertIsNotNone(hyp.hypothesis_id)
        self.assertEqual(hyp.statement, "Pytest falla por dependencia en scratch")
        self.assertEqual(hyp.status, HypothesisStatus.PROPOSED)

    def test_f02_04_refuted_hypothesis_causes_replanning(self):
        """TEST F02-04: Hipótesis refutada produce replanteamiento."""
        hyp = self.engine.propose_hypothesis("Pytest falla por sintaxis", proposed_tool="COMMAND")
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        evidence = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "ModuleNotFoundError"}, reliability=1.0)
        task_result = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[evidence])

        self.engine.evaluate_task_step(task, evidence, task_result)
        self.assertEqual(hyp.status, HypothesisStatus.REFUTED)
        self.assertEqual(self.engine.state, InvestigationState.MUTATING_STRATEGY)

    def test_f02_05_new_evidence_changes_decision(self):
        """TEST F02-05: Nueva evidencia cambia la decisión."""
        self.engine.start_investigation()
        # Primer paso fallido
        task1 = Task(task_id="t1", goal_id=self.goal.goal_id, description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        ev1 = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Error"}, reliability=1.0)
        res1 = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[ev1])
        self.engine.evaluate_task_step(task1, ev1, res1)

        # Segundo paso exitoso con unittest
        task2 = Task(task_id="t2", goal_id=self.goal.goal_id, description="Run unittest", tool="COMMAND", arguments={"command": "python -m unittest discover -v"})
        ev2 = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 0, "raw_output": "Ran 107 tests OK"}, reliability=1.0)
        res2 = TaskResult(task_id="t2", status=TaskResultStatus.PASS, evidence=[ev2])
        step_res2 = self.engine.evaluate_task_step(task2, ev2, res2)

        self.assertEqual(step_res2["action"], "CONTINUE")

    def test_f02_06_insufficient_investigation_produces_insufficient_status(self):
        """TEST F02-06: Investigación insuficiente produce INSUFFICIENT_EVIDENCE."""
        budget = ResearchBudget(max_steps=2)
        engine = AdaptiveInvestigationEngine(self.goal, budget=budget)
        engine.start_investigation()

        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="Run pytest", tool="COMMAND", arguments={"command": "pytest"})
        ev = TaskEvidence(source="COMMAND", type="command_result", value={"exit_code": 1, "raw_output": "Error"}, reliability=1.0)
        res = TaskResult(task_id="t1", status=TaskResultStatus.FAIL, evidence=[ev])
        
        engine.evaluate_task_step(task, ev, res)
        step_res2 = engine.evaluate_task_step(task, ev, res)

        self.assertEqual(step_res2["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(engine.state, InvestigationState.EXHAUSTED_INSUFFICIENT)

    def test_f02_07_sufficient_investigation_allows_decision(self):
        """TEST F02-07: Investigación suficiente permite decisión."""
        self.engine.start_investigation()
        # Simular lectura física y hecho verificado de no acción requerida
        from core.cognitive.physical_fact_verifier import VerifiedFact
        fact = VerifiedFact(fact_id="f1", fact_type="TEST", subject="unittest", verified=True)
        self.engine.verified_facts.append(fact)

        conc = self.engine.evaluate_mission_conclusion([], "no_action_required: la suite de pruebas paso 107/107.")
        self.assertEqual(conc.conclusion_status, "NO_ACTION_REQUIRED")
        self.assertEqual(self.engine.state, InvestigationState.CONCLUDED_NO_ACTION)

    def test_f02_08_no_infinite_repetition_without_new_evidence(self):
        """TEST F02-08: No se repite indefinidamente una investigación sin nueva evidencia."""
        h1 = self.engine.propose_hypothesis("Hypothesis A", proposed_tool="COMMAND")
        h1.status = HypothesisStatus.REFUTED

        # Proponer misma hipótesis
        h2 = self.engine.propose_hypothesis("Hypothesis A", proposed_tool="COMMAND")
        self.assertEqual(h2.status, HypothesisStatus.REFUTED)

if __name__ == '__main__':
    unittest.main()
