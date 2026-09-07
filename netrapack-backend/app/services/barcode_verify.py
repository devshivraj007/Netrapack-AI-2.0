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


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


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

    product = repository.get_product_by_barcode(scanned_barcode.strip())
    if not product:
        return BarcodeVerification(
            scanned_barcode=scanned_barcode, matched=False,
            note="Barcode not found in reference products (no confident match).",
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

    return BarcodeVerification(
        scanned_barcode=scanned_barcode, matched=True,
        product_code=product.get("product_code"),
        product_name=product.get("name"),
        comparisons=comparisons, note=note,
    )
