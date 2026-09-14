"""Pytest: post-extraction sanitisation of vision-model output.

Regression guard for the "42" bug — vision models sometimes emit a bare number
(e.g. "42") or junk placeholder for a text field (mfd_pkd_date, country_of_origin)
they cannot actually read. The backend must drop implausible values to None so the
app shows "Not declared" rather than a fabricated reading, instead of passing the
garbage straight through.
"""
from __future__ import annotations

from app.ai.providers import _extraction_from_data
from app.ai.types import AiSource


def _extract(**data):
    return _extraction_from_data(data, AiSource.CLOUD_GEMINI, "test-model")


# --- The core "42" bug ------------------------------------------------------
def test_bare_number_date_is_dropped():
    v = _extract(mfd_pkd_date="42", expiry_date="7")
    assert v.mfd_pkd_date is None
    assert v.expiry_date is None


def test_bare_number_country_is_dropped():
    v = _extract(country_of_origin="42")
    assert v.country_of_origin is None


# --- Real values must be preserved -----------------------------------------
def test_real_dates_preserved():
    assert _extract(mfd_pkd_date="MAR 2026").mfd_pkd_date == "MAR 2026"
    assert _extract(mfd_pkd_date="03/2026").mfd_pkd_date == "03/2026"
    assert _extract(mfd_pkd_date="12-01-2026").mfd_pkd_date == "12-01-2026"
    assert _extract(expiry_date="2027").expiry_date == "2027"


def test_real_country_preserved():
    assert _extract(country_of_origin="India").country_of_origin == "India"
    assert _extract(country_of_origin="Made in Sri Lanka").country_of_origin == "Made in Sri Lanka"


# --- Junk placeholders dropped ---------------------------------------------
def test_junk_tokens_dropped():
    for junk in ("N/A", "none", "null", "-", "unknown"):
        assert _extract(country_of_origin=junk).country_of_origin is None
        assert _extract(manufacturer_details=junk).manufacturer_details is None


# --- Prices sanitised -------------------------------------------------------
def test_bad_prices_dropped():
    assert _extract(mrp=0).mrp is None            # zero is not a real MRP
    assert _extract(mrp=-5).mrp is None           # negative
    assert _extract(unit_sale_price=0).unit_sale_price is None
    # a sane price is kept
    assert _extract(mrp=45).mrp == 45.0
    assert _extract(unit_sale_price=22.5).unit_sale_price == 22.5


def test_fssai_must_have_digits():
    assert _extract(fssai_license_number="abc").fssai_license_number is None
    assert _extract(fssai_license_number="10012345678901").fssai_license_number == "10012345678901"


def test_normal_full_extraction_unaffected():
    v = _extract(
        mrp=99, net_quantity="200g", unit_sale_price=49.5,
        mfd_pkd_date="JAN 2026", expiry_date="JAN 2027",
        fssai_license_number="10012345678901",
        manufacturer_details="ABC Foods, Pune",
        country_of_origin="India",
    )
    assert v.mrp == 99.0
    assert v.net_quantity == "200g"
    assert v.mfd_pkd_date == "JAN 2026"
    assert v.country_of_origin == "India"
    assert v.fssai_license_number == "10012345678901"


def test_unclear_fields_parsed():
    v = _extract(mrp=50, unclear_fields=["mrp", "mfd_pkd_date"])
    assert "mrp" in v.unclear_fields
    assert "mfd_pkd_date" in v.unclear_fields


def test_core_fields_counting():
    from app.ai.recognizer import _count_core_fields
    v_empty = _extract()
    assert _count_core_fields(v_empty) == 0

    v_partial = _extract(mrp=45, net_quantity="100g")
    assert _count_core_fields(v_partial) == 2

    v_full = _extract(
        mrp=45, net_quantity="100g", mfd_pkd_date="02/2026",
        manufacturer_details="Amul Anand", consumer_care_details="care@amul.in",
        country_of_origin="India"
    )
    assert _count_core_fields(v_full) == 6


def test_unclear_or_missing_core():
    from app.ai.recognizer import _get_unclear_or_missing_core
    v_empty = _extract()
    assert len(_get_unclear_or_missing_core(v_empty)) == 6

    # Full but date is in unclear_fields
    v_unclear_date = _extract(
        mrp=45, net_quantity="100g", mfd_pkd_date="02/2026",
        manufacturer_details="Amul Anand", consumer_care_details="care@amul.in",
        country_of_origin="India",
        unclear_fields=["mfd_pkd_date"]
    )
    needed = _get_unclear_or_missing_core(v_unclear_date)
    assert needed == ["mfd_pkd_date"]

    # Completely clear and declared
    v_all_clear = _extract(
        mrp=45, net_quantity="100g", mfd_pkd_date="02/2026",
        manufacturer_details="Amul Anand", consumer_care_details="care@amul.in",
        country_of_origin="India"
    )
    assert len(_get_unclear_or_missing_core(v_all_clear)) == 0


def test_intelligent_merge_clears_unclear():
    from app.ai.recognizer import _merge_extractions
    # Primary attempt had unclear mfd_pkd_date
    primary = _extract(mrp=50.0, mfd_pkd_date="01/26", unclear_fields=["mfd_pkd_date"])
    # Secondary attempt read mfd_pkd_date clearly!
    secondary = _extract(mfd_pkd_date="01/2026", net_quantity="200g")
    
    merged = _merge_extractions(primary, secondary)
    # Secondary clear reading replaces primary unclear reading
    assert merged.mfd_pkd_date == "01/2026"
    assert "mfd_pkd_date" not in merged.unclear_fields
    # Preserves primary clear mrp and secondary discovered net_quantity
    assert merged.mrp == 50.0
    assert merged.net_quantity == "200g"


def test_amul_milk_date_formats():
    from app.rule_engine.parsers import parse_month_year
    res_pkd = parse_month_year("PKD 07/AUG/26")
    assert res_pkd.ok is True
    assert res_pkd.month == 8
    assert res_pkd.year == 2026

    res_exp = parse_month_year("Exp: 03/FEB/27")
    assert res_exp.ok is True
    assert res_exp.month == 2
    assert res_exp.year == 2027


def test_fssai_barcode_rejection():
    from app.ai.providers import _clean_fssai
    # 13-digit EAN barcode starting with 890... must be rejected
    assert _clean_fssai("8 901262 150088") is None
    assert _clean_fssai("8901262150088") is None
    # Real 14-digit FSSAI number must pass
    assert _clean_fssai("10014022002711") == "10014022002711"



