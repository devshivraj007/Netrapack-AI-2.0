"""Scan orchestration service.

Ties the Day 2 pieces together for both input modes:

  Photo mode (new):
    image bytes
      -> product recognition (3-level: Ollama -> Gemini -> general)
      -> OCR pipeline (glare guard, deskew, spatial grouping, cleansing)
      -> [if retake required] return a retake verdict, no rule run
      -> rule engine (category gates the FSSAI check)
      -> attach AI recognition + OCR info + timing/model/online metadata
      -> persist scan (append-only) + any violations as reports

  Text mode (Day 1 compatible):
    typed fields -> rule engine -> verdict (+ optional recognition skipped)

The rule LOGIC itself is unchanged from Day 1; we only change what feeds it and
what metadata we attach around it.
"""

from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.ai.recognizer import ProductRecognizer, detect_online
from app.ai.types import AiSource, RecognitionResult
from app.db import repository
from app.ocr.pipeline import run_ocr_pipeline
from app.rule_engine.engine import RuleEngine
from app.services import barcode_verify
from app.schemas.scan import (
    AiRecognition,
    OcrInfo,
    OverallStatus,
    ReadabilityInfo,
    ScanMetadata,
    ScanRequest,
    ScanVerdict,
)

_engine = RuleEngine()
_recognizer = ProductRecognizer()


def _ai_level_label(source: AiSource) -> str:
    return {
        AiSource.CLOUD_GROQ: "cloud_ai",
        AiSource.LOCAL_OLLAMA: "local_ai",
        AiSource.CLOUD_GEMINI: "cloud_ai",
        AiSource.NONE: "rule_engine_only",
    }.get(source, "rule_engine_only")


_SCANS_DIR = Path(os.environ.get(
    "NETRAPACK_SCANS_DIR",
    str(Path(__file__).resolve().parents[2] / "storage" / "scans")))


def _store_image(scan_id: str, image_bytes: bytes) -> tuple[str, str]:
    """Save the raw image and return (sha256_hex, saved_path).

    The stored image + hash are the chain-of-custody evidence anchor.
    """
    sha = hashlib.sha256(image_bytes).hexdigest()
    _SCANS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitise scan_id for a filename.
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in scan_id)
    path = _SCANS_DIR / f"{safe}_{ts}.jpg"
    with open(path, "wb") as f:
        f.write(image_bytes)
    return sha, str(path)


def _edge_telemetry(source: AiSource, online: bool) -> tuple[str, str]:
    """Return (ai_level, connectivity_state) with the exact edge values.

    When the scan ran on the LOCAL model AND no network was available, we report
    the air-gapped edge state the spec asks for.
    """
    if not online and source == AiSource.LOCAL_OLLAMA:
        return "local_edge", "offline_edge"
    if not online:
        return _ai_level_label(source), "offline_edge"
    return _ai_level_label(source), "online"


def _to_ai_recognition(rec: RecognitionResult) -> AiRecognition:
    return AiRecognition(
        category=rec.category.value,
        effective_category=rec.effective_category.value,
        package_size=rec.package_size.value,
        package_shape=rec.package_shape.value,
        confidence=rec.confidence,
        ai_source=rec.ai_source.value,
        model_name=rec.model_name,
        below_confidence_threshold=rec.below_confidence_threshold,
        confirmation_status=rec.confirmation_status,
        note=rec.note,
    )


def _assess_readability(image_bytes: bytes) -> ReadabilityInfo:
    """Advisory font-size/readability estimate on the primary image.

    Runs a lightweight OCR word-geometry pass to compare median text height
    against the frame height. Degrades gracefully (assessed=False) when
    Tesseract is unavailable, the image cannot be decoded, or too little text
    is detected. Never raises into the scan path.
    """
    try:
        import cv2
        import numpy as np

        from app.ocr.image_prep import prepare_image
        from app.ocr.readability import assess_readability
        from app.ocr.reader import read_words, tesseract_available

        if not image_bytes:
            return ReadabilityInfo(
                assessed=False, note="No image supplied; readability not assessed.")
        if not tesseract_available():
            return ReadabilityInfo(
                assessed=False,
                note="OCR (Tesseract) not available; readability not assessed.")

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            return ReadabilityInfo(
                assessed=False, note="Could not decode image for readability.")

        prepared = prepare_image(bgr)
        ocr = read_words(prepared.image)
        result = assess_readability(ocr.words, prepared.image.shape[0])
        return ReadabilityInfo(
            assessed=result.assessed,
            approximate=result.approximate,
            median_char_px=result.median_char_px,
            image_height_px=result.image_height_px,
            char_height_fraction=result.char_height_fraction,
            likely_too_small=result.likely_too_small,
            note=result.note,
        )
    except Exception:
        # Readability is advisory; never break the scan response over it.
        return ReadabilityInfo(
            assessed=False, note="Readability check could not be completed.")


