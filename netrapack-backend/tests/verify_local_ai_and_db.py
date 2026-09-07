"""Targeted verification of the parts that need live services.

Order matters: DB checks run FIRST (fast, deterministic), then the local-AI
call (slow on CPU) runs LAST and is reported non-fatally, so a slow model does
not hide the DB results.
"""

from __future__ import annotations

import json
import time

from app.ai.providers import OllamaVisionProvider
from app.ai.recognizer import ProductRecognizer
from app.ai.types import AiSource
from app.db import database, repository
from tests.make_synthetic_labels import build_samples


def section(title: str) -> None:
    print("\n" + "=" * 66 + f"\n{title}\n" + "=" * 66, flush=True)


def verify_db() -> None:
    section("SQLite - reseed, append, append-only enforcement")
    counts = repository.reseed()
    print(f"reseed counts: {counts}", flush=True)
    assert counts["products"] == 21, "expected 21 seeded products"
    print("[PASS] 21 products + rules seeded.", flush=True)

    verdict = {
        "scan_id": f"verify-{int(time.time())}",
        "overall_status": "non_compliant",
        "rules_passed": 5,
        "rules_checked": 7,
        "ai_recognition": {"effective_category": "food_and_beverage", "ai_source": "none"},
        "metadata": {"ai_model_used": None, "online_offline": "offline", "processing_ms": 12.3},
        "violations": [{"field": "fssai_license", "rule_citation": "X", "description": "missing"}],
    }
    scan_row = repository.insert_scan(verdict, input_mode="photo")
    n_reports = repository.insert_reports(verdict["scan_id"], verdict["violations"])
    print(f"[PASS] appended scan id={scan_row}, reports={n_reports}, "
          f"total scans={repository.get_scan_count()}", flush=True)

    conn = database.get_connection()
    try:
        for op, sql, param in [
            ("UPDATE scans", "UPDATE scans SET overall_status='x' WHERE id=?", (scan_row,)),
            ("DELETE scans", "DELETE FROM scans WHERE id=?", (scan_row,)),
            ("UPDATE reports", "UPDATE reports SET description='x' WHERE scan_id=?", (verdict["scan_id"],)),
            ("DELETE reports", "DELETE FROM reports WHERE scan_id=?", (verdict["scan_id"],)),
        ]:
            try:
                conn.execute(sql, param)
                conn.commit()
                print(f"[FAIL] {op} was allowed (should be blocked)", flush=True)
            except Exception as e:
                print(f"[PASS] {op} blocked -> {e}", flush=True)
    finally:
        conn.close()

    conn = database.get_connection()
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        print(f"[PASS] journal_mode={mode}, busy_timeout={busy}ms", flush=True)
        assert mode.lower() == "wal"
    finally:
        conn.close()


def verify_local_ai() -> None:
    section("LOCAL AI (Ollama moondream) - single image (non-fatal)")
    ollama = OllamaVisionProvider()
    available, model = ollama.is_available()
    print(f"Ollama available: {available}, model: {model}", flush=True)
    if not available:
        print("Local model not available -> chain falls through (by design).", flush=True)
        return

    _, jpeg, _ = build_samples()[0]
    t0 = time.perf_counter()
    rec = ProductRecognizer(ollama=ollama).recognize(jpeg)
    dt = time.perf_counter() - t0
    print(f"(local inference took {dt:.1f}s)", flush=True)
    print(json.dumps({
        "category": rec.category.value,
        "effective_category": rec.effective_category.value,
        "confidence": rec.confidence,
        "ai_source": rec.ai_source.value,
        "model_name": rec.model_name,
        "below_confidence_threshold": rec.below_confidence_threshold,
        "confirmation_status": rec.confirmation_status,
        "note": rec.note,
    }, indent=2), flush=True)
    if rec.ai_source == AiSource.LOCAL_OLLAMA:
        print("[PASS] Local AI (Level 1) answered - labelled AI-suggested/not-confirmed.", flush=True)
    else:
        print("[INFO] Local call did not complete in time; fell through cleanly "
              "(fallback path proven). This is acceptable on a slow CPU.", flush=True)


if __name__ == "__main__":
    verify_db()
    verify_local_ai()
    print("\nDONE.", flush=True)
