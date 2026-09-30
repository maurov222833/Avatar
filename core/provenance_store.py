"""Procedencia de información externa (spec 003, U5).

El contenido externo es dato. Una instrucción dentro de una página no autoriza actos.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

STATES = ("RAW_EXTERNAL", "UNVERIFIED", "VALIDATED", "PROJECT_DECISION", "DEPRECATED")

_INJECTION = re.compile(
    r"(?i)(ignora las instrucciones|ignore (all|previous) instructions|"
    r"reveal (the )?secret|ejecuta este comando|you are now|"
    r"system prompt|olvida (las |tus )?reglas)"
)


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def detect_injection(text: str) -> Optional[str]:
    match = _INJECTION.search(text or "")
    return match.group(0) if match else None


def record_external(text: str, *, url: str, domain: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Añade una línea de procedencia. El texto largo se guarda recortado; el hash es del original."""
    import json
    import os
    destination = path or os.environ.get("AVATAR_PROVENANCE_PATH")
    if not destination:
        root = os.environ.get("AVATAR_HOME") or os.getcwd()
        destination = os.path.join(root, "memory", "provenance.jsonl")
    entry = {
        "url": url,
        "domain": domain,
        "state": "RAW_EXTERNAL",
        "content_hash": content_hash(text),
        "injection": detect_injection(text),
        "excerpt": (text or "")[:500],
    }
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


class ProvenanceStore:
    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []

    def add(self, text: str, *, url: str, domain: str, consulted_at: str,
            published_at: str = "", author: str = "", source_type: str = "tercero",
            mission_id: str = "", state: str = "RAW_EXTERNAL") -> Dict[str, Any]:
        if state not in STATES:
            state = "UNVERIFIED"
        injection = detect_injection(text)
        entry = {
            "url": url,
            "domain": domain,
            "consulted_at": consulted_at,
            "published_at": published_at,
            "author": author,
            "source_type": source_type,
            "state": state,
            "mission_id": mission_id,
            "content_hash": content_hash(text),
            "text": text,
            "injection": injection,
        }
        self.entries.append(entry)
        return entry

    def corroborate(self, claim_hash: str) -> str:
        """Dos copias del mismo texto cuentan como una fuente."""
        matches = [e for e in self.entries if e["content_hash"] == claim_hash and e["state"] != "DEPRECATED"]
        origins = {(e["domain"], e["author"]) for e in matches}
        if len(origins) >= 2 and any(e["source_type"] == "oficial" for e in matches):
            return "VALIDATED"
        if matches:
            return "UNVERIFIED"
        return "UNVERIFIED"

    def promote(self, content_hash_value: str, approved: bool) -> Optional[Dict[str, Any]]:
        for entry in self.entries:
            if entry["content_hash"] != content_hash_value:
                continue
            if entry["state"] != "VALIDATED" or not approved:
                return entry
            entry["state"] = "PROJECT_DECISION"
            return entry
        return None

    def deprecate(self, content_hash_value: str) -> None:
        for entry in self.entries:
            if entry["content_hash"] == content_hash_value:
                entry["state"] = "DEPRECATED"

    def current_facts(self) -> List[Dict[str, Any]]:
        return [e for e in self.entries if e["state"] == "PROJECT_DECISION"]