def process_text_scan(req: ScanRequest) -> ScanVerdict:
    """Day 1 compatible path: typed fields straight into the rule engine.

    No image, so no AI recognition; category defaults to 'general' (standard
    checks + FSSAI is skipped unless caller later supplies a category).
    """
    start = time.perf_counter()
    verdict = _engine.evaluate(req, product_category="general")
    
    if req.barcode:
        verdict.barcode_verification = barcode_verify.cross_verify(req.barcode, req.model_dump())
        
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    verdict.metadata = ScanMetadata(
        processing_ms=round(elapsed_ms, 2),
        ai_model_used=None,
        ai_level="rule_engine_only",
        online_offline="online" if detect_online() else "offline",
    )
    _persist(verdict, input_mode="text")
    return verdict


def process_photo_scan(scan_id: str, image_bytes: bytes,
                       barcode: Optional[str] = None) -> ScanVerdict:
    """Single-image convenience wrapper (back-compatible)."""
    return process_photo_scan_multi(scan_id, [image_bytes], barcode)


def _recognize_from_reference(ref: dict) -> RecognitionResult:
    """Build a recognition result from a known reference product (barcode match).

    Skips the AI category call entirely: the reference DB already tells us the
    category with certainty, so we return a full-confidence result and let the
    rule engine run immediately.
    """
    from app.ai.types import ProductCategory

    try:
        category = ProductCategory(str(ref.get("category", "general")))
    except ValueError:
        category = ProductCategory.GENERAL
    return RecognitionResult(
        category=category,
        confidence=1.0,
        ai_source=AiSource.NONE,
        model_name="reference_db",
        below_confidence_threshold=False,
        confirmation_status="ai_suggested_not_confirmed",
        note=(
            f"Category '{category.value}' taken from the reference product "
            "database (barcode match) — no AI category call needed."
        ),
    )


