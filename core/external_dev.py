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
