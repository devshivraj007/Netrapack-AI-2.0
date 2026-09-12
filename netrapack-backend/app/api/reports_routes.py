"""Report export routes.

  GET /api/v1/reports/{scan_id}/export?format=csv
      Export a scan's declarations + violations as CSV (default) or JSON.
      Complements the existing Section 36 PDF generation.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.auth.deps import require_officer
from app.db import repository

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{scan_id}/export", summary="Export a scan report as CSV or JSON")
def export_report(
    scan_id: str,
    format: str = Query("csv", description="csv (default) | json"),
    _user: dict = Depends(require_officer),
):
    scan = repository.get_latest_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404,
                            detail=f"No scan found for scan_id '{scan_id}'.")

    verdict = scan.get("verdict", {}) or {}
    ve = verdict.get("vision_extraction") or {}
    violations = verdict.get("violations", []) or []

    if format.lower() == "json":
        return {
            "scan_id": scan_id,
            "overall_status": verdict.get("overall_status"),
            "declarations": ve,
            "violations": violations,
        }

    # --- CSV ---------------------------------------------------------------
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Section 1: header/summary.
    writer.writerow(["NetraPack Scan Report"])
    writer.writerow(["scan_id", scan_id])
    writer.writerow(["created_at", scan.get("created_at", "")])
    writer.writerow(["overall_status", verdict.get("overall_status", "")])
    writer.writerow(["rules_passed", verdict.get("rules_passed", "")])
    writer.writerow(["rules_checked", verdict.get("rules_checked", "")])
    writer.writerow([])

    # Section 2: declarations (field, value).
    writer.writerow(["Declaration", "Value"])
    for key in [
        "mrp", "net_quantity", "unit_sale_price", "mfd_pkd_date",
        "expiry_date", "fssai_license_number", "manufacturer_details",
        "country_of_origin",
    ]:
        writer.writerow([key, _csv_val(ve.get(key))])
    writer.writerow([])

    # Section 3: violations (field, rule_citation, description).
    writer.writerow(["Violation Field", "Rule Citation", "Description"])
    if violations:
        for v in violations:
            writer.writerow([
                v.get("field", ""),
                v.get("rule_citation", ""),
                v.get("description", ""),
            ])
    else:
        writer.writerow(["(none)", "", "No violations recorded."])

    filename = f"netrapack_report_{scan_id}.csv"
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_val(v) -> str:
    if v is None:
        return "Not declared"
    return str(v)
