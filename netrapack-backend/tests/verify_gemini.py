"""Verify the Gemini (Level 2) cloud fallback.

Steps:
  1. Load .env and confirm GEMINI_API_KEY is present (value NOT printed).
  2. Confirm GeminiVisionProvider reports itself available.
  3. Force the Level-2 path: disable local Ollama so the recognizer must
     choose Gemini ahead of the rule-engine fallback, and show which source
     answered.
  4. Make a REAL Gemini call and report the raw outcome (success or the HTTP
     error), so we know whether the key actually authenticates.
"""

from __future__ import annotations

import json

from dotenv import load_dotenv

load_dotenv()

import os

from app.ai.providers import GeminiVisionProvider, OllamaVisionProvider
from app.ai.recognizer import ProductRecognizer
from app.ai.types import AiSource
from tests.make_synthetic_labels import build_samples


class DisabledOllama(OllamaVisionProvider):
    """Force Level 1 to be unavailable so the chain must try Gemini."""

    def is_available(self):
        return (False, None)


def main() -> None:
    print("=" * 66)
    key = os.environ.get("GEMINI_API_KEY")
    print(f"GEMINI_API_KEY present: {bool(key)}; length: {len(key) if key else 0}")
    if key:
        print(f"key prefix (first 4 chars): {key[:4]!r}")

    gem = GeminiVisionProvider()
    available, model = gem.is_available()
    print(f"Gemini provider available: {available}, model: {model}")

    # Force the Level-2 path (local disabled).
    recognizer = ProductRecognizer(ollama=DisabledOllama(), gemini=gem)

    _, jpeg, _ = build_samples()[0]
    print("\nMaking a REAL Gemini call (local disabled so Level 2 is used)...")
    try:
        rec = recognizer.recognize(jpeg)
        print(json.dumps({
            "category": rec.category.value,
            "effective_category": rec.effective_category.value,
            "confidence": rec.confidence,
            "ai_source": rec.ai_source.value,
            "model_name": rec.model_name,
            "confirmation_status": rec.confirmation_status,
            "note": rec.note,
        }, indent=2))
        if rec.ai_source == AiSource.CLOUD_GEMINI:
            print("[PASS] Level 2 (Gemini) answered and drove the result.")
        else:
            print("[INFO] Recognizer fell through to "
                  f"'{rec.ai_source.value}' - Gemini did not return a usable "
                  "answer (see direct-call detail below).")
    except Exception as e:
        print(f"[recognizer] unexpected error: {e!r}")

    # Direct call to surface the true HTTP outcome (bypasses fallthrough).
    print("\nDirect Gemini call (raw outcome):")
    try:
        rec = gem.recognize(jpeg)
        print("[PASS] Direct Gemini call succeeded:",
              rec.category.value, f"conf={rec.confidence}")
    except Exception as e:
        # Redact the key if it ever appears in an error string.
        msg = str(e)
        if key:
            msg = msg.replace(key, "***REDACTED***")
        print(f"[FAIL] Direct Gemini call raised: {type(e).__name__}: {msg}")


if __name__ == "__main__":
    main()
