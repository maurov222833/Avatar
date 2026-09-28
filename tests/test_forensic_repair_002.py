import os
import sys
import unittest
import tempfile
import json
import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_db import StateEngine
from core.cognitive.capability_registry import (
    CapabilityEvidenceRegistry,
    CapabilityEvidence,
    CapabilityStatus,
    EvidenceType
)
from core.cognitive.mission_completion_gate import MissionCompletionGate, MissionStatus
from core.cognitive.claim_validator import ClaimValidator
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier, VerifiedFact

class TestForensicRepair002(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_repair_002.db")
        self.state_db = StateEngine(db_path=self.db_path)
        self.registry = CapabilityEvidenceRegistry(state_db=self.state_db)

    def test_01_llm_false_claim_unverified(self):
        """TEST 1: LLM produce CAPABILITY_WHATSAPP = VERIFIED sin evidencia física."""
        llm_text = "CAPABILITY_WHATSAPP = VERIFIED\nCapacidad WhatsApp verificada exitosamente."
        res = ClaimValidator.validate_llm_claims(
            llm_text=llm_text,
            verified_facts=[],
            capability_registry=self.registry
        )
        self.assertEqual(len(res.unverified_claims), 1)
        self.assertIn("UNVERIFIED_CLAIM", res.sanitized_text)
        self.assertNotEqual(self.registry.get_capability_status("CAP_WHATSAPP_AUTO_REPLY"), CapabilityStatus.VERIFIED)

    def test_02_mission_completed_with_critical_gaps_blocked(self):
        """TEST 2: LLM produce MASTER_MISSION_STATUS = COMPLETED con CRITICAL_GAPS = 1."""
        gate_res = MissionCompletionGate.evaluate_mission_completion(
            mission_id="msn_002_test",
            required_capabilities=[],
            critical_gaps=1,
            blocking_findings=0,
            capability_registry=self.registry
        )
        self.assertFalse(gate_res.can_complete)
        self.assertEqual(gate_res.mission_status, MissionStatus.COMPLETED_WITH_BLOCKING_FINDINGS)

    def test_03_mission_completed_with_open_blocking_findings(self):
        """TEST 3: LLM produce MASTER_MISSION_STATUS = COMPLETED con OPEN_FINDINGS bloqueantes > 0."""
        gate_res = MissionCompletionGate.evaluate_mission_completion(
            mission_id="msn_003_test",
            required_capabilities=[],
            critical_gaps=0,
            blocking_findings=2,
            capability_registry=self.registry
        )
        self.assertFalse(gate_res.can_complete)
        self.assertEqual(gate_res.mission_status, MissionStatus.COMPLETED_WITH_BLOCKING_FINDINGS)

    def test_04_pytest_279_passed_does_not_verify_browser(self):
        """TEST 4: pytest 279 passed no debe verificar la capacidad Browser sin evidencia física."""
        fact = PhysicalFactVerifier.verify_test_execution("pytest tests/", "[Resultado PowerShell (ExitCode: 0)]:\nRan 279 tests in 26s\nOK")
        self.assertTrue(fact.verified)
        self.assertEqual(fact.evidence_data["fact_subtype"], "TEST_EXECUTION_VERIFIED")
        self.assertFalse(fact.evidence_data["capability_verified"])
        
        # Consultar estado en registry
        status = self.registry.get_capability_status("CAP_PLAYWRIGHT_BROWSER")
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_05_mocked_whatsapp_tests_do_not_verify_whatsapp(self):
        """TEST 5: Tests mocked de WhatsApp no otorgan VERIFIED operacional."""
        ev = CapabilityEvidence(
            evidence_id="ev_mock_wa",
            capability_id="CAP_WHATSAPP_AUTO_REPLY",
            action="unit_test_mock",
            expected="mock_ok",
            actual="mock_ok",
            evidence_type=EvidenceType.TEST_RESULT,
            physical_evidence=False,  # Test unitario con mocks
            source="unittest",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            verification_result=True,
            verifier="UnitTester"
        )
        new_status = self.registry.register_evidence("CAP_WHATSAPP_AUTO_REPLY", ev)
        self.assertNotEqual(new_status, CapabilityStatus.VERIFIED)

    def test_06_markdown_document_creation_does_not_verify_audit(self):
        """TEST 6: Crear AVATAR_MASTER_CAPABILITY_AUDIT.md demuestra DOCUMENT_CREATED pero no AUDIT_VERIFIED."""
        doc_path = os.path.join(self.temp_dir, "AVATAR_MASTER_CAPABILITY_AUDIT.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("# AUDIT REPORT\nVERIFIED = 18")

        fact = PhysicalFactVerifier.verify_write_file(doc_path)
        self.assertTrue(fact.verified)
        self.assertEqual(fact.fact_type, "WRITE_FILE")
        # Verificar que el documento escrito no altera el registro de estado de capacidades
        self.assertNotEqual(self.registry.get_capability_status("CAP_PLAYWRIGHT_BROWSER"), CapabilityStatus.VERIFIED)

    def test_07_llm_writing_verified_true_in_file_does_not_change_registry(self):
        """TEST 7: El LLM escribe VERIFIED = TRUE en un archivo pero el estado autoritativo permanece inmutable."""
        file_path = os.path.join(self.temp_dir, "report.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("CAPABILITY_STATE = VERIFIED")

        status = self.registry.get_capability_status("CAP_WHATSAPP_AUTO_REPLY")
        self.assertNotEqual(status, CapabilityStatus.VERIFIED)

    def test_08_internal_unit_test_passed_separated_from_capability_operation(self):
        """
        TEST 8: Distinción formal entre TEST_EXECUTION_VERIFIED y CAPABILITY_OPERATION_VERIFIED.

        REWRITTEN IN IMPLEMENTATION 003. The old version called
        `verify_capability_operation(cap, <any existing file>)` and asserted it produced
        `capability_verified: True`. That function treated `bool(data)` — the mere existence
        of a file — as proof of a capability operation, which is exactly how a text file
        containing the eight bytes of a PNG signature "verified" CAP_DESKTOP_VISION in
        test_09. The function no longer exists.

        The distinction is now enforced structurally: a TEST fact is never admissible as
        capability evidence for any capability, because no `CapabilityDefinition` declares
        `TEST` among its `verifiable_by_fact_types`.
        """
        from core.cognitive.capability_specific_verifier import (
            CapabilitySpecificVerifier,
            VerificationRejection,
        )

        fact_test = PhysicalFactVerifier.verify_test_execution(
            "pytest tests/test_state_engine.py", "Ran 18 tests\nOK"
        )
        self.assertEqual(fact_test.evidence_data["fact_subtype"], "TEST_EXECUTION_VERIFIED")
        self.assertFalse(fact_test.evidence_data["capability_verified"])

        result = CapabilitySpecificVerifier.verify("CAP_DESKTOP_VISION", fact_test)
        self.assertFalse(result.verified)
        self.assertIn(result.reason, (
            VerificationRejection.REASON_FACT_TYPE_NOT_ALLOWED,
            VerificationRejection.REASON_NO_VERIFIER,
        ))

    def test_09_physical_demonstration_cycle(self):
        """
        DEMOSTRACIÓN FÍSICA OBLIGATORIA (Sección 21) — INVERTED IN IMPLEMENTATION 003.

        The old version of this test "demonstrated" the full cycle to VERIFIED by writing a
        file whose first eight bytes were a PNG signature and passing it to
        `verify_capability_operation`. That is the D-6 defect in its purest form: a text file
        impersonating a screenshot certified a desktop-vision capability.

        CAP_DESKTOP_VISION has no capability-specific verifier, so it is permanently
        NOT_IMPLEMENTED. The demonstration now runs against CAP_STATE_ENGINE, the one
        capability with a real, deterministic physical verifier, and the fake-screenshot
        attack is retained as an explicit rejection.
        """
        from core.cognitive.capability_specific_verifier import CapabilitySpecificVerifier
        from tests.authority_fixtures import make_mission, certify_state_engine

        cap_id = "CAP_DESKTOP_VISION"

        # Paso 1: Claim falso sin evidencia
        initial_status = self.registry.get_capability_status(cap_id)
        self.assertNotEqual(initial_status, CapabilityStatus.VERIFIED)

        claim_res = ClaimValidator.validate_llm_claims(
            llm_text=f"{cap_id}: VERIFIED",
            verified_facts=[],
            capability_registry=self.registry,
            state_db=self.state_db,
        )
        self.assertGreaterEqual(len(claim_res.unverified_claims), 1)

        # Paso 2: el "screenshot" falso NO verifica nada
        screen_file = os.path.join(self.temp_dir, "real_observation.png")
        with open(screen_file, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")  # Solo la firma PNG
        fact_fake = PhysicalFactVerifier.verify_write_file(screen_file)
        self.assertTrue(fact_fake.verified, "the file exists; that is all it proves")
        self.assertFalse(CapabilitySpecificVerifier.verify(cap_id, fact_fake).verified)
        self.assertNotEqual(
            self.registry.get_capability_status(cap_id), CapabilityStatus.VERIFIED
        )

        # Paso 3 y 4: el ciclo real, sobre una capability con verificador específico
        mission_id = make_mission(self.state_db, ["CAP_STATE_ENGINE"])
        self.assertEqual(
            certify_state_engine(self.state_db, self.registry, mission_id),
            CapabilityStatus.VERIFIED,
        )
        self.assertEqual(
            self.registry.get_capability_status(
                "CAP_STATE_ENGINE", mission_id=mission_id
            ),
            CapabilityStatus.VERIFIED,
        )

        # Y la afirmación del LLM sólo se acepta cuando el registro realmente lo sostiene
        claim_res_post = ClaimValidator.validate_llm_claims(
            llm_text="CAPABILITY_STATE_ENGINE = VERIFIED",
            verified_facts=[],
            capability_registry=self.registry,
            state_db=self.state_db,
            mission_id=mission_id,
        )
        self.assertGreaterEqual(len(claim_res_post.verified_claims), 1)

if __name__ == "__main__":
    unittest.main()
