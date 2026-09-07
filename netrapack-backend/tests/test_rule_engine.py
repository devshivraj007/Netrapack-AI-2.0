"""Pytest: Day 1 rule engine + Part D behaviours (deterministic, fast)."""
from __future__ import annotations

from app.ocr.cleansing import cleanse_fields, cleanse_numeric_field
from app.rule_engine.engine import RuleEngine
from app.schemas.scan import OverallStatus, ScanRequest

engine = RuleEngine()


def _req(**kw):
    base = dict(scan_id="t", mrp_declaration="MRP Rs. 90",
                net_quantity_declaration="200g",
                manufacturing_date_declaration="MAR 2026",
                expiry_date_declaration="MAR 2027",
                unit_sale_price_declaration="Rs 45 per 100g",
                manufacturer_name_address="ABC Foods, Pune 411001",
                country_of_origin_declaration="Made in India",
                consumer_care_details="care@abc.com, 1800-111-222",
                fssai_license_number="FSSAI 10012345678901")
    base.update(kw)
    return ScanRequest(**base)


def test_fully_compliant_food():
    v = engine.evaluate(_req(), product_category="food_and_beverage")
    assert v.overall_status == OverallStatus.FULLY_COMPLIANT
    assert v.rules_passed == v.rules_checked


def test_mrp_double_price_needs_review():
    v = engine.evaluate(_req(mrp_declaration="MRP Rs. 250 Rs. 240"),
                        product_category="food_and_beverage")
    assert v.overall_status == OverallStatus.NEEDS_MANUAL_REVIEW


def test_usp_exemption_1kg():
    v = engine.evaluate(_req(net_quantity_declaration="1kg",
                             unit_sale_price_declaration=None),
                        product_category="food_and_beverage")
    assert v.parsed_fields["unit_sale_price"].status.value == "not_required"


def test_usp_exemption_low_mrp():
    v = engine.evaluate(_req(mrp_declaration="MRP Rs. 10",
                             net_quantity_declaration="9g",
                             unit_sale_price_declaration=None),
                        product_category="food_and_beverage")
    assert v.parsed_fields["unit_sale_price"].status.value == "not_required"


def test_bonus_pack_paid_vs_total():
    v = engine.evaluate(_req(net_quantity_declaration="100g + 20g extra",
                             mrp_declaration="MRP Rs. 60",
                             unit_sale_price_declaration="Rs 60 per 100g"),
                        product_category="food_and_beverage")
    nq = v.parsed_fields["net_quantity"].parsed
    assert nq["total_quantity_base"] == 120.0
    assert nq["paid_quantity_base"] == 100.0


def test_category_general_skips_fssai():
    v = engine.evaluate(_req(fssai_license_number=""), product_category="general")
    assert "fssai_license" not in v.parsed_fields


def test_category_food_runs_fssai():
    v = engine.evaluate(_req(fssai_license_number=""),
                        product_category="food_and_beverage")
    assert "fssai_license" in v.parsed_fields
    assert any(x.field == "fssai_license" for x in v.violations)


def test_d1_numeric_cleansing():
    assert cleanse_numeric_field("Rs. 1OO") == "Rs. 100"
    assert cleanse_numeric_field("2OOg") == "200g"
    assert cleanse_numeric_field("3S0g") == "350g"
    out = cleanse_fields({"mrp_declaration": "Rs. 4S",
                          "manufacturer_name_address": "ABC Foods, Solapur"})
    assert out["mrp_declaration"] == "Rs. 45"
    assert out["manufacturer_name_address"] == "ABC Foods, Solapur"
