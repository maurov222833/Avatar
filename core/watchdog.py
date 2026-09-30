"""In-process mission watchdog (D-7 / Fase 3b).

Decision
--------
Use an **in-process watchdog** rather than the Windows Task Scheduler as the
primary supervisor. Reasons: it runs on the same shared orchestrator (F-16),
is testable on Linux CI, and never auto-approves EXEC / contaminated acts
(F-06 / F-18). Mauro can still wrap `Watchdog.run_forever` with the Task
Scheduler later if he wants boot-time start on his PC.

What one tick does
------------------
1. Report pending human approvals (never resolves them).
2. Inspect missions in IN_PROGRESS / PENDING.
3. Auto-resume only missions evaluated as SAFE_TO_RESUME when
   `watchdog.auto_resume_safe` is true (default). UNCERTAIN / FAILED are
   reported and left alone.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _wdlog(message: str, level: str = "INFO") -> None:
    try:
        from core.logging_util import log
        log(level, message, component="Watchdog")
    except Exception:
        pass


@dataclass
class WatchdogConfig:
    enabled: bool = True
    auto_resume_safe: bool = True
    interval_seconds: float = 60.0
    max_resumes_per_tick: int = 3

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "WatchdogConfig":
        raw = raw or {}
        return cls(
            enabled=bool(raw.get("enabled", True)),
            auto_resume_safe=bool(raw.get("auto_resume_safe", True)),
            interval_seconds=float(raw.get("interval_seconds", 60) or 60),
            max_resumes_per_tick=max(0, int(raw.get("max_resumes_per_tick", 3) or 0)),
        )


@dataclass
class WatchdogTickReport:
    pending_approvals: List[Dict[str, Any]] = field(default_factory=list)
    missions_inspected: List[Dict[str, Any]] = field(default_factory=list)
    resumed: List[Dict[str, Any]] = field(default_factory=list)
    skipped_uncertain: List[Dict[str, Any]] = field(default_factory=list)
    skipped_failed: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pending_approvals": self.pending_approvals,
            "pending_count": len(self.pending_approvals),
            "missions_inspected": self.missions_inspected,
            "resumed": self.resumed,
            "skipped_uncertain": self.skipped_uncertain,
            "skipped_failed": self.skipped_failed,
            "notes": self.notes,
        }


class Watchdog:
    """Single-process supervisor over approvals + safe mission resume."""

    def __init__(self, orchestrator, config: Optional[WatchdogConfig] = None):
        self.orchestrator = orchestrator
        if config is not None:
            self.config = config
        else:
            raw = {}
            try:
                raw = (orchestrator.config or {}).get("watchdog", {}) or {}
            except Exception:
                raw = {}
            self.config = WatchdogConfig.from_dict(raw)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def tick(self) -> WatchdogTickReport:
        report = WatchdogTickReport()
        from core.halt import missions_blocked
        if missions_blocked():
            report.notes.append("halt_active")
            return report
        if not self.config.enabled:
            report.notes.append("watchdog.disabled")
            return report

        cp = getattr(self.orchestrator, "chokepoint", None)
        if cp is not None:
            try:
                for row in cp.list_pending_approvals():
                    report.pending_approvals.append({
                        "approval_id": row.get("approval_id"),
                        "act_type": row.get("act_type"),
                        "reason": row.get("reason"),
                        "created_at": row.get("created_at"),
                    })
            except Exception as exc:
                report.notes.append(f"approvals_error:{type(exc).__name__}")

        resume_engine = getattr(self.orchestrator, "resume_engine", None)
        if resume_engine is None:
            report.notes.append("no_resume_engine")
            return report

        try:
            missions = resume_engine.inspect_active_missions()
        except Exception as exc:
            report.notes.append(f"inspect_error:{type(exc).__name__}")
            return report

        resumes_left = self.config.max_resumes_per_tick
        for mission in missions:
            mission_id = mission.get("mission_id") or ""
            status, task, message = resume_engine.evaluate_mission_for_resume(mission_id)
            entry = {
                "mission_id": mission_id,
                "evaluate_status": status,
                "message": message,
                "task_id": (task or {}).get("task_id") if task else None,
            }
            report.missions_inspected.append(entry)

            from core.resume_engine import MissionResumeStatus
            if status == MissionResumeStatus.ACTIVE_MISSION_UNCERTAIN:
                report.skipped_uncertain.append(entry)
                continue
            if status == MissionResumeStatus.ACTIVE_MISSION_FAILED:
                report.skipped_failed.append(entry)
                continue
            if status != MissionResumeStatus.ACTIVE_MISSION_SAFE_TO_RESUME:
                continue
            if not self.config.auto_resume_safe or resumes_left <= 0:
                continue
            try:
                result = self.orchestrator.resume_mission(mission_id)
            except Exception as exc:
                report.notes.append(f"resume_error:{mission_id}:{type(exc).__name__}")
                continue
            resumes_left -= 1
            report.resumed.append({
                "mission_id": mission_id,
                "result_status": result.get("status"),
                "message": result.get("message"),
            })

        return report

    def run_forever(self) -> None:
        """Blocking loop until stop(). Intended for a dedicated supervisor process."""
        while not self._stop.is_set():
            try:
                report = self.tick()
                _wdlog(
                    f"[Watchdog]: tick pendientes={report.to_dict()['pending_count']} "
                    f"reanudadas={len(report.resumed)} "
                    f"inciertas={len(report.skipped_uncertain)}"
                )
            except Exception as exc:
                _wdlog(f"[Watchdog ERROR]: {type(exc).__name__}: {exc}")
            self._stop.wait(max(1.0, float(self.config.interval_seconds)))

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self.run_forever, name="avatar-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
