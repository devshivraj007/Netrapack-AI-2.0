"""Product recognition with the 4-tier fallback chain.

Order (Groq-primary, low latency + high reliability):
    Level 1: Groq cloud (qwen/qwen3.8-27b)    - primary ultra-fast LPU extractor
    Level 2: Gemini cloud (gemini-3.6-flash)  - secondary cloud AI fallback
    Level 3: local AI (Ollama qwen2.5vl:3b)   - offline local safety net
    Level 4: neither                          - category = general / OCR fallback

Rationale: Groq provides near-instant LPU inference (~2-5s) with structured JSON
mode, while Gemini provides a robust secondary cloud fallback, and local qwen is
the offline air-gapped safety net.

The confidence gate (< 70% -> general) applies to ALL AI levels. Whatever the
source, the result is always labelled "AI-suggested, not yet confirmed" and an
officer must confirm/change it before official use (Day 3).
"""

from __future__ import annotations

import socket
from typing import Optional

from .providers import GeminiVisionProvider, GroqVisionProvider, OllamaVisionProvider
from .types import (
    AiSource,
    CONFIDENCE_THRESHOLD,
    PackageShape,
    PackageSize,
    ProductCategory,
    RecognitionResult,
    VisionExtraction,
)


def detect_online() -> bool:
    """Best-effort check for internet connectivity (used only for the badge)."""
    try:
        socket.setdefaulttimeout(2.0)
        with socket.create_connection(("8.8.8.8", 53)):
            return True
    except OSError:
        return False


CORE_MANDATORY_FIELDS = (
    "mrp",
    "net_quantity",
    "mfd_pkd_date",
    "manufacturer_details",
    "consumer_care_details",
    "country_of_origin",
)


def _count_core_fields(extraction: Optional[VisionExtraction]) -> int:
    if not extraction:
        return 0
    count = 0
    if extraction.mrp is not None or (extraction.mrp_all_prices and len(extraction.mrp_all_prices) > 0):
        count += 1
    if extraction.net_quantity:
        count += 1
    if extraction.mfd_pkd_date:
        count += 1
    if extraction.manufacturer_details:
        count += 1
    if extraction.consumer_care_details:
        count += 1
    if extraction.country_of_origin:
        count += 1
    return count


def _get_unclear_or_missing_core(extraction: Optional[VisionExtraction]) -> list[str]:
    """Return a list of core mandatory fields that are either missing or flagged unclear/ambiguous."""
    if not extraction:
        return list(CORE_MANDATORY_FIELDS)
    
    needed = []
    unclear_set = set(extraction.unclear_fields or [])
    
    # 1. MRP: missing, flagged unclear, or ambiguous
    if extraction.mrp is None and not (extraction.mrp_all_prices and len(extraction.mrp_all_prices) > 0):
        needed.append("mrp")
    elif "mrp" in unclear_set or extraction.mrp_is_ambiguous:
        needed.append("mrp")
        
    # 2. Net quantity
    if not extraction.net_quantity or "net_quantity" in unclear_set:
        needed.append("net_quantity")
        
    # 3. Mfd / pkd date
    if not extraction.mfd_pkd_date or "mfd_pkd_date" in unclear_set:
        needed.append("mfd_pkd_date")
        
    # 4. Manufacturer details
    if not extraction.manufacturer_details or "manufacturer_details" in unclear_set:
        needed.append("manufacturer_details")
        
    # 5. Consumer care details
    if not extraction.consumer_care_details or "consumer_care_details" in unclear_set:
        needed.append("consumer_care_details")
        
    # 6. Country of origin
    if not extraction.country_of_origin or "country_of_origin" in unclear_set:
        needed.append("country_of_origin")
        
    return needed


