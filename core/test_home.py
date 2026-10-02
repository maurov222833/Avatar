"""Aisla la suite del directorio operativo.

``unittest discover`` no importa ``tests/conftest.py``. Sin este pin, el
primer ``import core`` de un test abre ``memory/state_engine.db`` del
repositorio y, si ``server`` arranca, el listener de Telegram lee el token
del entorno.
"""
from __future__ import annotations

import atexit
import ipaddress
import json
import os
import shutil
import sys
import tempfile

_PINNED = False
_TEST_HOME = ""


def _head_is_test_runner(head: str) -> bool:
    """argv[0] a veces es el comando entero: «python -m unittest» o «python.exe -m unittest»."""
    text = (head or "").replace("\\", "/").lower()
    if "-m unittest" in text or "-m pytest" in text:
        return True
    if text.endswith("unittest/__main__.py") or text.endswith("pytest/__main__.py"):
        return True
    base = os.path.basename(text)
    return base in {"pytest", "py.test", "pytest.exe"}


def running_as_test() -> bool:
    """Verdadero solo en el proceso de la suite. Un server o el supervisor no entran."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    argv = [str(arg) for arg in (sys.argv or [])]
    if argv and _head_is_test_runner(argv[0]):
        return True
    for arg in argv:
        if arg == "unittest":
            return True
        base = os.path.basename(arg.replace("\\", "/")).lower()
        if base in {"pytest", "py.test", "pytest.exe"}:
            return True
    return False


def pin_test_home() -> str:
    """Fija AVATAR_HOME en un temporal y aparta el token de Telegram. Idempotente."""
    global _PINNED, _TEST_HOME
    if _PINNED:
        return _TEST_HOME
    if not running_as_test():
        return ""
    _PINNED = True
    _TEST_HOME = tempfile.mkdtemp(prefix="avatar_test_")
    os.environ["AVATAR_HOME"] = _TEST_HOME
    # El token del operador no entra en la suite. Un test que lo necesite lo pone después.
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.makedirs(os.path.join(_TEST_HOME, "memory"), exist_ok=True)
    with open(os.path.join(_TEST_HOME, "config.json"), "w", encoding="utf-8") as handle:
        json.dump({
            "default_provider": "gemini",
            "gemini": {"api_key": "", "model": "gemini-3.6-flash"},
            "security": {"exec_requires_approval": True, "exec_allowlist": []},
            "telegram": {"allowed_chat_ids": []},
        }, handle, indent=2)
    _patch_default_stores(_TEST_HOME)
    install_network_guard()
    atexit.register(shutil.rmtree, _TEST_HOME, True)
    return _TEST_HOME


class ExternalNetworkBlocked(RuntimeError):
    """La suite no abre conexiones fuera de localhost."""


def _is_local_host(host) -> bool:
    if host is None:
        return True
    text = str(host).strip().lower()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if text in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0", "::"}:
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def install_network_guard() -> None:
    """Bloquea api.telegram.org y cualquier host que no sea localhost."""
    import socket
    if getattr(socket, "_avatar_network_guard", False):
        return

    def _reject(address) -> None:
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_local_host(host):
            raise ExternalNetworkBlocked(str(host))

    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        _reject(address)
        return orig_connect(self, address)

    def connect_ex(self, address):
        _reject(address)
        return orig_connect_ex(self, address)

    def getaddrinfo(host, port, *args, **kwargs):
        if not _is_local_host(host):
            raise ExternalNetworkBlocked(str(host))
        return orig_getaddrinfo(host, port, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    socket._avatar_network_guard = True


def _patch_default_stores(test_home: str) -> None:
    """Un db_path explícito sigue siendo del test. El implícito no es el operativo."""
    import core.rag_memory as rag_memory
    import core.state_db as state_db

    orig_rag = rag_memory.RAGMemory.__init__
    orig_engine = state_db.StateEngine.__init__

    def rag_init(self, memory_dir=None, state_db=None, *args, **kwargs):
        if memory_dir is None:
            memory_dir = os.path.join(test_home, "memory")
        orig_rag(self, memory_dir, state_db, *args, **kwargs)

    def engine_init(self, db_path=None, *args, **kwargs):
        if db_path is None:
            db_path = os.path.join(test_home, "memory", "state_engine.db")
        orig_engine(self, db_path, *args, **kwargs)

    rag_memory.RAGMemory.__init__ = rag_init
    state_db.StateEngine.__init__ = engine_init
