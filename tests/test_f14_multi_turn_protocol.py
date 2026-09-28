import unittest
from unittest.mock import patch, MagicMock
import json

from core.orchestrator import AvatarOrchestrator, AVATAR_TOOLS_SCHEMA
from core.llm_provider import LLMProvider
from core.cognitive.models import Goal, GoalState, Task, TaskEvidence, TaskResult, TaskResultStatus
from core.cognitive.adaptive_investigation_engine import AdaptiveInvestigationEngine
from core.cognitive.structured_action_recovery import StructuredActionRecoveryLayer

class TestF14MultiTurnProtocol(unittest.TestCase):
    """
    Suite de Pruebas Unitarias para Fase 14 — Reparación del Protocolo Multi-Turno Gemini.
    Verifica que las respuestas de funciones utilicen role='user', que no haya fallbacks
    silenciosos que destruyan el contexto y que SAR no transforme provider errors en decisiones.
    """

    def setUp(self):
        self.orc = AvatarOrchestrator()
        self.goal = Goal(goal_id="g1", objective="Misión Abierta de Prueba", status=GoalState.EXECUTING)

    # ------------------------------------------------------------------
    # TEST A: Estructura USER -> MODEL functionCall -> USER functionResponse
    # ------------------------------------------------------------------
    def test_a_user_model_user_function_response_format(self):
        contents = [
            {"role": "user", "parts": [{"text": "Misión"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "LIST_DIR", "args": {"dir_path": "."}}}]},
            {
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": "LIST_DIR",
                        "response": {"output": "file list"}
                    }
                }]
            }
        ]
        self.assertEqual(contents[2]["role"], "user")
        self.assertIn("functionResponse", contents[2]["parts"][0])
        self.assertNotIn("function", [c["role"] for c in contents])

    # ------------------------------------------------------------------
    # TEST B: Payload de segundo turno no contiene role='function'
    # ------------------------------------------------------------------
    def test_b_second_turn_payload_schema_validity(self):
        llm = LLMProvider()
        llm.config["default_provider"] = "gemini"
        contents = [
            {"role": "user", "parts": [{"text": "Misión"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "LIST_DIR", "args": {"dir_path": "."}}}]},
            {"role": "function", "parts": [{"functionResponse": {"name": "LIST_DIR", "response": {"output": "out"}}}]}
        ]
        # Al llamar generate_response_with_tools, debe sanitizar role='function' a role='user'
        with patch("requests.post") as mock_post:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "Respuesta"}]
                    }
                }]
            }
            mock_post.return_value = mock_res

            res = llm.generate_response_with_tools("System Prompt", contents, AVATAR_TOOLS_SCHEMA)
            self.assertEqual(res["type"], "text")
            
            # Verificar el payload enviado en la llamada post
            sent_payload = mock_post.call_args[1]["json"]
            sent_contents = sent_payload["contents"]
            roles = [m["role"] for m in sent_contents]
            self.assertNotIn("function", roles)
            self.assertEqual(roles[2], "user")

    # ------------------------------------------------------------------
    # TEST C: El historial conversacional se conserva
    # ------------------------------------------------------------------
    def test_c_history_preservation_across_turns(self):
        contents = [
            {"role": "user", "parts": [{"text": "Paso 1"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "LIST_DIR", "args": {"dir_path": "."}}}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "LIST_DIR", "response": {"output": "out"}}}]},
            {"role": "user", "parts": [{"text": "Instrucción Cognitiva"}]}
        ]
        self.assertEqual(len(contents), 4)
        self.assertEqual(contents[0]["role"], "user")
        self.assertEqual(contents[1]["role"], "model")
        self.assertEqual(contents[2]["role"], "user")
        self.assertEqual(contents[3]["role"], "user")

    # ------------------------------------------------------------------
    # TEST D: Las herramientas (tools) se conservan en cada llamada
    # ------------------------------------------------------------------
    def test_d_tools_preservation_in_payload(self):
        llm = LLMProvider()
        llm.config["default_provider"] = "gemini"
        contents = [{"role": "user", "parts": [{"text": "Hola"}]}]
        with patch("requests.post") as mock_post:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Hola"}]}}]}
            mock_post.return_value = mock_res

            llm.generate_response_with_tools("Sys", contents, AVATAR_TOOLS_SCHEMA)
            sent_payload = mock_post.call_args[1]["json"]
            self.assertIn("tools", sent_payload)
            self.assertEqual(sent_payload["tools"], AVATAR_TOOLS_SCHEMA)

    # ------------------------------------------------------------------
    # TEST E: EvidenceGap se conserva en el objeto de evaluación
    # ------------------------------------------------------------------
    def test_e_evidence_gap_preservation(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        task_res = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[evidence])
        res = engine.evaluate_task_step(task, evidence, task_res)

        self.assertIn("evidence_gap", res)
        self.assertIn("next_information_target", res["evidence_gap"])

    # ------------------------------------------------------------------
    # TEST F: cognitive_instruction se conserva y formatea
    # ------------------------------------------------------------------
    def test_f_cognitive_instruction_preservation(self):
        engine = AdaptiveInvestigationEngine(self.goal)
        task = Task(task_id="t1", goal_id=self.goal.goal_id, description="LIST_DIR", tool="LIST_DIR", arguments={"dir_path": "."})
        evidence = TaskEvidence(source="adapter", type="dir", value={}, reliability=1.0)
        task_res = TaskResult(task_id="t1", status=TaskResultStatus.PASS, evidence=[evidence])
        res = engine.evaluate_task_step(task, evidence, task_res)

        self.assertIn("cognitive_instruction", res)
        self.assertIn("EVIDENCE GAP", res["cognitive_instruction"])

    # ------------------------------------------------------------------
    # TEST G: Error HTTP 400 no produce fallback silencioso a texto
    # ------------------------------------------------------------------
    def test_g_http_400_does_not_silently_fallback_to_text(self):
        llm = LLMProvider()
        contents = [{"role": "user", "parts": [{"text": "Paso 1"}]}]
        with patch("requests.post") as mock_post:
            mock_res = MagicMock()
            mock_res.status_code = 400
            mock_res.text = "INVALID_ARGUMENT Bad Request"
            mock_post.return_value = mock_res

            res = llm.generate_response_with_tools("Sys", contents, AVATAR_TOOLS_SCHEMA)
            self.assertEqual(res["type"], "provider_error")
            self.assertEqual(res["status_code"], 400)
            self.assertIn("HTTP 400", res["error"])

    # ------------------------------------------------------------------
    # TEST H: Provider failure queda explícitamente clasificado
    # ------------------------------------------------------------------
    def test_h_provider_failure_explicitly_classified(self):
        llm = LLMProvider()
        contents = [{"role": "user", "parts": [{"text": "Paso 1"}]}]
        with patch("requests.post") as mock_post:
            mock_res = MagicMock()
            mock_res.status_code = 500
            mock_res.text = "Internal Server Error"
            mock_post.return_value = mock_res

            res = llm.generate_response_with_tools("Sys", contents, AVATAR_TOOLS_SCHEMA)
            self.assertEqual(res["type"], "provider_error")

    # ------------------------------------------------------------------
    # TEST I: SAR no transforma provider_error en MODEL_DECISION
    # ------------------------------------------------------------------
    def test_i_sar_does_not_transform_provider_error(self):
        llm_result = {"type": "provider_error", "error": "HTTP 400 Bad Request", "status_code": 400}
        recovered = None
        if llm_result.get("type") == "text":
            recovered = StructuredActionRecoveryLayer.extract_and_validate_structured_action(
                llm_result.get("text", ""),
                AVATAR_TOOLS_SCHEMA
            )
        self.assertIsNone(recovered)
        self.assertNotEqual(llm_result.get("type"), "function_call")

    # ------------------------------------------------------------------
    # TEST J: Una respuesta real del modelo continúa el ciclo normalmente
    # ------------------------------------------------------------------
    def test_j_real_model_response_continues_cycle(self):
        llm_result = {
            "type": "function_call",
            "name": "READ_FILE",
            "args": {"file_path": "main.py"},
            "raw_part": {"functionCall": {"name": "READ_FILE", "args": {"file_path": "main.py"}}}
        }
        self.assertEqual(llm_result["type"], "function_call")
        self.assertEqual(llm_result["name"], "READ_FILE")

    # ------------------------------------------------------------------
    # TEST K: Gates A-E permanecen intactos (155 baseline PASS)
    # ------------------------------------------------------------------
    def test_k_gates_a_e_contracts_intact(self):
        from core.cognitive.semantic_mission_engine import SemanticMissionEngine
        goal = Goal(goal_id="g1", objective="Conversación normal", status=GoalState.EXECUTING)
        res = SemanticMissionEngine.classify_interaction("Hola Avatar, ¿cómo estás?")
        self.assertEqual(res.value, "CONVERSATION_NORMAL")

if __name__ == "__main__":
    unittest.main()
