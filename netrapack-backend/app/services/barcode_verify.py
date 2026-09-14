"""Barcode cross-verification.

Given a scanned barcode, look up the reference product in the SQLite
`products` table and compare the label's declared values (from OCR) against
the trusted reference record. This is the Day 3 groundwork: today we prove the
match + field comparison works on products whose barcode is confirmed.

Design notes:
  * We ONLY match against barcodes that were seeded (confirmed ones). If a
    barcode is not found, we say so plainly rather than inventing a match.
  * Field comparison is advisory: it reports agree / mismatch / not_available
    per field so an officer can see where the printed label diverges from the
    reference. It never auto-fails a scan on its own today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.db import repository


@dataclass
class FieldComparison:
    field: str
    reference: Optional[str]
    declared: Optional[str]
    status: str  # agree | mismatch | not_available


@dataclass
class BarcodeVerification:
    scanned_barcode: Optional[str]
    matched: bool
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    comparisons: list[FieldComparison] = field(default_factory=list)
    note: Optional[str] = None
    gs1_prefix: Optional[str] = None
    gs1_country: Optional[str] = None
    origin_matches_barcode: Optional[bool] = None


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def resolve_gs1_prefix(barcode: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Decode standard GS1 prefix to member country / organization."""
    if not barcode:
        return None, None
    clean = re.sub(r"\D", "", barcode)
    if len(clean) < 3:
        return None, None
    p3 = clean[:3]
    try:
        val3 = int(p3)
    except ValueError:
        return None, None

    if val3 == 890:
        return "890", "India (GS1 India)"
    if 0 <= val3 <= 139:
        return clean[:2], "United States & Canada"
    if 300 <= val3 <= 379:
        return "300-379", "France"
    if 400 <= val3 <= 440:
        return "400-440", "Germany"
    if 450 <= val3 <= 459 or 490 <= val3 <= 499:
        return clean[:3], "Japan"
    if 460 <= val3 <= 469:
        return "460-469", "Russia"
    if val3 == 471:
        return "471", "Taiwan"
    if val3 == 489:
        return "489", "Hong Kong"
    if 500 <= val3 <= 509:
        return "500-509", "United Kingdom"
    if 690 <= val3 <= 699:
        return "690-699", "China"
    if 789 <= val3 <= 790:
        return "789-790", "Brazil"
    if val3 == 880:
        return "880", "South Korea"
    if val3 == 885:
        return "885", "Thailand"
    if val3 == 888:
        return "888", "Singapore"
    if val3 == 893:
        return "893", "Vietnam"
    if 930 <= val3 <= 939:
        return "930-939", "Australia"
    return p3, f"GS1 Prefix {p3}"


def check_origin_matches_barcode(gs1_country: Optional[str], declared_origin: Optional[str]) -> Optional[bool]:
    if not gs1_country or not declared_origin:
        return None
    c_lower = gs1_country.lower()
    o_lower = declared_origin.lower()
    if "india" in c_lower and "india" in o_lower:
        return True
    if "china" in c_lower and "china" in o_lower:
        return True
    if "united states" in c_lower and any(x in o_lower for x in ["usa", "united states", "america"]):
        return True
    if "germany" in c_lower and "germany" in o_lower:
        return True
    if "japan" in c_lower and "japan" in o_lower:
        return True
    if "united kingdom" in c_lower and any(x in o_lower for x in ["uk", "united kingdom", "britain"]):
        return True
    if "korea" in c_lower and "korea" in o_lower:
        return True
    if "thailand" in c_lower and "thailand" in o_lower:
        return True
    # Obvious mismatches
    if "india" in c_lower and any(x in o_lower for x in ["china", "vietnam", "taiwan", "germany", "imported"]):
        return False
    if "china" in c_lower and "india" in o_lower:
        return False
    return None


def _num(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    m = _NUM_RE.search(str(text))
    return float(m.group(0)) if m else None


def _norm_qty(text: Optional[str]) -> Optional[str]:
    """Normalise a quantity string for loose comparison (digits+unit only)."""
    if not text:
        return None
    t = str(text).lower().replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)(kg|g|ml|l|units?|unit|n|pcs?|piece)?", t)
    return m.group(0) if m else None


