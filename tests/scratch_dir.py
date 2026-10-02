"""Carpeta de trabajo de las pruebas, dentro del repo.

El temporal del sistema en Windows cae bajo AppData, y path_guard lo niega.
Esta carpeta no es Temp y git la ignora. AppData sigue prohibido.
"""
from __future__ import annotations

import os
import tempfile


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def work_dir(prefix: str = "work_") -> str:
    root = os.path.join(repo_root(), ".test_scratch")
    os.makedirs(root, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=root)
