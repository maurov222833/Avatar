"""Director de desarrollo (spec 003, U18), solo con IDE simulado.

No lanza Cursor, no fusiona a la rama principal y no debilita el chokepoint.
La frase del IDE no es evidencia. El estado sale de lo observado.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core.command_risk import classify_command
from core.external_dev import review_diff

MISSION_STATES = (
    "PLANNING",
    "DISPATCHED",
    "IN_PROGRESS",
    "STALLED_RECOVERING",
    "VERIFYING",
    "WAITING_FOR_MAURO",
    "BLOCKED",
    "COMPLETED_VERIFIED",
    "COMPLETED_WITH_LIMITATIONS",
    "FAILED",
    "ABORTED",
)

_D3 = {
    "governance",
    "privilege",
    "secret",
    "force_push",
    "deploy",
    "critical_component",
}
_CHEATS = (
    "pytest.skip",
    "pytest.mark.skip",
    "unittest.skip",
    "skiptest",
    "except exception: pass",
    "except: pass",
)
_SECRET_WORDS = ("api_key", "api key", "password=", "begin private", "bearer ")
_IRREVERSIBLE = ("api publica", "borrar", "seguridad", "merge", "deploy", "secreto", "force push")
_HARD_RESTRICTIONS = (
    "sin merge a main",
    "sin secretos en el briefing",
    "sin debilitar pruebas",
    "PROHIBITED no se aprueba",
)
_RESUMABLE = {
    "PLANNING",
    "DISPATCHED",
    "IN_PROGRESS",
    "STALLED_RECOVERING",
    "VERIFYING",
    "WAITING_FOR_MAURO",
    "BLOCKED",
}
# El director puede proponer un parche. No lo acepta si toca estos módulos.
_CRITICAL_FILES = frozenset({
    "act_chokepoint.py",
    "halt.py",
    "path_guard.py",
    "grants.py",
    "command_risk.py",
    "closed_gates.py",
    "containment.py",
    "state_db.py",
    "redaction.py",
    "remote_guard.py",
    "telegram_daemon.py",
    "model_inventory.py",
    "llm_provider.py",
    "provider_usage.py",
})


def _fold(text: str) -> str:
    return (text or "").casefold()


class DevEnvelope:
    def __init__(
        self,
        *,
        max_wps: int = 5,
        max_stalls: int = 3,
        token_budget: int = 1000,
        allow_merge: bool = False,
    ) -> None:
        self.max_wps = max_wps
        self.max_stalls = max_stalls
        self.token_budget = token_budget
        self.allow_merge = allow_merge
        self.spent_tokens = 0
        self.consecutive_stalls = 0
        self.security_failures = 0
        self.destructive_attempts = 0
        self.accepted = 0

    def stop_reason(self) -> Optional[str]:
        if self.consecutive_stalls >= self.max_stalls:
            return "STALLS_WITHOUT_PROGRESS"
        if self.spent_tokens > self.token_budget:
            return "BUDGET_EXHAUSTED"
        if self.security_failures >= 2:
            return "SECURITY_FAILURES"
        if self.destructive_attempts >= 2:
            return "DESTRUCTIVE_REPEATED"
        if self.accepted >= self.max_wps:
            return "WP_CAP"
        return None


class StateKeeper:
    def __init__(self, root: str) -> None:
        self.root = root
        self.path = os.path.join(root, "docs", "brain", "STATE.md")

    def write(self, mission: Dict[str, Any]) -> str:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        lines = [
            "# Estado",
            "",
            f"Estado de la misión: {mission.get('state')}",
            "",
            "## Decisiones",
        ]
        for row in mission.get("decisions") or []:
            lines.append(f"- {row.get('id')} {row.get('level')} {row.get('choice')} ({row.get('status')})")
        lines.append("")
        lines.append("## Supuestos")
        for row in mission.get("assumptions") or []:
            lines.append(f"- {row}")
        lines.append("")
        lines.append("## Preguntas")
        for row in mission.get("questions") or []:
            lines.append(f"- {row.get('text')} default={row.get('default')}")
        text = "\n".join(lines) + "\n"
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)
        ledger = os.path.join(self.root, "docs", "brain", "ledger.json")
        with open(ledger, "w", encoding="utf-8") as handle:
            json.dump(mission, handle, ensure_ascii=False, indent=2)
        return self.path


def build_briefing(wp: Dict[str, Any]) -> str:
    acceptance = list(wp.get("acceptance") or [])
    if not acceptance:
        raise ValueError("WP_SIN_CRITERIOS")
    supplied = " ".join([
        str(wp.get("title") or ""),
        str(wp.get("goal") or ""),
        str(wp.get("project") or ""),
        " ".join(str(item) for item in (wp.get("acceptance") or [])),
        " ".join(str(item) for item in (wp.get("allowed") or [])),
        " ".join(str(item) for item in (wp.get("read") or [])),
    ])
    if any(mark in _fold(supplied) for mark in _SECRET_WORDS):
        raise ValueError("BRIEFING_CON_SECRETO")
    text = "\n".join([
        f"# {wp.get('id')} — {wp.get('title')}",
        "",
        "## Contexto (leer antes de empezar)",
        f"- Proyecto: {wp.get('project') or 'piloto'}",
        f"- Lee solamente: {', '.join(wp.get('read') or [])}",
        "",
        "## Objetivo",
        str(wp.get("goal") or ""),
        "",
        "## Alcance",
        f"- Puedes modificar: {', '.join(wp.get('allowed') or [])}",
        "- NO modifiques: "
        + ", ".join(list(wp.get("forbidden") or []) + sorted(_CRITICAL_FILES)),
        "",
        "## Restricciones",
        "- Seguridad: sin secretos, sin rutas de sistema, sin comandos prohibidos",
        "",
        "## Criterios de aceptación",
        *[f"{index}. {item}" for index, item in enumerate(acceptance, 1)],
        "",
        "## Verificación (ejecútala tú antes de entregar)",
        *[f"- {item}" for item in (wp.get("verify") or ["pytest"])],
        "",
        "## Si te falta información",
        "- Elige la opción más reversible, anótala en tu resumen como SUPUESTO y continúa.",
        "- Detente y pregunta SOLO si: cambia una API pública, borra datos o toca seguridad.",
        "",
        "## Prohibido",
        "- Desactivar, omitir o debilitar pruebas.",
        "- Escribir resultados esperados a mano para pasar una prueba.",
        "- Modificar archivos fuera del alcance.",
        "",
        "## Entrega",
        f"- Commit en la rama {wp.get('branch') or 'wp'}",
        "",
    ])
    return text


def detect_stall(obs: Dict[str, Any]) -> Optional[str]:
    """Clasifica una observación. S14 es trabajo largo, no una caída."""
    pending = str(obs.get("pending_command") or "")
    log = _fold(str(obs.get("log") or ""))
    if pending:
        level, _why = classify_command(pending)
        if level == "PROHIBITED":
            return "S11"
        return "S1"
    written = [str(path) for path in (obs.get("written") or [])]
    allowed = str(obs.get("allowed_dir") or "")
    if allowed and review_diff(written, allowed):
        return "S8"
    if obs.get("same_failure") and obs.get("tests_passed") is False:
        return "S6"
    if obs.get("claim") and obs.get("tests_passed") is False:
        return "S9"
    if int(obs.get("repeat_count") or 0) >= 3:
        return "S5"
    if "quota" in log or "cuota" in log:
        return "S2"
    if "401" in log or "unauthorized" in log or "permission denied" in log:
        return "S13"
    if "503" in log or "5xx" in log:
        return "S3"
    if "install failed" in log or "version incompatible" in log:
        return "S12"
    if obs.get("degraded"):
        return "S4"
    if obs.get("asks_human"):
        return "S7"
    if obs.get("status") == "hung" and not obs.get("activity"):
        return "S10"
    if obs.get("status") == "running" and obs.get("activity"):
        return "S14"
    return None


def find_cheats(diff: str) -> List[str]:
    folded = _fold(diff)
    return [mark for mark in _CHEATS if mark in folded]


def _has_acceptance(item: Dict[str, Any]) -> bool:
    raw = item.get("acceptance")
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, (list, tuple)):
        return any(str(piece).strip() for piece in raw)
    return False


def plan_packages(items: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """PB-02. Un paquete sin criterios no sale. No se inventan criterios."""
    ready: List[Dict[str, Any]] = []
    held: List[str] = []
    for item in items or []:
        if _has_acceptance(item):
            ready.append(item)
        else:
            held.append(str(item.get("id") or ""))
    return {
        "packages": ready,
        "held": held,
        "status": "PLANNED" if ready else "NO_SAFE_WORK",
    }


def index_files(root: str) -> set:
    """Archivos ya presentes bajo la carpeta. No sigue enlaces."""
    base = os.path.realpath(root)
    found = set()
    if not os.path.isdir(base):
        return found
    for dirpath, _dirnames, filenames in os.walk(base, followlinks=False):
        for name in filenames:
            path = os.path.realpath(os.path.join(dirpath, name))
            try:
                inside = os.path.commonpath([path, base]) == base
            except ValueError:
                inside = False
            if inside:
                found.add(path)
    return found


def revert_new_files(root: str, before: set, written: List[str]) -> Dict[str, List[str]]:
    """PB-10. Borra solo archivos nuevos dentro del alcance. No llama a git."""
    base = os.path.realpath(root)
    removed: List[str] = []
    left: List[str] = []
    for path in written:
        real = os.path.realpath(path)
        try:
            inside = os.path.commonpath([real, base]) == base
        except ValueError:
            inside = False
        if not inside or real in before or not os.path.isfile(real):
            left.append(real)
            continue
        os.remove(real)
        removed.append(real)
    return {"removed": removed, "left_in_place": left}


def critical_write(written: List[str]) -> Optional[str]:
    """Un parche sobre autoridad, parada, secretos o gasto no se acepta."""
    for path in written:
        if os.path.basename(str(path)).lower() in _CRITICAL_FILES:
            return "CRITICAL"
    return None


def lint_written_python(written: List[str], allowed_dir: str) -> Optional[str]:
    """Sintaxis de los .py escritos dentro del alcance. No ejecuta el archivo."""
    root = os.path.realpath(allowed_dir)
    for path in written:
        if not str(path).lower().endswith(".py"):
            continue
        real = os.path.realpath(path)
        try:
            inside = os.path.commonpath([real, root]) == root
        except ValueError:
            inside = False
        if not inside:
            continue
        try:
            with open(real, "r", encoding="utf-8") as handle:
                source = handle.read()
            compile(source, real, "exec")
        except (OSError, SyntaxError, UnicodeError):
            return "LINT"
    return None


def license_conflict(diff: str, rejected: List[str]) -> Optional[str]:
    """Solo compara con las licencias que el paquete ya rechaza. No elige una política."""
    folded = _fold(diff)
    for name in rejected or []:
        token = _fold(str(name)).strip()
        if token and token in folded:
            return "LICENSE"
    return None


def verify_package(wp: Dict[str, Any], obs: Dict[str, Any], allowed_dir: str) -> List[str]:
    """Puertas que no creen la frase del IDE. Lista vacía: aceptable."""
    reasons: List[str] = []
    written = [str(path) for path in (obs.get("written") or [])]
    outside = review_diff(written, allowed_dir)
    if outside:
        reasons.append("SCOPE")
    cheats = find_cheats(str(obs.get("diff") or ""))
    if cheats:
        reasons.append("CHEAT")
    if wp.get("verify") and obs.get("tests_passed") is not True:
        reasons.append("TESTS")
    if obs.get("claim") and obs.get("tests_passed") is not True:
        reasons.append("FALSE_DONE")
    folded = _fold(str(obs.get("diff") or ""))
    if "api_key=" in folded or "begin private" in folded:
        reasons.append("SECRET")
    if critical_write(written) == "CRITICAL":
        reasons.append("CRITICAL")
    if lint_written_python(written, allowed_dir) == "LINT":
        reasons.append("LINT")
    if license_conflict(str(obs.get("diff") or ""), list(wp.get("rejected_licenses") or [])) == "LICENSE":
        reasons.append("LICENSE")
    return reasons


def decide(level: str, choice: str, *, reason: str, reversible: bool) -> Dict[str, Any]:
    kind = (level or "").upper()
    if kind == "D3" or choice in _D3:
        return {
            "level": "D3",
            "choice": choice,
            "status": "BLOCKED",
            "reason": reason,
            "reversible": False,
        }
    if kind == "D2":
        return {
            "level": "D2",
            "choice": choice,
            "status": "QUEUED",
            "reason": reason,
            "reversible": reversible,
            "default": "no ejecutar",
        }
    status = "DECIDED"
    return {
        "level": kind or "D0",
        "choice": choice,
        "status": status,
        "reason": reason,
        "reversible": reversible,
    }


def request_merge(target: str, envelope: DevEnvelope) -> Dict[str, Any]:
    branch = (target or "").strip().lower()
    if branch in ("main", "master") and not envelope.allow_merge:
        return decide("D2", "merge", reason="sin delegacion de Mauro", reversible=True)
    return decide("D0", "merge-rama-de-trabajo", reason="rama de integracion", reversible=True)


def resolve_gap(text: str) -> Dict[str, Any]:
    folded = _fold(text)
    if any(mark in folded for mark in _IRREVERSIBLE):
        return {
            "continued": False,
            "assumption": None,
            "question": text,
            "default": "esperar",
        }
    return {
        "continued": True,
        "assumption": f"SUPUESTO reversible: {text}",
        "question": text,
        "default": "opcion reversible",
    }


def consider_untrusted(text: str, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Un comentario, un README o un log es dato. No cambia decisiones."""
    _ = text
    return list(decisions)


