"""Deterministic verification of the three Part D QA checkpoints.

Runs pure-logic checks (no OCR randomness) so the results are unambiguous.

  D1: OCR character cleansing for number fields only.
  D2/D7: category fallback isolation - 'general' skips FSSAI, no crash.
  D3: multi-line address merging into one block.
"""

from __future__ import annotations

from app.ocr.cleansing import cleanse_fields, cleanse_numeric_field
from app.ocr.reader import Word
from app.ocr.spatial import group_text
from app.rule_engine.engine import RuleEngine
from app.schemas.scan import ScanRequest


def check(label: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" :: {detail}" if detail else ""))
    return condition


def verify_d1() -> bool:
    print("\n=== D1: OCR character cleansing (number fields only) ===")
    ok = True

    # Confusable letters inside numbers get fixed.
    ok &= check("O->0 in price", cleanse_numeric_field("Rs. 1OO") == "Rs. 100",
                cleanse_numeric_field("Rs. 1OO"))
    ok &= check("l/I->1 in quantity", cleanse_numeric_field("2OOg") == "200g",
                cleanse_numeric_field("2OOg"))
    ok &= check("S->5 in number", cleanse_numeric_field("3S0g") == "350g",
                cleanse_numeric_field("3S0g"))

    # Only number fields are cleansed; name/address left intact.
    fields = {
        "mrp_declaration": "Rs. 4S",
        "net_quantity_declaration": "2OOg",
        "unit_sale_price_declaration": "Rs 22.SO per 1OOg",
        "manufacturer_name_address": "ABC Foods, Solapur",  # must NOT change
        "country_of_origin_declaration": "Made in India",
    }
    out = cleanse_fields(fields)
    ok &= check("mrp cleansed", out["mrp_declaration"] == "Rs. 45", out["mrp_declaration"])
    ok &= check("net qty cleansed", out["net_quantity_declaration"] == "200g",
                out["net_quantity_declaration"])
    ok &= check("usp cleansed", out["unit_sale_price_declaration"] == "Rs 22.50 per 100g",
                out["unit_sale_price_declaration"])
    ok &= check("manufacturer untouched (Solapur stays)",
                out["manufacturer_name_address"] == "ABC Foods, Solapur",
                out["manufacturer_name_address"])
    ok &= check("origin untouched",
                out["country_of_origin_declaration"] == "Made in India",
                out["country_of_origin_declaration"])
    return ok


def verify_d2() -> bool:
    print("\n=== D2/D7: category fallback isolation (general skips FSSAI) ===")
    ok = True
    engine = RuleEngine()
    # A food-ish request WITHOUT a valid FSSAI number.
    req = ScanRequest(
        scan_id="d2-test",
        mrp_declaration="MRP Rs. 90",
        net_quantity_declaration="200g",
        manufacturing_date_declaration="MAR 2026",
        expiry_date_declaration="MAR 2027",
        unit_sale_price_declaration="Rs 45 per 100g",
        manufacturer_name_address="ABC Foods, Pune 411001",
        country_of_origin_declaration="Made in India",
        consumer_care_details="care@abc.com, 1800-111-222",
        fssai_license_number="",  # missing
    )

    # general -> FSSAI check must be SKIPPED entirely, no crash.
    v_general = engine.evaluate(req, product_category="general")
    ok &= check("general: no fssai_license field present",
                "fssai_license" not in v_general.parsed_fields,
                str(list(v_general.parsed_fields.keys())))
    ok &= check("general: no FSSAI violation",
                all(vi.field != "fssai_license" for vi in v_general.violations))
    ok &= check("general: did not crash and produced a verdict",
                v_general.overall_status is not None)

    # food_and_beverage -> FSSAI check SHOULD run and flag the missing number.
    v_food = engine.evaluate(req, product_category="food_and_beverage")
    ok &= check("food: fssai_license field present",
                "fssai_license" in v_food.parsed_fields)
    ok &= check("food: FSSAI violation raised",
                any(vi.field == "fssai_license" for vi in v_food.violations))
    return ok


def verify_d3() -> bool:
    print("\n=== D3: multi-line address merging into one block ===")
    ok = True
    # Simulate OCR words on separate lines: an anchor line + 2 address lines
    # + a PIN line. Build Word boxes with increasing 'top' to mimic lines.
    def line_words(text: str, line_num: int, top: int) -> list[Word]:
        words = []
        left = 40
        for w in text.split():
            words.append(Word(text=w, left=left, top=top, width=len(w) * 14,
                              height=30, conf=90.0, line_num=line_num, block_num=1))
            left += len(w) * 16 + 12
        return words

    words: list[Word] = []
    words += line_words("Mfg by Beverage Co", 1, 40)
    words += line_words("12 Industrial Area", 2, 82)
    words += line_words("Bengaluru Karnataka", 3, 124)
    words += line_words("560002", 4, 166)

    grouped = group_text(words)
    block = grouped.manufacturer_block
    ok &= check("anchor 'Mfg by' present in block", "Mfg by" in block or "mfg by" in block.lower(), block)
    ok &= check("address line merged", "Industrial Area" in block, block)
    ok &= check("city merged", "Bengaluru" in block, block)
    ok &= check("PIN code merged into same block", "560002" in block, block)
    ok &= check("single block (no embedded newline)", "\n" not in block, repr(block))
    return ok


def main() -> None:
    d1 = verify_d1()
    d2 = verify_d2()
    d3 = verify_d3()
    print("\n==================== PART D SUMMARY ====================")
    print(f"D1 (numeric cleansing)      : {'PASS' if d1 else 'FAIL'}")
    print(f"D2/D7 (category isolation)  : {'PASS' if d2 else 'FAIL'}")
    print(f"D3 (address merging)        : {'PASS' if d3 else 'FAIL'}")
    print(f"ALL PART D: {'PASS' if (d1 and d2 and d3) else 'FAIL'}")


if __name__ == "__main__":
    main()
