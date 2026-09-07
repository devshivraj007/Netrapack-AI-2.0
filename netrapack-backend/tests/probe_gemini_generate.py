"""Find a model + API version that the generateContent endpoint accepts.

Auth already works (models.list returned 200). This tries a tiny text-only
generateContent call across a few (version, model) combos and reports the
status for each, so we pick a working one. Key never printed.
"""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

KEY = os.environ.get("GEMINI_API_KEY", "")
HEADERS = {"Content-Type": "application/json", "x-goog-api-key": KEY}
PAYLOAD = {"contents": [{"parts": [{"text": "reply with the word ok"}]}]}


def redact(s: str) -> str:
    return s.replace(KEY, "***") if KEY else s


def main() -> None:
    combos = [
        ("v1beta", "gemini-2.5-flash"),
        ("v1", "gemini-2.5-flash"),
        ("v1beta", "gemini-flash-latest"),
        ("v1beta", "gemini-2.5-pro"),
        ("v1", "gemini-flash-latest"),
    ]
    for version, model in combos:
        url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent"
        try:
            r = httpx.post(url, headers=HEADERS, json=PAYLOAD, timeout=30.0)
            ok = r.status_code == 200
            note = "OK" if ok else redact(r.text[:180])
            print(f"[{r.status_code}] {version}/{model} -> {note}")
            if ok:
                print(f"    >>> WORKING COMBO: version={version}, model={model}")
        except Exception as e:
            print(f"[ERR] {version}/{model} -> {redact(str(e))}")


if __name__ == "__main__":
    main()
