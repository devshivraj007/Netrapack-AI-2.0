"""Verify Day 4/5 features end-to-end (in-process TestClient, no external deps
required to PASS - AI tiers degrade gracefully).

Covers:
  * Chat /api/v1/chat/query: answers a scan, carries exact disclaimer, 3-tier.
  * Admin status state machine: PENDING->NOTICE_ISSUED->RESOLVED + illegal 409.
  * Chain-of-custody triggers (via the verify script's trigger test).
  * Offline edge telemetry logic (_edge_telemetry).
  * URL scanner graceful-degrade on a non-product URL.
"""
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.ai.chatbot import LEGAL_DISCLAIMER
from app.ai.types import AiSource
from app.db import repository
from app.main import app
from app.services.scan_service import _edge_telemetry


def main() -> None:
    repository.reseed()
    ok = True
    with TestClient(app) as client:
        ok &= _chat(client)
        ok &= _admin_status(client)
        ok &= _url_scanner(client)
    ok &= _edge_telemetry_logic()
    ok &= _triggers()
    print("\nDAY4/5 VERIFY:", "PASS" if ok else "FAIL")


def _make_scan(client, scan_id: str) -> None:
    client.post("/api/v1/scan/process", json={
        "scan_id": scan_id,
        "mrp_declaration": "MRP Rs. 200",
        "net_quantity_declaration": "500g",
        "manufacturing_date_declaration": "2026",
        "fssai_license_number": "",
    })


def _chat(client) -> bool:
    print("\n=== Chat /api/v1/chat/query ===")
    sid = "d45-chat-1"
    _make_scan(client, sid)
    r = client.post("/api/v1/chat/query", json={
        "scan_id": sid, "question": "Why is this product non-compliant?"})
    ok = r.status_code == 200
    body = r.json() if ok else {}
    ans = body.get("answer", "")
    print("status:", r.status_code, "ai_level:", body.get("ai_level"),
          "source:", body.get("ai_source"))
    print("answer[:120]:", ans[:120].replace("\n", " "))
    disc = LEGAL_DISCLAIMER in ans
    print("[{}] mandatory disclaimer present".format("PASS" if disc else "FAIL"))
    # 404 on unknown scan.
    r404 = client.post("/api/v1/chat/query",
                       json={"scan_id": "nope", "question": "x"})
    print("[{}] unknown scan -> 404".format("PASS" if r404.status_code == 404 else "FAIL"))
    return ok and disc and r404.status_code == 404


def _admin_status(client) -> bool:
    print("\n=== Admin status state machine ===")
    sid = "d45-status-1"
    _make_scan(client, sid)
    ok = True

    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "NOTICE_ISSUED", "changed_by": "ADM-1"})
    print("PENDING->NOTICE_ISSUED:", r.status_code)
    ok &= r.status_code == 200 and r.json()["old_status"] == "PENDING"

    # Illegal jump backwards.
    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "PENDING"})
    print("NOTICE_ISSUED->PENDING (illegal):", r.status_code, "(expect 409)")
    ok &= r.status_code == 409

    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "RESOLVED", "changed_by": "ADM-1"})
    print("NOTICE_ISSUED->RESOLVED:", r.status_code)
    ok &= r.status_code == 200

    # Terminal: nothing allowed after RESOLVED.
    r = client.post(f"/api/v1/admin/reports/{sid}/status",
                    json={"new_status": "NOTICE_ISSUED"})
    print("RESOLVED->NOTICE_ISSUED (terminal):", r.status_code, "(expect 409)")
    ok &= r.status_code == 409

    # History should have 2 transitions, append-only.
    hist = repository.get_status_history(sid)
    print("history length:", len(hist))
    ok &= len(hist) == 2
    print("[{}] admin state machine".format("PASS" if ok else "FAIL"))
    return ok


def _url_scanner(client) -> bool:
    print("\n=== URL scanner (graceful degrade) ===")
    r = client.post("/api/v1/scan/url", json={"url": "not-a-url"})
    ok1 = r.status_code == 200 and r.json()["fetched"] is False
    print("[{}] invalid URL handled gracefully".format("PASS" if ok1 else "FAIL"))
    return ok1


def _edge_telemetry_logic() -> bool:
    print("\n=== Offline edge telemetry logic ===")
    lvl, conn = _edge_telemetry(AiSource.LOCAL_OLLAMA, online=False)
    ok1 = (lvl == "local_edge" and conn == "offline_edge")
    print(f"[{ 'PASS' if ok1 else 'FAIL'}] local+offline -> ai_level={lvl}, connectivity_state={conn}")
    lvl2, conn2 = _edge_telemetry(AiSource.CLOUD_GEMINI, online=True)
    ok2 = (conn2 == "online")
    print(f"[{'PASS' if ok2 else 'FAIL'}] cloud+online -> connectivity_state={conn2}")
    return ok1 and ok2


def _triggers() -> bool:
    print("\n=== Chain-of-custody trigger test ===")
    from scripts.verify_chain_of_custody import verify_triggers
    result = verify_triggers()
    print("[{}] append-only triggers block UPDATE/DELETE".format("PASS" if result else "FAIL"))
    return result


if __name__ == "__main__":
    main()
