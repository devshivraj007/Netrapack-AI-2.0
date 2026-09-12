"""API routes for scan processing."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from pydantic import BaseModel, Field

from app.schemas.scan import ScanRequest, ScanVerdict
from app.services import scan_service, url_scanner

router = APIRouter(prefix="/api/v1/scan", tags=["scan"])


@router.post("/process", response_model=ScanVerdict, summary="Process a text scan submission")
def process_scan(request: ScanRequest) -> ScanVerdict:
    """Run the compliance rule engine over pre-extracted label text.

    Day 1 compatible: input is typed-out text. Returns a verdict with overall
    status, pass count, violations, parsed fields, and Day 2 metadata
    (timing / model / online-offline).
    """
    return scan_service.process_text_scan(request)


@router.post(
    "/process-photo",
    response_model=ScanVerdict,
    summary="Process a scan from real photo(s) (Day 3: Vision AI extraction)",
)
async def process_photo(
    scan_id: str = Form(...),
    barcode: Optional[str] = Form(None),
    image: UploadFile = File(..., description="Front image (required)."),
    image_back: Optional[UploadFile] = File(None, description="Back image (optional)."),
) -> ScanVerdict:
    """Full Day 3 pipeline: product recognition + Vision AI field extraction.

    Accepts front (and optional back) photos. Runs product recognition, then
    Vision AI structured field extraction (Level 1 Ollama -> Level 2 Gemini) as
    the primary label reader, falling back to Tesseract OCR when no vision model
    is available. The extracted fields feed the Day 1 rule engine unchanged.
    """
    images = [await image.read()]
    if image_back is not None:
        images.append(await image_back.read())
    return scan_service.process_photo_scan_multi(scan_id, images, barcode)


@router.post("/readability-check",
             summary="Approximate font-size/readability check (LMPC Rule 9, advisory)")
async def readability_check(image: UploadFile = File(...)) -> dict:
    """Advisory-only estimate of whether declaration text is large enough.

    HONEST LIMITATION: a photo has no physical scale, so this returns a
    PROPORTIONAL approximation (text height vs frame), not a certified mm
    measurement. Flags 'possibly too small' for manual verification.
    """
    import cv2
    import numpy as np

    from app.ocr.image_prep import prepare_image
    from app.ocr.reader import read_words, tesseract_available
    from app.ocr.readability import assess_readability

    if not tesseract_available():
        return {"assessed": False,
                "note": "OCR (Tesseract) not available; cannot assess readability."}
    data = await image.read()
    arr = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"assessed": False, "note": "Could not decode image."}
    prepared = prepare_image(bgr)
    ocr = read_words(prepared.image)
    result = assess_readability(ocr.words, prepared.image.shape[0])
    return {
        "assessed": result.assessed,
        "approximate": result.approximate,
        "median_char_px": result.median_char_px,
        "image_height_px": result.image_height_px,
        "char_height_fraction": result.char_height_fraction,
        "likely_too_small": result.likely_too_small,
        "note": result.note,
    }


class UrlScanRequest(BaseModel):
    url: str = Field(..., description="Product page URL (Blinkit, Amazon India, etc.).")


@router.post("/url", summary="Scan an e-commerce product URL (LMPC Rule 6(10))")
def scan_url(req: UrlScanRequest) -> dict:
    """Fetch a product listing and check e-commerce mandatory declarations.

    Extracts MRP, net quantity, country of origin, and manufacturer from the
    page and runs Rule 6(10) checks. Degrades gracefully on JS-rendered or
    bot-protected pages (reports what it could not read rather than guessing).
    """
    result = url_scanner.scan_url(req.url)
    return {
        "url": result.url,
        "fetched": result.fetched,
        "http_status": result.http_status,
        "extracted": result.extracted,
        "verdict": result.verdict,
        "note": result.note,
    }
