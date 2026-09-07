"""Admin sync routes (Day 3) for the Lovable Admin Dashboard.

  * GET /api/v1/admin/reports
        Returns scan/violation summary rows with optional status and date-range
        filtering. Read-only view over the append-only scans table.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import repository

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Investigation state machine. Each state lists its allowed next states.
_ALLOWED_TRANSITIONS = {
    "PENDING": {"NOTICE_ISSUED", "RESOLVED"},
    "NOTICE_ISSUED": {"RESOLVED"},
    "RESOLVED": set(),  # terminal
}
_VALID_STATES = set(_ALLOWED_TRANSITIONS) | {"RESOLVED"}


@router.get("/reports", summary="List scan reports with status/date filters")
def list_reports(
    status: Optional[str] = Query(
        None, description="Filter by overall_status: fully_compliant | "
                          "non_compliant | needs_manual_review."),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD (inclusive)."),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD (inclusive)."),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    rows = repository.query_reports(status=status, date_from=date_from,
                                   date_to=date_to, limit=limit)
    # Attach current investigation status to each row.
    for r in rows:
        r["investigation_status"] = repository.get_current_status(r["scan_id"])
    return {
        "count": len(rows),
        "filters": {"status": status, "date_from": date_from, "date_to": date_to},
        "reports": rows,
    }


class StatusUpdateRequest(BaseModel):
    new_status: str = Field(..., description="PENDING | NOTICE_ISSUED | RESOLVED")
    changed_by: Optional[str] = Field(None, description="Admin officer id.")
    note: Optional[str] = None


@router.post("/reports/{report_id}/status",
             summary="Update an investigation's status (state machine)")
def update_report_status(report_id: str, req: StatusUpdateRequest) -> dict:
    new_status = req.new_status.strip().upper()
    if new_status not in _VALID_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{new_status}'. Valid: {sorted(_VALID_STATES)}.")

    # The report_id is the scan_id; require the scan to exist.
    if not repository.get_latest_scan(report_id):
        raise HTTPException(status_code=404,
                            detail=f"No scan/report found for '{report_id}'.")

    current = repository.get_current_status(report_id)
    if new_status == current:
        raise HTTPException(status_code=409,
                            detail=f"Report is already in state '{current}'.")
    if new_status not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=409,
            detail=(f"Illegal transition {current} -> {new_status}. "
                    f"Allowed from {current}: "
                    f"{sorted(_ALLOWED_TRANSITIONS.get(current, set())) or 'none (terminal)'}."))

    hist_id = repository.add_status_transition(
        report_id, current, new_status, req.changed_by, req.note)
    return {
        "report_id": report_id,
        "old_status": current,
        "new_status": new_status,
        "transition_id": hist_id,
        "history": repository.get_status_history(report_id),
    }
