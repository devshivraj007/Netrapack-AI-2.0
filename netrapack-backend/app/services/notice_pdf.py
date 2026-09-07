"""Section 36 Legal Notice PDF generator (reportlab).

Produces a formal Notice of Violation under Section 36 of the Legal Metrology
Act, 2009 read with Rule 32 of the LMPC Rules, 2011. Includes tamper-evidence
metadata (SHA-256 of the verdict payload, GPS, timestamp, shop, inspector,
barcode) and an itemised table of violated rules (declared value vs legal
requirement). Saved under ./storage/notices/.

NOTE on citations: the statutory title and rule citations are used as provided
by the project. They remain PROVISIONAL pending final legal-reviewer sign-off
(the Section-24-vs-36 class of error we flagged on Day 1). This generator reads
citations from each violation; it does not invent them.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

STATUTORY_TITLE = (
    "NOTICE OF VIOLATION UNDER SECTION 36 OF THE LEGAL METROLOGY ACT, 2009 "
    "READ WITH RULE 32 OF LMPC RULES, 2011"
)

_NOTICES_DIR = Path(os.environ.get("NETRAPACK_NOTICES_DIR",
                                   str(Path(__file__).resolve().parents[2]
                                       / "storage" / "notices")))


def evidence_hash(verdict: dict[str, Any]) -> str:
    """SHA-256 over a canonical JSON of the verdict (tamper-evidence)."""
    canonical = json.dumps(verdict, sort_keys=True, separators=(",", ":"),
                           default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def generate_notice_pdf(
    scan_id: str,
    verdict: dict[str, Any],
    *,
    shop_name: str,
    inspector_id: str,
    gps_coordinates: str,
    product_barcode: Optional[str] = None,
    confirmed_category: Optional[str] = None,
) -> dict[str, Any]:
    """Render the Section 36 notice PDF and save it. Returns metadata."""
    _NOTICES_DIR.mkdir(parents=True, exist_ok=True)

    sha256 = evidence_hash(verdict)
    timestamp = datetime.now(timezone.utc).isoformat()
    filename = f"section36_{scan_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    out_path = _NOTICES_DIR / filename

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Section36Title", parent=styles["Title"], fontSize=13, leading=17,
        alignment=1, textColor=colors.HexColor("#7a0000"),
    )
    h_style = ParagraphStyle("H", parent=styles["Heading2"], fontSize=11)
    body = styles["BodyText"]

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"Section 36 Notice - {scan_id}",
    )
    story: list[Any] = []

    story.append(Paragraph(STATUTORY_TITLE, title_style))
    story.append(Spacer(1, 8 * mm))

    # --- Evidence metadata block ------------------------------------------
    story.append(Paragraph("Evidence &amp; Inspection Metadata", h_style))
    meta_rows = [
        ["Scan ID", scan_id],
        ["Shop / Establishment", shop_name],
        ["Inspector ID", inspector_id],
        ["GPS Coordinates", gps_coordinates],
        ["Product Barcode", product_barcode or "(not provided)"],
        ["Confirmed Category", confirmed_category or "(unconfirmed)"],
        ["Notice Timestamp (UTC)", timestamp],
        ["Evidence SHA-256", sha256],
        ["Overall Status", str(verdict.get("overall_status", ""))],
    ]
    meta_table = Table(meta_rows, colWidths=[55 * mm, 115 * mm])
    meta_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8 * mm))

    # --- Violations table --------------------------------------------------
    story.append(Paragraph("Itemised Violations", h_style))
    violations = verdict.get("violations", []) or []
    parsed = verdict.get("parsed_fields", {}) or {}

    table_data = [["#", "Field", "Rule Citation", "Declared Value",
                   "Legal Requirement / Issue"]]
    for i, v in enumerate(violations, start=1):
        field = v.get("field", "")
        pf = parsed.get(field, {}) if isinstance(parsed, dict) else {}
        declared = (pf.get("raw_input") if isinstance(pf, dict) else None) or "(missing)"
        table_data.append([
            str(i),
            Paragraph(str(field), body),
            Paragraph(str(v.get("rule_citation", "")), body),
            Paragraph(str(declared), body),
            Paragraph(str(v.get("description", "")), body),
        ])
    if not violations:
        table_data.append(["-", Paragraph("None", body), "", "",
                           Paragraph("No violations recorded for this scan.", body)])

    vio_table = Table(table_data,
                      colWidths=[8 * mm, 28 * mm, 52 * mm, 32 * mm, 50 * mm])
    vio_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7a0000")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(vio_table)
    story.append(Spacer(1, 10 * mm))

    disclaimer = ParagraphStyle("Disc", parent=body, fontSize=7,
                                textColor=colors.grey)
    story.append(Paragraph(
        "This notice was generated by the NetraPack compliance system from an "
        "officer-confirmed inspection record. Rule citations are subject to "
        "final legal review. The SHA-256 hash above binds this notice to the "
        "specific scan evidence for integrity verification.", disclaimer))

    doc.build(story)

    return {
        "scan_id": scan_id,
        "file_path": str(out_path),
        "file_name": filename,
        "evidence_sha256": sha256,
        "timestamp_utc": timestamp,
        "violations_count": len(violations),
    }
