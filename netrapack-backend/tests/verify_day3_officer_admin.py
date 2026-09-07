"""Verify Day 3 Officer gate + Section 36 PDF + Admin sync end-to-end.

Uses the FastAPI app in-process (TestClient) so no server/network needed.
Flow:
  1. Create a non-compliant scan via /scan/process (text mode).
  2. Attempt /officer/generate-notice -> expect HTTP 403 (category unconfirmed).
  3. /officer/confirm-category -> inspector_confirmed.
  4. /officer/generate-notice -> expect 200 + PDF saved to storage/notices.
  5. /admin/reports with status filter -> the scan appears.
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.db import repository
from app.main import app


def main() -> None:
    # Ensure schema (incl. category_confirmations) exists before testing.
    repository.reseed()
    ok = True
    with TestClient(app) as client:
        ok = _run(client)
    print("\nDAY3 OFFICER/ADMIN:", "PASS" if ok else "FAIL")


def _run(client) -> bool:
    ok = True

    # 1) A non-compliant scan (missing FSSAI on a food product etc.).
    scan_id = "day3-officer-001"
    scan_req = {
        "scan_id": scan_id,
        "mrp_declaration": "MRP Rs. 200",
        "net_quantity_declaration": "500g",
        "manufacturing_date_declaration": "2026",       # invalid -> violation
        "unit_sale_price_declaration": "Rs 25 per 100g", # mismatch -> violation
        "manufacturer_name_address": "Mystery Brand",
        "country_of_origin_declaration": "Premium quality",  # no origin phrase
        "consumer_care_details": "Visit our stores",         # no phone/email
        "fssai_license_number": "",
    }
    r = client.post("/api/v1/scan/process", json=scan_req)
    print("1) scan status:", r.status_code, "overall:",
          r.json().get("overall_status"))
    ok &= r.status_code == 200

    # 2) Notice before confirmation -> must be 403.
    notice_req = {
        "scan_id": scan_id,
        "shop_name": "Testmart, MG Road",
        "inspector_id": "INSP-042",
        "gps_coordinates": "19.0760,72.8777",
        "product_barcode": "8901499010728",
    }
    r = client.post("/api/v1/officer/generate-notice", json=notice_req)
    print("2) generate-notice (unconfirmed):", r.status_code,
          "(expect 403)")
    ok &= r.status_code == 403

    # 3) Confirm category.
    r = client.post("/api/v1/officer/confirm-category", json={
        "scan_id": scan_id,
        "confirmed_category": "food_and_beverage",
        "inspector_id": "INSP-042",
    })
    print("3) confirm-category:", r.status_code, r.json().get("status"))
    ok &= r.status_code == 200 and r.json().get("status") == "inspector_confirmed"

    # 4) Notice after confirmation -> 200 + file exists.
    r = client.post("/api/v1/officer/generate-notice", json=notice_req)
    print("4) generate-notice (confirmed):", r.status_code)
    ok &= r.status_code == 200
    if r.status_code == 200:
        body = r.json()
        path = body.get("file_path")
        exists = bool(path and os.path.exists(path))
        print("   PDF saved:", exists, "| sha256:", body.get("evidence_sha256", "")[:16],
              "| violations:", body.get("violations_count"))
        ok &= exists

    # 5) Admin reports with status filter.
    r = client.get("/api/v1/admin/reports", params={"status": "non_compliant"})
    print("5) admin/reports non_compliant count:", r.json().get("count"))
    ok &= r.status_code == 200 and any(
        row["scan_id"] == scan_id for row in r.json().get("reports", []))

    return ok


if __name__ == "__main__":
    main()
