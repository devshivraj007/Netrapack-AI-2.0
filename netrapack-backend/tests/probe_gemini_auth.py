"""Probe: is the 401 auth-wide or model-specific?

Calls the models.list endpoint (needs only auth, no model). If this also 401s,
the key/project itself is being rejected, not the model name. Key is never
printed; any occurrence in error text is redacted.
"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

KEY = os.environ.get("GEMINI_API_KEY", "")


def redact(s: str) -> str:
    return s.replace(KEY, "***REDACTED***") if KEY else s


def main() -> None:
    print(f"key present: {bool(KEY)}, length: {len(KEY)}")
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"x-goog-api-key": KEY}
    try:
        resp = httpx.get(url, headers=headers, timeout=20.0)
        print(f"models.list status: {resp.status_code}")
        if resp.status_code == 200:
            names = [m.get("name") for m in resp.json().get("models", [])][:8]
            print("[PASS] Auth OK. Sample models:", names)
        else:
            print("[FAIL] body:", redact(resp.text[:600]))
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {redact(str(e))}")


if __name__ == "__main__":
    main()
