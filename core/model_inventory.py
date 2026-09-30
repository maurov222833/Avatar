"""Inventario de modelos y tope de gasto (spec 003, U7).

Lo que no se puede comprobar queda UNKNOWN. No se inventan precios.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def normalize_entry(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": raw.get("provider") or "UNKNOWN",
        "name": raw.get("name") or "UNKNOWN",
        "available": bool(raw.get("available")),
        "authenticated": raw.get("authenticated") if "authenticated" in raw else "UNKNOWN",
        "context": raw.get("context") if raw.get("context") is not None else "UNKNOWN",
        "price": raw.get("price") if raw.get("price") is not None else "UNKNOWN",
        "paid_upgrade": bool(raw.get("paid_upgrade")),
        "checked_at": raw.get("checked_at") or "UNKNOWN",
    }


class ModelRouter:
    def __init__(self, inventory: List[Dict[str, Any]], *, mission_budget: float) -> None:
        self.inventory = [normalize_entry(item) for item in inventory]
        self.mission_budget = mission_budget
        self.spent = 0.0
        self.decisions: List[Dict[str, Any]] = []
        self.saved_mission: Optional[str] = None

    def choose(self, task: str, required: str = "text") -> Dict[str, Any]:
        usable = [item for item in self.inventory if item["available"] and not item["paid_upgrade"]]
        if not usable:
            paid = [item for item in self.inventory if item["available"] and item["paid_upgrade"]]
            self.saved_mission = task
            decision = {
                "task": task,
                "model": None,
                "reason": "PAID_ALTERNATIVE_BLOCKED" if paid else "NO_MODEL",
            }
            self.decisions.append(decision)
            return decision
        chosen = usable[0]
        decision = {
            "task": task,
            "model": chosen["name"],
            "provider": chosen["provider"],
            "reason": "AVAILABLE_WITHOUT_EXTRA_PAYMENT",
            "price": chosen["price"],
        }
        self.decisions.append(decision)
        return decision

    def charge(self, amount: Optional[float]) -> bool:
        """False si el costo es desconocido o supera el tope. No se cobra a ciegas."""
        if amount is None:
            return False
        if self.spent + amount > self.mission_budget:
            self.saved_mission = "budget"
            return False
        self.spent += amount
        return True
