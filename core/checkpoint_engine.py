import os
import json
import uuid
import datetime
from typing import Dict, Any, List, Optional
from core.state_db import StateEngine

class IdempotencyClass:
    IDEMPOTENT = "IDEMPOTENT"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"
    UNKNOWN = "UNKNOWN"

class CheckpointEngine:
    """
    CheckpointEngine para Avatar AI (Fase 2).
    Gestiona el ciclo de vida atómico de checkpoints pre y post ejecución de herramientas.
    Garantiza la persistencia atómica en SQLite WAL antes de invocar cualquier herramienta.
    """

    IDEMPOTENT_TOOLS = {"READ_FILE", "LIST_DIR", "FETCH_URL", "WEB_SEARCH"}
    NON_IDEMPOTENT_TOOLS = {"WRITE_FILE", "COMMAND", "SEND_WHATSAPP", "DELETE_FILE", "MOVE_FILE"}

    def __init__(self, state_db: Optional[StateEngine] = None):
        if state_db is not None:
            self.state_db = state_db
        else:
            self.state_db = StateEngine()

    @classmethod
    def classify_idempotency(cls, tool_name: str, tool_args: Optional[Dict[str, Any]] = None) -> str:
        """
        Clasifica una herramienta en IDEMPOTENT, NON_IDEMPOTENT o UNKNOWN.
        Las herramientas UNKNOWN se tratan implícitamente como NON_IDEMPOTENT por seguridad.
        """
        if not tool_name:
            return IdempotencyClass.UNKNOWN
        
        norm_tool = tool_name.upper().strip()
        if norm_tool in cls.IDEMPOTENT_TOOLS:
            return IdempotencyClass.IDEMPOTENT
        elif norm_tool in cls.NON_IDEMPOTENT_TOOLS:
            return IdempotencyClass.NON_IDEMPOTENT
        else:
            return IdempotencyClass.UNKNOWN

    def save_pre_tool_checkpoint(
        self,
        mission_id: str,
        task_id: str,
        step_index: int,
        description: str,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> str:
        """
        Guarda el checkpoint PRE_TOOL_EXECUTION atómicamente en SQLite WAL ANTES de invocar la herramienta.
        Si la transacción falla, lanza una excepción para evitar ejecutar la herramienta a ciegas.
        """
        idempotency = self.classify_idempotency(tool_name, tool_args)
        
        # Enriquecer tool_args con metadata de idempotencia
        args_payload = dict(tool_args) if isinstance(tool_args, dict) else {"raw": str(tool_args)}
        args_payload["__idempotency__"] = idempotency
        args_payload["__checkpoint_time__"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Intentar obtener la tarea si ya existe, de lo contrario crearla
        existing_tasks = self.state_db.get_planner_tasks(mission_id)
        task_exists = any(t["task_id"] == task_id for t in existing_tasks)

        if task_exists:
            self.state_db.update_planner_task(task_id, status="PRE_TOOL_EXECUTION")
        else:
            self.state_db.create_planner_task(
                task_id=task_id,
                mission_id=mission_id,
                step_index=step_index,
                description=description,
                tool_name=tool_name,
                tool_args=args_payload,
                status="PRE_TOOL_EXECUTION"
            )
        
        return task_id

    def save_post_tool_checkpoint(
        self,
        mission_id: str,
        task_id: str,
        execution_output: str,
        evidence_data: Optional[Dict[str, Any]] = None,
        verifier_status: str = "COMPLETED"
    ):
        """
        Guarda el checkpoint POST_TOOL_EXECUTION después de capturar la salida de la herramienta.
        """
        status_to_set = "POST_TOOL_EXECUTION" if verifier_status == "COMPLETED" else verifier_status
        self.state_db.update_planner_task(
            task_id=task_id,
            status=status_to_set,
            execution_output=execution_output
        )

        if evidence_data:
            self.state_db.add_evidence(
                evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                mission_id=mission_id,
                task_id=task_id,
                source=evidence_data.get("source", "tool_execution"),
                data_reference=evidence_data.get("reference", str(evidence_data)[:200])
            )

    def mark_verified(self, mission_id: str, task_id: str, claim: str = "Task Verification", evidence_data: Optional[Dict[str, Any]] = None):
        """Marca una tarea como VERIFIED en StateEngine DB."""
        self.state_db.update_planner_task(task_id, status="VERIFIED")
        if evidence_data:
            self.state_db.add_verification_record(
                fact_id=f"fact_{uuid.uuid4().hex[:10]}",
                mission_id=mission_id,
                task_id=task_id,
                claim=claim,
                verified_status="PASS",
                evidence_data=evidence_data
            )

    def mark_uncertain(self, mission_id: str, task_id: str, reason: str = "Crash before post-checkpoint"):
        """Marca una tarea como UNCERTAIN_EXECUTION en StateEngine DB."""
        self.state_db.update_planner_task(task_id, status="UNCERTAIN_EXECUTION")
        self.state_db.add_evidence_gap(
            gap_id=f"gap_{uuid.uuid4().hex[:10]}",
            mission_id=mission_id,
            task_id=task_id,
            description=reason,
            status="UNRESOLVED"
        )