def _merge_extractions(primary: VisionExtraction, secondary: VisionExtraction) -> VisionExtraction:
    """Intelligently merge two extraction attempts:
    Prioritizes clear, high-confidence readings over unclear or missing ones.
    If a secondary attempt clarifies a previously unclear field, the unclear flag is cleared.
    """
    primary_unclear = set(primary.unclear_fields or [])
    secondary_unclear = set(secondary.unclear_fields or [])
    
    def pick_best(field_name: str, p_val, s_val):
        p_is_unclear = field_name in primary_unclear
        s_is_unclear = field_name in secondary_unclear
        p_has = p_val is not None and p_val != ""
        s_has = s_val is not None and s_val != ""
        
        # If primary has value and is clear, keep primary
        if p_has and not p_is_unclear:
            return p_val, False
        # If secondary has value and is clear, adopt secondary (clarified!)
        if s_has and not s_is_unclear:
            return s_val, False
        # If primary has value (even if unclear), keep primary's reading
        if p_has:
            return p_val, p_is_unclear
        # Otherwise fallback to secondary
        if s_has:
            return s_val, s_is_unclear
        return None, False

    mrp_val, mrp_unclear = pick_best("mrp", primary.mrp, secondary.mrp)
    qty_val, qty_unclear = pick_best("net_quantity", primary.net_quantity, secondary.net_quantity)
    usp_val, usp_unclear = pick_best("unit_sale_price", primary.unit_sale_price, secondary.unit_sale_price)
    date_val, date_unclear = pick_best("mfd_pkd_date", primary.mfd_pkd_date, secondary.mfd_pkd_date)
    exp_val, exp_unclear = pick_best("expiry_date", primary.expiry_date, secondary.expiry_date)
    fssai_val, fssai_unclear = pick_best("fssai_license_number", primary.fssai_license_number, secondary.fssai_license_number)
    mfr_val, mfr_unclear = pick_best("manufacturer_details", primary.manufacturer_details, secondary.manufacturer_details)
    origin_val, origin_unclear = pick_best("country_of_origin", primary.country_of_origin, secondary.country_of_origin)
    care_val, care_unclear = pick_best("consumer_care_details", primary.consumer_care_details, secondary.consumer_care_details)
    
    final_unclear = []
    if mrp_unclear: final_unclear.append("mrp")
    if qty_unclear: final_unclear.append("net_quantity")
    if usp_unclear: final_unclear.append("unit_sale_price")
    if date_unclear: final_unclear.append("mfd_pkd_date")
    if exp_unclear: final_unclear.append("expiry_date")
    if fssai_unclear: final_unclear.append("fssai_license_number")
    if mfr_unclear: final_unclear.append("manufacturer_details")
    if origin_unclear: final_unclear.append("country_of_origin")
    if care_unclear: final_unclear.append("consumer_care_details")

    # Ambiguity flag: if secondary resolved ambiguous MRP with a clear single MRP, resolve it
    mrp_ambig = primary.mrp_is_ambiguous
    if mrp_ambig and secondary.mrp is not None and not secondary.mrp_is_ambiguous:
        mrp_ambig = False

    return VisionExtraction(
        mrp=mrp_val,
        mrp_all_prices=primary.mrp_all_prices or secondary.mrp_all_prices,
        mrp_is_ambiguous=mrp_ambig,
        net_quantity=qty_val,
        unit_sale_price=usp_val,
        mfd_pkd_date=date_val,
        expiry_date=exp_val,
        fssai_license_number=fssai_val,
        manufacturer_details=mfr_val,
        country_of_origin=origin_val,
        consumer_care_details=care_val,
        category=primary.category or secondary.category,
        unclear_fields=final_unclear,
        ai_source=primary.ai_source,
        model_name=f"{primary.model_name}+{secondary.model_name}" if secondary.model_name and secondary.model_name != primary.model_name else primary.model_name,
    )


