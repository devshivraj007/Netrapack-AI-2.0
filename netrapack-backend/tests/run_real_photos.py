"""Run the full pipeline against the 42 REAL product photos and report:

  1. OCR accuracy  - per product, does OCR find the key fields (MRP, net qty,
     FSSAI) that the reference data says are on the pack? Scored against the
     back-of-pack photo (where declarations live) with front as fallback.
  2. Product recognition - the AI category/size/shape guess + which AI level.
  3. Barcode cross-verification - for products with a CONFIRMED barcode, feed
     that barcode in (a barcode scanner's job; Tesseract can't decode barcodes)
     and check the reference match + field comparison.

We pair NN_front.jpg + NN_back.jpg per product and OCR both, merging fields
(back-of-pack usually carries the legal declarations).

Usage:  python -u -m tests.run_real_photos   (set RECOGNIZE=0 to skip AI)
"""

from __future__ import annotations

import glob
import json
import os
import re

from app.ai.recognizer import ProductRecognizer, detect_online
from app.db import repository
from app.ocr.pipeline import run_ocr_pipeline
from app.services import barcode_verify

PHOTO_DIR = os.path.join(os.path.dirname(__file__), "photos")

# Set RECOGNIZE=0 to skip AI recognition (OCR + barcode only, much faster).
DO_RECOGNIZE = os.environ.get("RECOGNIZE", "1") != "0"

