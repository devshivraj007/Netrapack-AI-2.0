"""AI provider clients for product recognition.

Two real providers behind a common shape:
  * OllamaVisionProvider  - Level 1, local, offline-capable (moondream2 /
    qwen2.5vl:3b via the Ollama HTTP API on localhost).
  * GeminiVisionProvider  - Level 2, cloud, needs GEMINI_API_KEY + internet.

Each provider's `recognize(image_bytes)` returns a RecognitionResult or raises
so the orchestrator can fall through to the next level. Neither provider is
required to be installed/configured for the pipeline to work: if a provider is
unavailable it simply reports so and the chain falls through to the next level,
ending at Level 3 (rule engine only, category = general).
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from typing import Optional

import httpx

# Load .env at import so GEMINI_API_KEY is available no matter which entry point
# constructs the providers (FastAPI server, benchmark, tests, scripts). Without
# this, scripts that import the AI layer directly (not via main.py) would build
# the Gemini provider with no key and silently fall back to local/OCR.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from .types import (
    AiSource,
    PackageShape,
    PackageSize,
    ProductCategory,
    RecognitionResult,
    VisionExtraction,
)

# Local vision model preference (first available wins). qwen2.5-VL is far more
# reliable at STRUCTURED extraction than moondream (which hallucinates JSON), so
# it is preferred; moondream stays as a lighter fallback for category guessing.
OLLAMA_VISION_MODELS = ["qwen2.5vl:3b", "qwen2.5vl", "moondream", "moondream2"]

# Local chat model for the RAG assistant (Level 1).
OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# Fallback model tried automatically if the primary returns a transient/server
# error (e.g. the 503 "high demand" we saw during testing). "gemini-flash-latest"
# always points at a current flash model, so it survives model retirements too.
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-flash-latest")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# HTTP statuses that are worth retrying on the fallback model:
#   429 rate limited, 500 internal, 503 overloaded, 404 model retired/unavailable.
_GEMINI_RETRYABLE_STATUS = {404, 429, 500, 503}
# Extraction retries per model, with linear backoff, to ride out brief 503s.
_GEMINI_MAX_RETRIES = 2
_GEMINI_BACKOFF_SECONDS = 3.0

# The instruction we give either model. We ask for STRICT JSON so parsing is
# deterministic across models.
_RECOGNITION_PROMPT = (
    "You are a product-label classifier. Look at the product image and reply "
    "with STRICT JSON only, no prose. Schema: "
    '{"category": one of '
    '["food_and_beverage","personal_care","household","electronics",'
    '"pharmaceutical","baby_care","other"], '
    '"package_size": one of ["very_small_sachet","standard","bulk_pack"], '
    '"package_shape": one of ["flat_box","cylindrical_can","pouch","bottle"], '
    '"confidence": a number between 0 and 1}. '
    "If you are unsure, use your best guess and set a low confidence."
)

# Structured field-extraction prompt. One or more label images are supplied
# (front + back). We ask for STRICT JSON matching the agreed schema so the
# values feed the Day 1 rule engine directly. Read the ACTUAL printed values;
# do not invent. Use null when a field is genuinely not visible.
_EXTRACTION_PROMPT = (
    "You are a Legal Metrology label reader for Indian packaged commodities. "
    "You are given one or more photos of the SAME product (front and back). "
    "Read the printed declarations and reply with STRICT JSON ONLY, no prose, "
    "matching exactly this schema and key names:\n"
    "{\n"
    '  "mrp": number or null,               // the ACTIVE selling MRP in INR (see price rules)\n'
    '  "mrp_all_prices": [numbers],         // EVERY distinct price seen near MRP, incl. struck-through\n'
    '  "mrp_is_ambiguous": true/false,      // true if you CANNOT tell which price is the active one\n'
    '  "net_quantity": string or null,      // e.g. "150g", "300ml", "1 unit"\n'
    '  "unit_sale_price": number or null,   // per-unit price if printed, else null\n'
    '  "mfd_pkd_date": string or null,      // manufacture/packed date as printed\n'
    '  "expiry_date": string or null,       // expiry/best-before/use-by as printed\n'
    '  "fssai_license_number": string or null, // the 14-digit number only, if present\n'
    '  "manufacturer_details": string or null, // name + address block as printed\n'
    '  "country_of_origin": string or null  // e.g. "India", "China", "Sri Lanka"\n'
    "}\n"
    "PRICE RULES (important):\n"
    "- List every distinct price you see near the MRP in mrp_all_prices.\n"
    "- If ONE price is struck through / crossed out and another is not, the "
    "NON-struck (usually LOWER) price is the active MRP: set mrp to it and set "
    "mrp_is_ambiguous=false.\n"
    "- If two or more prices are shown together and you CANNOT confidently tell "
    "which is the active selling price (no clear strikethrough), set "
    "mrp_is_ambiguous=true and leave mrp=null.\n"
    "- If only one price is shown, set mrp to it and mrp_is_ambiguous=false.\n"
    "General: Report ONLY what is actually printed. Do NOT guess a value that is "
    "not visible - use null. Return numbers without currency symbols."
)


def _coerce_category(value: str) -> ProductCategory:
    try:
        return ProductCategory(value)
    except ValueError:
        return ProductCategory.OTHER


def _coerce_size(value: str) -> PackageSize:
    try:
        return PackageSize(value)
    except ValueError:
        return PackageSize.UNKNOWN


def _coerce_shape(value: str) -> PackageShape:
    try:
        return PackageShape(value)
    except ValueError:
        return PackageShape.UNKNOWN


def _parse_model_json(text: str) -> dict:
    """Extract the first JSON object from a model's text reply.

    Tolerant of small models that truncate the closing brace: if a normal parse
    fails, retry after appending a closing '}' to the last-open object.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object in model reply: {text[:200]!r}")
    end = text.rfind("}")
    if end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    # Truncated reply: try closing the object at the last complete "key":val.
    fragment = text[start:].rstrip().rstrip(",")
    try:
        return json.loads(fragment + "}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Unparseable model JSON: {text[:200]!r}") from e


