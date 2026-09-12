"""Pytest: strikethrough / promotional MRP handling in VisionExtraction."""
from __future__ import annotations

from app.ai.types import VisionExtraction
from app.rule_engine.engine import RuleEngine
from app.schemas.scan import OverallStatus, ScanRequest

engine = RuleEngine()


def _run(ve: VisionExtraction):
    fields = ve.to_scan_fields()
    req = ScanRequest(scan_id="t", **fields)
    return fields, engine.evaluate(req, product_category="food_and_beverage")


def test_clear_strikethrough_uses_lower_active_price():
    # Chheda's case: 85.10 struck through, 75 active. Model resolved mrp=75.
    ve = VisionExtraction(mrp=75.0, mrp_all_prices=[85.1, 75.0],
                          mrp_is_ambiguous=False, net_quantity="150g")
    fields, verdict = _run(ve)
    assert fields["mrp_declaration"] == "MRP Rs. 75"
    assert verdict.parsed_fields["mrp"].parsed.get("mrp") == 75.0


def test_ambiguous_two_prices_routes_to_manual_review():
    # Two prices, no clear strikethrough -> don't guess, route to review.
    ve = VisionExtraction(mrp=None, mrp_all_prices=[250.0, 240.0],
                          mrp_is_ambiguous=True, net_quantity="1kg")
    fields, verdict = _run(ve)
    # Both prices present so the Day 1 MRP rule flags multiple candidates.
    assert "250" in fields["mrp_declaration"] and "240" in fields["mrp_declaration"]
    assert verdict.parsed_fields["mrp"].status.value == "needs_manual_review"


def test_single_price_normal():
    ve = VisionExtraction(mrp=90.0, mrp_all_prices=[90.0],
                          mrp_is_ambiguous=False, net_quantity="200g")
    fields, _ = _run(ve)
    assert fields["mrp_declaration"] == "MRP Rs. 90"


def test_strikethrough_without_resolved_mrp_falls_back_to_lowest():
    # Model listed both but didn't resolve mrp, not ambiguous -> lowest active.
    ve = VisionExtraction(mrp=None, mrp_all_prices=[85.1, 75.0],
                          mrp_is_ambiguous=False, net_quantity="150g")
    fields, _ = _run(ve)
    assert fields["mrp_declaration"] == "MRP Rs. 75"
