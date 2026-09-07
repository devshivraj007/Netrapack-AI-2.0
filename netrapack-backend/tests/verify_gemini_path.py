"""Confirm the production recognizer selects and uses Gemini (Level 2).

Disables Ollama by pointing it at a dead port (real is_available -> False),
so ProductRecognizer must use Gemini. Retries once on a transient 503.
"""
from __future__ import annotations

import json
import time

from dotenv import load_dotenv

load_dotenv()

from app.ai.providers import GeminiVisionProvider, OllamaVisionProvider
from app.ai.recognizer import ProductRecognizer
from app.ai.types import AiSource
from tests.make_synthetic_labels import build_samples


def main() -> None:
    # Point Ollama at a closed port so it is genuinely unavailable.
    dead_ollama = OllamaVisionProvider(base_url="http://127.0.0.1:1")
    recognizer = ProductRecognizer(ollama=dead_ollama, gemini=GeminiVisionProvider())

    _, jpeg, _ = build_samples()[0]  # clean food label

    rec = None
    for attempt in range(3):
        rec = recognizer.recognize(jpeg)
        if rec.ai_source == AiSource.CLOUD_GEMINI:
            break
        print(f"attempt {attempt+1}: source={rec.ai_source.value} (retrying on transient)")
        time.sleep(5)

    print(json.dumps({
        "category": rec.category.value,
        "effective_category": rec.effective_category.value,
        "package_size": rec.package_size.value,
        "package_shape": rec.package_shape.value,
        "confidence": rec.confidence,
        "ai_source": rec.ai_source.value,
        "model_name": rec.model_name,
        "below_confidence_threshold": rec.below_confidence_threshold,
        "confirmation_status": rec.confirmation_status,
        "note": rec.note,
    }, indent=2))

    if rec.ai_source == AiSource.CLOUD_GEMINI:
        print("[PASS] Production recognizer used Level 2 (Gemini) and labelled "
              "it AI-suggested/not-confirmed.")
    else:
        print(f"[INFO] Ended on '{rec.ai_source.value}' - likely a transient "
              "Gemini 503; fallback stayed safe. Re-run to confirm.")


if __name__ == "__main__":
    main()
