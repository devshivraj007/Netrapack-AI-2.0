"""Shared types for the AI product-recognition layer."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProductCategory(str, Enum):
    FOOD_AND_BEVERAGE = "food_and_beverage"
    PERSONAL_CARE = "personal_care"
    HOUSEHOLD = "household"
    ELECTRONICS = "electronics"
    PHARMACEUTICAL = "pharmaceutical"
    BABY_CARE = "baby_care"
    OTHER = "other"
    # Fallback when the AI is unavailable or not confident enough.
    GENERAL = "general"


class PackageSize(str, Enum):
    VERY_SMALL_SACHET = "very_small_sachet"
    STANDARD = "standard"
    BULK_PACK = "bulk_pack"
    UNKNOWN = "unknown"


class PackageShape(str, Enum):
    FLAT_BOX = "flat_box"
    CYLINDRICAL_CAN = "cylindrical_can"
    POUCH = "pouch"
    BOTTLE = "bottle"
    UNKNOWN = "unknown"


class AiSource(str, Enum):
    CLOUD_GROQ = "cloud_groq"
    LOCAL_OLLAMA = "local_ollama"
    CLOUD_GEMINI = "cloud_gemini"
    NONE = "none"  # no AI available -> rule engine only (Level 3)


class VisionExtraction(BaseModel):
    """Structured label fields read by the vision model (strict JSON schema).

    All optional: the model returns null for anything not visible on the pack.
    These map directly onto the Day 1 rule-engine ScanRequest fields.
    """

    mrp: Optional[float] = None
    # All distinct prices seen near the MRP (incl. struck-through), and whether
    # base-vs-promotional could NOT be confidently distinguished.
    mrp_all_prices: list[float] = Field(default_factory=list)
    mrp_is_ambiguous: bool = False
    net_quantity: Optional[str] = None
    unit_sale_price: Optional[float] = None
    mfd_pkd_date: Optional[str] = None
    expiry_date: Optional[str] = None
    fssai_license_number: Optional[str] = None
    manufacturer_details: Optional[str] = None
    country_of_origin: Optional[str] = None

    # Provenance for the demo badge / debugging.
    ai_source: "AiSource" = AiSource.NONE
    model_name: Optional[str] = None

    def to_scan_fields(self) -> dict[str, Optional[str]]:
        """Map to ScanRequest string fields the rule engine expects.

        The rule engine parses strings (it extracts numbers/units itself), so we
        stringify numeric values and preserve the MRP with a currency hint.

        MRP price handling (strikethrough/promotional):
          * ambiguous (can't tell base vs promo) -> pass ALL detected prices so
            the Day 1 MRP rule sees multiple values and routes to manual review.
          * clear single/active price -> use the resolved (lower/active) mrp.
        """
        mrp_decl = self._mrp_declaration()
        return {
            "mrp_declaration": mrp_decl,
            "net_quantity_declaration": self.net_quantity,
            "unit_sale_price_declaration": (
                f"Rs {self.unit_sale_price}" if self.unit_sale_price is not None else None
            ),
            "manufacturing_date_declaration": self.mfd_pkd_date,
            "expiry_date_declaration": self.expiry_date,
            "country_of_origin_declaration": self.country_of_origin,
            "manufacturer_name_address": self.manufacturer_details,
            "consumer_care_details": None,  # not in the required schema
            "fssai_license_number": (
                f"FSSAI {self.fssai_license_number}"
                if self.fssai_license_number else None
            ),
        }

    def _mrp_declaration(self) -> Optional[str]:
        """Build the MRP declaration string for the rule engine.

        - Ambiguous multi-price (no clear strikethrough): emit ALL prices so the
          Day 1 MRP rule detects multiple candidates and routes to manual review
          rather than guessing.
        - Otherwise: prefer the model's resolved active mrp; if that's missing
          but multiple prices were seen, fall back to the lowest (active/promo).
        """
        prices = [p for p in (self.mrp_all_prices or []) if p is not None]
        distinct = sorted(set(prices))

        # Ambiguous, or two+ indistinguishable prices with no resolved mrp:
        # hand both to the rule engine (its MRP check flags multiple prices).
        if self.mrp_is_ambiguous and len(distinct) >= 2:
            joined = " ".join(f"Rs. {p:g}" for p in distinct)
            return f"MRP {joined}"

        if self.mrp is not None:
            return f"MRP Rs. {self.mrp:g}"

        # No resolved mrp but a clear strikethrough set -> lowest is active.
        if len(distinct) >= 2 and not self.mrp_is_ambiguous:
            return f"MRP Rs. {distinct[0]:g}"
        if len(distinct) == 1:
            return f"MRP Rs. {distinct[0]:g}"
        return None


# Below this confidence we treat the guess as "general" and run only the
# standard checks (no category-specific FSSAI checks). Applies to BOTH the
# local model and Gemini.
CONFIDENCE_THRESHOLD = 0.70


class RecognitionResult(BaseModel):
    """The product-recognition outcome attached to a scan.

    Always labelled AI-suggested / not yet confirmed: an officer must confirm
    or change the category before it is trusted for anything official
    (the confirm/change screen is Day 3, in the app).
    """

    category: ProductCategory = ProductCategory.GENERAL
    package_size: PackageSize = PackageSize.UNKNOWN
    package_shape: PackageShape = PackageShape.UNKNOWN
    confidence: float = 0.0
    ai_source: AiSource = AiSource.NONE
    model_name: Optional[str] = None
    # Confidence gate outcome, surfaced for transparency.
    below_confidence_threshold: bool = False
    confirmation_status: str = Field(
        default="ai_suggested_not_confirmed",
        description="Always AI-suggested until an officer confirms (Day 3).",
    )
    note: Optional[str] = None

    @property
    def effective_category(self) -> ProductCategory:
        """The category actually used to drive checks.

        If confidence is below threshold, we degrade to GENERAL regardless of
        what the model guessed, so only standard checks run.
        """
        if self.below_confidence_threshold:
            return ProductCategory.GENERAL
        return self.category
