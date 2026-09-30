"""Asistente personal (spec 003, U12), sin cuentas reales.

Correo: los borradores no se envían solos. OCR: confianza por campo.
Respaldos: una misión no los borra. Voz: el riesgo alto pide otro canal.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from core.provenance_store import detect_injection


class Mailbox:
    def __init__(self) -> None:
        self.drafts: List[Dict[str, str]] = []
        self.sent: List[Dict[str, str]] = []
        self.events: List[Dict[str, str]] = []

    def ingest(self, message: Dict[str, str]) -> Dict[str, Any]:
        injection = detect_injection(message.get("body") or "")
        return {
            "level": "A",
            "summary": (message.get("subject") or "")[:120],
            "injection": injection,
            "action_taken": None if not injection else "MARKED_UNTRUSTED",
        }

    def draft(self, to: str, subject: str, body: str) -> Dict[str, str]:
        item = {"to": to, "subject": subject, "body": body, "status": "DRAFT"}
        self.drafts.append(item)
        return item

    def send(self, draft: Dict[str, str], *, authorized: bool) -> str:
        if not authorized:
            return "HELD"
        if draft not in self.drafts:
            return "UNKNOWN_DRAFT"
        draft["status"] = "SENT"
        self.sent.append(draft)
        return "SENT"

    def add_event(self, start: str, end: str, title: str, *, invites_others: bool) -> str:
        if invites_others:
            self.events.append({"title": title, "status": "NEEDS_APPROVAL"})
            return "NEEDS_APPROVAL"
        self.events.append({"title": title, "start": start, "end": end, "status": "CREATED"})
        return "CREATED"


class JobScheduler:
    def __init__(self) -> None:
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.suspended = False

    def add(self, job_id: str, *, expires_at: str, level: str) -> None:
        self.jobs[job_id] = {"expires_at": expires_at, "level": level, "runs": 0}

    def due(self, job_id: str, now: str) -> str:
        if self.suspended:
            return "SUSPENDED"
        job = self.jobs.get(job_id)
        if not job:
            return "MISSING"
        if job["expires_at"] < now:
            return "EXPIRED"
        if job["level"] not in ("A", "B"):
            return "QUEUED"
        job["runs"] += 1
        return "RAN"

    def kill_switch(self) -> None:
        self.suspended = True


def ocr_fields(raw_text: str, confidence: float) -> Dict[str, Any]:
    """Un campo con confianza baja no entra solo a un estado financiero."""
    amount = None
    for token in raw_text.replace(",", "").split():
        try:
            amount = float(token)
        except ValueError:
            continue
    trusted = confidence >= 0.8 and amount is not None
    return {
        "amount": amount if trusted else None,
        "raw_amount_marked": None if trusted else amount,
        "confidence": confidence,
        "needs_review": not trusted,
    }


def backup_tree(source: str, dest_root: str) -> Dict[str, Any]:
    os.makedirs(dest_root, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = os.path.join(dest_root, stamp)
    shutil.copytree(source, dest)
    digest = hashlib.sha256()
    count = 0
    for root, _, files in os.walk(dest):
        for name in sorted(files):
            count += 1
            with open(os.path.join(root, name), "rb") as handle:
                digest.update(handle.read())
    manifest = os.path.join(dest, ".manifest.sha256")
    with open(manifest, "w", encoding="utf-8") as handle:
        handle.write(digest.hexdigest() + "\n")
    return {"path": dest, "files": count, "sha256": digest.hexdigest()}


def verify_backup(backup_path: str) -> bool:
    manifest = os.path.join(backup_path, ".manifest.sha256")
    try:
        with open(manifest, "r", encoding="utf-8") as handle:
            expected = handle.read().strip()
    except OSError:
        return False
    digest = hashlib.sha256()
    for root, _, files in os.walk(backup_path):
        for name in sorted(files):
            if name == ".manifest.sha256":
                continue
            with open(os.path.join(root, name), "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest() == expected


def voice_order(transcript: str, confidence: float, level: str) -> Dict[str, str]:
    if confidence < 0.7:
        return {"disposition": "REPEAT", "transcript": transcript}
    if level in ("C", "D"):
        return {"disposition": "CONFIRM_OTHER_CHANNEL", "transcript": transcript}
    return {"disposition": "EXECUTE", "transcript": transcript}