def _compare_mrp(ref: Optional[float], declared: Optional[str]) -> FieldComparison:
    d = _num(declared)
    if ref is None or d is None:
        return FieldComparison("mrp", str(ref) if ref is not None else None,
                               declared, "not_available")
    status = "agree" if abs(ref - d) <= max(0.5, ref * 0.02) else "mismatch"
    return FieldComparison("mrp", str(ref), declared, status)


def _compare_qty(ref: Optional[str], declared: Optional[str]) -> FieldComparison:
    rn, dn = _norm_qty(ref), _norm_qty(declared)
    if rn is None or dn is None:
        return FieldComparison("net_quantity", ref, declared, "not_available")
    status = "agree" if rn == dn else "mismatch"
    return FieldComparison("net_quantity", ref, declared, status)


def _compare_text(name: str, ref: Optional[str], declared: Optional[str]) -> FieldComparison:
    if not ref or not declared:
        return FieldComparison(name, ref, declared, "not_available")
    # Loose containment either direction (OCR is partial/messy).
    r, d = ref.lower(), declared.lower()
    key = r.split(",")[0].split()[0] if r.split() else r  # first ref token
    status = "agree" if (key and key in d) else "mismatch"
    return FieldComparison(name, ref, declared, status)


def cross_verify(scanned_barcode: Optional[str],
                declared_fields: dict[str, Any]) -> BarcodeVerification:
    """Match the barcode to a reference product and compare fields.

    `declared_fields` uses ScanRequest-style keys (mrp_declaration,
    net_quantity_declaration, manufacturer_name_address,
    country_of_origin_declaration, fssai_license_number).
    """
    if not scanned_barcode:
        return BarcodeVerification(
            scanned_barcode=None, matched=False,
            note="No barcode scanned; cross-verification skipped.",
        )

    clean_barcode = scanned_barcode.strip()
    gs1_prefix, gs1_country = resolve_gs1_prefix(clean_barcode)
    declared_origin = declared_fields.get("country_of_origin_declaration") or declared_fields.get("country_of_origin")
    origin_matches = check_origin_matches_barcode(gs1_country, declared_origin)

    product = repository.get_product_by_barcode(clean_barcode)
    if not product:
        note = "Barcode not found in reference products."
        if gs1_country:
            note += f" GS1 Prefix indicates: {gs1_country}."
        if origin_matches is False:
            note += f" Potential Origin Mismatch: GS1 is {gs1_country} but label says '{declared_origin}'."
        return BarcodeVerification(
            scanned_barcode=scanned_barcode, matched=False,
            note=note,
            gs1_prefix=gs1_prefix,
            gs1_country=gs1_country,
            origin_matches_barcode=origin_matches,
        )

    comparisons = [
        _compare_mrp(product.get("mrp"), declared_fields.get("mrp_declaration")),
        _compare_qty(product.get("net_quantity"),
                     declared_fields.get("net_quantity_declaration")),
        _compare_text("manufacturer", product.get("manufacturer"),
                      declared_fields.get("manufacturer_name_address")),
        _compare_text("country_of_origin", product.get("country_of_origin"),
                      declared_fields.get("country_of_origin_declaration")),
        _compare_text("fssai", product.get("fssai_number"),
                      declared_fields.get("fssai_license_number")),
    ]

    mismatches = [c.field for c in comparisons if c.status == "mismatch"]
    note = ("All comparable fields agree with the reference record."
            if not mismatches else
            f"Fields differing from reference: {', '.join(mismatches)}.")
    if origin_matches is False:
        note += f" Alert: GS1 country prefix is {gs1_country} but label claims '{declared_origin}'."

    return BarcodeVerification(
        scanned_barcode=scanned_barcode, matched=True,
        product_code=product.get("product_code"),
        product_name=product.get("name"),
        comparisons=comparisons, note=note,
        gs1_prefix=gs1_prefix,
        gs1_country=gs1_country,
        origin_matches_barcode=origin_matches,
    )