# Ground truth from the reference doc: which key fields SHOULD be readable, and
# the confirmed barcode (None if not confirmed). Used only for scoring.
# fields we expect to find text for: mrp / net_qty / fssai (True = present on pack)
GROUND_TRUTH = {
    "01": {"name": "Chheda's Banana Chips", "barcode": None,
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "02": {"name": "Amul PRO", "barcode": None,
           "expect": {"mrp": False, "net_qty": True, "fssai": True}},
    "03": {"name": "Kellogg's Corn Flakes", "barcode": "8901499008343",
           "expect": {"mrp": False, "net_qty": False, "fssai": False}},
    "04": {"name": "Maggi Ketchup", "barcode": None,
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "05": {"name": "MyFitness PB", "barcode": None,
           "expect": {"mrp": False, "net_qty": True, "fssai": False}},
    "06": {"name": "Balaji Bhel Mix", "barcode": "8906010504335",
           "expect": {"mrp": True, "net_qty": False, "fssai": True}},
    "07": {"name": "King Phool Makhana", "barcode": None,
           "expect": {"mrp": False, "net_qty": False, "fssai": False}},
    "08": {"name": "Kellogg's Chocos", "barcode": "8901499010728",
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "09": {"name": "Pintola Oats", "barcode": "8906136651951",
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "10": {"name": "Glucon-D", "barcode": "8901542001642",
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "11": {"name": "Coolberg", "barcode": None,
           "expect": {"mrp": False, "net_qty": True, "fssai": False}},
    "12": {"name": "Pepsi Zero", "barcode": "8902080000333",
           "expect": {"mrp": False, "net_qty": True, "fssai": True}},
    "13": {"name": "Hell Energy", "barcode": None,
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "14": {"name": "Monster Energy", "barcode": None,
           "expect": {"mrp": False, "net_qty": True, "fssai": False}},
    "15": {"name": "Parle B Fizz", "barcode": None,
           "expect": {"mrp": True, "net_qty": True, "fssai": True}},
    "16": {"name": "Motorola Edge 70", "barcode": "0840493611488",
           "expect": {"mrp": False, "net_qty": True, "fssai": False}},
    "17": {"name": "Johnson's Buds", "barcode": "8901012155080",
           "expect": {"mrp": False, "net_qty": True, "fssai": False}},
    "18": {"name": "Boost (worn)", "barcode": None,
           "expect": {"mrp": False, "net_qty": True, "fssai": True}},
    "19": {"name": "Derma Co Moisturizer", "barcode": "8906087779292",
           "expect": {"mrp": True, "net_qty": True, "fssai": False}},
    "20": {"name": "Portronics Mouse", "barcode": "8904336813858",
           "expect": {"mrp": True, "net_qty": True, "fssai": False}},
    "21": {"name": "Nescafe Classic", "barcode": None,
           "expect": {"mrp": True, "net_qty": False, "fssai": True}},
}


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _merge_fields(a: dict, b: dict) -> dict:
    """Merge two OCR field dicts; prefer any non-empty value across the pair."""
    out = {}
    keys = set(a) | set(b)
    for k in keys:
        out[k] = a.get(k) or b.get(k)
    return out


def _found(field_val) -> bool:
    return bool(field_val and str(field_val).strip())


def main() -> None:
    repository.reseed()
    recognizer = ProductRecognizer()
    online = detect_online()

    results = []
    ocr_hits = 0
    ocr_total = 0
    recog_used = {"local_ollama": 0, "cloud_gemini": 0, "none": 0}

    for num in sorted(GROUND_TRUTH):
        gt = GROUND_TRUTH[num]
        fronts = glob.glob(os.path.join(PHOTO_DIR, f"{num}_*front*.jpg"))
        backs = glob.glob(os.path.join(PHOTO_DIR, f"{num}_*back*.jpg"))
        if not fronts and not backs:
            continue

        # OCR both sides; the back usually carries declarations.
        front_res = run_ocr_pipeline(_read(fronts[0])) if fronts else None
        back_res = run_ocr_pipeline(_read(backs[0])) if backs else None

        fields = {}
        retake_flags = []
        confs = []
        for res, side in [(back_res, "back"), (front_res, "front")]:
            if res is None:
                continue
            if res.retake_required:
                retake_flags.append(side)
            if res.ok:
                fields = _merge_fields(fields, res.fields)
                confs.append(res.mean_conf)

        # Score OCR field discovery against expectation.
        per_field = {}
        for f_key, expected in gt["expect"].items():
            declared_key = {
                "mrp": "mrp_declaration",
                "net_qty": "net_quantity_declaration",
                "fssai": "fssai_license_number",
            }[f_key]
            got = _found(fields.get(declared_key))
            if expected:
                ocr_total += 1
                if got:
                    ocr_hits += 1
                per_field[f_key] = "found" if got else "MISSED"
            else:
                per_field[f_key] = ("found(unexpected)" if got else "n/a")

        # Product recognition on the front image (best product view).
        if DO_RECOGNIZE:
            recog_img = _read(fronts[0]) if fronts else _read(backs[0])
            rec = recognizer.recognize(recog_img)
            recog = {
                "category": rec.effective_category.value,
                "confidence": rec.confidence,
                "ai_source": rec.ai_source.value,
                "model": rec.model_name,
            }
            recog_used[rec.ai_source.value] = recog_used.get(rec.ai_source.value, 0) + 1
        else:
            recog = {"skipped": True}

        # Barcode cross-verification (only for confirmed barcodes).
        bc = None
        if gt["barcode"]:
            bv = barcode_verify.cross_verify(gt["barcode"], fields)
            bc = {
                "barcode": gt["barcode"],
                "matched": bv.matched,
                "product": bv.product_name,
                "note": bv.note,
                "field_status": {c.field: c.status for c in bv.comparisons},
            }

        entry = {
            "product": f"{num} {gt['name']}",
            "ocr_mean_conf": round(sum(confs) / len(confs), 1) if confs else 0.0,
            "retake_sides": retake_flags,
            "ocr_fields_found": per_field,
            "extracted": {
                "mrp": fields.get("mrp_declaration"),
                "net_qty": fields.get("net_quantity_declaration"),
                "fssai": fields.get("fssai_license_number"),
                "origin": fields.get("country_of_origin_declaration"),
            },
            "recognition": recog,
            "barcode_verification": bc,
        }
        results.append(entry)
        # Per-product progress line so we can watch it run.
        print(f"[done] {entry['product']}  conf={entry['ocr_mean_conf']}  "
              f"fields={per_field}  recog={recog.get('category', 'skipped')}"
              f"{'  barcode=MATCH' if bc and bc['matched'] else ''}", flush=True)

    summary = {
        "online": online,
        "products_tested": len(results),
        "ocr_field_recall": (f"{ocr_hits}/{ocr_total} "
                             f"({round(100*ocr_hits/ocr_total)}%)" if ocr_total else "n/a"),
        "recognition_sources": recog_used,
        "barcodes_confirmed": sum(1 for g in GROUND_TRUTH.values() if g["barcode"]),
    }
    print(json.dumps({"summary": summary, "results": results}, indent=2, default=str))


if __name__ == "__main__":
    main()
