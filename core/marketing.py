"""Métricas de marketing calculadas por código (spec 003, U14).

No hay publicación ni gasto real. Una reseña inventada se rechaza.
"""
from __future__ import annotations

from typing import Optional


def roi(gain: float, cost: float) -> Optional[float]:
    if cost == 0:
        return None
    return (gain - cost) / cost


def roas(revenue: float, ad_spend: float) -> Optional[float]:
    if ad_spend == 0:
        return None
    return revenue / ad_spend


def cac(ad_spend: float, new_customers: int) -> Optional[float]:
    if new_customers <= 0:
        return None
    return ad_spend / new_customers


def ltv(avg_order: float, orders_per_customer: float, margin: float) -> float:
    return avg_order * orders_per_customer * margin


def ab_conclusion(sample_a: int, sample_b: int, minimum: int) -> str:
    if sample_a < minimum or sample_b < minimum:
        return "INCONCLUSIVE"
    return "SUFFICIENT_SAMPLE"


def reject_fake_review(text: str, *, invented: bool) -> Optional[str]:
    if invented:
        return "RECHAZADO: Avatar no crea reseñas ni testimonios inventados"
    return None


class DemandTest:
    def __init__(self, spend_cap: float, min_margin: float) -> None:
        self.spend_cap = spend_cap
        self.min_margin = min_margin
        self.spent = 0.0
        self.stopped = False

    def spend(self, amount: float) -> str:
        if self.stopped or self.spent + amount > self.spend_cap:
            self.stopped = True
            return "STOPPED_AT_CAP"
        self.spent += amount
        return "SPENT"

    def may_publish(self, net_margin: float) -> bool:
        return net_margin >= self.min_margin
