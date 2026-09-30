"""Conocimiento por dominio (spec 003, U17).

Una ficha vencida no se usa como hecho vigente. El puntaje sale de casos, no de una frase.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


class KnowledgeBase:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def add(self, domain: str, fact: str, *, review_by: str, state: str = "VALIDATED") -> None:
        self.items.append({
            "domain": domain,
            "fact": fact,
            "review_by": review_by,
            "state": state,
        })

    def usable(self, today: str) -> List[Dict[str, Any]]:
        usable = []
        for item in self.items:
            if item["state"] == "DEPRECATED":
                continue
            if item["review_by"] < today:
                item["state"] = "NEEDS_REVALIDATION"
                continue
            usable.append(item)
        return usable

    def mark_deprecated(self, fact: str) -> None:
        for item in self.items:
            if item["fact"] == fact:
                item["state"] = "DEPRECATED"


def evaluate_domain(cases: List[Dict[str, Any]], answer: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
    correct = 0
    for case in cases:
        if answer(case) == case["expect"]:
            correct += 1
    total = len(cases)
    return {"correct": correct, "total": total, "score": (correct / total) if total else 0.0}
