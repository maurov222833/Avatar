"""
Shared fixtures for authority tests.

Everything here goes through the *real* production chain:

    PhysicalFactVerifier -> CapabilitySpecificVerifier -> AuthorizedEvidenceBuilder
                         -> CapabilityEvidenceRegistry

No test in the authority suites is permitted to hand-construct `CapabilityEvidence` and
expect it to be admitted; that pattern is exactly what D-6/D-8 exploited.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import List, Optional

from core.state_db import StateEngine
from core.cognitive.capability_registry import CapabilityEvidenceRegistry
from core.cognitive.physical_fact_verifier import PhysicalFactVerifier
from core.cognitive.authorized_evidence_builder import AuthorizedEvidenceBuilder
from core.cognitive.capability_definitions import SQLITE_PERSISTENCE_FACT


def temp_db() -> tuple:
    """Return `(StateEngine, temp_dir)` wired to a fresh on-disk database."""
    temp_dir = tempfile.mkdtemp()
    db = StateEngine(db_path=os.path.join(temp_dir, "authority.db"))
    return db, temp_dir


def cleanup(db, temp_dir) -> None:
    try:
        if db:
            db.close()
    except Exception:
        pass
    shutil.rmtree(temp_dir, ignore_errors=True)


def make_mission(db: StateEngine, required_capabilities: Optional[List[str]] = None,
                 declare_no_requirements: bool = False) -> str:
    session_id = db.create_session()
    return db.create_mission(
        session_id=session_id,
        raw_prompt="authority fixture mission",
        classified_intent="OPEN_ENGINEERING_MISSION",
        required_capabilities=required_capabilities,
        declare_no_requirements=declare_no_requirements,
    )


def sqlite_fact(db: StateEngine, execution_id: str = "exec-fixture"):
    """A genuine physical observation of the database file backing `db`."""
    return PhysicalFactVerifier.verify_sqlite_persistence(db.db_path, execution_id=execution_id)


def authorized_evidence_for(db: StateEngine, registry: CapabilityEvidenceRegistry,
                            mission_id: str, execution_id: str = "exec-fixture",
                            task_id: str = "T1"):
    """
    Run the full legitimate chain for CAP_STATE_ENGINE and return the produced evidence.

    Returns an empty list when the verification legitimately refuses, which is the normal
    outcome for capabilities that have no capability-specific verifier.
    """
    fact = sqlite_fact(db, execution_id=execution_id)
    return AuthorizedEvidenceBuilder.build_for_capability(
        capability_id="CAP_STATE_ENGINE",
        fact=fact,
        mission_id=mission_id,
        task_id=task_id,
        execution_id=execution_id,
        expected_resource=db.db_path,
    )


def certify_state_engine(db: StateEngine, registry: CapabilityEvidenceRegistry,
                        mission_id: str, execution_id: str = "exec-fixture",
                        task_id: str = "T1") -> str:
    """Admit all legitimately produced CAP_STATE_ENGINE evidence for `mission_id`."""
    status = registry.get_capability_status("CAP_STATE_ENGINE", mission_id=mission_id)
    for ev in authorized_evidence_for(db, registry, mission_id, execution_id, task_id):
        status = registry.register_evidence("CAP_STATE_ENGINE", ev, mission_id=mission_id)
    return status
