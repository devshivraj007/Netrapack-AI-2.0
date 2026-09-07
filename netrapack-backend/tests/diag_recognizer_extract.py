"""Why does recognizer.extract_fields fall through to None in the benchmark?

Reproduces the exact recognizer path with explicit per-provider error output.
"""
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
    imgs = [_read(glob.glob(os.path.join(PHOTO_DIR, "08_*front*.jpg"))[0]),
            _read(glob.glob(os.path.join(PHOTO_DIR, "08_*back*.jpg"))[0])]

    ollama = OllamaVisionProvider()
    print("== Ollama ==", ollama.is_available())
    t = time.perf_counter()
    try:
        r = ollama.extract_fields(imgs)
        print(f"ollama OK {time.perf_counter()-t:.1f}s:", r.model_dump(mode="json"))
    except Exception as e:
        print(f"ollama FAIL {time.perf_counter()-t:.1f}s: {type(e).__name__}: {str(e)[:150]}")

    gem = GeminiVisionProvider()
    print("== Gemini ==", gem.is_available(), "timeout=", gem.timeout)
    t = time.perf_counter()
    try:
        r = gem.extract_fields(imgs)
        print(f"gemini OK {time.perf_counter()-t:.1f}s:")
        print(json.dumps(r.model_dump(mode="json"), indent=2))
    except Exception as e:
        msg = str(e)
        if gem.api_key:
            msg = msg.replace(gem.api_key, "***")
        print(f"gemini FAIL {time.perf_counter()-t:.1f}s: {type(e).__name__}: {msg[:200]}")


if __name__ == "__main__":
    main()
