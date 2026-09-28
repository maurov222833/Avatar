import os
import tempfile
import sqlite3
import threading
import unittest
from core.state_db import StateEngine
from core.rag_memory import RAGMemory
from core.orchestrator import AvatarOrchestrator

class TestStateEnginePhase1(unittest.TestCase):
    """
    Suite de Pruebas Obligatorias de Integración y Persistencia para State Engine / Operational Memory (Fase 1).
    Cubre los 18 criterios de verificación exigidos.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_state_engine.db")
        self.engine = StateEngine(db_path=self.db_path)

    def tearDown(self):
        if hasattr(self, "engine") and self.engine:
            self.engine.close()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_01_create_session(self):
        sess_id = self.engine.create_session()
        self.assertTrue(sess_id.startswith("sess_"))
        sess_data = self.engine.get_session(sess_id)
        self.assertIsNotNone(sess_data)
        self.assertEqual(sess_data["session_id"], sess_id)
        self.assertEqual(sess_data["status"], "ACTIVE")

    def test_02_create_mission(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(
            session_id=sess_id,
            raw_prompt="Auditar arquitectura",
            classified_intent="OPEN_ENGINEERING_MISSION"
        )
        self.assertTrue(msn_id.startswith("msn_"))
        msn_data = self.engine.get_mission(msn_id)
        self.assertIsNotNone(msn_data)
        self.assertEqual(msn_data["session_id"], sess_id)
        self.assertEqual(msn_data["classified_intent"], "OPEN_ENGINEERING_MISSION")

    def test_03_create_tasks(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Prueba tareas")
        t_id = self.engine.create_planner_task(
            task_id="T1",
            mission_id=msn_id,
            step_index=1,
            description="Inspeccionar archivos",
            tool_name="READ_FILE",
            tool_args={"file_path": "core/state_db.py"},
            status="PENDING"
        )
        self.assertEqual(t_id, "T1")
        tasks = self.engine.get_planner_tasks(msn_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "T1")
        self.assertEqual(tasks[0]["tool_args"], {"file_path": "core/state_db.py"})

    def test_04_persist_state(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Persistir estado completo")
        self.engine.create_planner_task("T1", msn_id, 1, "Paso 1", "COMMAND", {"command": "dir"}, "IN_PROGRESS")
        
        msn = self.engine.get_mission(msn_id)
        tasks = self.engine.get_planner_tasks(msn_id)
        self.assertEqual(msn["status"], "IN_PROGRESS")
        self.assertEqual(tasks[0]["status"], "IN_PROGRESS")

    def test_05_read_after_close(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Read after close")
        self.engine.create_planner_task("T1", msn_id, 1, "Task 1", "COMMAND", {"command": "echo hello"})
        
        # Cerrar conexión
        self.engine.close()
        
        # Abrir nueva instancia sobre la misma BD
        new_engine = StateEngine(db_path=self.db_path)
        msn = new_engine.get_mission(msn_id)
        tasks = new_engine.get_planner_tasks(msn_id)
        new_engine.close()

        self.assertIsNotNone(msn)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["description"], "Task 1")

    def test_06_update_task_state(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Task state updates")
        self.engine.create_planner_task("T1", msn_id, 1, "Task 1", "COMMAND", {"command": "pytest"})
        
        self.engine.update_planner_task("T1", status="IN_PROGRESS")
        t1 = self.engine.get_planner_tasks(msn_id)[0]
        self.assertEqual(t1["status"], "IN_PROGRESS")
        
        self.engine.update_planner_task("T1", status="VERIFIED", execution_output="216 passed")
        t2 = self.engine.get_planner_tasks(msn_id)[0]
        self.assertEqual(t2["status"], "VERIFIED")
        self.assertEqual(t2["execution_output"], "216 passed")

    def test_07_persist_evidence(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Evidencia")
        ev_id = self.engine.add_evidence(
            evidence_id=None,
            mission_id=msn_id,
            source="pytest_output",
            data_reference="file:///logs/test_log.txt"
        )
        self.assertTrue(ev_id.startswith("ev_"))
        evidences = self.engine.get_evidences(msn_id)
        self.assertEqual(len(evidences), 1)
        self.assertEqual(evidences[0]["source"], "pytest_output")

    def test_08_persist_recovery_state(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Recovery")
        rec_id = self.engine.add_recovery_state(
            recovery_id=None,
            mission_id=msn_id,
            failure_context="ModuleNotFoundError: pytest",
            hypotheses_history=["Instalar dependencia pytest", "Usar venv"],
            retry_count=1,
            status="ACTIVE"
        )
        self.assertTrue(rec_id.startswith("rec_"))
        recs = self.engine.get_recovery_states(msn_id)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["retry_count"], 1)
        self.assertEqual(len(recs[0]["hypotheses_history"]), 2)

    def test_09_persist_evidence_gap(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Gap")
        gap_id = self.engine.add_evidence_gap(
            gap_id=None,
            mission_id=msn_id,
            description="Falta log de ejecución de PowerShell",
            status="UNRESOLVED"
        )
        self.assertTrue(gap_id.startswith("gap_"))
        gaps = self.engine.get_evidence_gaps(msn_id)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["description"], "Falta log de ejecución de PowerShell")

    def test_10_referential_integrity(self):
        # Intentar crear misión con session_id inexistente debe violar FK
        with self.assertRaises(sqlite3.IntegrityError):
            self.engine.create_mission(session_id="sess_non_existent", raw_prompt="Test FK")

    def test_11_transaction_rollback(self):
        # Verificar rollback al forzar un error sintáctico dentro de una transacción manual
        conn = self.engine._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("INSERT INTO sessions (session_id, started_at, updated_at, status) VALUES ('sess_rb', '2026', '2026', 'ACTIVE');")
            # Sentencia errónea para forzar excepción
            cursor.execute("INSERT INTO invalid_table VALUES (1);")
            conn.commit()
        except Exception:
            conn.rollback()

        # Comprobar que la sesión 'sess_rb' fue eliminada por rollback
        sess = self.engine.get_session("sess_rb")
        self.assertIsNone(sess)

    def test_12_failure_simulation_during_write(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Write Failure Simulation")
        
        # Intentar insertar una tarea con estado inválido para forzar CHECK constraint
        with self.assertRaises(sqlite3.IntegrityError):
            self.engine.create_planner_task("T_ERR", msn_id, 1, "Bad Status Task", "COMMAND", {}, status="INVALID_STATUS_NAME")
            
        tasks = self.engine.get_planner_tasks(msn_id)
        self.assertEqual(len(tasks), 0)

    def test_13_sqlite_wal_active(self):
        mode = self.engine.get_journal_mode()
        self.assertEqual(mode, "wal")

    def test_14_process_restart_data_recovery(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Process Restart Test")
        self.engine.add_evidence(None, msn_id, "test_source", "test_ref")
        self.engine.close()

        # Simular reinicio de proceso
        restarted_engine = StateEngine(db_path=self.db_path)
        msn = restarted_engine.get_mission(msn_id)
        evs = restarted_engine.get_evidences(msn_id)
        restarted_engine.close()

        self.assertIsNotNone(msn)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["source"], "test_source")

    def test_15_controlled_concurrent_persistence(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Concurrent Writes")
        
        def worker_task(idx):
            self.engine.create_planner_task(f"T_CONC_{idx}", msn_id, idx, f"Concurrent Task {idx}", "COMMAND", {"idx": idx})

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker_task, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        tasks = self.engine.get_planner_tasks(msn_id)
        self.assertEqual(len(tasks), 10)

    def test_16_no_data_loss_after_exception(self):
        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(session_id=sess_id, raw_prompt="Pre-exception Data")

        # Excepción simulada en lógica de aplicación
        try:
            raise ValueError("Fallo simulado en la lógica de aplicación")
        except ValueError:
            pass

        msn = self.engine.get_mission(msn_id)
        self.assertIsNotNone(msn)
        self.assertEqual(msn["raw_prompt"], "Pre-exception Data")

    def test_17_ragmemory_compatibility(self):
        memory_dir = os.path.join(self.temp_dir, "rag_mem")
        rag = RAGMemory(memory_dir=memory_dir, state_db=self.engine)
        
        # Guardar historial
        rag.save_history([{"role": "user", "content": "Hola Avatar"}, {"role": "assistant", "content": "Hola Mauro"}])
        history = rag.load_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["content"], "Hola Avatar")

        # Guardar tarea activa
        rag.save_active_task("Auditoría Fase 1", 50, "IN_PROGRESS")
        active = rag.get_active_task()
        self.assertEqual(active.get("task"), "Auditoría Fase 1")

    def test_18_orchestrator_compatibility(self):
        orchestrator = AvatarOrchestrator()
        self.assertIsNotNone(orchestrator.state_db)
        self.assertTrue(orchestrator.session_id.startswith("sess_"))

        # Registrar misión y tarea a través de la instancia del orquestador.
        # NOTA (IMPLEMENTATION 003): esta llamada antes usaba
        # `update_mission_status(msn_id, allow_empty_requirements=True)`, un argumento que la
        # auditoría forense 002 identificó como evasión de la frontera de autoridad (D-5). Ese
        # parámetro ya no existe. Una misión sin requirements ahora debe declararlo como
        # propiedad persistida (`declare_no_requirements=True`), no relajar la evaluación.
        msn_id = orchestrator.state_db.create_mission(
            session_id=orchestrator.session_id,
            raw_prompt="Test Orchestrator Integration",
            classified_intent="DIRECT_ACTION",
            declare_no_requirements=True
        )
        t_id = f"T1_{msn_id[:8]}"
        orchestrator.state_db.create_planner_task(t_id, msn_id, 1, "Task 1", "READ_FILE", {"file_path": "config.json"})
        orchestrator.state_db.update_planner_task(t_id, status="VERIFIED", execution_output="{}")
        orchestrator.state_db.complete_mission_with_authorization(msn_id)

        msn = orchestrator.state_db.get_mission(msn_id)
        tasks = orchestrator.state_db.get_planner_tasks(msn_id)
        self.assertEqual(msn["status"], "NO_REQUIREMENTS_DECLARED")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "VERIFIED")

    def test_18b_mission_with_unverified_requirement_is_not_completed(self):
        """
        D-5: una misión que declara requirements no verificados no puede completarse,
        y `update_mission_status` no expone ningún argumento para relajarlos.
        """
        import inspect
        params = list(inspect.signature(self.engine.update_mission_status).parameters)
        self.assertNotIn("required_capabilities", params)
        self.assertNotIn("allow_empty_requirements", params)

        sess_id = self.engine.create_session()
        msn_id = self.engine.create_mission(
            session_id=sess_id,
            raw_prompt="Requires unverified capability",
            required_capabilities=["CAP_WHATSAPP_AUTO_REPLY"],
        )
        self.assertNotEqual(self.engine.update_mission_status(msn_id), "COMPLETED")

    def test_18c_mission_cannot_be_created_completed(self):
        """D-3: una misión no puede nacer en estado terminal."""
        sess_id = self.engine.create_session()
        with self.assertRaises(ValueError):
            self.engine.create_mission(session_id=sess_id, raw_prompt="x", status="COMPLETED")

if __name__ == "__main__":
    unittest.main()
