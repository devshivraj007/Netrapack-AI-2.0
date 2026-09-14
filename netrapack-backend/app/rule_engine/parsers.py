"""Low-level text parsers shared by the rule-engine checks.

These are deliberately conservative: when input is ambiguous the parsers
report what they found rather than guessing, so callers can decide whether
to auto-resolve or flag for manual review.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------
# Canonical base units: mass -> grams, volume -> millilitres, count -> pieces,
# length -> metres. We normalise everything to a base so math is consistent.
MASS = "mass"
VOLUME = "volume"
COUNT = "count"
LENGTH = "length"

# unit token -> (dimension, factor to base unit)
_UNIT_TABLE: dict[str, tuple[str, float]] = {
    "kg": (MASS, 1000.0),
    "g": (MASS, 1.0),
    "gm": (MASS, 1.0),
    "gms": (MASS, 1.0),
    "gram": (MASS, 1.0),
    "grams": (MASS, 1.0),
    "mg": (MASS, 0.001),
    "l": (VOLUME, 1000.0),
    "ltr": (VOLUME, 1000.0),
    "litre": (VOLUME, 1000.0),
    "litres": (VOLUME, 1000.0),
    "liter": (VOLUME, 1000.0),
    "ml": (VOLUME, 1.0),
    "m": (LENGTH, 1.0),
    "metre": (LENGTH, 1.0),
    "meter": (LENGTH, 1.0),
    "cm": (LENGTH, 0.01),
    "piece": (COUNT, 1.0),
    "pieces": (COUNT, 1.0),
    "pc": (COUNT, 1.0),
    "pcs": (COUNT, 1.0),
    "unit": (COUNT, 1.0),
    "units": (COUNT, 1.0),
    "n": (COUNT, 1.0),
    # Common Indian label notations for single/counted items
    "no": (COUNT, 1.0),
    "nos": (COUNT, 1.0),
    "no.": (COUNT, 1.0),
    "nos.": (COUNT, 1.0),
    "number": (COUNT, 1.0),
    "item": (COUNT, 1.0),
    "items": (COUNT, 1.0),
    "pkt": (COUNT, 1.0),
    "pkts": (COUNT, 1.0),
    "packet": (COUNT, 1.0),
    "packets": (COUNT, 1.0),
}

_BASE_UNIT_LABEL = {MASS: "g", VOLUME: "ml", COUNT: "piece", LENGTH: "m"}


# ---------------------------------------------------------------------------
# Price parsing
# ---------------------------------------------------------------------------
# Matches numbers optionally attached to a currency marker. We capture the
# numeric value; currency symbols/words are treated as context only.
_PRICE_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_CURRENCY_CONTEXT_RE = re.compile(
    r"(?:₹|rs\.?|inr|mrp|price)\s*\.?\s*(\d+(?:\.\d+)?)", re.IGNORECASE
)


@dataclass
class PriceParseResult:
    prices: list[float] = field(default_factory=list)
    raw: Optional[str] = None

    @property
    def single(self) -> Optional[float]:
        return self.prices[0] if len(self.prices) == 1 else None

    @property
    def is_ambiguous(self) -> bool:
        return len(self.prices) > 1


def parse_prices(text: Optional[str]) -> PriceParseResult:
    """Extract distinct price candidates from MRP-style text.

    Strategy: prefer numbers that sit next to a currency marker (₹, Rs, INR,
    MRP). If none carry a currency marker, fall back to all bare numbers.
    Duplicates (the same value repeated) collapse to one candidate.
    """
    if not text or not text.strip():
        return PriceParseResult(prices=[], raw=text)

    currency_hits = [float(m) for m in _CURRENCY_CONTEXT_RE.findall(text)]
    if currency_hits:
        candidates = currency_hits
    else:
        candidates = [float(m) for m in _PRICE_NUMBER_RE.findall(text)]

    # Collapse exact duplicates while preserving order.
    seen: list[float] = []
    for value in candidates:
        if value not in seen:
            seen.append(value)
    return PriceParseResult(prices=seen, raw=text)


# ---------------------------------------------------------------------------
# Quantity parsing
# ---------------------------------------------------------------------------
_QTY_TOKEN_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*"
    r"(kg|g|gm|gms|gram|grams|mg"
    r"|l|ltr|litres?|liters?"
    r"|ml"
    r"|m|metres?|meters?|cm"
    r"|pieces?|pcs|pc"
    r"|units?"
    r"|packets?|pkts?|pkt"
    r"|nos?\.?|number"
    r"|items?"
    r"|n)\b",
    re.IGNORECASE,
)
_MULTIPACK_RE = re.compile(r"(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", re.IGNORECASE)
_BONUS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*\+\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)",
    re.IGNORECASE,
)


@dataclass
class QuantityParseResult:
    ok: bool = False
    pattern: str = "unknown"  # simple | multipack | bonus | unknown
    dimension: Optional[str] = None
    base_unit: Optional[str] = None
    # total_base: the full declared net quantity in base units (used for the
    # Net Quantity field itself). For a bonus pack this INCLUDES the extra.
    total_base: Optional[float] = None
    # paid_base: quantity the customer pays for, in base units. Equals
    # total_base except for bonus packs, where it excludes the free extra.
    # Used only for Unit Sale Price math.
    paid_base: Optional[float] = None
    display_total: Optional[str] = None
    display_paid: Optional[str] = None
    raw: Optional[str] = None
    error: Optional[str] = None


def _unit_lookup(token: str) -> Optional[tuple[str, float]]:
    return _UNIT_TABLE.get(token.lower())


def _fmt(value: float, dimension: str) -> str:
    label = _BASE_UNIT_LABEL[dimension]
    if value == int(value):
        return f"{int(value)}{label}"
    return f"{value:g}{label}"


def parse_quantity(text: Optional[str]) -> QuantityParseResult:
    """Parse a net-quantity declaration.

    Handles three patterns:
      * simple:    "200g"            -> total = paid = 200g
      * multipack: "3 x 50g"         -> total = paid = 150g
      * bonus:     "100g + 20g extra" -> total = 120g, paid = 100g
    """
    if not text or not text.strip():
        return QuantityParseResult(ok=False, raw=text, error="empty")

    cleaned = text.strip()

    # --- Bonus pattern: "100g + 20g extra" ---------------------------------
    bonus = _BONUS_RE.search(cleaned)
    if bonus:
        v1, u1, v2, u2 = bonus.groups()
        lu1, lu2 = _unit_lookup(u1), _unit_lookup(u2)
        if lu1 and lu2 and lu1[0] == lu2[0]:
            dim = lu1[0]
            paid = float(v1) * lu1[1]
            extra = float(v2) * lu2[1]
            total = paid + extra
            return QuantityParseResult(
                ok=True,
                pattern="bonus",
                dimension=dim,
                base_unit=_BASE_UNIT_LABEL[dim],
                total_base=total,
                paid_base=paid,
                display_total=_fmt(total, dim),
                display_paid=_fmt(paid, dim),
                raw=text,
            )
        return QuantityParseResult(
            ok=False, pattern="bonus", raw=text, error="bonus units mismatch or unknown"
        )

    # --- Multipack pattern: "3 x 50g" -------------------------------------
    multi = _MULTIPACK_RE.search(cleaned)
    if multi:
        count_str, per_str, unit = multi.groups()
        lu = _unit_lookup(unit)
        if lu:
            dim = lu[0]
            total = float(count_str) * float(per_str) * lu[1]
            return QuantityParseResult(
                ok=True,
                pattern="multipack",
                dimension=dim,
                base_unit=_BASE_UNIT_LABEL[dim],
                total_base=total,
                paid_base=total,
                display_total=_fmt(total, dim),
                display_paid=_fmt(total, dim),
                raw=text,
            )
        return QuantityParseResult(
            ok=False, pattern="multipack", raw=text, error="unknown unit"
        )

    # --- Simple pattern: "200g" -------------------------------------------
    token = _QTY_TOKEN_RE.search(cleaned)
    if token:
        value, unit = token.groups()
        lu = _unit_lookup(unit)
        if lu:
            dim = lu[0]
            total = float(value) * lu[1]
            return QuantityParseResult(
                ok=True,
                pattern="simple",
                dimension=dim,
                base_unit=_BASE_UNIT_LABEL[dim],
                total_base=total,
                paid_base=total,
                display_total=_fmt(total, dim),
                display_paid=_fmt(total, dim),
                raw=text,
            )
        return QuantityParseResult(ok=False, pattern="simple", raw=text, error="unknown unit")

    return QuantityParseResult(ok=False, pattern="unknown", raw=text, error="no quantity found")


# ---------------------------------------------------------------------------
# Date parsing (Month + Year only)
# ---------------------------------------------------------------------------
_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_DMY_RE = re.compile(r"\b(?:[0-2]?[0-9]|3[01])\s*[/\-.]\s*(0?[1-9]|1[0-2])\s*[/\-.]\s*(\d{2,4})\b")
_MM_YYYY_RE = re.compile(r"\b(0?[1-9]|1[0-2])\s*[/\-.]\s*(\d{2,4})\b")
_MON_YYYY_RE = re.compile(r"\b(?:(?:[0-2]?[0-9]|3[01])\s*[/\-.\s]\s*)?([A-Za-z]{3,9})\.?\s*[/\-.\s]?\s*(\d{2,4})\b")
_BEST_BEFORE_RE = re.compile(
    r"(?:best\s*before|use\s*by|use\s*within|bb|expiry\s*within)\s*(\d+)\s*(months?|days?|weeks?|yrs?|years?)",
    re.IGNORECASE,
)


@dataclass
class DateParseResult:
    ok: bool = False
    month: Optional[int] = None
    year: Optional[int] = None
    raw: Optional[str] = None
    error: Optional[str] = None
    is_best_before_statement: bool = False
    best_before_duration: Optional[str] = None

    def as_first_of_month(self) -> Optional[date]:
        if self.ok and self.month and self.year:
            return date(self.year, self.month, 1)
        return None

    def as_last_of_month(self) -> Optional[date]:
        if self.ok and self.month and self.year:
            last = calendar.monthrange(self.year, self.month)[1]
            return date(self.year, self.month, last)
        return None


def parse_month_year(text: Optional[str]) -> DateParseResult:
    """Parse a date or best-before declaration.

    Handles real Indian retail packaging variations (Amul, Britannia, etc.):
      1. Best-before duration: e.g. "Best before 9 months from packaging",
         "BEST BEFORE 180 DAYS FROM PKG".
      2. Full dates: "PKD 15/01/2026", "Packed: 05/02/26".
      3. Standard Month+Year: "03/2026", "02/26", "MAR 2026", "15-MAR-26".
      4. Stamped alphanumeric dates: "PKD 07/AUG/26", "Exp: 03/FEB/27".
    Day is not required by law (LMPC Rule 6(1)(c)), but if printed, month+year
    are cleanly extracted.
    """
    if not text or not text.strip():
        return DateParseResult(ok=False, raw=text, error="empty")

    cleaned = text.strip()

    # 1. Best Before duration statement
    bb_m = _BEST_BEFORE_RE.search(cleaned)
    if bb_m:
        duration = f"{bb_m.group(1)} {bb_m.group(2).lower()}"
        return DateParseResult(
            ok=True,
            is_best_before_statement=True,
            best_before_duration=duration,
            raw=text,
        )

    # 2. DD/MM/YYYY or DD/MM/YY (must check before MM/YY to avoid ambiguity)
    m = _DMY_RE.search(cleaned)
    if m:
        mo = int(m.group(1))
        yr = int(m.group(2))
        if yr < 100:
            yr += 2000
        return DateParseResult(ok=True, month=mo, year=yr, raw=text)

    # 3. MM/YYYY or MM/YY
    m = _MM_YYYY_RE.search(cleaned)
    if m:
        mo = int(m.group(1))
        yr = int(m.group(2))
        if yr < 100:
            yr += 2000
        return DateParseResult(ok=True, month=mo, year=yr, raw=text)

    # 4. Worded month / stamped alphanumeric dates: "PKD 07/AUG/26", "MAR 2026", "15-MAR-26", "Exp: 03/FEB/27"
    for m in _MON_YYYY_RE.finditer(cleaned):
        name = m.group(1).lower()
        if name in _MONTHS:
            yr = int(m.group(2))
            if yr < 100:
                yr += 2000
            return DateParseResult(ok=True, month=_MONTHS[name], year=yr, raw=text)

    return DateParseResult(ok=False, raw=text, error="not a recognised Month+Year or Best Before format")


# ---------------------------------------------------------------------------
# Contact + FSSAI patterns
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Phone: at least 8 digits, allowing separators, optional +country/toll-free.
_PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s]{7,}\d)")
# FSSAI: a run of exactly 14 digits (not part of a longer number run).
_FSSAI_14_RE = re.compile(r"(?<!\d)(\d{14})(?!\d)")


def find_email(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else None


def find_phone(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    # Avoid matching an email's digits: strip emails before phone search.
    scrubbed = _EMAIL_RE.sub(" ", text)
    m = _PHONE_RE.search(scrubbed)
    if not m:
        return None
    candidate = m.group(0)
    digit_count = sum(ch.isdigit() for ch in candidate)
    return candidate.strip() if digit_count >= 8 else None


def find_fssai_14(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _FSSAI_14_RE.search(text)
    return m.group(1) if m else None


def mentions_fssai(text: Optional[str]) -> bool:
    return bool(text) and "fssai" in text.lower()
