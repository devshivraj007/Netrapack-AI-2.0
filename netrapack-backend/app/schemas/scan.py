"""Pydantic schemas for the scan processing endpoint.

These describe the shape of the request (pre-extracted label text fields)
and the response (the compliance verdict).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class ScanRequest(BaseModel):
    """A scan submission with pre-extracted (typed-out) label text.

    On Day 1 we are testing the rule engine with typed text. Real OCR from
    photos arrives on Day 2, but the field contract stays the same.
    """

    scan_id: str = Field(..., description="Unique identifier for this scan.")
    barcode: Optional[str] = Field(
        None, description="Optional barcode digits. NOT used to infer origin."
    )

    mrp_declaration: Optional[str] = Field(
        None, description="Raw MRP text, e.g. 'MRP Rs. 45 (incl. of all taxes)'."
    )
    net_quantity_declaration: Optional[str] = Field(
        None, description="Raw net quantity text, e.g. '3 x 50g' or '100g + 20g extra'."
    )
    manufacturing_date_declaration: Optional[str] = Field(
        None, description="Raw mfg date text, e.g. '03/2026' or 'MAR 2026'."
    )
    expiry_date_declaration: Optional[str] = Field(
        None, description="Raw expiry/best-before text (may be absent)."
    )
    unit_sale_price_declaration: Optional[str] = Field(
        None, description="Raw unit sale price text, e.g. 'Rs 9 per 100g'."
    )
    manufacturer_name_address: Optional[str] = Field(
        None, description="Raw manufacturer name and address block."
    )
    country_of_origin_declaration: Optional[str] = Field(
        None, description="Raw origin text, e.g. 'Made in India'."
    )
    consumer_care_details: Optional[str] = Field(
        None, description="Raw consumer care text (should contain phone or email)."
    )
    fssai_license_number: Optional[str] = Field(
        None, description="Raw FSSAI text (should contain a 14-digit number)."
    )
    product_category: Optional[str] = Field(
        None, description="Optional product category (e.g. food_and_beverage, personal_care)."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "scan_id": "scan-001",
                "barcode": "8901234567890",
                "mrp_declaration": "MRP Rs. 45 (incl. of all taxes)",
                "net_quantity_declaration": "200g",
                "manufacturing_date_declaration": "MAR 2026",
                "expiry_date_declaration": "MAR 2027",
                "unit_sale_price_declaration": "Rs 22.50 per 100g",
                "manufacturer_name_address": "ABC Foods Pvt Ltd, Plot 5, Pune, MH 411001",
                "country_of_origin_declaration": "Made in India",
                "consumer_care_details": "care@abcfoods.com, 1800-123-456",
                "fssai_license_number": "FSSAI Lic. No. 10012345678901",
            }
        }
    }


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class OverallStatus(str, Enum):
    FULLY_COMPLIANT = "fully_compliant"
    NON_COMPLIANT = "non_compliant"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class FieldStatus(str, Enum):
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    NOT_REQUIRED = "not_required"  # e.g. USP exemption applies


class Violation(BaseModel):
    field: str = Field(..., description="Which field/check produced the violation.")
    rule_citation: str = Field(..., description="Exact legal rule reference.")
    description: str = Field(..., description="Plain-language description of the issue.")


class FieldResult(BaseModel):
    """Structured/parsed outcome for a single input field."""

    field: str
    status: FieldStatus
    raw_input: Optional[str] = None
    parsed: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class AiRecognition(BaseModel):
    """AI-suggested product recognition attached to a scan.

    Always AI-suggested until an officer confirms/changes it (Day 3).
    """

    category: str = "general"
    effective_category: str = "general"  # after the confidence gate
    package_size: str = "unknown"
    package_shape: str = "unknown"
    confidence: float = 0.0
    ai_source: str = "none"  # cloud_groq | cloud_gemini | local_ollama | none
    model_name: Optional[str] = None
    below_confidence_threshold: bool = False
    confirmation_status: str = "ai_suggested_not_confirmed"
    note: Optional[str] = None


class ScanMetadata(BaseModel):
    """Small technical facts about how this scan ran (for the demo badge)."""

    processing_ms: float = Field(..., description="Total processing time in ms.")
    ai_model_used: Optional[str] = Field(
        None, description="Model used for recognition (local/cloud) or None."
    )
    ai_level: str = Field(
        "rule_engine_only",
        description="local_ai | cloud_ai | rule_engine_only.",
    )
    online_offline: str = Field("offline", description="online | offline for this scan.")
    extraction_source: str = Field(
        "none",
        description="How label fields were read: vision_ai | ocr | none.",
    )
    # Day 5 edge telemetry (exact values for the demo badge).
    connectivity_state: str = Field(
        "online",
        description="online | offline_edge - offline_edge when no network was used.",
    )
    image_hash: Optional[str] = Field(
        None, description="SHA-256 of the raw scanned image (chain-of-custody)."
    )


class OcrInfo(BaseModel):
    """What the OCR step produced (present only for photo scans)."""

    used_ocr: bool = False
    retake_required: bool = False
    retake_reason: Optional[str] = None
    glare_fraction: float = 0.0
    deskew_angle_deg: float = 0.0
    mean_confidence: float = 0.0
    manufacturer_block: Optional[str] = None


class ReadabilityInfo(BaseModel):
    """Advisory font-size / readability estimate (LMPC Rule 9 area).

    HONEST SCOPE: this is a PROPORTIONAL approximation (text height vs frame),
    not a certified mm measurement. `assessed` is False when there was not
    enough data (e.g. OCR unavailable or too little text detected).
    """

    assessed: bool = False
    approximate: bool = True
    median_char_px: float = 0.0
    image_height_px: int = 0
    char_height_fraction: float = 0.0
    likely_too_small: bool = False
    note: str = ""


class FieldComparison(BaseModel):
    field: str
    reference: Optional[str]
    declared: Optional[str]
    status: str  # agree | mismatch | not_available


class BarcodeVerification(BaseModel):
    scanned_barcode: Optional[str]
    matched: bool
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    comparisons: list[FieldComparison] = Field(default_factory=list)
    note: Optional[str] = None
    gs1_prefix: Optional[str] = None
    gs1_country: Optional[str] = None
    origin_matches_barcode: Optional[bool] = None


class ScanVerdict(BaseModel):
    scan_id: str
    overall_status: OverallStatus
    rules_passed: int
    rules_checked: int
    violations: list[Violation] = Field(default_factory=list)
    parsed_fields: dict[str, FieldResult] = Field(default_factory=dict)

    # Day 2 additions (all optional so Day 1 text-only path is unaffected).
    ai_recognition: Optional[AiRecognition] = None
    ocr: Optional[OcrInfo] = None
    metadata: Optional[ScanMetadata] = None

    # Day 3: the structured fields the vision AI read from the label (when used).
    vision_extraction: Optional[dict[str, Any]] = None

    # Advisory font-size / readability estimate (LMPC Rule 9 area). Attached to
    # photo scans automatically; None on text-only scans or when unassessable.
    readability: Optional[ReadabilityInfo] = None
    
    # Day 3: Cross-verification of the printed text against the barcode database
    barcode_verification: Optional[BarcodeVerification] = None
