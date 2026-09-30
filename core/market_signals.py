"""Señales de mercado (spec 003, U16). Avatar no opera ni retira.

Una clave con permiso de trading se informa. No se guarda.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

TRADE_ENDPOINTS = ("/order", "/orders", "/withdraw", "/transfer", "/trade")
REQUIRED_SIGNAL_FIELDS = (
    "asset", "market", "as_of", "valid_until", "thesis", "horizon",
    "entry", "target", "invalidation", "risk_reward", "confidence",
    "counter_scenario", "unknowns", "warning",
)
WARNING = (
    "Apoyo de análisis, no asesoría financiera. Se puede perder dinero. "
    "El rendimiento pasado no garantiza resultados futuros."
)


def endpoint_allowed(path: str) -> tuple:
    lowered = (path or "").lower()
    for piece in TRADE_ENDPOINTS:
        if piece in lowered:
            return False, "TRADE_ENDPOINT_BLOCKED"
    if lowered.startswith("/market") or "/ticker" in lowered or "/klines" in lowered:
        return True, "READ_ONLY"
    return False, "ENDPOINT_NOT_ALLOWLISTED"


def inspect_key_permissions(permissions: List[str]) -> Optional[str]:
    extra = [item for item in permissions if item.lower() in ("trade", "withdraw", "transfer")]
    if extra:
        return "CLAVE_CON_PERMISO_DE_MAS:" + ",".join(extra)
    return None


def validate_signal(signal: Dict[str, Any]) -> List[str]:
    missing = [field for field in REQUIRED_SIGNAL_FIELDS if not signal.get(field)]
    if signal.get("warning") != WARNING and "warning" not in missing:
        missing.append("warning_text")
    return missing


def backtest_uses_future(rows: List[Dict[str, Any]]) -> bool:
    """Verdadero si una decisión en t mira un dato con marca posterior a t."""
    for row in rows:
        decision_at = row.get("decision_at")
        used = row.get("data_as_of")
        if decision_at is None or used is None:
            continue
        if used > decision_at:
            return True
    return False


def overfit_label(in_sample: float, out_of_sample: float) -> str:
    if in_sample > 0 and out_of_sample <= 0:
        return "OVERFIT"
    return "HOLDS_OUT_OF_SAMPLE"
