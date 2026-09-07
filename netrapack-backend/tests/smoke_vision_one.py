"""Smoke test: vision extraction on ONE product (08 Kellogg's Chocos)."""
from __future__ import annotations

import glob
import json
import os

from app.db import repository
from app.services import scan_service

PHOTO_DIR = os.path.join(os.path.dirname(__file__), "photos")


def _read(p):
    with open(p, "rb") as f:
        return f.read()


def main() -> None:
    repository.reseed()
    fronts = glob.glob(os.path.join(PHOTO_DIR, "08_*front*.jpg"))
    backs = glob.glob(os.path.join(PHOTO_DIR, "08_*back*.jpg"))
    images = [_read(fronts[0])] + ([_read(backs[0])] if backs else [])
    v = scan_service.process_photo_scan_multi("smoke-08", images,
                                             barcode="8901499010728").model_dump()
    print(json.dumps({
        "overall_status": v["overall_status"],
        "rules_passed": v["rules_passed"],
        "rules_checked": v["rules_checked"],
        "violations": [x["field"] for x in v.get("violations", [])],
        "extraction_source": (v.get("metadata") or {}).get("extraction_source"),
        "model": (v.get("metadata") or {}).get("ai_model_used"),
        "processing_ms": (v.get("metadata") or {}).get("processing_ms"),
        "category": (v.get("ai_recognition") or {}).get("category"),
        "vision_extraction": v.get("vision_extraction"),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
