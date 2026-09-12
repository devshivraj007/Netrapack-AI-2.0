"""Pytest for Checkpoint 2 backend gaps: auth+roles, search, CSV export.

Deterministic, in-process TestClient. Font-readability endpoint needs OCR
(Tesseract) + an image, so it's smoke-checked separately, not asserted here.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import repository
from app.main import app


@pytest.fixture(scope="module")
def client():
    repository.reseed()
    repository.seed_default_users()
    with TestClient(app) as c:
        yield c


def _login(client, username, password):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": password})


def _make_scan(client, scan_id):
    return client.post("/api/v1/scan/process", json={
        "scan_id": scan_id,
        "mrp_declaration": "MRP Rs. 200",
        "net_quantity_declaration": "500g",
        "manufacturing_date_declaration": "2026",
        "manufacturer_name_address": "TestCorp Foods, Pune",
        "fssai_license_number": "",
    })


# --- CP2-2: Real auth + roles ---------------------------------------------
def test_login_success_officer_and_admin(client):
    r = _login(client, "officer", "netra123")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "officer" and body["token"]

    r2 = _login(client, "admin", "admin123")
    assert r2.status_code == 200 and r2.json()["role"] == "admin"


def test_login_bad_password_rejected(client):
    r = _login(client, "officer", "wrong")
    assert r.status_code == 401


def test_password_is_hashed_not_plaintext(client):
    user = repository.get_user("officer")
    assert user is not None
    # Stored as salt$iterations$hash, never the raw password.
    assert "netra123" not in user["password_hash"]
    assert user["password_hash"].count("$") == 2


def test_officer_endpoint_requires_token(client):
    sid = f"cp2-auth-{uuid.uuid4().hex[:8]}"
    _make_scan(client, sid)
    # No token -> 401.
    r = client.post("/api/v1/officer/confirm-category", json={
        "scan_id": sid, "confirmed_category": "food_and_beverage",
        "inspector_id": "officer"})
    assert r.status_code == 401

    # With officer token -> 200.
    token = _login(client, "officer", "netra123").json()["token"]
    r2 = client.post("/api/v1/officer/confirm-category",
                     headers={"Authorization": f"Bearer {token}"},
                     json={"scan_id": sid, "confirmed_category": "food_and_beverage",
                           "inspector_id": "officer"})
    assert r2.status_code == 200 and r2.json()["status"] == "inspector_confirmed"


def test_admin_status_requires_admin_role(client):
    sid = f"cp2-role-{uuid.uuid4().hex[:8]}"
    _make_scan(client, sid)
    officer_token = _login(client, "officer", "netra123").json()["token"]
    admin_token = _login(client, "admin", "admin123").json()["token"]

    # Officer token is NOT enough for the admin-only status change -> 403.
    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    headers={"Authorization": f"Bearer {officer_token}"},
                    json={"new_status": "NOTICE_ISSUED"})
    assert r.status_code == 403

    # Admin token works.
    r2 = client.post(f"/api/v1/admin/reports/{sid}/status",
                     headers={"Authorization": f"Bearer {admin_token}"},
                     json={"new_status": "NOTICE_ISSUED"})
    assert r2.status_code == 200


# --- CP2-1: Search / retrieval --------------------------------------------
def test_search_by_scan_id_and_product(client):
    token = _login(client, "officer", "netra123").json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    sid = f"cp2-search-{uuid.uuid4().hex[:8]}"
    _make_scan(client, sid)

    # by scan_id (partial)
    r = client.get("/api/v1/admin/reports", headers=h,
                   params={"scan_id": sid[:12]})
    assert r.status_code == 200
    assert any(row["scan_id"] == sid for row in r.json()["reports"])

    # by product/manufacturer text (TestCorp is in the verdict json)
    r2 = client.get("/api/v1/admin/reports", headers=h,
                    params={"product_name": "TestCorp"})
    assert r2.status_code == 200
    assert any(row["scan_id"] == sid for row in r2.json()["reports"])

    # status filter still works
    r3 = client.get("/api/v1/admin/reports", headers=h,
                    params={"status": "non_compliant"})
    assert r3.status_code == 200


def test_search_requires_auth(client):
    r = client.get("/api/v1/admin/reports", params={"q": "x"})
    assert r.status_code == 401


# --- CP2-3: CSV export -----------------------------------------------------
def test_csv_export(client):
    token = _login(client, "officer", "netra123").json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    sid = f"cp2-csv-{uuid.uuid4().hex[:8]}"
    _make_scan(client, sid)

    r = client.get(f"/api/v1/reports/{sid}/export", headers=h,
                   params={"format": "csv"})
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    text = r.text
    assert "NetraPack Scan Report" in text
    assert sid in text
    assert "Declaration" in text and "Violation Field" in text

    # JSON variant
    rj = client.get(f"/api/v1/reports/{sid}/export", headers=h,
                    params={"format": "json"})
    assert rj.status_code == 200 and rj.json()["scan_id"] == sid


def test_csv_export_unknown_scan_404(client):
    token = _login(client, "officer", "netra123").json()["token"]
    r = client.get("/api/v1/reports/does-not-exist/export",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


# --- CP2-4: Readability check folded into the photo scan verdict ----------
def test_photo_scan_always_includes_readability():
    """The font-size/readability advisory must ride along on every photo scan
    verdict so the app can surface it automatically (no separate call needed).

    Deterministic: if OCR/Tesseract is unavailable the field is still present
    with assessed=False, so we assert on shape, not on a specific measurement.
    """
    from tests.make_synthetic_labels import build_samples
    from app.services import scan_service

    _, jpeg, _ = build_samples()[0]
    verdict = scan_service.process_photo_scan("cp2-readability", jpeg)
    rd = verdict.readability
    assert rd is not None, "photo scans must always attach a readability advisory"
    # Always advisory, never a certified mm measurement.
    assert rd.approximate is True
    assert isinstance(rd.assessed, bool)
    assert isinstance(rd.note, str) and rd.note  # human-readable note present
    if rd.assessed:
        # When we could assess, the proportional metrics are populated.
        assert rd.image_height_px > 0
        assert rd.char_height_fraction >= 0.0
        assert isinstance(rd.likely_too_small, bool)
