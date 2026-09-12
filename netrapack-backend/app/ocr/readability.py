"""Font-size / readability approximation (LMPC Rule 9 area, advisory only).

HONEST SCOPE: LMPC Rule 9 mandates MINIMUM character heights (in mm) for
declarations, scaled by the net quantity / Principal Display Panel (PDP) area.
A truly compliant check needs the PHYSICAL character height in millimetres,
which a single photo cannot give without a scale reference (known package
dimensions or a fiducial marker in frame). OCR/vision give us PIXEL heights
only.

So this module provides an APPROXIMATION, clearly flagged as advisory: it
compares the median text character pixel-height against the overall captured
image height. If key text occupies an abnormally small fraction of the frame,
it flags "declarations may be below the minimum legible size - verify manually."
It never asserts a precise mm value or a hard legal pass/fail.

This is intentionally conservative: it can prompt a manual check, but it does
not fabricate a mm measurement it cannot actually derive from an unscaled photo.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Optional

from .reader import Word

# If the median character height is below this fraction of the image height,
# we flag it as "possibly too small". Tuned to be conservative (only flags
# genuinely tiny text). This is a heuristic, not a legal threshold.
_SMALL_TEXT_FRACTION = 0.012  # ~1.2% of frame height


@dataclass
class ReadabilityResult:
    assessed: bool                 # did we have enough data to assess?
    approximate: bool = True       # always True - this is not a mm measurement
    median_char_px: float = 0.0
    image_height_px: int = 0
    char_height_fraction: float = 0.0
    likely_too_small: bool = False
    note: str = ""


def assess_readability(words: list[Word], image_height_px: int) -> ReadabilityResult:
    """Approximate whether declaration text is large enough to be legible.

    Returns an advisory result; `approximate` is always True to make clear this
    is not a certified mm-based Rule 9 measurement.
    """
    usable = [w for w in words if w.text and w.height > 0]
    if not usable or image_height_px <= 0:
        return ReadabilityResult(
            assessed=False,
            note="Not enough text detected to assess readability.",
        )

    med = float(median([w.height for w in usable]))
    frac = med / float(image_height_px)
    too_small = frac < _SMALL_TEXT_FRACTION

    if too_small:
        note = (
            f"Approximate check: median text height is ~{frac * 100:.1f}% of the "
            "frame, which is small - declarations MAY be below the minimum "
            "legible size under LMPC Rule 9. Verify manually with a physical "
            "measurement (photo-based estimate cannot give exact mm)."
        )
    else:
        note = (
            f"Approximate check: median text height ~{frac * 100:.1f}% of the "
            "frame appears adequately legible. Note: this is a proportional "
            "estimate, not a certified mm measurement of Rule 9 character height."
        )

    return ReadabilityResult(
        assessed=True,
        approximate=True,
        median_char_px=round(med, 1),
        image_height_px=image_height_px,
        char_height_fraction=round(frac, 4),
        likely_too_small=too_small,
        note=note,
    )
