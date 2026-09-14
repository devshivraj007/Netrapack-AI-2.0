"""Officer Mode routes (Day 3).

  * POST /api/v1/officer/confirm-category
        Records an inspector's confirmation/override of the AI-suggested
        category (ai_suggested_not_confirmed -> inspector_confirmed). Appended
        to an immutable audit trail.

  * POST /api/v1/officer/generate-notice
        Generates the Section 36 legal notice PDF. HARD BLOCK: returns HTTP 403
        if the scan's category has not been inspector-confirmed, so no official
        notice can be produced from an unconfirmed AI guess.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi import Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import os
from pathlib import Path

from app.auth.deps import require_officer
from app.db import repository
from app.services import notice_pdf

router = APIRouter(prefix="/api/v1/officer", tags=["officer"])


class ConfirmCategoryRequest(BaseModel):
    scan_id: str
    confirmed_category: str = Field(..., description="Officer-chosen category.")
    inspector_id: str


class ConfirmCategoryResponse(BaseModel):
    scan_id: str
    confirmed_category: str
    status: str
    inspector_id: str
    confirmation_id: int


@router.post("/confirm-category", response_model=ConfirmCategoryResponse,
             summary="Officer confirms/changes the AI-suggested category")
def confirm_category(req: ConfirmCategoryRequest,
                     _user: dict = Depends(require_officer)) -> ConfirmCategoryResponse:
    scan = repository.get_latest_scan(req.scan_id)
    if not scan:
        raise HTTPException(status_code=404,
                            detail=f"No scan found for scan_id '{req.scan_id}'.")

    conf_id = repository.add_category_confirmation(
        req.scan_id, req.confirmed_category, req.inspector_id)
    return ConfirmCategoryResponse(
        scan_id=req.scan_id,
        confirmed_category=req.confirmed_category,
        status="inspector_confirmed",
        inspector_id=req.inspector_id,
        confirmation_id=conf_id,
    )


class GenerateNoticeRequest(BaseModel):
    scan_id: str
    shop_name: str
    inspector_id: str
    gps_coordinates: str
    product_barcode: Optional[str] = None


@router.post("/generate-notice", summary="Generate the Section 36 notice PDF")
def generate_notice(req: GenerateNoticeRequest,
                    _user: dict = Depends(require_officer)) -> dict:
    scan = repository.get_latest_scan(req.scan_id)
    if not scan:
        raise HTTPException(status_code=404,
                            detail=f"No scan found for scan_id '{req.scan_id}'.")

    # HARD BLOCK: no Section 36 notice unless the category is inspector-confirmed.
    if not repository.is_category_confirmed(req.scan_id):
        raise HTTPException(
            status_code=403,
            detail=(
                "Category is not inspector-confirmed. A Section 36 notice cannot "
                "be generated from an AI-suggested (unconfirmed) category. "
                "Confirm the category via /api/v1/officer/confirm-category first."
            ),
        )

    confirmation = repository.get_latest_confirmation(req.scan_id) or {}
    result = notice_pdf.generate_notice_pdf(
        scan_id=req.scan_id,
        verdict=scan.get("verdict", {}),
        shop_name=req.shop_name,
        inspector_id=req.inspector_id,
        gps_coordinates=req.gps_coordinates,
        product_barcode=req.product_barcode,
        confirmed_category=confirmation.get("confirmed_category"),
    )
    return {"status": "generated", **result}


_NOTICES_DIR = Path(os.environ.get("NETRAPACK_NOTICES_DIR",
                                   str(Path(__file__).resolve().parents[3]
                                       / "storage" / "notices")))

@router.get("/notice/{file_name}", summary="Download a generated notice PDF")
def download_notice(file_name: str):
    # Security: prevent path traversal
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = _NOTICES_DIR / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Notice PDF not found")
        
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type="application/pdf"
    )
