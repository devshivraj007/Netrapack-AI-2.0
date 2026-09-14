"""End-to-end integration test verifying the full NetraPack compliance workflow:
1. Officer Login & Authentication
2. Scan ingestion & Rule Engine evaluation
3. Statutory Compliance Report PDF generation & download (/scan/{scan_id}/report-pdf)
4. Officer Category Confirmation & Section 36 Notice Generation
5. Section 36 Notice PDF download & validation
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import repository


def test_full_e2e_flow():
    repository.reseed()
    with TestClient(app) as client:
        # 1. Test officer login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"username": "officer", "password": "netra123"}
        )
        assert login_res.status_code == 200, login_res.text
        data = login_res.json()
        assert data.get("role") == "officer"
        token = data["token"]

        # 2. Test scan processing
        scan_payload = {
            "scan_id": "test-e2e-001",
            "barcode": "8901234567890",
            "mrp_declaration": "MRP Rs. 50 (incl. of all taxes)",
            "net_quantity_declaration": "200g",
            "unit_sale_price_declaration": "Rs 25.00 per 100g",
            "manufacturing_date_declaration": "01/2026",
            "expiry_date_declaration": "12/2026",
            "fssai_license_number": "10014011001234",
            "manufacturer_name_address": "ABC Foods Pvt Ltd, Delhi 110001",
            "country_of_origin_declaration": "Made in India",
            "consumer_care_details": "care@abcfoods.com"
        }
        scan_res = client.post("/api/v1/scan/process", json=scan_payload)
        assert scan_res.status_code == 200, scan_res.text
        verdict = scan_res.json()
        assert "overall_status" in verdict
        assert verdict.get("scan_id") == "test-e2e-001"

        # 3. Test Compliance Report PDF download
        report_res = client.get("/api/v1/scan/test-e2e-001/report-pdf")
        assert report_res.status_code == 200, report_res.text
        assert report_res.content.startswith(b"%PDF"), "Report is not a valid PDF"

        # 4. Confirm category & Generate Section 36 Notice
        headers = {"Authorization": f"Bearer {token}"}
        confirm_res = client.post(
            "/api/v1/officer/confirm-category",
            json={
                "scan_id": "test-e2e-001",
                "confirmed_category": "food_and_beverage",
                "inspector_id": "officer"
            },
            headers=headers
        )
        assert confirm_res.status_code == 200, confirm_res.text

        notice_gen_res = client.post(
            "/api/v1/officer/generate-notice",
            json={
                "scan_id": "test-e2e-001",
                "shop_name": "Gupta General Store",
                "inspector_id": "officer",
                "gps_coordinates": "28.6139,77.2090",
                "product_barcode": "8901234567890"
            },
            headers=headers
        )
        assert notice_gen_res.status_code == 200, notice_gen_res.text
        notice_info = notice_gen_res.json()
        filename = notice_info["file_name"]

        # 5. Download Section 36 Notice PDF
        notice_dl_res = client.get(f"/api/v1/officer/notice/{filename}")
        assert notice_dl_res.status_code == 200, notice_dl_res.text
        assert notice_dl_res.content.startswith(b"%PDF"), "Notice is not a valid PDF"


if __name__ == "__main__":
    test_full_e2e_flow()
    print("All E2E full flow tests passed successfully!")
