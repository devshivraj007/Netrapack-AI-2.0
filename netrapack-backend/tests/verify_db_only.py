"""DB-only verification (fast, no AI model call)."""
from __future__ import annotations

import time

from app.db import database, repository


def main() -> None:
    counts = repository.reseed()
    print(f"reseed counts: {counts}")
    assert counts["products"] == 21, "expected 21 seeded products"
    print("[PASS] 21 products + rules seeded on reseed.")

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
    print(f"[PASS] appended scan id={scan_row}, reports={n_reports}, total scans={repository.get_scan_count()}")

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
                print(f"[FAIL] {op} was allowed (should be blocked)")
            except Exception as e:
                print(f"[PASS] {op} blocked -> {e}")
    finally:
        conn.close()

    conn = database.get_connection()
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        print(f"[PASS] journal_mode={mode}, busy_timeout={busy}ms")
        assert mode.lower() == "wal"
    finally:
        conn.close()
    print("DB VERIFY DONE.")


if __name__ == "__main__":
    main()
