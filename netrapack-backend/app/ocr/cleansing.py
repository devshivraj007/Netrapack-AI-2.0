"""Part D #1: OCR character cleansing for NUMBER fields only.

OCR commonly misreads some letters as similar digits. In fields that are meant
to be numeric (MRP, net quantity), we correct these specific mix-ups BEFORE the
rule engine parses them, so a genuine price/quantity is not rejected or
miscalculated because a letter was read instead of a digit:

    O / o  ->  0
    l / I  ->  1
    S      ->  5

Crucially this is applied ONLY to number-bearing fields, never to name/address
fields, so we never corrupt words like "Foods" into "F00d5".
"""

from __future__ import annotations

import re

# Map of letter -> digit for the specific documented OCR confusions.
_DIGIT_CONFUSIONS = {
    "O": "0", "o": "0",
    "l": "1", "I": "1",
    "S": "5",
}


def cleanse_numeric_field(text: str | None) -> str | None:
    """Fix letter/digit confusions, but only where they sit inside a number.

    We only substitute a confusable letter when it is adjacent to a digit or
    another confusable letter, so units and stray words stay intact. For
    example: "Rs. lOO" -> "Rs. 100", but the "Rs" is left alone.
    """
    if text is None:
        return None
    if not text:
        return text

    chars = list(text)
    n = len(chars)

    def is_digit_context(idx: int) -> bool:
        # Look at neighbours to decide if this position is inside a number run.
        for j in (idx - 1, idx + 1):
            if 0 <= j < n:
                c = chars[j]
                if c.isdigit() or c in _DIGIT_CONFUSIONS:
                    return True
        return False

    for i, c in enumerate(chars):
        if c in _DIGIT_CONFUSIONS and is_digit_context(i):
            chars[i] = _DIGIT_CONFUSIONS[c]

    return "".join(chars)


# Fields that should receive numeric cleansing. Everything else is left as-is.
NUMERIC_FIELDS = {"mrp_declaration", "net_quantity_declaration",
                  "unit_sale_price_declaration"}


def cleanse_fields(fields: dict[str, str | None]) -> dict[str, str | None]:
    """Return a copy of `fields` with numeric fields cleansed.

    Non-numeric fields (manufacturer, origin, consumer care, FSSAI, dates) are
    returned unchanged so we never turn letters into digits where letters are
    legitimate. (FSSAI is validated as a strict 14-digit run by the rule engine
    itself, so we deliberately do not pre-mangle it here.)
    """
    out = dict(fields)
    for key in NUMERIC_FIELDS:
        if key in out:
            out[key] = cleanse_numeric_field(out[key])
    return out
