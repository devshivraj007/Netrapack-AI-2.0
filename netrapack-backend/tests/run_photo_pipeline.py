"""Run the full Day 2 photo pipeline over synthetic (and real) label images.

For each image: product recognition -> OCR -> rule engine -> verdict.
Prints a compact per-image summary and the Part D verification results.

Usage (from netrapack-backend):
    .\.venv\Scripts\python.exe -m tests.run_photo_pipeline
Real photos: drop image files into tests/photos/ and they are included too.
"""

from __future__ import annotations

import glob
import json
import os

from app.services import scan_service
from tests.make_synthetic_labels import build_samples


def _summarise(verdict) -> dict:
    v = verdict.model_dump()
    ocr = v.get("ocr") or {}
    ai = v.get("ai_recognition") or {}
    meta = v.get("metadata") or {}
    return {
        "scan_id": v["scan_id"],
        "overall_status": v["overall_status"],
        "passed_of_checked": f"{v['rules_passed']}/{v['rules_checked']}",
        "violations": [vi["field"] for vi in v.get("violations", [])],
        "retake_required": ocr.get("retake_required"),
        "glare_pct": round((ocr.get("glare_fraction") or 0) * 100, 1),
        "deskew_deg": ocr.get("deskew_angle_deg"),
        "ocr_conf": ocr.get("mean_confidence"),
        "manufacturer_block": ocr.get("manufacturer_block"),
        "ai_category": ai.get("effective_category"),
        "ai_source": ai.get("ai_source"),
        "ai_confirmation": ai.get("confirmation_status"),
        "ai_model": meta.get("ai_model_used"),
        "ai_level": meta.get("ai_level"),
        "online_offline": meta.get("online_offline"),
        "processing_ms": meta.get("processing_ms"),
        "fields": {
            k: (r.get("raw_input") if isinstance(r, dict) else None)
            for k, r in (v.get("parsed_fields") or {}).items()
        },
    }


def main() -> None:
    results = []

    # Synthetic samples.
    for name, jpeg, expected in build_samples():
        verdict = scan_service.process_photo_scan(scan_id=f"syn-{name}",
                                                  image_bytes=jpeg)
        summary = _summarise(verdict)
        summary["_expected"] = expected
        results.append(summary)

    # Real photos, if any were dropped in.
    photo_dir = os.path.join(os.path.dirname(__file__), "photos")
    real = sorted(
        glob.glob(os.path.join(photo_dir, "*.jpg"))
        + glob.glob(os.path.join(photo_dir, "*.jpeg"))
        + glob.glob(os.path.join(photo_dir, "*.png"))
    )
    for path in real:
        with open(path, "rb") as f:
            jpeg = f.read()
        name = os.path.splitext(os.path.basename(path))[0]
        verdict = scan_service.process_photo_scan(scan_id=f"real-{name}",
                                                  image_bytes=jpeg)
        summary = _summarise(verdict)
        summary["_expected"] = "real photo"
        results.append(summary)

    print(json.dumps(results, indent=2, default=str))
    print(f"\nTOTAL IMAGES PROCESSED: {len(results)} "
          f"(synthetic + {len(real)} real)")


if __name__ == "__main__":
    main()
