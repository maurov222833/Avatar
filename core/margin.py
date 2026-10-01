"""Margen neto real por pedido de dropshipping (spec 003, U15).

No llama a Amazon ni a Mercado Libre, no publica y no paga al proveedor.
Una cifra sin fuente queda incompleta. No se reemplaza por cero.
Una tabla de hipótesis no es una tarifa oficial.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

REQUIRED_LINES = (
    "supplier_cost",
    "commission",
    "shipping",
    "tax",
    "returns",
    "ads",
)
REQUIRED_IDENTITY = ("product", "country", "platform", "category", "supplier", "currency")

# Tasas de ejemplo para pruebas. No salen de un sitio oficial.
HYPOTHESIS_RATES = {
    ("simulada", "general"): 0.13,
}


def _amount(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return round(float(value), 2)


def line(name: str, amount: Any, source: str, note: str = "") -> Dict[str, Any]:
    """source es DADO, TABLA_HIPOTESIS o DESCONOCIDO."""
    if source not in ("DADO", "TABLA_HIPOTESIS", "DESCONOCIDO"):
        source = "DESCONOCIDO"
    number = _amount(amount)
    if source == "DESCONOCIDO" or number is None:
        return {"name": name, "amount": None, "source": "DESCONOCIDO", "note": note}
    return {"name": name, "amount": number, "source": source, "note": note}


def ficha_candidato(raw: Dict[str, Any]) -> Dict[str, Any]:
    missing = [key for key in REQUIRED_IDENTITY if not str(raw.get(key) or "").strip()]
    return {
        "product": raw.get("product") or "",
        "country": raw.get("country") or "",
        "platform": raw.get("platform") or "",
        "category": raw.get("category") or "",
        "supplier": raw.get("supplier") or "",
        "currency": raw.get("currency") or "",
        "missing": missing,
    }


def costo_proveedor(raw: Dict[str, Any], approved: List[str]) -> Dict[str, Any]:
    supplier = str(raw.get("supplier") or "")
    approved_set = set(approved)
    item = line(
        "supplier_cost",
        raw.get("supplier_cost"),
        str(raw.get("supplier_source") or ("DADO" if raw.get("supplier_cost") is not None else "DESCONOCIDO")),
    )
    item["supplier"] = supplier
    item["approved"] = supplier in approved_set
    return item


def comision(raw: Dict[str, Any]) -> Dict[str, Any]:
    if raw.get("commission") is not None:
        return line("commission", raw.get("commission"), str(raw.get("commission_source") or "DADO"))
    if raw.get("use_hypothesis"):
        return comision_hipotesis(
            str(raw.get("platform") or ""),
            str(raw.get("category") or ""),
            raw.get("price"),
        )
    return line("commission", None, "DESCONOCIDO", "sin tarifa oficial")


def comision_hipotesis(platform: str, category: str, price: Any) -> Dict[str, Any]:
    rate = HYPOTHESIS_RATES.get((platform, category))
    if rate is None or price is None:
        return line("commission", None, "DESCONOCIDO", "sin tarifa oficial")
    return line(
        "commission",
        float(price) * rate,
        "TABLA_HIPOTESIS",
        "no es tarifa oficial",
    )


def envio(raw: Dict[str, Any]) -> Dict[str, Any]:
    item = line(
        "shipping",
        raw.get("shipping"),
        str(raw.get("shipping_source") or ("DADO" if raw.get("shipping") is not None else "DESCONOCIDO")),
    )
    item["route"] = raw.get("route") or ""
    return item


def impuesto(raw: Dict[str, Any]) -> Dict[str, Any]:
    source = str(raw.get("tax_source") or ("DADO" if raw.get("tax") is not None else "DESCONOCIDO"))
    return line("tax", raw.get("tax"), source, "no se asume cero")


def devoluciones(raw: Dict[str, Any]) -> Dict[str, Any]:
    rate = raw.get("return_rate")
    cost = raw.get("return_cost")
    source = str(raw.get("return_source") or "DADO")
    if rate is None or cost is None:
        return line("returns", None, "DESCONOCIDO")
    if source == "DESCONOCIDO":
        return line("returns", None, "DESCONOCIDO")
    return line("returns", float(rate) * float(cost), source)


def publicidad(raw: Dict[str, Any]) -> Dict[str, Any]:
    return line(
        "ads",
        raw.get("ads"),
        str(raw.get("ads_source") or ("DADO" if raw.get("ads") is not None else "DESCONOCIDO")),
    )


def evaluate_product(
    raw: Dict[str, Any],
    *,
    min_margin: float,
    approved_suppliers: Optional[List[str]] = None,
    min_margin_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Veredicto VALE, NO_VALE o INCOMPLETO. No crea un anuncio ni un pedido."""
    approved_suppliers = approved_suppliers or []
    ficha = ficha_candidato(raw)
    supplier = costo_proveedor(raw, approved_suppliers)
    parts = [
        supplier,
        comision(raw),
        envio(raw),
        impuesto(raw),
        devoluciones(raw),
        publicidad(raw),
    ]
    price = _amount(raw.get("price"))
    price_source = str(raw.get("price_source") or ("DADO" if price is not None else "DESCONOCIDO"))
    if price_source == "DESCONOCIDO":
        price = None
    result: Dict[str, Any] = {
        "ficha": ficha,
        "lines": parts,
        "price": price,
        "net": None,
        "margin_pct": None,
        "missing": [],
        "verdict": "INCOMPLETO",
        "reason": "",
        "publishes": False,
        "orders_supplier": False,
    }
    if ficha["missing"]:
        result["missing"] = [f"ficha:{key}" for key in ficha["missing"]]
        result["reason"] = "ficha_incompleta"
        return result
    if not supplier["approved"]:
        result["verdict"] = "NO_VALE"
        result["reason"] = "proveedor_no_aprobado"
        return result
    missing = [item["name"] for item in parts if item["amount"] is None or item["source"] == "DESCONOCIDO"]
    if price is None:
        missing.append("price")
    if missing:
        result["missing"] = missing
        result["reason"] = "cifra_sin_fuente"
        return result
    net = round(
        price
        - supplier["amount"]
        - next(item["amount"] for item in parts if item["name"] == "commission")
        - next(item["amount"] for item in parts if item["name"] == "shipping")
        - next(item["amount"] for item in parts if item["name"] == "tax")
        - next(item["amount"] for item in parts if item["name"] == "returns")
        - next(item["amount"] for item in parts if item["name"] == "ads"),
        2,
    )
    pct = round((net / price) * 100, 2) if price else None
    verdict = "VALE" if net >= min_margin else "NO_VALE"
    if min_margin_pct is not None and pct is not None and pct < min_margin_pct:
        verdict = "NO_VALE"
    result.update({
        "net": net,
        "margin_pct": pct,
        "verdict": verdict,
        "reason": "margen",
        "missing": [],
    })
    return result
