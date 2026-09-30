"""Marketplaces en simulación (spec 003, U15).

No hay llamadas a Amazon ni a Mercado Libre, ni pagos, ni cuentas de Mauro.
Dropshipping es una máquina de estados con clave de idempotencia.
Los modos de acceso prohibidos se niegan aquí, no en un prompt.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PROHIBITED_ACCESS = frozenset({
    "human_impersonation",
    "fingerprint_spoof",
    "proxy_evasion",
    "multi_account_evasion",
    "captcha_bypass",
    "tos_scraping",
})

ORDER_FLOW = (
    "RECIBIDO",
    "VALIDADO",
    "PEDIDO_AL_PROVEEDOR",
    "CONFIRMADO_POR_PROVEEDOR",
    "TRACKING_PUBLICADO",
    "EN_TRANSITO",
    "ENTREGADO",
    "CERRADO_CONCILIADO",
)


def authorize_access_mode(mode: str) -> tuple:
    if mode in PROHIBITED_ACCESS:
        return False, "ACCESS_MODE_PROHIBITED"
    if mode in ("official_api", "delegated_user", "official_export", "assisted"):
        return True, "ACCESS_MODE_ALLOWED"
    return False, "ACCESS_MODE_UNKNOWN"


def unit_economics(
    product_cost: float,
    fees: float,
    shipping: float,
    ads: float,
    price: float,
) -> Dict[str, float]:
    net = price - product_cost - fees - shipping - ads
    return {"net": round(net, 2), "price": price}


class DropshipMachine:
    def __init__(self, *, min_margin: float, daily_pay_cap: float, approved_suppliers: List[str]) -> None:
        self.min_margin = min_margin
        self.daily_pay_cap = daily_pay_cap
        self.approved_suppliers = set(approved_suppliers)
        self.paid_today = 0.0
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.supplier_orders: List[str] = []
        self.alerts: List[str] = []
        self.killed = False

    def receive(self, key: str, order: Dict[str, Any]) -> str:
        if self.killed:
            return "HALTED"
        if key in self.orders:
            return self.orders[key]["state"]
        self.orders[key] = {"state": "RECIBIDO", "order": dict(order), "supplier_sent": False}
        return "RECIBIDO"

    def advance(self, key: str) -> str:
        if self.killed:
            return "HALTED"
        row = self.orders[key]
        order = row["order"]
        state = row["state"]
        if state == "RECIBIDO":
            supplier = order.get("supplier")
            if supplier not in self.approved_suppliers:
                row["state"] = "EXCEPCION"
                self.alerts.append("proveedor_no_aprobado")
                return row["state"]
            if order.get("fraud"):
                row["state"] = "EXCEPCION"
                self.alerts.append("fraude")
                return row["state"]
            if not order.get("address_ok", True):
                row["state"] = "EXCEPCION"
                self.alerts.append("direccion")
                return row["state"]
            net = unit_economics(
                order["cost"], order["fees"], order["shipping"], order.get("ads", 0), order["price"]
            )["net"]
            if net < self.min_margin:
                row["state"] = "EXCEPCION"
                self.alerts.append("margen")
                return row["state"]
            if order.get("stock", 1) <= 0:
                row["state"] = "EXCEPCION"
                self.alerts.append("sin_stock")
                return row["state"]
            row["state"] = "VALIDADO"
            return row["state"]
        if state == "VALIDADO":
            pay = float(order["cost"])
            if self.paid_today + pay > self.daily_pay_cap:
                self.alerts.append("tope_pago")
                return "QUEUED"
            if order.get("payment_change_message"):
                self.alerts.append("cambio_de_pago")
                row["state"] = "EXCEPCION"
                return row["state"]
            self.paid_today += pay
            row["supplier_sent"] = True
            self.supplier_orders.append(key)
            row["state"] = "PEDIDO_AL_PROVEEDOR"
            return row["state"]
        if state == "PEDIDO_AL_PROVEEDOR":
            row["state"] = "CONFIRMADO_POR_PROVEEDOR"
            return row["state"]
        if state == "CONFIRMADO_POR_PROVEEDOR":
            if order.get("deadline_risk"):
                self.alerts.append("plazo")
            row["state"] = "TRACKING_PUBLICADO"
            return row["state"]
        order_index = ORDER_FLOW.index(state)
        row["state"] = ORDER_FLOW[min(order_index + 1, len(ORDER_FLOW) - 1)]
        return row["state"]

    def kill(self) -> None:
        self.killed = True


class PlatformRegistry:
    """Una plataforma nueva entra con ficha y adaptador. SOMBRA no ejecuta."""

    def __init__(self) -> None:
        self.platforms: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, card: Dict[str, Any], capabilities: Dict[str, bool]) -> None:
        self.platforms[name] = {
            "state": card.get("state") or "EVALUADA",
            "card": card,
            "capabilities": capabilities,
        }

    def act(self, name: str, capability: str) -> str:
        platform = self.platforms[name]
        if platform["state"] == "SOMBRA":
            return "SHADOW_NO_EFFECT"
        if not platform["capabilities"].get(capability):
            return "CAPABILITY_UNSUPPORTED"
        return "READY"