def intervention(stall: str, tried: List[str]) -> Dict[str, Any]:
    """Sube un escalón y no repite una orden ya fallida."""
    floor = 5 if stall == "S5" else 1
    if stall == "S6":
        floor = max(floor, 3)
    if stall == "S14":
        return {"step": 1, "text": "observar: hay actividad de compilacion", "stall": stall}
    step = max(floor, min(8, 1 + len(tried)))
    texts = {
        1: "observar",
        2: f"continua WP sin cambiar el plan. intento {len(tried) + 1}",
        3: "reencuadro: el objetivo no cambio. no debilites pruebas",
        4: "divido el trabajo. ahora solo la parte 1",
        5: f"el enfoque anterior fallo. no lo repitas. estrategia {len(tried) + 1}",
        6: "revierte al ultimo punto bueno y reinicia el paquete",
        7: "segunda opinion del revisor",
        8: "pausa y escala a Mauro",
    }
    text = texts[step]
    while text in tried and step < 8:
        step += 1
        text = texts[step]
    return {"step": step, "text": text, "stall": stall}


def recover_crash(done_non_idempotent: List[str], pending: List[str]) -> List[str]:
    """No repite un pago u otra acción ya hecha."""
    done = set(done_non_idempotent)
    return [item for item in pending if item not in done]


