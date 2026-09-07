"""Chain-of-Custody verification script (Day 5).

Two jobs:

  1. For a given scan_id: recompute the SHA-256 of the stored raw packaging
     image and verify it matches scans.image_hash in netrapack.db. This proves
     the evidence image has not been altered since capture.

  2. Trigger test: verify the SQLite append-only triggers actually BLOCK any
     UPDATE or DELETE on scans, reports, and category_confirmations.

Usage:
    python -m scripts.verify_chain_of_custody --scan-id <scan_id>
    python -m scripts.verify_chain_of_custody --triggers-only
    python -m scripts.verify_chain_of_custody --scan-id <id> --triggers-only

Exit code 0 = all checks passed, 1 = a check failed.
"""

from __future__ import annotations

import argparse
import hashlib
import sys

from app.db import database


def verify_image_hash(scan_id: str) -> bool:
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT scan_id, image_hash, image_path FROM scans "
            "WHERE scan_id = ? ORDER BY id DESC LIMIT 1",
            (scan_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        print(f"[FAIL] No scan found for scan_id '{scan_id}'.")
        return False

    stored_hash = row["image_hash"]
    image_path = row["image_path"]
    if not stored_hash or not image_path:
        print(f"[WARN] scan '{scan_id}' has no stored image_hash/image_path "
              "(likely a text-mode scan). Nothing to verify.")
        return False

    try:
        with open(image_path, "rb") as f:
            recomputed = hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        print(f"[FAIL] Evidence image missing on disk: {image_path}")
        return False

    match = recomputed == stored_hash
    print(f"scan_id           : {scan_id}")
    print(f"image_path        : {image_path}")
    print(f"stored   sha256   : {stored_hash}")
    print(f"recomputed sha256 : {recomputed}")
    if match:
        print("[PASS] Image hash matches - chain of custody intact.")
    else:
        print("[FAIL] Image hash MISMATCH - evidence may have been altered!")
    return match


def verify_triggers() -> bool:
    """Confirm UPDATE/DELETE are blocked on the append-only tables."""
    ok = True
    conn = database.get_connection()
    try:
        database.init_schema(conn)

        # SQLite BEFORE UPDATE/DELETE triggers only fire when a row is actually
        # matched. Seed one row per table so the triggers have something to act
        # on; otherwise an UPDATE/DELETE on an empty table is a silent no-op and
        # would look (wrongly) like the trigger failed.
        seed = [
            ("scans",
             "INSERT INTO scans (scan_id, input_mode, overall_status, "
             "rules_passed, rules_checked, verdict_json) "
             "VALUES ('trig-test','text','x',0,0,'{}')"),
            ("reports",
             "INSERT INTO reports (scan_id, field, rule_citation, description) "
             "VALUES ('trig-test','f','c','d')"),
            ("category_confirmations",
             "INSERT INTO category_confirmations (scan_id, confirmed_category, "
             "status, inspector_id) VALUES ('trig-test','food_and_beverage',"
             "'inspector_confirmed','INSP-T')"),
            ("report_status_history",
             "INSERT INTO report_status_history (report_id, old_status, "
             "new_status, changed_by) VALUES ('trig-test','PENDING','RESOLVED','A')"),
        ]
        for _, ins in seed:
            try:
                conn.execute(ins)
                conn.commit()
            except Exception:
                pass  # row may already exist from a prior run; fine.

        checks = [
            ("scans", "UPDATE scans SET overall_status='x' WHERE scan_id='trig-test'"),
            ("scans", "DELETE FROM scans WHERE scan_id='trig-test'"),
            ("reports", "UPDATE reports SET description='x' WHERE scan_id='trig-test'"),
            ("reports", "DELETE FROM reports WHERE scan_id='trig-test'"),
            ("category_confirmations",
             "UPDATE category_confirmations SET status='x' WHERE scan_id='trig-test'"),
            ("category_confirmations",
             "DELETE FROM category_confirmations WHERE scan_id='trig-test'"),
            ("report_status_history",
             "UPDATE report_status_history SET new_status='x' WHERE report_id='trig-test'"),
            ("report_status_history",
             "DELETE FROM report_status_history WHERE report_id='trig-test'"),
        ]
        for table, sql in checks:
            op = sql.split()[0]
            try:
                conn.execute(sql)
                conn.commit()
                print(f"[FAIL] {op} on {table} was ALLOWED (should be blocked).")
                ok = False
            except Exception as e:
                print(f"[PASS] {op} on {table} blocked -> {e}")
    finally:
        conn.close()
    return ok


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="NetraPack chain-of-custody verifier.")
    p.add_argument("--scan-id", help="Scan to verify the image hash for.")
    p.add_argument("--triggers-only", action="store_true",
                   help="Only run the append-only trigger test.")
    args = p.parse_args(argv)

    all_ok = True
    if not args.triggers_only:
        if not args.scan_id:
            print("Provide --scan-id, or use --triggers-only.")
            return 1
        print("=== Image hash verification ===")
        all_ok &= verify_image_hash(args.scan_id)

    print("\n=== Append-only trigger test ===")
    all_ok &= verify_triggers()

    print("\nRESULT:", "ALL PASS" if all_ok else "FAILURES DETECTED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
