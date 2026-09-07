"""Turn grouped OCR text into the labelled fields the rule engine expects.

We scan the OCR lines for keyword anchors (MRP, Net Qty, Mfg, Best Before,
FSSAI, etc.) and pull the associated value. The manufacturer/address block is
taken from the spatial grouping step (already merged into one line, per Part D
#3). Number fields are then cleansed (Part D #1) by the pipeline before the
rule engine runs.

This is intentionally forgiving: OCR text is messy. Anything we cannot find is
left as None, and the rule engine already treats missing fields correctly.
"""

from __future__ import annotations

import re
from typing import Optional

from .spatial import GroupedText

# Keyword patterns -> which field they introduce.
_MRP_RE = re.compile(r"(?:m\.?r\.?p\.?|maximum retail price)\b(.*)", re.IGNORECASE)
_NET_QTY_RE = re.compile(
    r"(?:net\s*(?:qty|quantity|wt|weight|content|contents))\b(.*)", re.IGNORECASE
)
_USP_RE = re.compile(
    r"(?:unit sale price|price per|per\s*100\s*(?:g|ml)|per\s*(?:kg|l|litre))\b(.*)",
    re.IGNORECASE,
)
_MFG_RE = re.compile(
    r"(?:mfg\.?\s*(?:date)?|mfd\.?|manufactured on|date of (?:mfg|manufacture)|packed on)\b(.*)",
    re.IGNORECASE,
)
_EXP_RE = re.compile(
    r"(?:exp\.?\s*(?:date)?|expiry|best before|use by|bb)\b(.*)", re.IGNORECASE
)
_ORIGIN_RE = re.compile(
    r"(?:made in|product of|manufactured in|produce of|country of origin)\b.*",
    re.IGNORECASE,
)
_CARE_RE = re.compile(
    r"(?:consumer care|customer care|for complaints|helpline|toll[- ]?free|email|e-mail)\b(.*)",
    re.IGNORECASE,
)
_FSSAI_RE = re.compile(r"(?:fssai|lic(?:\.|ense)?\s*no)\b(.*)", re.IGNORECASE)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s]{7,}\d)")
_FSSAI_NUM_RE = re.compile(r"(?<!\d)(\d{14})(?!\d)")

# A date token: a month word or an MM/YYYY-style number. Used to make sure a
# "Mfg ..." line actually carries a date before we treat it as the mfg date -
# otherwise "Mfg by ABC Foods" (a manufacturer line) is wrongly captured.
_DATE_TOKEN_RE = re.compile(
    r"(?:\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b"
    r"|\b(?:0?[1-9]|1[0-2])\s*[/\-.]\s*\d{4}\b"
    r"|\b\d{4}\b)",
    re.IGNORECASE,
)


# --- Full-text fallback patterns (label and value may be separated) ---------
# Real packs often split the label from its value across OCR lines, use comma
# decimals ("210,00"), or embed the value in a phrase. These search the whole
# combined text and capture the value directly.

# MRP: "MRP ... 210.00" / "M.R.P Rs 75" / "₹ 210,00". Allow up to a few chars
# (Rs, ₹, :, spaces) between the keyword and the number.
_MRP_VALUE_RE = re.compile(
    r"m\.?\s*r\.?\s*p\.?[^0-9]{0,12}(\d{1,5}(?:[.,]\d{1,2})?)", re.IGNORECASE
)
# Net quantity value: "NET WEIGHT ... 385 g" / "Net Qty 150g" / "500 ml".
_NETQTY_VALUE_RE = re.compile(
    r"net\s*(?:qty|quantity|wt|weight|content|contents)[^0-9]{0,12}"
    r"(\d{1,5}(?:\.\d+)?\s*(?:kg|g|gm|gms|ml|l|ltr|litre|litres|n|units?|pcs?|piece)\b)",
    re.IGNORECASE,
)
# Bare quantity anywhere (fallback): a number tightly followed by a unit.
_BARE_QTY_RE = re.compile(
    r"\b(\d{1,5}(?:\.\d+)?\s*(?:kg|g|gm|gms|ml|l|ltr|litre|litres)\b)", re.IGNORECASE
)
# USP: "0.55 per g" / "Rs 55 per 100 g" / "₹0,50/g".
_USP_VALUE_RE = re.compile(
    r"(?:rs|₹)?\s*(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:/|per)\s*(?:100\s*)?(?:g|ml|kg|l)\b",
    re.IGNORECASE,
)
# Origin phrase captured directly.
_ORIGIN_VALUE_RE = re.compile(
    r"(?:made in|product of|produce of|country of origin[:\s]*)\s*"
    r"([A-Za-z][A-Za-z .'\-]{2,30})",
    re.IGNORECASE,
)