def calibration_stage(stats: Dict[str, Any], *, charter_approved: bool) -> Dict[str, Any]:
    """La carta no está aprobada: la etapa se queda en E0.

    Los números sugeridos están en U18_0. No definen E1, E2 ni E3, así que
    cumplirlos no sube de etapa.
    """
    if not charter_approved:
        return {"stage": "E0", "reason": "carta_sin_aprobar", "missing": []}
    missing: List[str] = []
    if int(stats.get("decisions") or 0) < 20:
        missing.append("decisions")
    accuracy = stats.get("accuracy")
    if not isinstance(accuracy, (int, float)) or float(accuracy) < 0.85:
        missing.append("accuracy")
    if int(stats.get("packages") or 0) < 10:
        missing.append("packages")
    if int(stats.get("stalls_recovered") or 0) < 3:
        missing.append("stalls_recovered")
    if int(stats.get("absences") or 0) < 5:
        missing.append("absences")
    if missing:
        return {"stage": "E0", "reason": "umbral_sugerido_incompleto", "missing": missing}
    return {"stage": "E0", "reason": "umbral_sugerido_sin_escala", "missing": []}


def second_opinion(*, per_session: int, currency: str) -> Dict[str, Any]:
    """PB-08. No llama a un modelo. Sin tope numérico no hay dictamen."""
    if not isinstance(per_session, int) or per_session <= 0 or currency in ("", "TODO_MAURO"):
        return {"status": "NO_BUDGET", "called": False}
    return {"status": "NOT_SENT", "called": False, "reason": "sin revisor local"}


