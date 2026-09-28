import unittest
import os
import tempfile
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier, VerifiedFact
from core.cognitive.claim_validator import ClaimValidator

class TestF03PhysicalEvidence(unittest.TestCase):

    def test_f03_01_write_file_generates_physical_evidence(self):
        """TEST F03-01: WRITE_FILE genera evidencia física."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
            tmp.write(b"print('hello')")
            tmp_path = tmp.name

        try:
            fact = PhysicalFactVerifier.verify_write_file(tmp_path, "print('hello')")
            self.assertTrue(fact.verified)
            self.assertEqual(fact.fact_type, "WRITE_FILE")
            self.assertTrue(fact.evidence_data["size_bytes"] > 0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_f03_02_write_file_declared_success_but_absent_produces_fail(self):
        """TEST F03-02: WRITE_FILE declarado exitoso pero físicamente ausente produce FAIL."""
        fake_path = "b:/PROYECTOS ANTIGRAVITY/Avatar/tests/non_existent_fake_file.py"
        fact = PhysicalFactVerifier.verify_write_file(fake_path, "content")
        self.assertFalse(fact.verified)
        self.assertIn("does not exist on disk", fact.error)

    def test_f03_03_modify_file_produces_before_after_evidence(self):
        """TEST F03-03: MODIFY_FILE produce evidencia before/after."""
        with tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".py") as tmp:
            tmp.write("v1")
            tmp_path = tmp.name

        try:
            initial_hash = PhysicalFactVerifier.calculate_file_hash(tmp_path)
            with open(tmp_path, "w") as f:
                f.write("v2")

            fact = PhysicalFactVerifier.verify_modify_file(tmp_path, initial_hash)
            self.assertTrue(fact.verified)
            self.assertTrue(fact.evidence_data["file_changed"])
            self.assertNotEqual(fact.evidence_data["initial_hash"], fact.evidence_data["current_hash"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_f03_04_delete_file_produces_physical_evidence(self):
        """TEST F03-04: DELETE_FILE produce evidencia física."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
            tmp_path = tmp.name

        existed_before = os.path.exists(tmp_path)
        os.remove(tmp_path)
        fact = PhysicalFactVerifier.verify_delete_file(tmp_path, existed_before)
        self.assertTrue(fact.verified)
        self.assertFalse(fact.evidence_data["currently_exists"])

    def test_f03_05_llm_claim_cannot_become_verified_fact_directly(self):
        """TEST F03-05: LLM CLAIM no puede convertirse directamente en VerifiedFact."""
        llm_text = "Se creó el archivo tests/test_avatar_core.py"
        verified_facts = []  # Sin hechos verificados en disco
        res = ClaimValidator.validate_llm_claims(llm_text, verified_facts)

        self.assertEqual(len(res.unverified_claims), 1)
        self.assertEqual(len(res.verified_claims), 0)
        self.assertIn("AFIRMACIÓN NO VERIFICADA", res.sanitized_text)

    def test_f03_06_false_llm_claim_remains_unverified(self):
        """TEST F03-06: Una afirmación falsa del LLM permanece UNVERIFIED."""
        llm_text = "Se creó el archivo tests/test_avatar_core.py para probar la integración."
        res = ClaimValidator.validate_llm_claims(llm_text, [])
        self.assertIn("FILE_EXISTS = False", res.sanitized_text)
        self.assertEqual(res.unverified_claims[0]["target_path"], "tests/test_avatar_core.py")

    def test_f03_07_command_exit_0_does_not_equal_objective_success(self):
        """TEST F03-07: COMMAND exit 0 no equivale a OBJECTIVE_SUCCESS."""
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout: dir executed"
        fact = PhysicalFactVerifier.verify_command("dir", raw_output)
        self.assertTrue(fact.verified)
        # La verificación física demuestra que el comando terminó, pero NO garantiza que el objetivo de ingeniería esté cumplido
        self.assertEqual(fact.fact_type, "COMMAND")

    def test_f03_08_test_requires_real_execution_evidence(self):
        """TEST F03-08: TEST requiere evidencia de ejecución real."""
        raw_output = "[Resultado PowerShell (ExitCode: 0)]:\nstdout:\nRan 107 tests in 0.5s\n\nOK"
        fact = PhysicalFactVerifier.verify_test_execution("python -m unittest discover -v", raw_output)
        self.assertTrue(fact.verified)
        self.assertEqual(fact.evidence_data["total_tests"], 107)
        self.assertEqual(fact.evidence_data["passed_tests"], 107)

if __name__ == '__main__':
    unittest.main()
