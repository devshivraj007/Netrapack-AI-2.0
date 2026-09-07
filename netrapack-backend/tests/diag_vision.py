"""Diagnose which vision provider answers extraction, with explicit errors."""
from __future__ import annotations

import glob
import json
import os
import time

from dotenv import load_dotenv

load_dotenv()

from app.ai.providers import GeminiVisionProvider, OllamaVisionProvider

PHOTO_DIR = os.path.join(os.path.dirname(__file__), "photos")


def _read(p):
    with open(p, "rb") as f:
        return f.read()


def main() -> None:
    fronts = glob.glob(os.path.join(PHOTO_DIR, "08_*front*.jpg"))
    backs = glob.glob(os.path.join(PHOTO_DIR, "08_*back*.jpg"))
    images = [_read(fronts[0])] + ([_read(backs[0])] if backs else [])
    print(f"images: {len(images)}")

    ollama = OllamaVisionProvider()
    print("ollama available:", ollama.is_available())
    t0 = time.perf_counter()
    try:
        r = ollama.extract_fields(images)
        print(f"ollama extract OK in {time.perf_counter()-t0:.1f}s:",
              r.model_dump(mode="json"))
    except Exception as e:
        print(f"ollama extract FAILED in {time.perf_counter()-t0:.1f}s: {type(e).__name__}: {e}")

    gem = GeminiVisionProvider()
    print("gemini available:", gem.is_available())
    t0 = time.perf_counter()
    try:
        r = gem.extract_fields(images)
        print(f"gemini extract OK in {time.perf_counter()-t0:.1f}s:")
        print(json.dumps(r.model_dump(mode="json"), indent=2))
    except Exception as e:
        msg = str(e)
        key = gem.api_key or ""
        if key:
            msg = msg.replace(key, "***")
        print(f"gemini extract FAILED in {time.perf_counter()-t0:.1f}s: {type(e).__name__}: {msg}")


if __name__ == "__main__":
    main()