def propose_lesson(text: str) -> Dict[str, Any]:
    return {"text": text, "status": "PROPOSED", "approved_by": ""}


def accept_lesson(lesson: Dict[str, Any], approved_by: str) -> Dict[str, Any]:
    row = dict(lesson)
    if approved_by != "Mauro":
        row["status"] = "PROPOSED"
        return row
    row["status"] = "APPROVED"
    row["approved_by"] = approved_by
    return row


def handover(mission: Dict[str, Any]) -> Dict[str, Any]:
    restrictions = list(mission.get("restrictions") or [])
    for item in _HARD_RESTRICTIONS:
        if item not in restrictions:
            restrictions.append(item)
    return {
        "state": mission.get("state"),
        "restrictions": restrictions,
        "decisions": list(mission.get("decisions") or []),
        "assumptions": list(mission.get("assumptions") or []),
        "next": mission.get("next") or "",
    }


def resume_from_handover(director: "DevDirector", packet: Dict[str, Any]) -> str:
    """PB-09. Un paquete que dice terminado no se acepta como estado."""
    restored = list(packet.get("restrictions") or [])
    for item in _HARD_RESTRICTIONS:
        if item not in restored:
            restored.append(item)
    director.mission["restrictions"] = restored
    director.mission["decisions"] = list(packet.get("decisions") or [])
    director.mission["assumptions"] = list(packet.get("assumptions") or [])
    director.mission["next"] = str(packet.get("next") or "")
    state = str(packet.get("state") or "")
    director.mission["state"] = state if state in _RESUMABLE else "PLANNING"
    director.mission["playbook"] = "PB-09"
    director.keeper.write(director.mission)
    return director.mission["state"]