def _downscale_jpeg(image_bytes: bytes, max_dim: int = 1280) -> bytes:
    """Shrink a photo's longest side to max_dim and re-encode as JPEG.

    Big retail photos (3000-4000px, >1MB) are slow to upload and slow for the
    vision model, and can blow the request timeout. Label text reads fine at
    ~1280px. Falls back to the original bytes if anything goes wrong.
    """
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        longest = max(w, h)
        if longest > max_dim:
            scale = max_dim / float(longest)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception:
        return image_bytes


class OllamaVisionProvider:
    """Level 1: local vision model via Ollama."""

    source = AiSource.LOCAL_OLLAMA

    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: float = 180.0):
        # Local vision inference on CPU can take a while for the first call
        # (model load) and per image. A generous timeout lets the local model
        # actually answer instead of prematurely falling through to cloud.
        # Overridable via OLLAMA_TIMEOUT for faster machines / GPUs.
        self.base_url = base_url.rstrip("/")
        self.timeout = float(os.environ.get("OLLAMA_TIMEOUT", timeout))

    def is_available(self) -> tuple[bool, Optional[str]]:
        """Return (available, model_name). Available means Ollama is up AND at
        least one of our vision models is present."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            resp.raise_for_status()
            installed = {m.get("name", "").split(":")[0] for m in resp.json().get("models", [])}
            installed_full = {m.get("name", "") for m in resp.json().get("models", [])}
        except Exception:
            return False, None
        for model in OLLAMA_VISION_MODELS:
            if model in installed_full or model.split(":")[0] in installed:
                return True, model
        return False, None

    def recognize(self, image_bytes: bytes) -> RecognitionResult:
        available, model = self.is_available()
        if not available or model is None:
            raise RuntimeError("Ollama vision model not available")

        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": model,
            "prompt": _RECOGNITION_PROMPT,
            "images": [b64],
            "stream": False,
            "format": "json",
        }
        resp = httpx.post(
            f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        body = resp.json()
        data = _parse_model_json(body.get("response", ""))
        return _result_from_data(data, self.source, model)

    def extract_fields(self, images: list[bytes]) -> VisionExtraction:
        """Read structured label fields from one or more images (front+back)."""
        available, model = self.is_available()
        if not available or model is None:
            raise RuntimeError("Ollama vision model not available")

        imgs = [base64.b64encode(_downscale_jpeg(b)).decode("ascii") for b in images]
        payload = {
            "model": model,
            "prompt": _EXTRACTION_PROMPT,
            "images": imgs,
            "stream": False,
            "format": "json",
        }
        resp = httpx.post(
            f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        data = _parse_model_json(resp.json().get("response", ""))
        return _extraction_from_data(data, self.source, model)

    # ------------------------------------------------------------------
    # Chat (RAG assistant, Level 1)
    # ------------------------------------------------------------------
    def chat_available(self) -> tuple[bool, Optional[str]]:
        """Return (available, chat_model) if Ollama is up and the chat model is present."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            resp.raise_for_status()
            names = {m.get("name", "") for m in resp.json().get("models", [])}
            names_base = {n.split(":")[0] for n in names}
        except Exception:
            return False, None
        if OLLAMA_CHAT_MODEL in names or OLLAMA_CHAT_MODEL.split(":")[0] in names_base:
            return True, OLLAMA_CHAT_MODEL
        return False, None

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a plain-text answer from the local chat model."""
        available, model = self.chat_available()
        if not available or model is None:
            raise RuntimeError("Ollama chat model not available")
        payload = {
            "model": model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
        }
        resp = httpx.post(
            f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        return (resp.json().get("response") or "").strip()


class GeminiVisionProvider:
    """Level 2: Gemini cloud vision. Requires GEMINI_API_KEY + internet."""

    source = AiSource.CLOUD_GEMINI

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or GEMINI_MODEL
        self.fallback_model = fallback_model or GEMINI_FALLBACK_MODEL
        # Structured extraction from full label images is heavier than a quick
        # category guess; give it a generous timeout (overridable via env).
        self.timeout = timeout if timeout is not None else float(
            os.environ.get("GEMINI_TIMEOUT", 90.0)
        )

    def is_available(self) -> tuple[bool, Optional[str]]:
        return (bool(self.api_key), self.model if self.api_key else None)

    def recognize(self, image_bytes: bytes) -> RecognitionResult:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        b64 = base64.b64encode(_downscale_jpeg(image_bytes)).decode("ascii")

        # Try the primary model; on a transient/server error (429/500/503) or a
        # model-unavailable 404, automatically retry once on the fallback model
        # so a momentary "high demand" blip does not knock out Level 2.
        try:
            return self._call_model(self.model, b64)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status in _GEMINI_RETRYABLE_STATUS and self.fallback_model != self.model:
                return self._call_model(self.fallback_model, b64)
            raise

    def _call_model(self, model: str, image_b64: str) -> RecognitionResult:
        # Authenticate via the x-goog-api-key header (the documented REST method
        # for the current "AQ." auth keys). Sending the key in a header instead
        # of the ?key= query param also keeps it out of URLs, logs and error
        # messages. See https://ai.google.dev/gemini-api/docs/api-key
        url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": _RECOGNITION_PROMPT},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    ]
                }
            ],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        data = _parse_model_json(text)
        # Report the model that actually answered (primary or fallback).
        return _result_from_data(data, self.source, model)

    def extract_fields(self, images: list[bytes]) -> VisionExtraction:
        """Read structured label fields from one or more images (front+back)."""
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        b64s = [base64.b64encode(_downscale_jpeg(b)).decode("ascii") for b in images]

        # Try primary then fallback model; each model gets a couple of retries
        # with backoff on transient server errors (503/429/500), because Google
        # flash models can be briefly overloaded. This self-heals short blips.
        models = [self.model]
        if self.fallback_model != self.model:
            models.append(self.fallback_model)

        last_exc: Optional[Exception] = None
        for model in models:
            for attempt in range(_GEMINI_MAX_RETRIES):
                try:
                    return self._extract_call(model, b64s)
                except httpx.HTTPStatusError as e:
                    last_exc = e
                    if e.response.status_code not in _GEMINI_RETRYABLE_STATUS:
                        raise
                    time.sleep(_GEMINI_BACKOFF_SECONDS * (attempt + 1))
                except httpx.TimeoutException as e:
                    last_exc = e
                    time.sleep(_GEMINI_BACKOFF_SECONDS)
        if last_exc:
            raise last_exc
        raise RuntimeError("Gemini extraction failed with no exception captured")

    def _extract_call(self, model: str, image_b64s: list[bytes]) -> VisionExtraction:
        url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        parts: list[dict] = [{"text": _EXTRACTION_PROMPT}]
        for b64 in image_b64s:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = _parse_model_json(text)
        return _extraction_from_data(data, self.source, model)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a plain-text answer via Gemini (Level 2), with model fallback."""
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        models = [self.model]
        if self.fallback_model != self.model:
            models.append(self.fallback_model)
        last_exc: Optional[Exception] = None
        for model in models:
            try:
                return self._chat_call(model, system_prompt, user_prompt)
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code not in _GEMINI_RETRYABLE_STATUS:
                    raise
            except httpx.TimeoutException as e:
                last_exc = e
        if last_exc:
            raise last_exc
        raise RuntimeError("Gemini chat failed with no exception captured")

    def _chat_call(self, model: str, system_prompt: str, user_prompt: str) -> str:
        url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
        }
        resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(m.group(0)) if m else None


