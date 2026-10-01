"""Margen neto de dropshipping. Sin red, sin tienda y sin tarifa oficial."""
from __future__ import annotations

import os
import unittest

from core.margin import comision_hipotesis, evaluate_product
from core.marketplace import DropshipMachine
from core.dev_director import load_playbook, playbook_for


def _completo(**extra):
    base = {
        "product": "lampara",
        "country": "CO",
        "platform": "simulada",
        "category": "general",
        "supplier": "prov",
        "currency": "USD",
        "price": 100,
        "supplier_cost": 40,
        "commission": 13,
        "shipping": 10,
        "tax": 5,
        "return_rate": 0.1,
        "return_cost": 20,
        "ads": 10,
        "route": "proveedor-cliente",
    }
    base.update(extra)
    return base


class MarginTests(unittest.TestCase):
    def test_missing_tax_is_incomplete_not_zero(self):
        raw = _completo()
        raw.pop("tax")
        result = evaluate_product(raw, min_margin=5, approved_suppliers=["prov"])
        self.assertEqual(result["verdict"], "INCOMPLETO")
        self.assertIn("tax", result["missing"])
        self.assertIsNone(result["net"])
        self.assertFalse(result["publishes"])
        self.assertFalse(result["orders_supplier"])

    def test_returns_and_ads_can_sink_a_product(self):
        good = evaluate_product(_completo(), min_margin=5, approved_suppliers=["prov"])
        self.assertEqual(good["verdict"], "VALE")
        self.assertEqual(good["net"], 20)
        sunk = evaluate_product(_completo(ads=40), min_margin=5, approved_suppliers=["prov"])
        self.assertEqual(sunk["verdict"], "NO_VALE")
        self.assertLess(sunk["net"], 5)

    def test_unknown_supplier_does_not_pass(self):
        result = evaluate_product(_completo(supplier="otro"), min_margin=1, approved_suppliers=["prov"])
        self.assertEqual(result["verdict"], "NO_VALE")
        self.assertEqual(result["reason"], "proveedor_no_aprobado")

    def test_hypothesis_is_not_an_official_tariff(self):
        item = comision_hipotesis("simulada", "general", 100)
        self.assertEqual(item["source"], "TABLA_HIPOTESIS")
        self.assertIn("no es tarifa oficial", item["note"])
        self.assertEqual(item["amount"], 13)
        missing = comision_hipotesis("mercadolibre", "general", 100)
        self.assertEqual(missing["source"], "DESCONOCIDO")
        self.assertIsNone(missing["amount"])

    def test_hypothesis_fills_commission_only_when_asked(self):
        raw = _completo()
        raw.pop("commission")
        blocked = evaluate_product(raw, min_margin=5, approved_suppliers=["prov"])
        self.assertEqual(blocked["verdict"], "INCOMPLETO")
        raw["use_hypothesis"] = True
        opened = evaluate_product(raw, min_margin=5, approved_suppliers=["prov"])
        self.assertEqual(opened["verdict"], "VALE")
        commission = next(item for item in opened["lines"] if item["name"] == "commission")
        self.assertEqual(commission["source"], "TABLA_HIPOTESIS")

    def test_strict_order_stops_and_legacy_order_still_validates(self):
        machine = DropshipMachine(min_margin=5, daily_pay_cap=100, approved_suppliers=["prov"])
        thin = {
            "supplier": "prov", "cost": 10, "fees": 2, "shipping": 3,
            "price": 30, "address_ok": True, "stock": 2,
        }
        machine.receive("old", thin)
        self.assertEqual(machine.advance("old"), "VALIDADO")
        strict = _completo(strict_margin=True, cost=40)
        strict.pop("tax")
        machine.receive("new", strict)
        self.assertEqual(machine.advance("new"), "EXCEPCION")
        self.assertIn("margen_incompleto", machine.alerts)

    def test_playbook_for_a_stall_is_on_disk(self):
        self.assertEqual(playbook_for("S6"), "PB-06")
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "engineering", "handover", "playbooks", "DIRECTOR.md",
        )
        text = load_playbook(path, "PB-06")
        self.assertIn("no debilitar pruebas", text.lower())
        self.assertIn("PB-12", load_playbook(path, "PB-12"))


if __name__ == "__main__":
    unittest.main()
