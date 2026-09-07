"""Day 3 benchmark: Vision AI structured extraction across the 21 real products.

For each product we pass front + back to the full pipeline
(process_photo_scan_multi) and score:
  * category accuracy   - AI category vs expected category from the ref doc
  * field extraction recall - of the fields the ref doc says are ON the pack
    (mrp / net_quantity / fssai / country_of_origin), how many did vision read?
  * latency             - processing_ms per scan

Prints a per-product line as it runs, then a summary block.
Usage:  python -u -m tests.benchmark_vision
"""

from __future__ import annotations

import glob
import json
import os

from app.db import repository
from app.services import scan_service

PHOTO_DIR = os.path.join(os.path.dirname(__file__), "photos")

# Ground truth from the reference doc. expected_category is the true category;
# expect_fields lists the fields that ARE printed on the pack (so we can score
# recall honestly - we only score fields that should be findable).
GT = {
    "01": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["mrp", "net_quantity", "fssai", "country_of_origin"]},
    "02": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["net_quantity", "fssai"]},
    "03": {"cat": "food_and_beverage", "barcode": "8901499008343",
           "expect": ["country_of_origin"]},
    "04": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["mrp", "net_quantity", "fssai"]},
    "05": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["net_quantity"]},
    "06": {"cat": "food_and_beverage", "barcode": "8906010504335",
           "expect": ["mrp", "fssai"]},
    "07": {"cat": "food_and_beverage", "barcode": None, "expect": []},
    "08": {"cat": "food_and_beverage", "barcode": "8901499010728",
           "expect": ["mrp", "net_quantity", "fssai", "country_of_origin"]},
    "09": {"cat": "food_and_beverage", "barcode": "8906136651951",
           "expect": ["mrp", "net_quantity", "fssai", "country_of_origin"]},
    "10": {"cat": "food_and_beverage", "barcode": "8901542001642",
           "expect": ["mrp", "net_quantity", "fssai", "country_of_origin"]},
    "11": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["net_quantity"]},
    "12": {"cat": "food_and_beverage", "barcode": "8902080000333",
           "expect": ["net_quantity", "fssai"]},
    "13": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["mrp", "net_quantity", "fssai", "country_of_origin"]},
    "14": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["net_quantity"]},
    "15": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["mrp", "net_quantity", "fssai"]},
    "16": {"cat": "electronics", "barcode": "0840493611488",
           "expect": ["net_quantity", "country_of_origin"]},
    "17": {"cat": "personal_care", "barcode": "8901012155080",
           "expect": ["net_quantity"]},
    "18": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["net_quantity", "fssai"]},
    "19": {"cat": "personal_care", "barcode": "8906087779292",
           "expect": ["mrp", "net_quantity"]},
    "20": {"cat": "electronics", "barcode": "8904336813858",
           "expect": ["mrp", "net_quantity", "country_of_origin"]},
    "21": {"cat": "food_and_beverage", "barcode": None,
           "expect": ["mrp", "fssai"]},
}

# Map ground-truth field keys -> the vision_extraction JSON keys.
_VKEY = {
    "mrp": "mrp",
    "net_quantity": "net_quantity",
    "fssai": "fssai_license_number",
    "country_of_origin": "country_of_origin",
}


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


RESULTS_FILE = os.path.join(os.path.dirname(__file__), "..", "bench_results.txt")


def _log(line: str) -> None:
    """Write a line to the results file immediately (own our output, not shell)."""
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    repository.reseed()
    # Truncate the results file at start.
    open(RESULTS_FILE, "w", encoding="utf-8").close()

    results = []
    cat_correct = 0
    cat_total = 0
    recall_hits = 0
    recall_total = 0
    latencies = []

    for num in sorted(GT):
        gt = GT[num]
        fronts = glob.glob(os.path.join(PHOTO_DIR, f"{num}_*front*.jpg"))
        backs = glob.glob(os.path.join(PHOTO_DIR, f"{num}_*back*.jpg"))
        images = []
        if fronts:
            images.append(_read(fronts[0]))
        if backs:
            images.append(_read(backs[0]))
        if not images:
            continue

        verdict = scan_service.process_photo_scan_multi(
            scan_id=f"bench-{num}", images=images, barcode=gt["barcode"])
        v = verdict.model_dump()
        ve = v.get("vision_extraction") or {}
        meta = v.get("metadata") or {}
        ai = v.get("ai_recognition") or {}

        # Category scoring.
        predicted = ai.get("category")
        cat_total += 1
        cat_ok = (predicted == gt["cat"])
        if cat_ok:
            cat_correct += 1

        # Field recall scoring (only fields expected on the pack).
        field_status = {}
        for f_key in gt["expect"]:
            recall_total += 1
            got = ve.get(_VKEY[f_key]) is not None
            if got:
                recall_hits += 1
            field_status[f_key] = "found" if got else "MISSED"

        ms = meta.get("processing_ms") or 0
        latencies.append(ms)

        results.append({
            "product": num,
            "category_pred": predicted,
            "category_expected": gt["cat"],
            "category_ok": cat_ok,
            "extraction_source": meta.get("extraction_source"),
            "model": meta.get("ai_model_used"),
            "field_recall": field_status,
            "extracted": {
                "mrp": ve.get("mrp"),
                "net_quantity": ve.get("net_quantity"),
                "fssai": ve.get("fssai_license_number"),
                "origin": ve.get("country_of_origin"),
            },
            "processing_ms": ms,
        })
        _log(f"[{num}] cat={predicted}/{gt['cat']} "
             f"{'OK' if cat_ok else 'X'}  recall={field_status}  "
             f"src={meta.get('extraction_source')}  model={meta.get('ai_model_used')}  "
             f"{round(ms)}ms  extracted={json.dumps(ve if isinstance(ve, dict) else {}, default=str)}")

    summary = {
        "products": len(results),
        "category_accuracy": (f"{cat_correct}/{cat_total} "
                              f"({round(100*cat_correct/cat_total)}%)" if cat_total else "n/a"),
        "field_recall": (f"{recall_hits}/{recall_total} "
                         f"({round(100*recall_hits/recall_total)}%)" if recall_total else "n/a"),
        "avg_processing_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "max_processing_ms": round(max(latencies)) if latencies else 0,
    }
    _log("\nSUMMARY " + json.dumps(summary, default=str))
    print("\n" + json.dumps({"summary": summary, "results": results}, indent=2, default=str))


if __name__ == "__main__":
    main()
