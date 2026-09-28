import os
import tempfile
import sqlite3
import threading
import unittest
from core.state_db import StateEngine
from core.checkpoint_engine import CheckpointEngine, IdempotencyClass
from core.resume_engine import ResumeEngine, MissionResumeStatus
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.orchestrator import AvatarOrchestrator

class TestCheckpointResumePhase2(unittest.TestCase):
    """
    Suite de Pruebas Obligatorias para Checkpoint Engine y Resume Engine (Fase 2).
    Cubre los 20 criterios de verificación exigidos.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_checkpoint_resume.db")
        self.state_db = StateEngine(db_path=self.db_path)
        self.checkpoint_engine = CheckpointEngine(state_db=self.state_db)
        self.resume_engine = ResumeEngine(state_db=self.state_db, checkpoint_engine=self.checkpoint_engine)

    def tearDown(self):
        if hasattr(self, "state_db") and self.state_db:
            self.state_db.close()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_01_checkpoint_pre_tool(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Pre-tool Checkpoint Test")
        t_id = self.checkpoint_engine.save_pre_tool_checkpoint(
            mission_id=msn_id,
            task_id="T1_PRE",
            step_index=1,
            description="Pre-tool task",
            tool_name="READ_FILE",
            tool_args={"file_path": "config.json"}
        )
        tasks = self.state_db.get_planner_tasks(msn_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "T1_PRE")
        self.assertEqual(tasks[0]["status"], "PRE_TOOL_EXECUTION")
        self.assertEqual(tasks[0]["tool_args"]["__idempotency__"], "IDEMPOTENT")

    def test_02_checkpoint_post_tool(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Post-tool Checkpoint Test")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1_POST", 1, "Post task", "COMMAND", {"command": "dir"})
        
        self.checkpoint_engine.save_post_tool_checkpoint(
            mission_id=msn_id,
            task_id="T1_POST",
            execution_output="[Directory listing]",
            evidence_data={"source": "COMMAND"}
        )
        tasks = self.state_db.get_planner_tasks(msn_id)
        self.assertEqual(tasks[0]["status"], "POST_TOOL_EXECUTION")
        self.assertEqual(tasks[0]["execution_output"], "[Directory listing]")

    def test_03_checkpoint_verified(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Mark Verified Test")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1_VER", 1, "Verified task", "READ_FILE", {"file_path": "a.txt"})
        self.checkpoint_engine.mark_verified(msn_id, "T1_VER", claim="Verified output", evidence_data={"ok": True})
        
        tasks = self.state_db.get_planner_tasks(msn_id)
        self.assertEqual(tasks[0]["status"], "VERIFIED")
        records = self.state_db.get_verification_records(msn_id)
        self.assertEqual(len(records), 1)

    def test_04_recovery_active_mission(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Active Mission Inspection", status="IN_PROGRESS")
        actives = self.resume_engine.inspect_active_missions()
        self.assertEqual(len(actives), 1)
        self.assertEqual(actives[0]["mission_id"], msn_id)

    def test_05_mission_no_pending_tasks(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="No pending tasks")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1", 1, "Task 1", "READ_FILE", {})
        self.checkpoint_engine.mark_verified(msn_id, "T1")
        
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_COMPLETED)
        self.assertIsNone(target)

    def test_06_resume_from_pending_task(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Resume from pending")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1", 1, "Task 1", "READ_FILE", {})
        self.checkpoint_engine.mark_verified(msn_id, "T1")
        self.state_db.create_planner_task("T2", msn_id, 2, "Task 2", "COMMAND", {"command": "echo hello"}, "PENDING")
        
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME)
        self.assertEqual(target["task_id"], "T2")

    def test_07_no_duplication_of_verified_tasks(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Anti duplication test", declare_no_requirements=True)
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1", 1, "Task 1", "READ_FILE", {})
        self.checkpoint_engine.mark_verified(msn_id, "T1")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T2", 2, "Task 2", "LIST_DIR", {})
        self.checkpoint_engine.mark_verified(msn_id, "T2")
        self.state_db.create_planner_task("T3", msn_id, 3, "Task 3", "READ_FILE", {}, "PENDING")

        def dummy_dispatcher(tool, args):
            return f"Executed {tool}"

        res = self.resume_engine.resume_active_mission(msn_id, tool_dispatcher=dummy_dispatcher)
        # IMPLEMENTATION 003: esta misión declara explícitamente que no requiere
        # capabilities (`declare_no_requirements=True`). Al no haber requirements que
        # verificar, el veredicto terminal honesto es NO_REQUIREMENTS_DECLARED y no
        # COMPLETED, que implicaría que existen requirements-predeterminados que se cumplieron.
        self.assertEqual(res["status"], "NO_REQUIREMENTS_DECLARED")
        executed = res["executed_trace"]
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0]["task_id"], "T3")

    def test_08_idempotent_retry(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Idempotent retry")
        # Simular crash en PRE_TOOL_EXECUTION para herramienta IDEMPOTENT (READ_FILE)
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1_IDEM", 1, "Read task", "READ_FILE", {"file_path": "a.txt"})
        
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME)
        self.assertEqual(target["task_id"], "T1_IDEM")

    def test_09_non_idempotent_uncertainty(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Non-idempotent uncertainty")
        # Simular crash en PRE_TOOL_EXECUTION para herramienta NON_IDEMPOTENT (WRITE_FILE) sin criterios
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1_NON", 1, "Write task", "WRITE_FILE", {"file_path": "non_existent_file_xyz_99.txt", "content": "hello"})
        
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        # Como el archivo no existe, PhysicalFactVerifier devuelve 'NO', por lo que autoriza reintento seguro
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME)

    def test_10_unknown_treated_as_non_idempotent(self):
        self.assertEqual(CheckpointEngine.classify_idempotency("CUSTOM_UNKNOWN_TOOL"), IdempotencyClass.UNKNOWN)

    def test_11_physical_fact_verifier_integration(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Physical Fact Verifier Integration")
        
        # Crear archivo temporal para simular que el efecto secundario de WRITE_FILE ya ocurrió
        test_file = os.path.join(self.temp_dir, "side_effect.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("side_effect_content")

        self.checkpoint_engine.save_pre_tool_checkpoint(
            msn_id, "T1_SIDE", 1, "Write Task", "WRITE_FILE",
            {"file_path": test_file, "content": "side_effect_content"}
        )

        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        # PhysicalFactVerifier detecta que el archivo ya existe con el contenido exacto -> Marcar VERIFIED y avanzar a COMPLETED
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_COMPLETED)
        
        t1 = self.state_db.get_planner_tasks(msn_id)[0]
        self.assertEqual(t1["status"], "VERIFIED")

    def test_12_recovery_engine_integration(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Recovery Engine Integration")
        self.state_db.create_planner_task("T1_FAIL", msn_id, 1, "Failed Task", "COMMAND", {}, "FAILED")
        
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_FAILED)
        self.assertEqual(target["task_id"], "T1_FAIL")

    def test_13_checkpoint_transaction_failure(self):
        # Simular fallo en la conexión SQLite WAL lanzando excepción
        broken_db = StateEngine(db_path=self.db_path)
        broken_engine = CheckpointEngine(state_db=broken_db)
        broken_db.close()  # Cerrar la conexión forzadamente

        with self.assertRaises(Exception):
            broken_engine.save_pre_tool_checkpoint("msn_err", "T_ERR", 1, "Desc", "READ_FILE", {})

    def test_14_process_restart(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Process Restart Test")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1", 1, "Task 1", "READ_FILE", {})
        self.checkpoint_engine.mark_verified(msn_id, "T1")
        self.state_db.create_planner_task("T2", msn_id, 2, "Task 2", "LIST_DIR", {}, "PENDING")
        self.state_db.close()

        # Simular reinicio de proceso creando instancias completamente nuevas sobre el archivo SQLite DB
        restarted_db = StateEngine(db_path=self.db_path)
        restarted_resume = ResumeEngine(state_db=restarted_db)
        status, target, reason = restarted_resume.evaluate_mission_for_resume(msn_id)
        restarted_db.close()

        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME)
        self.assertEqual(target["task_id"], "T2")

    def test_15_corrupted_incomplete_checkpoint(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Corrupted Checkpoint Test")
        # Tarea con JSON corrupto en tool_args
        self.state_db.create_planner_task("T_CORRUPT", msn_id, 1, "Corrupt Task", "CUSTOM_TOOL", "NOT_A_VALID_JSON", "PRE_TOOL_EXECUTION")
        
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertIsNotNone(status)

    def test_16_multiple_missions(self):
        sess_id = self.state_db.create_session()
        msn1 = self.state_db.create_mission(session_id=sess_id, raw_prompt="Mission 1")
        msn2 = self.state_db.create_mission(session_id=sess_id, raw_prompt="Mission 2")
        actives = self.resume_engine.inspect_active_missions()
        self.assertEqual(len(actives), 2)

    def test_17_concurrent_resume_protection(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Concurrent Resume Test", declare_no_requirements=True)
        self.state_db.create_planner_task("T1", msn_id, 1, "Task 1", "READ_FILE", {}, "PENDING")

        def worker_resume():
            self.resume_engine.resume_active_mission(msn_id)

        t1 = threading.Thread(target=worker_resume)
        t2 = threading.Thread(target=worker_resume)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        msn = self.state_db.get_mission(msn_id)
        # Ver IMPLEMENTATION 003 en test_07: la misión declara que no requiere capabilities,
        # por lo que su estado terminal es NO_REQUIREMENTS_DECLARED.
        self.assertEqual(msn["status"], "NO_REQUIREMENTS_DECLARED")

    def test_18_crash_pre_tool_simulation(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Crash Pre-tool Simulation")
        # Interrupción inmediata tras guardar PRE_TOOL_EXECUTION
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1_CRASH_PRE", 1, "Pre crash task", "READ_FILE", {"file_path": "a.txt"})
        
        # Simular reconstrucción de estado tras reinicio
        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME)

    def test_19_crash_post_tool_simulation(self):
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Crash Post-tool Simulation")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "T1_CRASH_POST", 1, "Post crash task", "COMMAND", {"command": "dir"})
        # Guardar salida pero simular crash antes de llamar a mark_verified
        self.checkpoint_engine.save_post_tool_checkpoint(msn_id, "T1_CRASH_POST", "[Output Captured]", {"source": "COMMAND"})

        status, target, reason = self.resume_engine.evaluate_mission_for_resume(msn_id)
        self.assertEqual(status, MissionResumeStatus.ACTIVE_MISSION_COMPLETED)

    def test_20_e2e_5_task_mission_resume(self):
        """
        PRUEBA CRÍTICA E2E FISICA: Misión de 5 tareas con interrupción real tras Tarea 3.
        Demuestra anti-duplicación, reanudación desde Tarea 4 y finalización verificada.
        """
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="E2E 5 Task Crash & Resume Mission", declare_no_requirements=True)

        # 1. Ejecutar Tareas 1, 2 y 3 normalmente y marcar VERIFIED
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "TASK_1", 1, "LIST_DIR", "LIST_DIR", {"dir_path": "."})
        self.checkpoint_engine.mark_verified(msn_id, "TASK_1")

        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "TASK_2", 2, "READ_FILE", "READ_FILE", {"file_path": "config.json"})
        self.checkpoint_engine.mark_verified(msn_id, "TASK_2")

        test_write_file = os.path.join(self.temp_dir, "task_3_output.txt")
        self.checkpoint_engine.save_pre_tool_checkpoint(msn_id, "TASK_3", 3, "WRITE_FILE", "WRITE_FILE", {"file_path": test_write_file, "content": "e2e_pass"})
        with open(test_write_file, "w", encoding="utf-8") as f:
            f.write("e2e_pass")
        self.checkpoint_engine.mark_verified(msn_id, "TASK_3")

        # 2. Registrar Tareas 4 y 5 como PENDING (Interrupción simulada del proceso)
        self.state_db.create_planner_task("TASK_4", msn_id, 4, "READ_FILE Task 4", "READ_FILE", {"file_path": test_write_file}, "PENDING")
        self.state_db.create_planner_task("TASK_5", msn_id, 5, "Conclusion Task 5", "LIST_DIR", {"dir_path": "."}, "PENDING")

        # 3. Simular Cierre Físico del Proceso
        self.state_db.close()

        # 4. Abrir nuevas instancias de StateEngine y ResumeEngine tras el reinicio
        restarted_db = StateEngine(db_path=self.db_path)
        restarted_checkpoint = CheckpointEngine(state_db=restarted_db)
        restarted_resume = ResumeEngine(state_db=restarted_db, checkpoint_engine=restarted_checkpoint)

        def simple_dispatcher(tool, args):
            if tool == "READ_FILE":
                path = args.get("file_path", "")
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
            return "OK"

        res = restarted_resume.resume_active_mission(msn_id, tool_dispatcher=simple_dispatcher)
        restarted_db.close()

        # 5. Confirmaciones Físicas
        # Ver IMPLEMENTATION 003 en test_07: la misión declara que no requiere capabilities,
        # por lo que su estado terminal tras el reinicio es NO_REQUIREMENTS_DECLARED.
        self.assertEqual(res["status"], "NO_REQUIREMENTS_DECLARED")
        executed_trace = res["executed_trace"]
        # Debe haber ejecutado ÚNICAMENTE las Tareas 4 y 5 (Anti-duplicación de Tareas 1, 2 y 3)
        self.assertEqual(len(executed_trace), 2)
        self.assertEqual(executed_trace[0]["task_id"], "TASK_4")
        self.assertEqual(executed_trace[1]["task_id"], "TASK_5")

    def test_21_second_resume_is_idempotent_and_shape_stable(self):
        """La segunda pasada no re-ejecuta y mantiene executed_trace (aunque vacío)."""
        sess_id = self.state_db.create_session()
        msn_id = self.state_db.create_mission(session_id=sess_id, raw_prompt="Idempotent Resume", declare_no_requirements=True)
        self.state_db.create_planner_task("T1", msn_id, 1, "leer", "READ_FILE", {"file_path": "main.py"}, "PENDING")

        first = self.resume_engine.resume_active_mission(msn_id, tool_dispatcher=lambda tool, args: "ok")
        self.assertEqual([e["task_id"] for e in first["executed_trace"]], ["T1"])

        second = self.resume_engine.resume_active_mission(msn_id, tool_dispatcher=lambda tool, args: "SHOULD NOT RUN")
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(second["executed_trace"], [])

if __name__ == "__main__":
    unittest.main()
