"""Pytest: API endpoints - officer gate, PDF, admin state machine, chat,
chain-of-custody triggers, URL scanner. Uses in-process TestClient.

AI-dependent paths are asserted only on structure/fallback behaviour so the
suite is deterministic and does not require live models or network.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.ai.chatbot import LEGAL_DISCLAIMER
from app.ai.types import AiSource
from app.db import repository
from app.main import app
from app.services.scan_service import _edge_telemetry, _store_image


@pytest.fixture(scope="module")
def client():
    repository.reseed()
    with TestClient(app) as c:
        yield c


def _make_noncompliant(client, scan_id):
    return client.post("/api/v1/scan/process", json={
        "scan_id": scan_id,
        "mrp_declaration": "MRP Rs. 200",
        "net_quantity_declaration": "500g",
        "manufacturing_date_declaration": "2026",
        "unit_sale_price_declaration": "Rs 25 per 100g",
        "manufacturer_name_address": "Mystery Brand",
        "country_of_origin_declaration": "Premium quality",
        "consumer_care_details": "Visit our stores",
        "fssai_license_number": "",
    })


# --- Officer gate + Section 36 PDF ----------------------------------------
def test_officer_gate_and_pdf(client):
    sid = "pt-officer-1"
    assert _make_noncompliant(client, sid).status_code == 200

    # 403 before confirmation.
    notice = {"scan_id": sid, "shop_name": "Testmart", "inspector_id": "INSP-1",
              "gps_coordinates": "19.07,72.87", "product_barcode": "8901499010728"}
    assert client.post("/api/v1/officer/generate-notice", json=notice).status_code == 403

    # Confirm category.
    r = client.post("/api/v1/officer/confirm-category", json={
        "scan_id": sid, "confirmed_category": "food_and_beverage",
        "inspector_id": "INSP-1"})
    assert r.status_code == 200 and r.json()["status"] == "inspector_confirmed"

    # 200 + PDF saved.
    r = client.post("/api/v1/officer/generate-notice", json=notice)
    assert r.status_code == 200
    body = r.json()
    assert os.path.exists(body["file_path"])
    assert len(body["evidence_sha256"]) == 64


# --- Admin state machine ---------------------------------------------------
def test_admin_state_machine(client):
    sid = "pt-status-1"
    _make_noncompliant(client, sid)

    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "NOTICE_ISSUED"})
    assert r.status_code == 200 and r.json()["old_status"] == "PENDING"

    # Illegal backward transition.
    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "PENDING"})
    assert r.status_code == 409

    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "RESOLVED"})
    assert r.status_code == 200

    # Terminal.
    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "NOTICE_ISSUED"})
    assert r.status_code == 409

    assert len(repository.get_status_history(sid)) == 2


def test_admin_reports_filter(client):
    r = client.get("/api/v1/admin/reports", params={"status": "non_compliant"})
    assert r.status_code == 200
    assert r.json()["count"] >= 1


# --- Chat: disclaimer always present, 404 on unknown scan ------------------
def test_chat_unknown_scan_404(client):
    r = client.post("/api/v1/chat/query",
                    json={"scan_id": "does-not-exist", "question": "x"})
    assert r.status_code == 404


def test_chat_disclaimer_and_tier():
    """Test the chatbot's deterministic tier + disclaimer directly (no live model,
    so this is fast and deterministic). The live 3-tier path is exercised
    separately in the manual verification script."""
    from app.ai.chatbot import ChatContext, ComplianceChatbot
    from app.ai.providers import GeminiVisionProvider, OllamaVisionProvider

    class _DeadOllama(OllamaVisionProvider):
        def chat_available(self):
            return (False, None)

    class _DeadGemini(GeminiVisionProvider):
        def is_available(self):
            return (False, None)

    bot = ComplianceChatbot(ollama=_DeadOllama(), gemini=_DeadGemini())
    ctx = ChatContext(
        scan_id="pt-chat-det",
        verdict={"overall_status": "non_compliant", "rules_passed": 5,
                 "rules_checked": 7,
                 "violations": [{"field": "fssai_license",
                                 "rule_citation": "FSS Act 2006",
                                 "description": "missing"}]},
        applicable_rules=[])
    result = bot.answer("Why non-compliant?", ctx)
    assert LEGAL_DISCLAIMER in result["answer"]
    assert result["ai_level"] == "rule_engine_only"
    assert result["answer"].count(LEGAL_DISCLAIMER) == 1  # appended exactly once


# --- URL scanner graceful degrade -----------------------------------------
def test_url_scanner_invalid(client):
    r = client.post("/api/v1/scan/url", json={"url": "not-a-url"})
    assert r.status_code == 200 and r.json()["fetched"] is False


# --- Offline edge telemetry ------------------------------------------------
def test_edge_telemetry():
    lvl, conn = _edge_telemetry(AiSource.LOCAL_OLLAMA, online=False)
    assert lvl == "local_edge" and conn == "offline_edge"
    _, conn2 = _edge_telemetry(AiSource.CLOUD_GEMINI, online=True)
    assert conn2 == "online"


# --- Chain-of-custody: image hash + tamper detection -----------------------
def test_chain_of_custody_hash(tmp_path, monkeypatch):
    from scripts.verify_chain_of_custody import verify_image_hash
    from tests.make_synthetic_labels import build_samples

    repository.reseed()
    _, jpeg, _ = build_samples()[0]
    sid = "pt-custody-1"
    image_hash, image_path = _store_image(sid, jpeg)
    repository.insert_scan(
        {"scan_id": sid, "overall_status": "fully_compliant",
         "rules_passed": 6, "rules_checked": 6, "violations": [],
         "metadata": {"processing_ms": 1.0}, "ai_recognition": {}},
        input_mode="photo", image_hash=image_hash, image_path=image_path)
    assert verify_image_hash(sid) is True
    # Tamper -> mismatch.
    with open(image_path, "ab") as f:
        f.write(b"\x00")
    assert verify_image_hash(sid) is False


def test_chain_of_custody_triggers():
    from scripts.verify_chain_of_custody import verify_triggers
    assert verify_triggers() is True
