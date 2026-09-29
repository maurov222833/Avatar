"""F-21: requirements.txt must declare real runtime deps with pinned versions."""
from __future__ import annotations

import ast
import importlib
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"

# Packages the HTTP server / orchestrator / bridges import at runtime.
REQUIRED_RUNTIME = {
    "fastapi",
    "uvicorn",
    "python-multipart",
    "requests",
    "pydantic",
    "rich",
    "Pillow",
    "pyperclip",
    "playwright",
}

# Declared historically but never imported by Avatar code.
FORBIDDEN_UNUSED = {
    "google-generativeai",
    "prompt_toolkit",
    "prompt-toolkit",
    "colorama",
}

# Import name for each requirements name (when different).
IMPORT_NAME = {
    "python-multipart": "python_multipart",
    "Pillow": "PIL",
    "pyperclip": "pyperclip",
    "playwright": "playwright",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "requests": "requests",
    "pydantic": "pydantic",
    "rich": "rich",
}


def _parse_requirements(path: Path) -> dict[str, str]:
    """Return {normalized_name: version} for every pinned (==) line."""
    pinned: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)", line)
        if not m:
            raise AssertionError(
                f"every runtime dependency must be pinned with ==, got: {raw!r}"
            )
        pinned[m.group(1)] = m.group(2)
    return pinned


class TestF21Dependencies(unittest.TestCase):
    def test_requirements_file_exists(self):
        self.assertTrue(REQ.is_file(), "requirements.txt must exist at repo root")

    def test_runtime_packages_are_declared_and_pinned(self):
        pinned = _parse_requirements(REQ)
        names_lower = {n.lower(): n for n in pinned}
        for pkg in REQUIRED_RUNTIME:
            self.assertIn(
                pkg.lower(),
                names_lower,
                f"{pkg} must be declared in requirements.txt (F-21)",
            )

    def test_unused_declared_packages_are_gone(self):
        pinned = _parse_requirements(REQ)
        names_lower = {n.lower() for n in pinned}
        for pkg in FORBIDDEN_UNUSED:
            self.assertNotIn(
                pkg.lower(),
                names_lower,
                f"{pkg} is unused by Avatar code and must not be declared",
            )

    def test_declared_runtime_packages_import(self):
        pinned = _parse_requirements(REQ)
        for name in REQUIRED_RUNTIME:
            # Match case-insensitively to the pinned key.
            key = next(k for k in pinned if k.lower() == name.lower())
            mod_name = IMPORT_NAME[name]
            try:
                importlib.import_module(mod_name)
            except ModuleNotFoundError as exc:
                self.fail(f"{key}=={pinned[key]} declared but not importable: {exc}")

    def test_project_code_does_not_import_removed_sdk(self):
        """google-generativeai must stay unused: LLM talks HTTP via requests."""
        skip = {".git", "__pycache__", ".pytest_cache", "scratch", "tests", "b:"}
        hits = []
        for path in ROOT.rglob("*.py"):
            if skip.intersection(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("google.generativeai") or alias.name == "google":
                            # bare `google` alone is too broad; only flag generativeai
                            if "generativeai" in alias.name:
                                hits.append(f"{path}:{node.lineno}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if "generativeai" in node.module:
                        hits.append(f"{path}:{node.lineno}")
        self.assertEqual(hits, [], f"unexpected generativeai imports: {hits}")


if __name__ == "__main__":
    unittest.main()