def _to_str(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# --- Post-extraction sanitisation ------------------------------------------
# Vision models occasionally hallucinate or misread label noise as a bare number
# (e.g. "42") for text fields, or emit placeholder junk. We validate the shape of
# each field and drop implausible values to null rather than showing an officer a
# fabricated reading. Better to say "Not declared" than to display garbage.

_MONTH_RE = re.compile(
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec", re.IGNORECASE
)
# A plausible printed date has either a month name, or two number groups
# separated by / - . or space (e.g. 03/2026, 12-01-2026, 2026 03).
_DATE_NUMSEP_RE = re.compile(r"\d{1,4}\s*[/\-.]\s*\d{1,4}")
# Junk/placeholder tokens some models emit.
_JUNK_TOKENS = {"n/a", "na", "none", "null", "nil", "-", "--", "unknown", "not visible"}


def _clean_str(value) -> Optional[str]:
    """Normalise a text field and drop obvious junk/placeholder tokens."""
    s = _to_str(value)
    if s is None:
        return None
    if s.strip().lower() in _JUNK_TOKENS:
        return None
    return s


def _clean_date(value) -> Optional[str]:
    """Return the printed date string only if it looks like a real date.

    Rejects bare numbers like "42" (a common model misread) and junk tokens: a
    real mfg/expiry declaration contains a month name OR a number-separator date
    pattern OR a 4-digit year. Otherwise -> None ("Not declared").
    """
    s = _clean_str(value)
    if s is None:
        return None
    if _MONTH_RE.search(s):
        return s
    if _DATE_NUMSEP_RE.search(s):
        return s
    if re.search(r"\b(19|20)\d{2}\b", s):  # a 4-digit year like 2026
        return s
    # A bare short number ("42", "7", "123") is not a plausible date.
    return None


def _clean_country(value) -> Optional[str]:
    """Country of origin must contain letters. Reject bare numbers like '42'."""
    s = _clean_str(value)
    if s is None:
        return None
    if not re.search(r"[A-Za-z]", s):
        return None
    return s


def _clean_price(value) -> Optional[float]:
    """A price must be a positive, sane number. Reject 0 and absurd values."""
    fp = _to_float(value)
    if fp is None:
        return None
    if fp <= 0 or fp > 1_000_000:
        return None
    return fp


def _extraction_from_data(
    data: dict, source: AiSource, model_name: str
) -> VisionExtraction:
    # Parse the price list (strikethrough handling).
    raw_prices = data.get("mrp_all_prices") or []
    all_prices: list[float] = []
    if isinstance(raw_prices, list):
        for p in raw_prices:
            fp = _clean_price(p)
            if fp is not None:
                all_prices.append(fp)
    # Sanitise every field: models sometimes emit a bare "42" or junk for a
    # field they can't actually read. Validate the shape and drop implausible
    # values to null so the app shows "Not declared" instead of a fake reading.
    fssai = _clean_str(data.get("fssai_license_number"))
    if fssai is not None and not re.search(r"\d", fssai):
        fssai = None  # an FSSAI licence must contain digits
    return VisionExtraction(
        mrp=_clean_price(data.get("mrp")),
        mrp_all_prices=all_prices,
        mrp_is_ambiguous=bool(data.get("mrp_is_ambiguous", False)),
        net_quantity=_clean_str(data.get("net_quantity")),
        unit_sale_price=_clean_price(data.get("unit_sale_price")),
        mfd_pkd_date=_clean_date(data.get("mfd_pkd_date")),
        expiry_date=_clean_date(data.get("expiry_date")),
        fssai_license_number=fssai,
        manufacturer_details=_clean_str(data.get("manufacturer_details")),
        country_of_origin=_clean_country(data.get("country_of_origin")),
        ai_source=source,
        model_name=model_name,
    )


def _result_from_data(
    data: dict, source: AiSource, model_name: str
) -> RecognitionResult:
    confidence = float(data.get("confidence", 0.0))
    return RecognitionResult(
        category=_coerce_category(str(data.get("category", "other"))),
        package_size=_coerce_size(str(data.get("package_size", "unknown"))),
        package_shape=_coerce_shape(str(data.get("package_shape", "unknown"))),
        confidence=confidence,
        ai_source=source,
        model_name=model_name,
    )
