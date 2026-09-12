"""Product recognition with the 3-level fallback chain.

Order (Gemini-primary, per reliability decision on Day 6):
    Level 1: Gemini cloud (gemini-3.6-flash) - primary; most reliable extractor
    Level 2: local AI (Ollama qwen2.5vl:3b)  - fallback when cloud unavailable
    Level 3: neither                         - category = general / OCR fallback

Rationale: the 21-product benchmark showed the local 3B model degrading to OCR
on most real labels, while Gemini extracts cleanly. So Gemini leads and local
qwen is the offline safety net. Ollama still guarantees the app works with no
internet.

The confidence gate (< 70% -> general) applies to BOTH AI levels. Whatever the
source, the result is always labelled "AI-suggested, not yet confirmed" and an
officer must confirm/change it before official use (Day 3).
"""

from __future__ import annotations

import socket
from typing import Optional

from .providers import GeminiVisionProvider, OllamaVisionProvider
from .types import (
    AiSource,
    CONFIDENCE_THRESHOLD,
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


class ProductRecognizer:
    def __init__(
        self,
        ollama: Optional[OllamaVisionProvider] = None,
        gemini: Optional[GeminiVisionProvider] = None,
    ):
        self.ollama = ollama or OllamaVisionProvider()
        self.gemini = gemini or GeminiVisionProvider()

    def recognize(self, image_bytes: bytes) -> RecognitionResult:
        # Level 1: Gemini cloud (primary).
        result = self._try_provider(self.gemini, image_bytes)
        # Level 2: local Ollama (fallback when cloud is unavailable/fails).
        if result is None:
            result = self._try_provider(self.ollama, image_bytes)
        # Level 3: no AI available -> general, standard checks only.
        if result is None:
            return RecognitionResult(
                category=ProductCategory.GENERAL,
                ai_source=AiSource.NONE,
                model_name=None,
                confidence=0.0,
                below_confidence_threshold=False,
                note=(
                    "No AI available (cloud and local both unavailable). "
                    "Falling back to standard Legal Metrology checks only; "
                    "category-specific (FSSAI) checks are skipped."
                ),
            )

        # Apply the confidence gate to whichever AI answered.
        return self._apply_confidence_gate(result)

    def _try_provider(self, provider, image_bytes: bytes) -> Optional[RecognitionResult]:
        try:
            available, _ = provider.is_available()
            if not available:
                return None
            return provider.recognize(image_bytes)
        except Exception:
            # Any failure (timeout, bad response, network) -> fall through.
            return None

    def extract_fields(self, images: list[bytes]) -> Optional[VisionExtraction]:
        """Vision structured extraction with the same 3-level fallback.

        Gemini (cloud) is tried FIRST as the reliable primary extractor; local
        qwen is the offline fallback. Returns None only if BOTH cloud and local
        vision are unavailable/failed, in which case the caller falls back to OCR.
        """
        for provider in (self.gemini, self.ollama):
            try:
                available, _ = provider.is_available()
                if not available:
                    continue
                return provider.extract_fields(images)
            except Exception:
                continue
        return None

    def _apply_confidence_gate(self, result: RecognitionResult) -> RecognitionResult:
        if result.confidence < CONFIDENCE_THRESHOLD:
            result.below_confidence_threshold = True
            result.note = (
                f"Confidence {result.confidence:.0%} is below the "
                f"{CONFIDENCE_THRESHOLD:.0%} threshold; treating as 'general' "
                "and running standard checks only (no category-specific checks)."
            )
        else:
            result.below_confidence_threshold = False
            result.note = (
                f"AI-suggested category '{result.category.value}' "
                f"(confidence {result.confidence:.0%}). Not yet confirmed - an "
                "officer must confirm or change this before official use."
            )
        return result
