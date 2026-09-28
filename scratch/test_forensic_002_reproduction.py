import os
import sys
import unittest

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cognitive.physical_fact_verifier import PhysicalFactVerifier, VerifiedFact
from core.cognitive.claim_validator import ClaimValidator
from core.cognitive.semantic_mission_engine import SemanticMissionEngine
from core.cognitive.models import Goal, TaskState, GoalState

class TestForensicAudit002Reproduction(unittest.TestCase):

    def test_01_llm_claim_capability_verified_unblocked(self):
        """
        Demuestra que si el LLM produce texto afirmando 'CAPABILITY_WHATSAPP = VERIFIED',
        ClaimValidator NO intercepta ni valida esta afirmación porque solo busca patrones
        de creación/modificación de archivos (FILE_CREATION, FILE_MODIFICATION).
        """
        llm_text = (
            "# AVATAR AUDIT REPORT\n"
            "STATUS: COMPLETED\n"
            "CAPABILITY_WHATSAPP: VERIFIED\n"
            "CAPABILITY_PLAYWRIGHT: VERIFIED\n"
        )
        verified_facts = []  # Ninguna evidencia física
        result = ClaimValidator.validate_llm_claims(llm_text, verified_facts)

        # Confirmar que detected_claims está vacío y sanitized_text no añade warning
        self.assertEqual(len(result.detected_claims), 0)
        self.assertEqual(len(result.unverified_claims), 0)
        self.assertEqual(result.sanitized_text, llm_text)
        print("[Reproduction Test 01]: ClaimValidator ignora afirmaciones de CAPABILITY = VERIFIED.")

    def test_02_mission_completed_with_critical_gaps_unblocked(self):
        """
        Demuestra que el sistema no valida sintáctica ni determinísticamente si una misión
        declarada COMPLETED por el LLM tiene CRITICAL_GAPS > 0 o OPEN_FINDINGS > 0.
        """
        llm_report = (
            "MASTER_MISSION_STATUS = COMPLETED\n"
            "CRITICAL_GAPS = 1\n"
            "OPEN_FINDINGS = 2\n"
        )
        goal = Goal(goal_id="g1", objective="Audit Capabilities")
        eval_res = SemanticMissionEngine.is_evidence_sufficient_for_goal(
            goal=goal,
            executed_steps=[
                {
                    "tool_name": "COMMAND",
                    "args": {"command": "python -m pytest tests/"},
                    "output": "Ran 279 tests in 26s\nOK",
                    "task_result": type("Res", (), {"status": type("Stat", (), {"is_success": lambda self: True})()})()
                }
            ],
            llm_text=llm_report
        )
        # La evaluación es heurística sobre el texto, no una regla estricta sobre gaps
        print(f"[Reproduction Test 02]: Evidence sufficiency result: {eval_res}")

    def test_03_pytest_279_passed_vs_excluded_infrastructure(self):
        """
        Verifica que PhysicalFactVerifier.verify_test_execution valida únicamente el exit code
        y conteo total del comando de prueba, pero NO valida si componentes de infraestructura
        (Browser, WhatsApp) fueron realmente probados o excluidos.
        """
        cmd_output = (
            "[Resultado PowerShell (ExitCode: 0)]:\n"
            "Ran 279 tests in 26.63s\n"
            "OK\n"
        )
        fact = PhysicalFactVerifier.verify_test_execution("pytest tests/", cmd_output)
        self.assertTrue(fact.verified)
        self.assertEqual(fact.evidence_data["passed_tests"], 279)
        # Demuestra que TEST_PASS = True no equivale a CAPABILITY_VERIFIED para Browser o WhatsApp
        print(f"[Reproduction Test 03]: verify_test_execution fact verified: {fact.verified}")

if __name__ == "__main__":
    unittest.main()