def propose_case(text: str, verdict: str = "") -> Dict[str, Any]:
    """Un caso sin veredicto de Mauro no es una regla."""
    return {"text": text, "verdict": verdict, "status": "PROPOSED", "approved_by": "", "usable": False}


def accept_case(case: Dict[str, Any], approved_by: str) -> Dict[str, Any]:
    row = dict(case)
    if approved_by != "Mauro" or not str(row.get("verdict") or "").strip():
        row["status"] = "PROPOSED"
        row["approved_by"] = ""
        row["usable"] = False
        return row
    row["status"] = "APPROVED"
    row["approved_by"] = "Mauro"
    row["usable"] = True
    return row


def rule_from_case(case: Dict[str, Any]) -> Optional[str]:
    if case.get("usable") is True and case.get("approved_by") == "Mauro" and str(case.get("verdict") or "").strip():
        return str(case["verdict"])
    return None


_STALL_PLAYBOOK = {
    "S1": "PB-05",
    "S2": "PB-09",
    "S5": "PB-07",
    "S6": "PB-06",
    "S7": "PB-11",
    "S8": "PB-10",
    "S9": "PB-06",
    "S10": "PB-10",
    "S11": "PB-05",
    "S14": "PB-05",
}


def playbook_for(stall: str) -> str:
    return _STALL_PLAYBOOK.get(stall, "PB-05")


