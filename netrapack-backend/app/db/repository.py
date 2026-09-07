"""Repository layer over the SQLite database.

Deliberately narrow surface:
  * products / rules  -> upsert (used only by the startup reseed).
  * scans / reports   -> INSERT and SELECT only. No update/delete method exists,
    which together with the DB triggers keeps them append-only for evidence
    integrity.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from . import seed_data
from .database import get_connection, init_schema


# ---------------------------------------------------------------------------
# Startup: schema + idempotent reseed
# ---------------------------------------------------------------------------
def reseed(conn: Optional[sqlite3.Connection] = None) -> dict[str, int]:
    """Create schema (if needed) and upsert the 21 products + rules.

    Idempotent: safe to run on every startup. Uses product_code / rule_key as
    stable keys so re-seeding updates in place rather than duplicating. Does NOT
    touch scans or reports.
    """
    owns = conn is None
    conn = conn or get_connection()
    try:
        init_schema(conn)

        for p in seed_data.PRODUCTS:
            conn.execute(
                """
                INSERT INTO products
                    (product_code, barcode, name, category, mrp, net_quantity,
                     manufacturer, country_of_origin, fssai_number, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_code) DO UPDATE SET
                    barcode=excluded.barcode,
                    name=excluded.name,
                    category=excluded.category,
                    mrp=excluded.mrp,
                    net_quantity=excluded.net_quantity,
                    manufacturer=excluded.manufacturer,
                    country_of_origin=excluded.country_of_origin,
                    fssai_number=excluded.fssai_number,
                    notes=excluded.notes
                """,
                p,
            )

        # Rules: rule_key is not unique across versions (effective ranges), so
        # clear-and-insert the current definition set for a clean reseed.
        conn.execute("DELETE FROM rules;")
        for r in seed_data.RULES:
            conn.execute(
                """
                INSERT INTO rules
                    (rule_key, citation, description, effective_from,
                     effective_to, params_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                r,
            )

        conn.commit()
        counts = {
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "rules": conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0],
        }
        return counts
    finally:
        if owns:
            conn.close()


# ---------------------------------------------------------------------------
# Scans (append-only)
# ---------------------------------------------------------------------------
def insert_scan(verdict: dict[str, Any], input_mode: str,
                image_hash: Optional[str] = None,
                image_path: Optional[str] = None) -> int:
    """Append a scan record. Returns the new row id."""
    meta = verdict.get("metadata") or {}
    ai = verdict.get("ai_recognition") or {}
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO scans
                (scan_id, input_mode, overall_status, rules_passed,
                 rules_checked, ai_category, ai_source, ai_model,
                 online_offline, processing_ms, image_hash, image_path,
                 verdict_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verdict.get("scan_id"),
                input_mode,
                verdict.get("overall_status"),
                verdict.get("rules_passed", 0),
                verdict.get("rules_checked", 0),
                ai.get("effective_category"),
                ai.get("ai_source"),
                meta.get("ai_model_used"),
                meta.get("online_offline"),
                meta.get("processing_ms"),
                image_hash,
                image_path,
                json.dumps(verdict, default=str),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def insert_reports(scan_id: str, violations: list[dict[str, Any]]) -> int:
    """Append one report row per violation. Returns count inserted."""
    if not violations:
        return 0
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO reports (scan_id, field, rule_citation, description)
            VALUES (?, ?, ?, ?)
            """,
            [
                (scan_id, v.get("field"), v.get("rule_citation"), v.get("description"))
                for v in violations
            ],
        )
        conn.commit()
        return len(violations)
    finally:
        conn.close()


def get_scan_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
    finally:
        conn.close()


def get_product_by_barcode(barcode: str) -> Optional[dict[str, Any]]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM products WHERE barcode = ?", (barcode,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Scan lookup + officer category confirmation (append-only audit trail)
# ---------------------------------------------------------------------------
def get_latest_scan(scan_id: str) -> Optional[dict[str, Any]]:
    """Return the most recent scan row for a scan_id (with parsed verdict)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM scans WHERE scan_id = ? ORDER BY id DESC LIMIT 1",
            (scan_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["verdict"] = json.loads(d.get("verdict_json") or "{}")
        except json.JSONDecodeError:
            d["verdict"] = {}
        return d
    finally:
        conn.close()


def add_category_confirmation(scan_id: str, category: str,
                              inspector_id: str) -> int:
    """Append an officer category confirmation. Returns the new row id."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO category_confirmations
                (scan_id, confirmed_category, status, inspector_id)
            VALUES (?, ?, 'inspector_confirmed', ?)
            """,
            (scan_id, category, inspector_id),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_latest_confirmation(scan_id: str) -> Optional[dict[str, Any]]:
    """Return the latest category confirmation for a scan, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM category_confirmations WHERE scan_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (scan_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_category_confirmed(scan_id: str) -> bool:
    """True only if the scan has an inspector_confirmed category."""
    conf = get_latest_confirmation(scan_id)
    return bool(conf and conf.get("status") == "inspector_confirmed")


def query_reports(status: Optional[str] = None,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None,
                  limit: int = 200) -> list[dict[str, Any]]:
    """Query scans for the admin dashboard, with optional status/date filters.

    status filters on the scan's overall_status. Dates are ISO (YYYY-MM-DD) and
    filter on created_at. Returns scan summary rows (newest first).
    """
    clauses = []
    params: list[Any] = []
    if status:
        clauses.append("overall_status = ?")
        params.append(status)
    if date_from:
        clauses.append("date(created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        clauses.append("date(created_at) <= date(?)")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT scan_id, created_at, input_mode, overall_status,
                   rules_passed, rules_checked, ai_category, ai_source,
                   ai_model, online_offline, processing_ms
            FROM scans{where}
            ORDER BY id DESC LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Rules retrieval (RAG context for the chatbot)
# ---------------------------------------------------------------------------
def get_all_rules() -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM rules ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_rules_for_verdict(verdict: dict[str, Any]) -> list[dict[str, Any]]:
    """Pick rule rows relevant to a verdict for RAG injection.

    Matches on citations present in the verdict's violations, plus always
    includes the USP exemption rules (commonly asked about). Falls back to all
    rules if nothing matches.
    """
    all_rules = get_all_rules()
    if not all_rules:
        return []
    citations = {
        (x.get("rule_citation") or "").split(" - ")[0].strip()
        for x in (verdict.get("violations", []) or [])
    }
    picked = []
    for r in all_rules:
        rule_cite = (r.get("citation") or "").strip()
        if any(rule_cite and (rule_cite in c or c in rule_cite) for c in citations if c):
            picked.append(r)
        elif r.get("rule_key", "").startswith("usp_exemption"):
            picked.append(r)
    return picked or all_rules


# ---------------------------------------------------------------------------
# Admin investigation status (append-only state machine history)
# ---------------------------------------------------------------------------
def get_current_status(report_id: str) -> str:
    """Latest status for a report_id; defaults to PENDING if never set."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT new_status FROM report_status_history WHERE report_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (report_id,),
        ).fetchone()
        return row["new_status"] if row else "PENDING"
    finally:
        conn.close()


def add_status_transition(report_id: str, old_status: str, new_status: str,
                          changed_by: Optional[str], note: Optional[str]) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO report_status_history
                (report_id, old_status, new_status, changed_by, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, old_status, new_status, changed_by, note),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_status_history(report_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM report_status_history WHERE report_id = ? ORDER BY id",
            (report_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
