"""OCR pipeline orchestrator: raw image bytes -> labelled, cleansed fields.

Flow:
    bytes -> decode -> prepare (glare check + deskew)
          -> [if too much glare] STOP and ask for retake
          -> Tesseract word boxes
          -> spatial grouping (lines + phrase anchors, address merged)
          -> field extraction (keyword anchors)
          -> numeric character cleansing (Part D #1)
          -> field dict ready for the rule engine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from . import cleansing
from .field_extractor import extract_fields
from .image_prep import GLARE_RETAKE_THRESHOLD, prepare_image
from .reader import read_words, tesseract_available
from .spatial import group_text

# Glare handling thresholds.
#   _GLARE_HARD_CEILING : glare fraction above which we retake without trying OCR.
#   Below that, we attempt OCR and only retake when glare is elevated AND the
#   read was poor (too few words or very low confidence) - so glossy-but-readable
#   labels are not thrown away.
_GLARE_HARD_CEILING = 0.45   # 45%
_MIN_USABLE_WORDS = 12
_MIN_USABLE_CONF = 35.0


@dataclass
class OcrPipelineResult:
    ok: bool
    retake_required: bool = False
    retake_reason: Optional[str] = None
    glare_fraction: float = 0.0
    deskew_angle_deg: float = 0.0
    mean_conf: float = 0.0
    raw_text: str = ""
    manufacturer_block: str = ""
    fields: dict[str, Optional[str]] = field(default_factory=dict)
    error: Optional[str] = None


def decode_image(image_bytes: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def run_ocr_pipeline(image_bytes: bytes) -> OcrPipelineResult:
    if not tesseract_available():
        return OcrPipelineResult(
            ok=False,
            error="Tesseract OCR binary not found. Set TESSERACT_CMD or install it.",
        )

    bgr = decode_image(image_bytes)
    if bgr is None:
        return OcrPipelineResult(ok=False, error="Could not decode image bytes.")

    prepared = prepare_image(bgr)
    glare_pct = round(prepared.glare.glare_fraction * 100, 1)

    # Severe-glare ceiling: above this the image is genuinely unusable, so we
    # ask for a retake without even attempting OCR.
    if prepared.glare.glare_fraction >= _GLARE_HARD_CEILING:
        return OcrPipelineResult(
            ok=False,
            retake_required=True,
            retake_reason=(
                f"About {glare_pct}% of the image is affected by glare, which is "
                "too much to read reliably. Please retake the photo at a different "
                "angle to avoid a false reading."
            ),
            glare_fraction=prepared.glare.glare_fraction,
            deskew_angle_deg=prepared.deskew_angle_deg,
        )

    # Otherwise, run OCR and decide the retake based on whether text was
    # actually recoverable - not on a raw glare pixel count. Glossy retail
    # packaging often has moderate glare yet reads fine; we should not throw
    # those away. We only demand a retake when glare is elevated AND OCR came
    # back with too little usable content (few words / very low confidence).
    ocr = read_words(prepared.image)

    glare_elevated = prepared.glare.glare_fraction > GLARE_RETAKE_THRESHOLD
    poor_read = len(ocr.words) < _MIN_USABLE_WORDS or ocr.mean_conf < _MIN_USABLE_CONF
    if glare_elevated and poor_read:
        return OcrPipelineResult(
            ok=False,
            retake_required=True,
            retake_reason=(
                f"About {glare_pct}% of the image is affected by glare and the "
                "text could not be read reliably. Please retake the photo at a "
                "different angle to avoid a false reading."
            ),
            glare_fraction=prepared.glare.glare_fraction,
            deskew_angle_deg=prepared.deskew_angle_deg,
            mean_conf=ocr.mean_conf,
        )

    grouped = group_text(ocr.words)
    raw_fields = extract_fields(grouped)
    cleansed = cleansing.cleanse_fields(raw_fields)

    return OcrPipelineResult(
        ok=True,
        glare_fraction=prepared.glare.glare_fraction,
        deskew_angle_deg=prepared.deskew_angle_deg,
        mean_conf=ocr.mean_conf,
        raw_text=ocr.raw_text,
        manufacturer_block=grouped.manufacturer_block,
        fields=cleansed,
    )
