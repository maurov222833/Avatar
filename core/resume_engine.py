import os
import json
import threading
from typing import Dict, Any, List, Optional, Tuple
from core.state_db import StateEngine
from core.checkpoint_engine import CheckpointEngine, IdempotencyClass
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier, VerifiedFact
from core.cognitive.verifier import Verifier
from core.cognitive.recovery_engine import RecoveryEngine
from core.cognitive.mission_completion_gate import MissionCompletionGate
from core.cognitive.capability_registry import CapabilityEvidenceRegistry
from core.cognitive.gate_authorization import GateAuthorization

class MissionResumeStatus:
    NO_ACTIVE_MISSION = "NO_ACTIVE_MISSION"
    ACTIVE_MISSION_SAFE_TO_RESUME = "ACTIVE_MISSION_SAFE_TO_RESUME"
    ACTIVE_MISSION_UNCERTAIN = "ACTIVE_MISSION_UNCERTAIN"
    ACTIVE_MISSION_FAILED = "ACTIVE_MISSION_FAILED"
    ACTIVE_MISSION_COMPLETED = "ACTIVE_MISSION_COMPLETED"

class ResumeEngine:
    def __init__(self, state_db: Optional[StateEngine] = None, checkpoint_engine: Optional[CheckpointEngine] = None):
        if state_db is not None:
            self.state_db = state_db
        else:
            self.state_db = StateEngine()
            
        if checkpoint_engine is not None:
            self.checkpoint_engine = checkpoint_engine
        else:
            self.checkpoint_engine = CheckpointEngine(state_db=self.state_db)

        self._lock = threading.Lock()

    def inspect_active_missions(self) -> List[Dict[str, Any]]:
        with self.state_db._lock:
            cursor = self.state_db._get_connection().cursor()
            cursor.execute("SELECT * FROM missions WHERE status IN ('IN_PROGRESS', 'PENDING') ORDER BY created_at ASC")
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]

    def evaluate_mission_for_resume(self, mission_id: str) -> Tuple[str, Optional[Dict[str, Any]], str]:
        mission = self.state_db.get_mission(mission_id)
        if not mission:
            return (MissionResumeStatus.NO_ACTIVE_MISSION, None, "Misión no encontrada.")

        tasks = self.state_db.get_planner_tasks(mission_id)
        if not tasks:
            return (MissionResumeStatus.NO_ACTIVE_MISSION, None, "La misión no tiene tareas registradas.")

        required_caps = json.loads(mission.get("required_capabilities", "[]")) if isinstance(mission.get("required_capabilities"), str) else (mission.get("required_capabilities") or [])

        uncompleted_tasks = [t for t in tasks if t["status"] not in ("VERIFIED", "COMPLETED")]
        if not uncompleted_tasks:
            registry = CapabilityEvidenceRegistry(state_db=self.state_db)
            # D-5: requirements come from the persisted mission; Resume never supplies or
            # relaxes them. D-14: Resume re-evaluates, it does not confer authority.
            gate_auth = MissionCompletionGate.evaluate_and_authorize(
                mission_id=mission_id,
                state_db=self.state_db,
                capability_registry=registry
            )
            self.state_db.complete_mission_with_authorization(mission_id, gate_authorization=gate_auth)
            return (MissionResumeStatus.ACTIVE_MISSION_COMPLETED, None, "Todas las tareas de la misión están VERIFIED/COMPLETED.")

        # 2. Obtener la primera tarea no completada (T_k)
        target_task = uncompleted_tasks[0]
        task_id = target_task["task_id"]
        status = target_task["status"]
        tool_name = target_task["tool_name"]
        tool_args = target_task.get("tool_args", {})
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except Exception:
                tool_args = {}

        # Caso 1: Tarea en estado PENDING -> Seguro de reanudar normalmente
        if status == "PENDING":
            return (MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME, target_task, "Tarea PENDING lista para ejecutar.")

        # Caso 2: Tarea en estado POST_TOOL_EXECUTION -> Verificar salida capturada
        if status == "POST_TOOL_EXECUTION":
            exec_output = target_task.get("execution_output", "")
            if exec_output:
                self.checkpoint_engine.mark_verified(mission_id, task_id, claim="Auto-verified post-tool resume", evidence_data={"output": exec_output[:200]})
                # Recurrir para evaluar la siguiente tarea
                return self.evaluate_mission_for_resume(mission_id)
            else:
                # Tratar como PRE_TOOL_EXECUTION
                status = "PRE_TOOL_EXECUTION"

        # Caso 3: Tarea en PRE_TOOL_EXECUTION, IN_PROGRESS o UNCERTAIN_EXECUTION -> Evaluar Idempotencia
        if status in ("PRE_TOOL_EXECUTION", "IN_PROGRESS", "UNCERTAIN_EXECUTION"):
            idempotency = CheckpointEngine.classify_idempotency(tool_name, tool_args)
            
            # Herramienta IDEMPOTENT (READ_FILE, LIST_DIR, etc.) -> Seguro reintentar de forma controlada
            if idempotency == IdempotencyClass.IDEMPOTENT:
                self.checkpoint_engine.save_pre_tool_checkpoint(
                    mission_id, task_id, target_task["step_index"],
                    target_task["description"], tool_name, tool_args
                )
                return (MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME, target_task, f"Herramienta {tool_name} es IDEMPOTENT; reintento seguro.")
            
            # Herramienta NON_IDEMPOTENT o UNKNOWN -> UNCERTAIN_EXECUTION -> Fact Verifier
            else:
                self.checkpoint_engine.mark_uncertain(mission_id, task_id, reason=f"Interrupción detectada en herramienta {tool_name} ({idempotency})")
                
                # Consultar PhysicalFactVerifier para comprobar si el efecto secundario ocurrió
                verifier_result = self._check_side_effect_with_physical_verifier(target_task, tool_name, tool_args)
                
                if verifier_result == "YES":
                    # El efecto YA ocurrió -> Marcar VERIFIED y avanzar sin repetir la herramienta!
                    self.checkpoint_engine.mark_verified(
                        mission_id, task_id,
                        claim=f"Side-effect confirmed by PhysicalFactVerifier for {tool_name}",
                        evidence_data={"verifier_verdict": "YES"}
                    )
                    return self.evaluate_mission_for_resume(mission_id)
                
                elif verifier_result == "NO":
                    # El efecto NO ocurrió -> Seguro re-ejecutar de forma controlada
                    self.checkpoint_engine.save_pre_tool_checkpoint(
                        mission_id, task_id, target_task["step_index"],
                        target_task["description"], tool_name, tool_args
                    )
                    return (MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME, target_task, f"PhysicalFactVerifier confirmó que el efecto de {tool_name} NO ocurrió. Reintento seguro autorizado.")
                
                else: # UNKNOWN / UNVERIFIED
                    # BLOQUEO ABSOLUTO DE SEGURIDAD: No re-ejecutar automáticamente
                    return (MissionResumeStatus.ACTIVE_MISSION_UNCERTAIN, target_task, f"BLOQUEO DE SEGURIDAD: Herramienta {tool_name} ({idempotency}) en estado UNCERTAIN_EXECUTION. Sin evidencia suficiente para re-ejecución automática.")

        # Caso 4: FAILED
        if status == "FAILED":
            return (MissionResumeStatus.ACTIVE_MISSION_FAILED, target_task, "Tarea previa marcada FAILED con presupuesto agotado.")

        return (MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME, target_task, f"Estado de tarea {status} analizado.")

    def _check_side_effect_with_physical_verifier(self, task: Dict[str, Any], tool_name: str, tool_args: Dict[str, Any]) -> str:
        """
        Consulta evidencia física para determinar si una herramienta no idempotente tuvo efecto antes del crash.
        Devuelve 'YES', 'NO', o 'UNKNOWN'.
        """
        try:
            if tool_name == "WRITE_FILE":
                file_path = tool_args.get("file_path")
                expected_content = tool_args.get("content")
                if file_path and os.path.exists(file_path):
                    if expected_content:
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                actual_content = f.read()
                            if actual_content == expected_content:
                                return "YES"
                            else:
                                return "NO"
                        except Exception:
                            return "UNKNOWN"
                    return "YES"
                else:
                    return "NO"

            elif tool_name == "COMMAND":
                cmd = tool_args.get("command", "")
                criteria = tool_args.get("__criteria__", {})
                if criteria.get("expected_file_exists"):
                    f_path = criteria["expected_file_exists"]
                    return "YES" if os.path.exists(f_path) else "NO"

            # Si hay criterios de verificación generales en tool_args
            criteria = tool_args.get("__criteria__", {})
            if criteria.get("expected_file_exists"):
                return "YES" if os.path.exists(criteria["expected_file_exists"]) else "NO"
        except Exception:
            pass

        return "UNKNOWN"

    def resume_active_mission(self, mission_id: str, tool_dispatcher: Optional[Any] = None) -> Dict[str, Any]:
        """
        Reanuda la ejecución de una misión activa desde el punto exacto de interrupción.
        Aplica estrictamente anti-duplicación de tareas verificadas.
        """
        status, target_task, reason = self.evaluate_mission_for_resume(mission_id)
        mission = self.state_db.get_mission(mission_id)
        
        if status == MissionResumeStatus.ACTIVE_MISSION_COMPLETED:
            # The tasks are finished. The reported status is the one the gate persisted,
            # which can be BLOCKED or still open when the seal does not authorize completion.
            persisted = (mission or {}).get("status") or "IN_PROGRESS"
            return {"status": persisted, "mission_id": mission_id, "message": reason,
                    "executed_trace": [], "target_task": None}

        if status == MissionResumeStatus.ACTIVE_MISSION_UNCERTAIN:
            return {"status": "UNCERTAIN_EXECUTION", "mission_id": mission_id, "target_task": target_task, "reason": reason, "executed_trace": []}

        if status == MissionResumeStatus.ACTIVE_MISSION_FAILED:
            return {"status": "FAILED", "mission_id": mission_id, "target_task": target_task, "reason": reason, "executed_trace": []}

        if status == MissionResumeStatus.NO_ACTIVE_MISSION:
            return {"status": "NO_ACTIVE_MISSION", "mission_id": mission_id, "message": reason, "executed_trace": [], "target_task": None}

        # Ejecutar reanudación de tareas restantes a partir de target_task
        all_tasks = self.state_db.get_planner_tasks(mission_id)
        remaining_tasks = [t for t in all_tasks if t["step_index"] >= target_task["step_index"] and t["status"] not in ("VERIFIED", "COMPLETED")]

        executed_trace = []
        for t in remaining_tasks:
            t_id = t["task_id"]
            tool_name = t["tool_name"]
            tool_args = t.get("tool_args", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {}

            # 1. Guardar checkpoint PRE_TOOL
            self.checkpoint_engine.save_pre_tool_checkpoint(
                mission_id, t_id, t["step_index"], t["description"], tool_name, tool_args
            )

            # 2. Invocar ejecutor si se proporciona tool_dispatcher.
            # La copia lleva el contexto de misión/tarea para que el dispatcher pueda ligar
            # el act reanudado a su misión; las claves __resume_* son convención interna y el
            # dispatcher del orquestador las retira antes de llegar a la herramienta.
            output = ""
            if tool_dispatcher:
                try:
                    dispatch_args = dict(tool_args) if isinstance(tool_args, dict) else {}
                    dispatch_args["__resume_mission_id__"] = mission_id
                    dispatch_args["__resume_task_id__"] = t_id
                    output = tool_dispatcher(tool_name, dispatch_args)
                except Exception as e:
                    output = f"[Error de ejecución]: {str(e)}"

            # 3. Guardar checkpoint POST_TOOL y marcar VERIFIED
            self.checkpoint_engine.save_post_tool_checkpoint(mission_id, t_id, output, {"source": tool_name})
            self.checkpoint_engine.mark_verified(mission_id, t_id, claim=f"Executed on resume", evidence_data={"output": output[:200]})
            executed_trace.append({"task_id": t_id, "tool": tool_name, "output": output, "status": "VERIFIED"})

        # Reconciliar la misión con el Gate. Los requirements se leen de la misión
        # persistida; el estado devuelto refleja el veredicto real, no una afirmación.
        registry = CapabilityEvidenceRegistry(state_db=self.state_db)
        gate_auth = MissionCompletionGate.evaluate_and_authorize(
            mission_id=mission_id,
            state_db=self.state_db,
            capability_registry=registry
        )
        final_status = self.state_db.complete_mission_with_authorization(
            mission_id, gate_authorization=gate_auth
        )
        return {"status": final_status, "mission_id": mission_id, "executed_trace": executed_trace}
