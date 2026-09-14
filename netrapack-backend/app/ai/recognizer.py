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
        groq: Optional[GroqVisionProvider] = None,
        gemini: Optional[GeminiVisionProvider] = None,
        ollama: Optional[OllamaVisionProvider] = None,
    ):
        self.groq = groq or GroqVisionProvider()
        self.gemini = gemini or GeminiVisionProvider()
        self.ollama = ollama or OllamaVisionProvider()

    def recognize(self, image_bytes: bytes) -> RecognitionResult:
        # Level 1: Groq cloud (primary).
        result = self._try_provider(self.groq, image_bytes)
        # Level 2: Gemini cloud (secondary fallback).
        if result is None:
            result = self._try_provider(self.gemini, image_bytes)
        # Level 3: local Ollama (offline fallback).
        if result is None:
            result = self._try_provider(self.ollama, image_bytes)
        # Level 4: no AI available -> general, standard checks only.
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
        """Vision structured extraction with the same 4-tier fallback:
        Groq -> Gemini -> Ollama -> None (caller falls back to OCR).
        """
        for provider in (self.groq, self.gemini, self.ollama):
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