def _first_match_value(
    lines: list[str], pattern: re.Pattern, require: Optional[re.Pattern] = None
) -> Optional[str]:
    """Return the first line where `pattern` matches.

    If `require` is given, the line must ALSO contain that pattern (used to make
    date fields require an actual date token on the line).
    """
    for line in lines:
        if pattern.search(line) and (require is None or require.search(line)):
            return line.strip()
    return None


def _search_value(text: str, pattern: re.Pattern) -> Optional[str]:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def extract_fields(grouped: GroupedText) -> dict[str, Optional[str]]:
    """Map grouped OCR text to ScanRequest field names."""
    lines = grouped.lines or grouped.full_text.splitlines()
    flat = [ln.strip() for ln in lines if ln.strip()]

    fields: dict[str, Optional[str]] = {
        "mrp_declaration": _first_match_value(flat, _MRP_RE),
        "net_quantity_declaration": _first_match_value(flat, _NET_QTY_RE),
        "unit_sale_price_declaration": _first_match_value(flat, _USP_RE),
        "manufacturing_date_declaration": _first_match_value(
            flat, _MFG_RE, require=_DATE_TOKEN_RE),
        "expiry_date_declaration": _first_match_value(
            flat, _EXP_RE, require=_DATE_TOKEN_RE),
        "country_of_origin_declaration": _first_match_value(flat, _ORIGIN_RE),
        # Manufacturer block comes from spatial grouping (already merged).
        "manufacturer_name_address": grouped.manufacturer_block or None,
        "consumer_care_details": _first_match_value(flat, _CARE_RE),
        "fssai_license_number": _first_match_value(flat, _FSSAI_RE),
    }

    # --- Full-text fallback for fields the per-line pass missed. Real labels
    # often separate the keyword from its value; search the whole combined text.
    joined_full = " ".join(flat)

    if not fields["mrp_declaration"]:
        v = _search_value(joined_full, _MRP_VALUE_RE)
        if v:
            fields["mrp_declaration"] = f"MRP {v}"

    if not fields["net_quantity_declaration"]:
        v = _search_value(joined_full, _NETQTY_VALUE_RE)
        if not v:
            v = _search_value(joined_full, _BARE_QTY_RE)
        if v:
            fields["net_quantity_declaration"] = v

    if not fields["unit_sale_price_declaration"]:
        m = _USP_VALUE_RE.search(joined_full)
        if m:
            fields["unit_sale_price_declaration"] = m.group(0).strip()

    if not fields["country_of_origin_declaration"]:
        m = _ORIGIN_VALUE_RE.search(joined_full)
        if m:
            fields["country_of_origin_declaration"] = m.group(0).strip()

    # Consumer care: if no explicit "care" line, salvage any email/phone found.
    # Strip any 14-digit FSSAI number first so it is not mistaken for a phone.
    if not fields["consumer_care_details"]:
        joined = " ".join(flat)
        phone_search_space = _FSSAI_NUM_RE.sub(" ", joined)
        email = _EMAIL_RE.search(joined)
        phone = _PHONE_RE.search(phone_search_space)
        parts = [p.group(0).strip() for p in (email, phone) if p]
        if parts:
            fields["consumer_care_details"] = ", ".join(parts)

    # FSSAI: if we saw a bare 14-digit number anywhere, keep it even without a
    # keyword, so a valid licence is not lost.
    if not fields["fssai_license_number"]:
        joined = " ".join(flat)
        num = _FSSAI_NUM_RE.search(joined)
        if num:
            fields["fssai_license_number"] = f"FSSAI {num.group(1)}"

    return fields
