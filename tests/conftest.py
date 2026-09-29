"""
Global test isolation.

Problem this solves
-------------------
Several tests construct `AvatarOrchestrator()`, which builds a `RAGMemory`, which opens the
*real* operational database at `memory/state_engine.db`. Running the suite therefore injected
dozens of test missions into the developer's live state, and — worse — a failing or partially
executed test could corrupt genuine operational history.

This module redirects every implicit database path to a per-session temporary directory, so no
test can reach the operational store regardless of what it does. It is applied at import time
(deliberately not as a fixture, because pytest fixtures do not apply to `unittest.TestCase`
subclasses, which is how most of this suite is written).

Explicitly-passed paths are left untouched: a test that supplies its own `db_path` is already
isolated and is not affected.

F-15: ``AVATAR_HOME`` is pinned to the same temp directory before core imports, so config.json
writes (HTTP /api/config/update, CLI provider switch) never touch the developer's real config.
"""
import atexit
import json
import os
import shutil
import tempfile

_TEST_HOME = tempfile.mkdtemp(prefix="avatar_test_")
os.environ["AVATAR_HOME"] = _TEST_HOME
os.makedirs(os.path.join(_TEST_HOME, "memory"), exist_ok=True)
with open(os.path.join(_TEST_HOME, "config.json"), "w", encoding="utf-8") as _cfg:
    json.dump({
        "default_provider": "gemini",
        "gemini": {"api_key": "", "model": "gemini-3.6-flash"},
        "security": {"exec_requires_approval": True, "exec_allowlist": []},
        "telegram": {"allowed_chat_ids": []},
    }, _cfg, indent=2)

# ---------------------------------------------------------------- RAGMemory
import core.rag_memory as rag_memory

REAL_MEMORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory"
)

_orig_rag_init = rag_memory.RAGMemory.__init__


def _patched_rag_init(self, memory_dir=None, state_db=None, *args, **kwargs):
    if memory_dir is None:
        memory_dir = os.path.join(_TEST_HOME, "memory")
    _orig_rag_init(self, memory_dir, state_db, *args, **kwargs)


rag_memory.RAGMemory.__init__ = _patched_rag_init

# ---------------------------------------------------------------- StateEngine
import core.state_db as state_db

_orig_engine_init = state_db.StateEngine.__init__


def _patched_engine_init(self, db_path=None, *args, **kwargs):
    if db_path is None:
        db_path = os.path.join(_TEST_HOME, "memory", "state_engine.db")
    _orig_engine_init(self, db_path, *args, **kwargs)


state_db.StateEngine.__init__ = _patched_engine_init

atexit.register(shutil.rmtree, _TEST_HOME, True)


def _refuse_operational_db():
    """Guard used by tests that need to be certain the real store is untouched."""
    if os.path.exists(os.path.join(REAL_MEMORY_DIR, "state_engine.db")):
        return REAL_MEMORY_DIR
    return None