def process_photo_scan_multi(scan_id: str, images: list[bytes],
                            barcode: Optional[str] = None) -> ScanVerdict:
    """Day 3 photo path (front + back).

    Speed strategy:
      0. Barcode shortcut: if the barcode matches a known reference product, use
         its category directly and SKIP the AI category-recognition call.
      1. Category recognition (AI) and field reading run CONCURRENTLY (not
         sequentially) when a vision call is needed, so we pay one round-trip of
         wall-clock time instead of two.
      2. Field reading: Gemini (short timeout) -> local Ollama -> Tesseract OCR.
    """
    start = time.perf_counter()
    online = detect_online()
    primary = images[0] if images else b""

    # Chain-of-custody: store the raw (front) image and its SHA-256 up front.
    image_hash, image_path = (None, None)
    if primary:
        image_hash, image_path = _store_image(scan_id, primary)

    # --- Barcode shortcut: known product -> skip the AI category call --------
    reference = None
    if barcode:
        try:
            reference = repository.get_product_by_barcode(barcode)
        except Exception:
            reference = None

    # --- Run category recognition + field extraction CONCURRENTLY ------------
    # When the barcode is known we already have the category, so we only need
    # the field extraction; otherwise we fire both at once and join.
    with ThreadPoolExecutor(max_workers=2) as pool:
        fields_future = pool.submit(_recognizer.extract_fields, images)
        if reference is not None:
            rec = _recognize_from_reference(reference)
        else:
            rec_future = pool.submit(_recognizer.recognize, primary)
            rec = rec_future.result()
        vision = fields_future.result()

    ai_recognition = _to_ai_recognition(rec)

    ocr_info: Optional[OcrInfo] = None
    extraction_source = "none"
    vision_payload = None
    fields: dict = {}

    if vision is not None:
        extraction_source = "vision_ai"
        vision_payload = vision.model_dump(mode="json")
        fields = vision.to_scan_fields()
        # The model that actually read the fields determines edge state.
        field_source = vision.ai_source
    else:
        field_source = AiSource.NONE
        # --- Fallback: OCR --------------------------------------------------
        ocr = run_ocr_pipeline(primary)
        ocr_info = OcrInfo(
            used_ocr=True,
            retake_required=ocr.retake_required,
            retake_reason=ocr.retake_reason,
            glare_fraction=round(ocr.glare_fraction, 4),
            deskew_angle_deg=round(ocr.deskew_angle_deg, 2),
            mean_confidence=round(ocr.mean_conf, 2),
            manufacturer_block=ocr.manufacturer_block or None,
        )
        if ocr.retake_required or not ocr.ok:
            if not ocr.ok and not ocr.retake_reason:
                ocr_info.retake_reason = ocr.error
            return _finish(
                scan_id, OverallStatus.NEEDS_MANUAL_REVIEW, [], {},
                ai_recognition, ocr_info, None, "ocr", rec, online, start,
                image_hash, image_path, _assess_readability(primary),
            )
        extraction_source = "ocr"
        fields = dict(ocr.fields)

    # --- Rule engine (category gates the FSSAI check) ------------------------
    req = ScanRequest(scan_id=scan_id, barcode=barcode, **fields)
    verdict = _engine.evaluate(req, product_category=rec.effective_category.value)
    
    if barcode:
        verdict.barcode_verification = barcode_verify.cross_verify(barcode, req.model_dump())
        
    verdict.ai_recognition = ai_recognition
    verdict.ocr = ocr_info
    verdict.vision_extraction = vision_payload
    # Advisory font-size/readability estimate on the front image (always attached
    # to photo scans so it can't be missed; degrades to assessed=False).
    verdict.readability = _assess_readability(primary)

    # Edge telemetry keys off whichever source actually read the label fields.
    ai_level, connectivity = _edge_telemetry(field_source, online)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    verdict.metadata = ScanMetadata(
        processing_ms=round(elapsed_ms, 2),
        ai_model_used=(vision.model_name if vision else rec.model_name),
        ai_level=ai_level,
        online_offline="online" if online else "offline",
        extraction_source=extraction_source,
        connectivity_state=connectivity,
        image_hash=image_hash,
    )
    _persist(verdict, input_mode="photo", image_hash=image_hash,
             image_path=image_path)
    return verdict


def _finish(scan_id, status, violations, parsed, ai_recognition, ocr_info,
            vision_payload, extraction_source, rec, online, start,
            image_hash=None, image_path=None, readability=None) -> ScanVerdict:
    """Assemble a verdict for an early-return (e.g. glare retake) and persist."""
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    ai_level, connectivity = _edge_telemetry(rec.ai_source, online)
    verdict = ScanVerdict(
        scan_id=scan_id, overall_status=status,
        rules_passed=0, rules_checked=0, violations=violations,
        parsed_fields=parsed, ai_recognition=ai_recognition, ocr=ocr_info,
        vision_extraction=vision_payload, readability=readability,
        metadata=ScanMetadata(
            processing_ms=round(elapsed_ms, 2),
            ai_model_used=rec.model_name,
            ai_level=ai_level,
            online_offline="online" if online else "offline",
            extraction_source=extraction_source,
            connectivity_state=connectivity,
            image_hash=image_hash,
        ),
    )
    _persist(verdict, input_mode="photo", image_hash=image_hash,
             image_path=image_path)
    return verdict


def _persist(verdict: ScanVerdict, input_mode: str,
             image_hash: Optional[str] = None,
             image_path: Optional[str] = None) -> None:
    """Append the scan and any violations. Never raises into the request path."""
    try:
        payload = verdict.model_dump()
        repository.insert_scan(payload, input_mode=input_mode,
                               image_hash=image_hash, image_path=image_path)
        repository.insert_reports(verdict.scan_id, payload.get("violations", []))
    except Exception:
        # Persistence must not break the response; scans/reports are best-effort
        # writes and any DB issue is logged elsewhere in a real deployment.
        pass
