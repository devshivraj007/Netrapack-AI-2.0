"""Verify the Gemini model fallback.

Forces the primary model to a known-retired one (gemini-2.5-flash, which
returns 404 'no longer available' for this account) and confirms the provider
automatically retries on the fallback model and still returns a result.
Key never printed.
"""
from __future__ import annotations

import json

from dotenv import load_dotenv

load_dotenv()

from app.ai.providers import GeminiVisionProvider
from tests.make_synthetic_labels import build_samples


def main() -> None:
    # Primary is deliberately a retired model -> should trigger fallback.
    gem = GeminiVisionProvider(model="gemini-2.5-flash",
                              fallback_model="gemini-flash-latest")
    print(f"primary={gem.model}, fallback={gem.fallback_model}")

    _, jpeg, _ = build_samples()[0]  # clean food label
    try:
        rec = gem.recognize(jpeg)
        print(json.dumps({
            "category": rec.category.value,
            "confidence": rec.confidence,
            "ai_source": rec.ai_source.value,
            "model_name": rec.model_name,
        }, indent=2))
        if rec.model_name == gem.fallback_model:
            print("[PASS] Primary failed (retired) and provider fell back to "
                  f"'{rec.model_name}' successfully.")
        else:
            print(f"[INFO] Answered on '{rec.model_name}' (primary unexpectedly worked).")
    except Exception as e:
        msg = str(e)
        key = gem.api_key or ""
        if key:
            msg = msg.replace(key, "***")
        print(f"[FAIL] fallback did not save the call: {type(e).__name__}: {msg}")


if __name__ == "__main__":
    main()