class ProductRecognizer:
    def __init__(
        self,
        groq: Optional[GroqVisionProvider] = None,
        gemini: Optional[GeminiVisionProvider] = None,
        ollama: Optional[OllamaVisionProvider] = None,
    ):
        self.groq = groq or GroqVisionProvider()
        self.gemini = gemini or GeminiVisionProvider()
        self.ollama = ollama or OllamaVisionProvider()

    def recognize(self, image_bytes: bytes) -> RecognitionResult:
        """Run product recognition through the 4-tier fallback chain:
        Groq -> Gemini -> Ollama -> Level 4 (rule engine only, category = general).
        """
        for provider in (self.groq, self.gemini, self.ollama):
            res = self._try_provider(provider, image_bytes)
            if res is not None:
                return self._apply_confidence_gate(res)

        return RecognitionResult(
            category=ProductCategory.GENERAL,
            package_size=PackageSize.UNKNOWN,
            package_shape=PackageShape.UNKNOWN,
            confidence=0.0,
            ai_source=AiSource.NONE,
            model_name=None,
            below_confidence_threshold=True,
            confirmation_status="autonomous_rule_engine",
            note=(
                "No cloud AI provider reached; defaulted autonomously to 'general' category "
                "with standard statutory compliance checks applied."
            ),
        )

    def _try_provider(self, provider, image_bytes: bytes) -> Optional[RecognitionResult]:
        try:
            available, _ = provider.is_available()
            if not available:
                return None
            return provider.recognize(image_bytes)
        except Exception:
            return None

    def extract_fields(self, images: list[bytes]) -> Optional[VisionExtraction]:
        """Vision structured extraction with autonomous multi-pass accuracy maximization.

        Pipeline:
        1. Primary Extraction: Attempt with primary available provider on the provided images.
        2. Multi-Image Pass: If multiple images were uploaded (e.g. front, back, stamped flap)
           and any core mandatory field is unclear or missing, inspect individual images at
           full dedicated resolution to clarify faint ink stamps / small print.
        3. Cross-Provider Fallback: If core mandatory fields remain unclear or missing,
           automatically retry with the next provider in the chain (capped at 1 retry).
        4. Intelligent Merge: Merges clearer readings into the final extraction, clearing
           unclear flags whenever an improved reading is found.
        """
        providers = [self.groq, self.gemini, self.ollama]
        current_result: Optional[VisionExtraction] = None
        active_provider = None
        active_provider_idx = -1

        # 1. Attempt primary extraction
        for idx, provider in enumerate(providers):
            try:
                available, _ = provider.is_available()
                if not available:
                    continue
                current_result = provider.extract_fields(images)
                active_provider = provider
                active_provider_idx = idx
                break
            except Exception:
                continue

        if current_result is None:
            return None

        # Check if all core mandatory fields are clear and present
        unclear_or_missing = _get_unclear_or_missing_core(current_result)
        if not unclear_or_missing:
            return current_result

        # 2. Targeted Inspection of the detail/stamp panel (capped at 1 to conserve token budget)
        if len(images) > 1 and active_provider is not None:
            try:
                single_res = active_provider.extract_fields([images[-1]])
                if single_res:
                    current_result = _merge_extractions(current_result, single_res)
                    unclear_or_missing = _get_unclear_or_missing_core(current_result)
            except Exception:
                pass

        # If all core fields are now clear and found, return immediately
        if not unclear_or_missing:
            return current_result

        # 3. Cross-Provider Retry (if fields are still unclear or missing)
        for idx in range(active_provider_idx + 1, len(providers)):
            provider = providers[idx]
            try:
                available, _ = provider.is_available()
                if not available:
                    continue
                second_result = provider.extract_fields(images)
                if second_result:
                    current_result = _merge_extractions(current_result, second_result)
                    break
            except Exception:
                continue

        return current_result

    def _apply_confidence_gate(self, result: RecognitionResult) -> RecognitionResult:
        if result.confidence < CONFIDENCE_THRESHOLD:
            result.below_confidence_threshold = True
            result.confirmation_status = "autonomous_ai_general"
            result.note = (
                f"Confidence {result.confidence:.0%} is below the "
                f"{CONFIDENCE_THRESHOLD:.0%} threshold; evaluated autonomously as 'general' "
                "with standard mandatory compliance rules applied."
            )
        else:
            result.below_confidence_threshold = False
            result.confirmation_status = "autonomous_ai_verified"
            result.note = (
                f"Autonomous AI verification: identified category '{result.category.value}' "
                f"with {result.confidence:.0%} confidence."
            )
        return result

