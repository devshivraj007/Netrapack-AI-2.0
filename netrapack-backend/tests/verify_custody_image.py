"""Verify image-hash chain-of-custody directly (no slow vision call).

Stores a raw image + hash into the scans table exactly as the scan service
does, then runs the verify script's hash check. Also verifies tamper detection
(mutating the stored file makes verification FAIL).
"""
from __future__ import annotations

import hashlib

from app.db import repository
from app.services.scan_service import _store_image
from scripts.verify_chain_of_custody import verify_image_hash
from tests.make_synthetic_labels import build_samples


def main() -> None:
    repository.reseed()
    _, jpeg, _ = build_samples()[0]
    scan_id = "custody-img-1"

    # Replicate the custody step the scan service performs.
    image_hash, image_path = _store_image(scan_id, jpeg)
    verdict = {
        "scan_id": scan_id, "overall_status": "fully_compliant",
        "rules_passed": 6, "rules_checked": 6, "violations": [],
        "metadata": {"processing_ms": 1.0},
        "ai_recognition": {"effective_category": "food_and_beverage"},
    }
    repository.insert_scan(verdict, input_mode="photo",
                           image_hash=image_hash, image_path=image_path)
    print(f"stored hash: {image_hash[:16]}  path set: {bool(image_path)}")

    print("\n=== verify_image_hash (intact) ===")
    ok_intact = verify_image_hash(scan_id)

    # Tamper test: modify the stored file and confirm verification FAILS.
    print("\n=== tamper test (append a byte) ===")
    with open(image_path, "ab") as f:
        f.write(b"\x00")
    ok_tamper = verify_image_hash(scan_id)  # should be False now

    passed = ok_intact and (ok_tamper is False)
    print("\nCUSTODY IMAGE VERIFY:", "PASS" if passed else "FAIL",
          "(intact matches, tamper detected)")


if __name__ == "__main__":
    main()