def load_playbook(path: str, pb_id: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    marker = f"## {pb_id} "
    start = text.find(marker)
    if start < 0:
        raise KeyError(pb_id)
    rest = text[start + len(marker):]
    nxt = rest.find("\n## ")
    body = rest if nxt < 0 else rest[:nxt]
    return f"## {pb_id} {body}".strip()


def render_report(mission: Dict[str, Any]) -> str:
    cost = mission.get("cost")
    cost_line = "UNKNOWN" if cost is None else str(cost)
    lines = [
        f"INFORME DE DIRECCIÓN DE DESARROLLO — {mission.get('project') or 'piloto'}",
        f"Estado de la misión: {mission.get('state')}",
        "1. Resumen",
        str(mission.get("summary") or ""),
        "2. Trabajo aceptado",
        ", ".join(mission.get("accepted") or []) or "(ninguno)",
        "4. Decisiones",
        "; ".join(f"{row.get('id')} {row.get('level')} {row.get('status')}" for row in mission.get("decisions") or []) or "(ninguna)",
        "5. Supuestos",
        "; ".join(mission.get("assumptions") or []) or "(ninguno)",
        "6. Preguntas",
        "; ".join(row.get("text", "") for row in mission.get("questions") or []) or "(ninguna)",
        "7. Detenciones",
        ", ".join(mission.get("stalls") or []) or "(ninguna)",
        f"8. Costo {cost_line}",
        "9. Riesgos: no se comprobó un IDE real ni el PC de Mauro",
    ]
    return "\n".join(lines)


class DevDirector:
    def __init__(self, agent: Any, root: str, envelope: Optional[DevEnvelope] = None) -> None:
        self.agent = agent
        self.root = root
        self.envelope = envelope or DevEnvelope()
        self.keeper = StateKeeper(root)
        self.mission: Dict[str, Any] = {
            "project": "piloto",
            "state": "PLANNING",
            "decisions": [],
            "assumptions": [],
            "questions": [],
            "stalls": [],
            "accepted": [],
            "restrictions": list(_HARD_RESTRICTIONS),
            "tried": [],
            "cost": 0,
            "summary": "",
            "next": "",
            "non_idempotent_done": [],
        }
        self._n = 0

    def _record_decision(self, row: Dict[str, Any]) -> Dict[str, Any]:
        self._n += 1
        row = dict(row)
        row["id"] = f"DEC-{self._n}"
        self.mission["decisions"].append(row)
        return row

    def begin(self, objective: str, *, digest_present: bool) -> str:
        """PB-01. Anota el objetivo y no despacha."""
        self.mission["state"] = "PLANNING"
        self.mission["playbook"] = "PB-01"
        self.mission["summary"] = objective
        self.mission["digest_ok"] = bool(digest_present)
        if not digest_present:
            self.mission["questions"].append({
                "text": "digest no verificado",
                "default": "no despachar",
            })
        self.keeper.write(self.mission)
        return "PLANNING"

    def run_next(self, items: Optional[List[Dict[str, Any]]], brief: Optional[Dict[str, str]] = None) -> str:
        """Un paquete por llamada. El servidor no llama esto solo."""
        if not self.mission.get("digest_ok"):
            if self.mission.get("playbook") != "PB-01":
                self.mission["state"] = "PLANNING"
                self.keeper.write(self.mission)
                return "PB01_PENDIENTE"
            self.keeper.write(self.mission)
            return "DIGEST_NO_VERIFICADO"
        planned = plan_packages(items)
        accepted = {str(item) for item in (self.mission.get("accepted") or [])}
        packages = [
            item for item in planned["packages"]
            if str(item.get("id") or "") not in accepted
        ]
        self.mission["held"] = planned["held"]
        if not packages:
            self.mission["playbook"] = "PB-12"
            self.mission["remaining"] = []
            if self.mission.get("accepted") and planned["held"]:
                self.mission["state"] = "COMPLETED_WITH_LIMITATIONS"
                self.mission["summary"] = "paquetes sin criterios siguen en espera"
            elif self.mission.get("accepted"):
                self.mission["state"] = "COMPLETED_VERIFIED"
                self.mission["summary"] = "no quedan paquetes"
            else:
                self.mission["state"] = "BLOCKED"
                self.mission["summary"] = "NO_SAFE_WORK"
                self.mission["next"] = "esperar"
            self.mission["report"] = render_report(self.mission)
            self.keeper.write(self.mission)
            if self.mission["state"] == "BLOCKED":
                return "NO_SAFE_WORK"
            return self.mission["state"]
        self.mission["remaining"] = [str(item.get("id") or "") for item in packages[1:]]
        self.mission["playbook"] = "PB-04"
        return self.tick(packages[0], brief)

    def tick(self, wp: Optional[Dict[str, Any]], brief: Optional[Dict[str, str]] = None) -> str:
        from core.halt import current_block_reason

        reason = current_block_reason()
        if reason:
            if self.mission.get("task_id"):
                self.agent.cancel(self.mission["task_id"])
            self.mission["state"] = "ABORTED"
            self.mission["summary"] = reason
            self.keeper.write(self.mission)
            return reason
        stop = self.envelope.stop_reason()
        if stop:
            self.mission["state"] = "WAITING_FOR_MAURO"
            self.mission["summary"] = stop
            self.keeper.write(self.mission)
            return stop
        if not wp:
            self.mission["state"] = "BLOCKED"
            self.mission["summary"] = "NO_SAFE_WORK"
            self.mission["next"] = "esperar"
            self.keeper.write(self.mission)
            return "NO_SAFE_WORK"
        if not wp.get("acceptance"):
            self.mission["state"] = "BLOCKED"
            self.keeper.write(self.mission)
            return "WP_SIN_CRITERIOS"
        briefing = build_briefing(wp)
        payload = dict(brief or {})
        payload["instruction"] = briefing
        payload["allowed_dir"] = payload.get("allowed_dir") or self.root
        self._before = index_files(payload["allowed_dir"])
        task_id = self.agent.start(payload)
        self.mission["task_id"] = task_id
        self.mission["state"] = "DISPATCHED"
        obs = self.agent.observe(task_id)
        obs["allowed_dir"] = payload["allowed_dir"]
        if payload.get("extra_spend"):
            obs["extra_spend"] = True
        self.envelope.spent_tokens += int(obs.get("tokens") or 0)
        self.mission["cost"] = self.envelope.spent_tokens
        stall = detect_stall(obs)
        if stall:
            return self._on_stall(stall, obs, wp, payload["allowed_dir"])
        problems = verify_package(wp, obs, payload["allowed_dir"])
        if problems:
            self.envelope.consecutive_stalls += 1
            if "CHEAT" in problems or "FALSE_DONE" in problems:
                self.envelope.security_failures += 1
            self.mission["state"] = "VERIFYING"
            self.mission["stalls"].append("REJECTED:" + ",".join(problems))
            self.keeper.write(self.mission)
            return "REJECTED:" + ",".join(problems)
        self.envelope.consecutive_stalls = 0
        self.envelope.accepted += 1
        self.mission["accepted"].append(wp.get("id"))
        self.mission["state"] = "COMPLETED_VERIFIED"
        self.mission["summary"] = f"aceptado {wp.get('id')} con pruebas observadas"
        self.keeper.write(self.mission)
        return "ACCEPTED"

    def _on_stall(self, stall: str, obs: Dict[str, Any], wp: Dict[str, Any], allowed_dir: str) -> str:
        self.mission["stalls"].append(stall)
        self.mission["playbook"] = playbook_for(stall)
        self.mission["state"] = "STALLED_RECOVERING"
        if stall == "S14":
            self.envelope.consecutive_stalls = 0
            self.mission["state"] = "IN_PROGRESS"
            self.mission["summary"] = "compilacion en curso"
            self.keeper.write(self.mission)
            return "S14_WAIT"
        self.envelope.consecutive_stalls += 1
        if stall == "S1":
            return self._dialog(obs)
        if stall == "S11":
            self.envelope.destructive_attempts += 1
            self.envelope.security_failures += 1
            self.mission["summary"] = "comando destructivo no aprobado"
            move = intervention("S11", self.mission["tried"])
            self.mission["tried"].append(move["text"])
            self.keeper.write(self.mission)
            return "S11_BLOCKED"
        if stall == "S2":
            if obs.get("extra_spend"):
                self.mission["questions"].append({
                    "text": "la alternativa gasta de mas",
                    "default": "esperar",
                })
                self.mission["state"] = "WAITING_FOR_MAURO"
                self.keeper.write(self.mission)
                return "S2_WAIT"
            self.mission["summary"] = "estado guardado; alternativa autorizada"
            self.mission["handover"] = handover(self.mission)
            self.mission["playbook"] = "PB-09"
            self.keeper.write(self.mission)
            return "S2_SWITCH"
        if stall == "S5":
            move = intervention("S5", self.mission["tried"])
            if move["text"] in self.mission["tried"]:
                move = intervention("S5", self.mission["tried"] + [move["text"]])
            self.mission["tried"].append(move["text"])
            self.mission["summary"] = move["text"]
            self.keeper.write(self.mission)
            return f"S5_STEP_{move['step']}"
        if stall == "S6":
            move = intervention("S6", self.mission["tried"])
            self.mission["tried"].append(move["text"])
            self.keeper.write(self.mission)
            return "S6_NO_WEAKEN"
        if stall == "S8":
            report = revert_new_files(
                allowed_dir,
                getattr(self, "_before", set()),
                [str(path) for path in (obs.get("written") or [])],
            )
            self.mission["revert"] = report
            self.mission["playbook"] = "PB-10"
            self.keeper.write(self.mission)
            return "S8_REVERT"
        if stall == "S9":
            self.envelope.security_failures += 1
            self.keeper.write(self.mission)
            return "S9_REJECTED"
        if stall == "S10":
            pending = [str(item) for item in (obs.get("non_idempotent") or [])]
            already = list(self.mission["non_idempotent_done"])
            done_now = already + [item for item in pending if item not in already]
            repeat = recover_crash(done_now, pending)
            self.mission["non_idempotent_done"] = done_now
            self.mission["summary"] = "no se repite " + ",".join(pending)
            self.mission["next"] = ",".join(repeat)
            self.keeper.write(self.mission)
            return "S10_RECOVERED"
        if stall == "S13":
            self.mission["questions"].append({"text": obs.get("log") or "credencial", "default": "esperar"})
            self.mission["state"] = "WAITING_FOR_MAURO"
            self.keeper.write(self.mission)
            return "S13_QUEUE"
        if stall == "S7":
            gap = resolve_gap(str(obs.get("log") or "falta un dato"))
            if gap["assumption"]:
                self.mission["assumptions"].append(gap["assumption"])
            self.mission["questions"].append({"text": gap["question"], "default": gap["default"]})
            self.mission["state"] = "IN_PROGRESS" if gap["continued"] else "WAITING_FOR_MAURO"
            self.keeper.write(self.mission)
            return "S7_CONTINUE" if gap["continued"] else "S7_WAIT"
        move = intervention(stall, self.mission["tried"])
        self.mission["tried"].append(move["text"])
        self.keeper.write(self.mission)
        return f"{stall}_STEP_{move['step']}"

    def _dialog(self, obs: Dict[str, Any]) -> str:
        command = str(obs.get("pending_command") or "")
        level, why = classify_command(command)
        if level in ("A", "B"):
            verdict = self.agent.approve_pending(self.mission["task_id"])
            self._record_decision(decide("D0", command, reason=why, reversible=True))
            self.keeper.write(self.mission)
            return "S1_APPROVED" if verdict == "APPROVED" else "S1_REFUSED"
        self.mission["questions"].append({
            "text": f"{command} es nivel {level}",
            "default": "no aprobar",
        })
        self._record_decision(decide("D2", command, reason=why, reversible=True))
        self.mission["state"] = "WAITING_FOR_MAURO"
        self.keeper.write(self.mission)
        return "S1_QUEUED"

    def contain(self, chokepoint: Any, command: str) -> str:
        result = chokepoint.perform("COMMAND", {"command": command})
        self.envelope.destructive_attempts += 1
        self.mission["stalls"].append("S11")
        move = intervention("S11", self.mission["tried"])
        self.mission["tried"].append(move["text"])
        self.mission["summary"] = str(result)
        self.keeper.write(self.mission)
        return str(result)
