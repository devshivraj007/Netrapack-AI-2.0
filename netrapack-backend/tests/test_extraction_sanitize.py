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
