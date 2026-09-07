"""E-commerce compliance URL scanner (Day 5).

Fetches a product page (Blinkit, Instamart, Amazon India, etc.), extracts the
online packaging declarations (MRP, net quantity, country of origin,
manufacturer), and runs LMPC Rule 6(10) e-commerce compliance checks via the
same Day 1 rule engine.

HONEST LIMITATION: major e-commerce sites are JavaScript-heavy and actively
anti-scrape, so a plain server-side fetch will often get a bot page or partial
HTML rather than the rendered product data. This scanner parses whatever static
HTML/JSON-LD it can retrieve and degrades gracefully - it clearly reports which
fields it could and could not read, rather than fabricating values. Full
rendering (headless browser) or official APIs would be needed for robust
production coverage.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Optional

import httpx

from app.rule_engine.engine import RuleEngine
from app.schemas.scan import ScanRequest

_engine = RuleEngine()

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping script/style, but capture JSON-LD blocks."""

    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._in_ldjson = False
        self.text_parts: list[str] = []
        self.ldjson_blocks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            attr = dict(attrs)
            if tag == "script" and attr.get("type") == "application/ld+json":
                self._in_ldjson = True
            else:
                self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            if self._in_ldjson:
                self._in_ldjson = False
            elif self._skip > 0:
                self._skip -= 1

    def handle_data(self, data):
        if self._in_ldjson:
            self.ldjson_blocks.append(data)
        elif self._skip == 0:
            s = data.strip()
            if s:
                self.text_parts.append(s)


@dataclass
class UrlScanResult:
    url: str
    fetched: bool
    http_status: Optional[int] = None
    extracted: dict[str, Optional[str]] = field(default_factory=dict)
    verdict: Optional[dict[str, Any]] = None
    note: Optional[str] = None


# Extraction patterns tolerant of e-commerce text.
_MRP_RE = re.compile(r"(?:m\.?r\.?p\.?|maximum retail price)[^0-9]{0,15}(\d{1,6}(?:[.,]\d{1,2})?)",
                     re.IGNORECASE)
_NETQTY_RE = re.compile(
    r"(?:net\s*(?:qty|quantity|wt|weight|content)s?|unit)[^0-9]{0,12}"
    r"(\d{1,5}(?:\.\d+)?\s*(?:kg|g|gm|ml|l|ltr|litre|units?|pcs?|piece|n)\b)",
    re.IGNORECASE)
_BARE_QTY_RE = re.compile(r"\b(\d{1,5}(?:\.\d+)?\s*(?:kg|g|ml|l|ltr)\b)", re.IGNORECASE)
_ORIGIN_RE = re.compile(
    r"(?:country of origin|made in|product of)[:\s]*([A-Za-z][A-Za-z .'\-]{2,30})",
    re.IGNORECASE)
_MANUF_RE = re.compile(
    r"(?:manufacturer|marketed by|packed by|manufactured by|mfg by)[:\s]*"
    r"([A-Za-z0-9][A-Za-z0-9 .,&'\-/]{5,120})", re.IGNORECASE)


def _from_ldjson(blocks: list[str]) -> dict[str, Optional[str]]:
    """Try to pull fields from schema.org Product JSON-LD if present."""
    out: dict[str, Optional[str]] = {}
    for raw in blocks:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict):
                continue
            offers = it.get("offers") or {}
            if isinstance(offers, list) and offers:
                offers = offers[0]
            if isinstance(offers, dict) and offers.get("price") and "mrp" not in out:
                out["mrp"] = str(offers.get("price"))
            if it.get("countryOfOrigin") and "origin" not in out:
                out["origin"] = str(it.get("countryOfOrigin"))
            brand = it.get("brand")
            if brand and "manufacturer" not in out:
                out["manufacturer"] = (brand.get("name") if isinstance(brand, dict)
                                       else str(brand))
    return out


def _extract(text: str, ldjson: dict[str, Optional[str]]) -> dict[str, Optional[str]]:
    def find(rx):
        m = rx.search(text)
        return m.group(1).strip() if m else None

    mrp = ldjson.get("mrp") or find(_MRP_RE)
    qty = find(_NETQTY_RE) or find(_BARE_QTY_RE)
    origin = ldjson.get("origin") or find(_ORIGIN_RE)
    manuf = ldjson.get("manufacturer") or find(_MANUF_RE)
    return {"mrp": mrp, "net_quantity": qty,
            "country_of_origin": origin, "manufacturer": manuf}


def scan_url(url: str) -> UrlScanResult:
    """Fetch, extract declarations, and run Rule 6(10) e-commerce checks."""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return UrlScanResult(url=url, fetched=False,
                             note="URL must start with http:// or https://.")
    try:
        resp = httpx.get(url, headers={"User-Agent": _UA}, timeout=15.0,
                         follow_redirects=True)
    except Exception as e:
        return UrlScanResult(url=url, fetched=False,
                             note=f"Could not fetch URL: {type(e).__name__}.")

    if resp.status_code != 200:
        return UrlScanResult(url=url, fetched=False, http_status=resp.status_code,
                             note=f"Fetch returned HTTP {resp.status_code} "
                                  "(page may require JavaScript or block bots).")

    parser = _TextExtractor()
    try:
        parser.feed(resp.text)
    except Exception:
        pass
    text = " ".join(parser.text_parts)
    ldjson = _from_ldjson(parser.ldjson_blocks)
    extracted = _extract(text, ldjson)

    found = {k: v for k, v in extracted.items() if v}
    if not found:
        return UrlScanResult(
            url=url, fetched=True, http_status=200, extracted=extracted,
            note=("Page fetched but no packaging declarations could be extracted "
                  "from static HTML (likely JavaScript-rendered / bot-protected). "
                  "No values fabricated."))

    # Build a ScanRequest from what we found and run the rule engine.
    req = ScanRequest(
        scan_id=f"url-{abs(hash(url)) % 10_000_000}",
        mrp_declaration=(f"MRP Rs. {extracted['mrp']}" if extracted["mrp"] else None),
        net_quantity_declaration=extracted["net_quantity"],
        country_of_origin_declaration=(
            f"Country of Origin: {extracted['country_of_origin']}"
            if extracted["country_of_origin"] else None),
        manufacturer_name_address=extracted["manufacturer"],
    )
    # E-commerce listings must carry MRP, net qty, country of origin, and
    # manufacturer (LMPC Rule 6(10)); category 'general' keeps standard checks.
    verdict = _engine.evaluate(req, product_category="general")
    note = ("Rule 6(10) e-commerce mandatory declarations checked against what "
            "was extractable from the page. Missing fields may be due to page "
            "rendering limits, not necessarily non-compliance.")
    return UrlScanResult(url=url, fetched=True, http_status=200,
                         extracted=extracted,
                         verdict=verdict.model_dump(mode="json"), note=note)
