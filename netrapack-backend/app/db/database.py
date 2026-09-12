"""SQLite database access for NetraPack.

Requirements honoured here (confirmed with compliance reviewer):
  * WAL journal mode + a busy timeout, so multiple concurrent requests don't
    trip over each other with "database is locked".
  * Single local database file in its own clearly-named folder, excluded from
    Git (see .gitignore).
  * scans and reports are APPEND-ONLY. There is no update/delete path for them
    anywhere in the app, to protect evidence integrity for Officer Mode.
  * Schema + reseed of the 22 reference products and the rule definitions runs
    automatically every time the backend starts.

The append-only guarantee is enforced two ways:
  1. The repository layer exposes only insert/select methods for scans/reports.
  2. SQLite triggers raise on any UPDATE or DELETE against those tables, so even
     a stray query cannot mutate them.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator

# Database lives in its own clearly-named folder inside the backend package
# root. Overridable via env for tests.
_DEFAULT_DB_DIR = Path(__file__).resolve().parents[2] / "data"
DB_DIR = Path(os.environ.get("NETRAPACK_DB_DIR", str(_DEFAULT_DB_DIR)))
DB_PATH = DB_DIR / "netrapack.db"

BUSY_TIMEOUT_MS = 5000


def _ensure_dir() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Open a connection with WAL + busy timeout configured."""
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


SCHEMA_SQL = """
-- Application users for role-based access (Officer / Admin).
-- Passwords are stored as PBKDF2-HMAC-SHA256 hashes (salt$iterations$hash),
-- never in plaintext. This table is mutable (users can be added/updated).
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    username            TEXT UNIQUE NOT NULL,
    password_hash       TEXT NOT NULL,
    role                TEXT NOT NULL,             -- 'officer' | 'admin'
    display_name        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Reference products (for barcode matching later, Day 3).
CREATE TABLE IF NOT EXISTS products (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code        TEXT UNIQUE NOT NULL,      -- our internal code
    barcode             TEXT,
    name                TEXT NOT NULL,
    category            TEXT NOT NULL,
    mrp                 REAL,
    net_quantity        TEXT,
    manufacturer        TEXT,
    country_of_origin   TEXT,
    fssai_number        TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Every scan performed (APPEND-ONLY).
CREATE TABLE IF NOT EXISTS scans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id             TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    input_mode          TEXT NOT NULL,             -- 'text' | 'photo'
    overall_status      TEXT NOT NULL,
    rules_passed        INTEGER NOT NULL,
    rules_checked       INTEGER NOT NULL,
    ai_category         TEXT,
    ai_source           TEXT,
    ai_model            TEXT,
    online_offline      TEXT,
    processing_ms       REAL,
    image_hash          TEXT,                      -- SHA-256 of raw image (chain-of-custody)
    image_path          TEXT,                      -- stored raw image location
    verdict_json        TEXT NOT NULL              -- full verdict snapshot
);

-- Flagged violation reports (APPEND-ONLY).
CREATE TABLE IF NOT EXISTS reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id             TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    field               TEXT NOT NULL,
    rule_citation       TEXT NOT NULL,
    description         TEXT NOT NULL
);

-- Admin investigation status history (APPEND-ONLY).
-- Each row is a state transition for a report/scan; the latest row is the
-- current state. States: PENDING -> NOTICE_ISSUED -> RESOLVED.
CREATE TABLE IF NOT EXISTS report_status_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id           TEXT NOT NULL,             -- scan_id used as report id
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    old_status          TEXT,
    new_status          TEXT NOT NULL,
    changed_by          TEXT,
    note                TEXT
);

-- Officer category confirmations (APPEND-ONLY audit trail).
-- The scans table is immutable, so an officer's confirm/change of the
-- AI-suggested category is recorded here as a new row. The LATEST row for a
-- scan_id is the current confirmation state. This preserves the full history
-- (who changed what, when) for evidence integrity in Officer Mode.
CREATE TABLE IF NOT EXISTS category_confirmations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id             TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    confirmed_category  TEXT NOT NULL,
    status              TEXT NOT NULL,             -- 'inspector_confirmed'
    inspector_id        TEXT NOT NULL
);

-- Rule definitions with effective-date ranges, so we can apply the right rule
-- version based on a product's manufacturing date (not just today's rules).
CREATE TABLE IF NOT EXISTS rules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key            TEXT NOT NULL,             -- e.g. 'usp_exemption_mrp'
    citation            TEXT NOT NULL,
    description         TEXT NOT NULL,
    effective_from      TEXT NOT NULL,             -- ISO date
    effective_to        TEXT,                      -- ISO date or NULL = current
    params_json         TEXT
);

-- Append-only enforcement: block UPDATE/DELETE on scans and reports.
CREATE TRIGGER IF NOT EXISTS scans_no_update
BEFORE UPDATE ON scans
BEGIN
    SELECT RAISE(ABORT, 'scans is append-only');
END;

CREATE TRIGGER IF NOT EXISTS scans_no_delete
BEFORE DELETE ON scans
BEGIN
    SELECT RAISE(ABORT, 'scans is append-only');
END;

CREATE TRIGGER IF NOT EXISTS reports_no_update
BEFORE UPDATE ON reports
BEGIN
    SELECT RAISE(ABORT, 'reports is append-only');
END;

CREATE TRIGGER IF NOT EXISTS reports_no_delete
BEFORE DELETE ON reports
BEGIN
    SELECT RAISE(ABORT, 'reports is append-only');
END;

CREATE TRIGGER IF NOT EXISTS catconf_no_update
BEFORE UPDATE ON category_confirmations
BEGIN
    SELECT RAISE(ABORT, 'category_confirmations is append-only');
END;

CREATE TRIGGER IF NOT EXISTS catconf_no_delete
BEFORE DELETE ON category_confirmations
BEGIN
    SELECT RAISE(ABORT, 'category_confirmations is append-only');
END;

CREATE TRIGGER IF NOT EXISTS status_hist_no_update
BEFORE UPDATE ON report_status_history
BEGIN
    SELECT RAISE(ABORT, 'report_status_history is append-only');
END;

CREATE TRIGGER IF NOT EXISTS status_hist_no_delete
BEFORE DELETE ON report_status_history
BEGIN
    SELECT RAISE(ABORT, 'report_status_history is append-only');
END;
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def iter_rows(conn: sqlite3.Connection, query: str, params: tuple = ()) -> Iterator[sqlite3.Row]:
    cur = conn.execute(query, params)
    yield from cur.fetchall()
