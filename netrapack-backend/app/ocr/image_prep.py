"""Image cleanup before OCR.

Two jobs:
  1. Deskew a tilted photo so text lines are horizontal (helps OCR a lot).
  2. Detect and reduce glare/reflection. If glare covers more than a
     configurable fraction of the label area we DO NOT try to read the
     hidden text - the caller returns a "retake the photo" result instead
     of risking a false reading.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# If glare covers more than this fraction of the image, ask for a retake.
GLARE_RETAKE_THRESHOLD = 0.15  # 15%

# A pixel is considered "glare" when it is a CLIPPED specular highlight: nearly
# maximum brightness (a real reflection blows out to ~255) AND low-saturation.
# Ordinary paper/label white photographed under normal light sits noticeably
# below 250, so this floor separates a bright label from an actual reflection.
# The detail-loss test in _glare_mask adds a second, independent condition.
_GLARE_VALUE_MIN = 250  # brightness (V in HSV), 0-255 - true clipping
_GLARE_SATURATION_MAX = 25  # saturation (S in HSV), 0-255


@dataclass
class GlareReport:
    glare_fraction: float
    too_much_glare: bool
    threshold: float = GLARE_RETAKE_THRESHOLD


@dataclass
class PreparedImage:
    image: np.ndarray  # cleaned BGR image ready for OCR
    glare: GlareReport
    deskew_angle_deg: float


# Local detail (texture) threshold. Real glare is a blown-out patch that has
# LOST local detail - it is bright AND smooth. A plain white label background
# is bright too, but wherever there is text it has high local variance, so it
# is not counted as glare. This is what stops a clean white label from being
# mistaken for a fully glared one.
_GLARE_LOCAL_STDDEV_MAX = 8.0  # 0-255 scale; below this = "no detail here"
_GLARE_WINDOW = 15  # neighbourhood size for the local std-dev estimate


def _glare_mask(bgr: np.ndarray) -> np.ndarray:
    """Boolean mask of pixels that are bright, low-saturation, AND detail-less.

    Detail is measured as local standard deviation of brightness in a window.
    Glare = saturated highlight with no readable structure underneath.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1]
    v = hsv[:, :, 2].astype(np.float32)

    bright_lowsat = (v >= _GLARE_VALUE_MIN) & (s <= _GLARE_SATURATION_MAX)

    # Local std-dev via E[x^2] - E[x]^2 over a box window.
    ksize = (_GLARE_WINDOW, _GLARE_WINDOW)
    mean = cv2.blur(v, ksize)
    mean_sq = cv2.blur(v * v, ksize)
    variance = np.clip(mean_sq - mean * mean, 0, None)
    local_std = np.sqrt(variance)

    detail_less = local_std <= _GLARE_LOCAL_STDDEV_MAX
    return bright_lowsat & detail_less


def measure_glare(bgr: np.ndarray) -> GlareReport:
    """Estimate the fraction of the image that is genuine (detail-less) glare."""
    mask = _glare_mask(bgr)
    fraction = float(np.count_nonzero(mask)) / float(mask.size)
    return GlareReport(
        glare_fraction=fraction,
        too_much_glare=fraction > GLARE_RETAKE_THRESHOLD,
    )


def reduce_glare(bgr: np.ndarray) -> np.ndarray:
    """Soften moderate glare so it interferes less with OCR.

    We inpaint the detail-less blown-out patches using surrounding pixels. This
    only helps for modest glare; heavy glare is caught by measure_glare and
    routed to a retake instead.
    """
    mask = _glare_mask(bgr).astype(np.uint8) * 255
    if np.count_nonzero(mask) == 0:
        return bgr
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return cv2.inpaint(bgr, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)


def estimate_skew_angle(bgr: np.ndarray) -> float:
    """Estimate the tilt of the text in degrees.

    Positive angle means the image is rotated counter-clockwise. We threshold
    to find dark text on light background, then take the minimum-area rectangle
    around all text pixels and read its angle.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]
    if np.count_nonzero(thresh) < 20:
        return 0.0

    # Projection-profile skew estimate: for each candidate angle, rotate the
    # binary text mask and measure how "peaky" the row-sum profile is. When the
    # text lines are horizontal, rows alternate between dense (text) and empty
    # (gaps), giving a high variance. We pick the angle with the max variance.
    # This is far more stable than minAreaRect on scattered glyph pixels and it
    # naturally returns ~0 for an already-straight label.
    small = cv2.resize(thresh, (thresh.shape[1] // 2 or 1, thresh.shape[0] // 2 or 1))
    best_angle = 0.0
    best_score = -1.0
    for angle in np.arange(-_MAX_SKEW_DEG, _MAX_SKEW_DEG + 0.5, 0.5):
        rotated = _rotate_for_score(small, angle)
        profile = rotated.sum(axis=1, dtype=np.float64)
        score = float(np.var(profile))
        if score > best_score:
            best_score = score
            best_angle = float(angle)
    return best_angle


# A hand-held label photo is realistically tilted at most this many degrees;
# clamping avoids nonsensical 90-degree "corrections".
_MAX_SKEW_DEG = 15.0


def _rotate_for_score(mask: np.ndarray, angle: float) -> np.ndarray:
    (h, w) = mask.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(mask, matrix, (w, h), flags=cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def deskew(bgr: np.ndarray, angle: float) -> np.ndarray:
    """Rotate the image by -angle to make text horizontal."""
    if abs(angle) < 0.5:
        return bgr  # not worth rotating
    (h, w) = bgr.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        bgr, matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


# Cap the longest side before processing. Retail photos are often 3000-4000px;
# Tesseract is much slower on those and label text reads fine at ~1600px. This
# is a big speedup with negligible accuracy loss for label-sized text.
_MAX_DIMENSION = 1600


def downscale(bgr: np.ndarray, max_dim: int = _MAX_DIMENSION) -> np.ndarray:
    h, w = bgr.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return bgr
    scale = max_dim / float(longest)
    new_size = (int(w * scale), int(h * scale))
    return cv2.resize(bgr, new_size, interpolation=cv2.INTER_AREA)


def prepare_image(bgr: np.ndarray) -> PreparedImage:
    """Full cleanup: downscale, measure glare, reduce it, then deskew.

    Glare is measured on the (downscaled) image before inpainting so the retake
    decision reflects the real photo quality.
    """
    bgr = downscale(bgr)
    glare = measure_glare(bgr)
    working = reduce_glare(bgr)
    angle = estimate_skew_angle(working)
    working = deskew(working, angle)
    return PreparedImage(image=working, glare=glare, deskew_angle_deg=angle)
