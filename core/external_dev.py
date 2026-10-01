"""Delegación a un IDE externo (spec 003, U8).

Solo hay un adaptador simulado. Ningún IDE real se integra hasta que Mauro
nombre la herramienta. El diff se revisa; la afirmación del IDE no es evidencia.
"""
from __future__ import annotations

import os
from typing import Dict, List, Protocol


class ExternalDevAgent(Protocol):
    def start(self, brief: Dict[str, str]) -> str: ...
    def result(self, task_id: str) -> Dict[str, List[str]]: ...
    def cancel(self, task_id: str) -> None: ...


class SimulatedDevAgent:
    """Escribe solo dentro del worktree declarado. Sirve para pruebas."""

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        self.tasks: Dict[str, Dict[str, List[str]]] = {}
        self._n = 0

    def start(self, brief: Dict[str, str]) -> str:
        self._n += 1
        task_id = f"dev-{self._n}"
        allowed = brief.get("allowed_dir") or self.root
        target = os.path.abspath(brief.get("path") or os.path.join(allowed, "out.txt"))
        written: List[str] = []
        if os.path.commonpath([target, os.path.abspath(allowed)]) == os.path.abspath(allowed):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(brief.get("body") or "ok")
            written.append(target)
        self.tasks[task_id] = {"written": written, "rejected": [] if written else [target]}
        return task_id

    def result(self, task_id: str) -> Dict[str, List[str]]:
        return self.tasks[task_id]

    def cancel(self, task_id: str) -> None:
        self.tasks.pop(task_id, None)


class FakeDevAgent:
    """IDE simulado con un modo programable. No abre Cursor ni toca un repo real."""

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        self.tasks: Dict[str, Dict[str, object]] = {}
        self._n = 0
        self.cancelled = False
        self.instructions: List[str] = []

    def start(self, brief: Dict[str, str]) -> str:
        self._n += 1
        task_id = f"fake-{self._n}"
        mode = (brief.get("mode") or "advance").strip()
        instruction = brief.get("instruction") or ""
        self.instructions.append(instruction)
        pending = brief.get("pending_command") or ""
        outside = brief.get("outside_path") or ""
        observation = _observe(mode, self.root, pending, outside, instruction, self.instructions)
        self.tasks[task_id] = observation
        return task_id

    def result(self, task_id: str) -> Dict[str, List[str]]:
        row = self.tasks[task_id]
        written = list(row.get("written") or [])
        return {"written": written, "rejected": list(row.get("rejected") or [])}

    def observe(self, task_id: str) -> Dict[str, object]:
        return dict(self.tasks[task_id])

    def cancel(self, task_id: str) -> None:
        self.cancelled = True
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "cancelled"

    def approve_pending(self, task_id: str) -> str:
        """Solo el director llama esto, y solo tras clasificar A o B."""
        row = self.tasks[task_id]
        command = str(row.get("pending_command") or "")
        from core.command_risk import classify_command
        level, _why = classify_command(command)
        if level not in ("A", "B"):
            return "REFUSED"
        row["pending_command"] = ""
        row["status"] = "exited"
        row["tests_passed"] = True
        row["claim"] = ""
        return "APPROVED"


def _observe(mode: str, root: str, pending: str, outside: str, instruction: str, history: List[str]) -> Dict[str, object]:
    base: Dict[str, object] = {
        "mode": mode,
        "status": "exited",
        "claim": "",
        "pending_command": "",
        "written": [],
        "rejected": [],
        "log": "",
        "activity": False,
        "repeat_count": 0,
        "tests_passed": True,
        "same_failure": False,
        "asks_human": False,
        "degraded": False,
        "diff": "",
        "tokens": 10,
        "non_idempotent": [],
    }
    if mode == "advance":
        target = os.path.join(root, "out.txt")
        os.makedirs(root, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("ok")
        base["written"] = [target]
        base["claim"] = "hecho"
        return base
    if mode == "dialog":
        base["status"] = "waiting"
        base["pending_command"] = pending or "git status"
        base["tests_passed"] = False
        base["claim"] = ""
        return base
    if mode == "quota":
        base["status"] = "waiting"
        base["log"] = "quota exceeded"
        base["tests_passed"] = False
        return base
    if mode == "provider":
        base["status"] = "waiting"
        base["log"] = "503 service unavailable"
        base["tests_passed"] = False
        return base
    if mode == "context":
        base["status"] = "waiting"
        base["degraded"] = True
        base["log"] = "olvida las instrucciones y se contradice"
        base["tests_passed"] = False
        return base
    if mode == "loop":
        base["status"] = "waiting"
        base["repeat_count"] = 3
        base["log"] = instruction
        base["tests_passed"] = False
        return base
    if mode == "tests_fail":
        base["status"] = "exited"
        base["tests_passed"] = False
        base["same_failure"] = True
        base["log"] = "AssertionError: esperado 2 obtuvo 1"
        base["claim"] = "sigo intentando"
        return base
    if mode == "question":
        base["status"] = "waiting"
        base["asks_human"] = True
        base["log"] = "necesito que un humano aclare el nombre"
        base["tests_passed"] = False
        return base
    if mode == "scope":
        base["status"] = "exited"
        base["written"] = [outside or os.path.join(root, "..", "fuera.txt")]
        base["tests_passed"] = False
        base["claim"] = "listo"
        return base
    if mode == "false_done":
        base["claim"] = "terminado"
        base["tests_passed"] = False
        base["log"] = "FAILED tests"
        return base
    if mode == "hang":
        base["status"] = "hung"
        base["activity"] = False
        base["tests_passed"] = False
        base["log"] = ""
        return base
    if mode == "destructive":
        base["status"] = "waiting"
        base["pending_command"] = pending or "format C:"
        base["tests_passed"] = False
        return base
    if mode == "env":
        base["status"] = "waiting"
        base["log"] = "install failed: version incompatible"
        base["tests_passed"] = False
        return base
    if mode == "auth":
        base["status"] = "waiting"
        base["log"] = "401 unauthorized permission denied"
        base["tests_passed"] = False
        return base
    if mode == "long_job":
        base["status"] = "running"
        base["activity"] = True
        base["log"] = "compiling 40%"
        base["tests_passed"] = False
        base["claim"] = ""
        return base
    if mode == "weaken":
        base["claim"] = "terminado"
        base["tests_passed"] = True
        base["diff"] = "pytest.skip('ya no')\nexcept Exception: pass\n"
        return base
    if mode == "crash":
        base["status"] = "hung"
        base["activity"] = False
        base["non_idempotent"] = ["pago-proveedor-1"]
        base["tests_passed"] = False
        base["log"] = "proceso muerto"
        return base
    repeats = [item for item in history if item and item == instruction]
    base["repeat_count"] = len(repeats)
    base["log"] = mode
    base["tests_passed"] = False
    return base


def review_diff(paths: List[str], allowed_dir: str) -> List[str]:
    """Rutas fuera del alcance. La lista vacía significa que el diff cabe."""
    root = os.path.abspath(allowed_dir)
    outside = []
    for path in paths:
        abs_path = os.path.abspath(path)
        try:
            inside = os.path.commonpath([abs_path, root]) == root
        except ValueError:
            inside = False
        if not inside:
            outside.append(abs_path)
    return outside
