"""Generate synthetic label images to exercise the OCR pipeline.

These stand in for real photographs until you drop real ones into tests/photos.
We render crisp label text with Pillow, then apply transformations:
  * clean labels (baseline OCR),
  * a tilted label (tests deskew),
  * a heavy-glare label (must trigger the >15% retake guard),
  * a curved-surface style label with a multi-line manufacturer address
    introduced by an anchor phrase (tests spatial grouping + address merge),
  * a label with OCR-confusable numbers (tests numeric cleansing indirectly).

Returns a list of (name, jpeg_bytes, expected_note) tuples.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("arial.ttf", "DejaVuSans.ttf", "Verdana.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# Realistic off-white "paper" - a real photo of a label is never pure 255
# white; specular glare is what clips to 255. Using off-white here keeps the
# background from being mistaken for glare.
_PAPER = (238, 236, 232)


def _render_label(lines: list[str], size=(900, 600), font_size=34) -> Image.Image:
    img = Image.new("RGB", size, _PAPER)
    draw = ImageDraw.Draw(img)
    font = _font(font_size)
    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += int(font_size * 1.5)
    return img


def _to_jpeg(img: Image.Image, quality=92) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _tilt(img: Image.Image, degrees: float) -> Image.Image:
    # Fill exposed corners with paper colour (not pure white) so they are not
    # mistaken for specular glare.
    return img.rotate(degrees, expand=True, fillcolor=_PAPER)


def _add_glare(img: Image.Image, coverage: float) -> Image.Image:
    """Paint bright near-white blobs covering ~coverage of the area."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    target = int(h * w * coverage)
    painted = 0
    rng = np.random.default_rng(42)
    while painted < target:
        bw = rng.integers(w // 6, w // 3)
        bh = rng.integers(h // 6, h // 3)
        x = rng.integers(0, max(1, w - bw))
        y = rng.integers(0, max(1, h - bh))
        arr[y : y + bh, x : x + bw] = 255
        painted += bw * bh
    return Image.fromarray(arr)


def build_samples() -> list[tuple[str, bytes, str]]:
    samples: list[tuple[str, bytes, str]] = []

    # 1) Clean compliant food label.
    clean = _render_label([
        "ABC Biscuits",
        "MRP Rs. 45",
        "Net Qty: 200g",
        "Mfg: MAR 2026",
        "Best Before: MAR 2027",
        "Mfg by ABC Foods Pvt Ltd",
        "Plot 5, MIDC, Pune",
        "Maharashtra 411001",
        "FSSAI 10012345678901",
        "care@abcfoods.com  1800-123-456",
        "Made in India",
    ])
    samples.append(("clean_food_label", _to_jpeg(clean), "clean baseline"))

    # 2) Tilted label (deskew test).
    tilt = _render_label([
        "Green Tea",
        "MRP Rs. 150",
        "Net Qty: 25 units",
        "Mfg: JAN 2026",
        "Mfg by Tea Estates Ltd",
        "Siliguri, West Bengal 734001",
        "FSSAI 10012345678918",
        "Made in India",
    ])
    samples.append(("tilted_label", _to_jpeg(_tilt(tilt, 8)), "should deskew ~8deg"))

    # 3) Heavy glare (must trigger retake).
    glare_base = _render_label([
        "Shampoo",
        "MRP Rs. 120",
        "Net Qty: 180ml",
        "Mfg by Care Products Ltd",
    ])
    samples.append((
        "heavy_glare_label",
        _to_jpeg(_add_glare(glare_base, 0.30)),
        "should require retake (>15% glare)",
    ))

    # 4) Curved-surface style: anchor phrase + multi-line address.
    curved = _render_label([
        "Cola Soft Drink",
        "MRP Rs. 40",
        "Net Qty: 300ml",
        "Mfg: FEB 2026",
        "Marketed by Beverage Co",
        "12 Industrial Area",
        "Bengaluru, Karnataka",
        "560002",
        "FSSAI 10012345678919",
        "Made in India",
    ])
    samples.append((
        "curved_multiline_address",
        _to_jpeg(curved),
        "address should merge into one block",
    ))

    # 5) Low-price sachet (USP exemption via <=Rs35 and tiny pack).
    sachet = _render_label([
        "Candy Sachet",
        "MRP Rs. 10",
        "Net Qty: 9g",
        "Mfg: JAN 2026",
        "Mfg by Sweet Co, Mumbai 400002",
        "FSSAI 10012345678921",
        "Made in India",
    ])
    samples.append(("low_price_sachet", _to_jpeg(sachet), "USP exemption expected"))

    # 6) 1kg pack (USP exemption via exactly 1kg).
    onekg = _render_label([
        "Wheat Flour",
        "MRP Rs. 55",
        "Net Qty: 1kg",
        "Mfg: FEB 2026",
        "Mfg by Grain Mills Ltd",
        "Chandigarh 160022",
        "FSSAI 10012345678922",
        "Made in India",
    ])
    samples.append(("one_kg_pack", _to_jpeg(onekg), "USP exemption (1kg)"))

    # 7) Personal care (non-food -> FSSAI check should be skipped for category).
    personal = _render_label([
        "Toothpaste",
        "MRP Rs. 55",
        "Net Qty: 100g",
        "Mfg: MAR 2026",
        "Mfg by Oral Care Pvt Ltd",
        "Ahmedabad 380001",
        "care@oralcare.com",
        "Made in India",
    ])
    samples.append(("personal_care_toothpaste", _to_jpeg(personal), "non-food category"))

    # 8) Electronics (non-food).
    electronics = _render_label([
        "LED Bulb 9W",
        "MRP Rs. 130",
        "Net Qty: 1 unit",
        "Mfg: JAN 2026",
        "Mfg by Bright Electricals Pvt Ltd",
        "Noida 201301",
        "helpline 1800-999-000",
        "Made in India",
    ])
    samples.append(("electronics_bulb", _to_jpeg(electronics), "1 unit USP exemption"))

    # 9) Missing FSSAI on a food product (should violate IF food category).
    missing_fssai = _render_label([
        "Instant Noodles",
        "MRP Rs. 15",
        "Net Qty: 70g",
        "Mfg: MAR 2026",
        "Mfg by Noodle Co, Nagpur 440001",
        "Made in India",
    ])
    samples.append(("food_missing_fssai", _to_jpeg(missing_fssai), "no FSSAI number"))

    # 10) Double price (MRP manual review).
    double_price = _render_label([
        "Cooking Oil",
        "MRP Rs. 250  Rs. 240",
        "Net Qty: 1L",
        "Mfg: FEB 2026",
        "Mfg by Oil Co, Mumbai 400001",
        "FSSAI 10012345678902",
        "Made in India",
    ])
    samples.append(("double_price_mrp", _to_jpeg(double_price), "two prices -> review"))

    # 11) Mild glare (below threshold -> should still read).
    mild = _render_label([
        "Detergent Powder",
        "MRP Rs. 110",
        "Net Qty: 1kg",
        "Mfg by Wash Co, Indore 452001",
        "Made in India",
    ])
    samples.append(("mild_glare_label", _to_jpeg(_add_glare(mild, 0.05)), "should still read"))

    return samples
