"""PaddleOCR (PP-OCRv4) reader engine via RapidOCR ONNX Runtime.

Excels at alphanumeric dot-matrix ink-jet stamps (PKD, EXP, B.No), curved pouch
packaging, and arbitrary text orientations without requiring Tesseract binaries.
"""

from __future__ import annotations

import logging
from typing import Optional
import numpy as np

from .reader import OcrResult, Word

logger = logging.getLogger(__name__)

_rapid_ocr_instance = None
_paddle_available: Optional[bool] = None


def paddle_available() -> bool:
    """Return True if rapidocr_onnxruntime is importable and functional."""
    global _paddle_available
    if _paddle_available is not None:
        return _paddle_available
    try:
        from rapidocr_onnxruntime import RapidOCR
        _paddle_available = True
    except Exception as e:
        logger.debug("PaddleOCR (RapidOCR) not available: %s", e)
        _paddle_available = False
    return _paddle_available


def get_paddle_engine():
    """Lazy-load singleton instance of RapidOCR."""
    global _rapid_ocr_instance
    if _rapid_ocr_instance is None:
        if not paddle_available():
            return None
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_instance = RapidOCR()
        except Exception as e:
            logger.error("Failed to initialize RapidOCR engine: %s", e)
            return None
    return _rapid_ocr_instance


def read_words_paddle(bgr: np.ndarray, min_conf: float = 30.0) -> OcrResult:
    """Run PP-OCRv4 detection and recognition on BGR image.
    
    Converts RapidOCR boxes into standard NetraPack Word objects compatible
    with spatial grouping and field extraction.
    """
    engine = get_paddle_engine()
    if engine is None:
        return OcrResult(words=[], raw_text="", mean_conf=0.0)

    scale_factor = 1.0
    h, w = bgr.shape[:2]
    max_dim = max(h, w)
    if max_dim > 1280:
        import cv2
        scale_factor = 1280.0 / float(max_dim)
        bgr = cv2.resize(bgr, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_AREA)

    try:
        results, _ = engine(bgr)
    except Exception as e:
        logger.error("PaddleOCR execution error: %s", e)
        return OcrResult(words=[], raw_text="", mean_conf=0.0)

    if not results:
        return OcrResult(words=[], raw_text="", mean_conf=0.0)

    words: list[Word] = []
    confs: list[float] = []

    for line_idx, item in enumerate(results):
        # item: [box, text, score]
        box, text, score = item[0], item[1], item[2]
        if not text or not str(text).strip():
            continue

        conf = float(score) * 100.0 if float(score) <= 1.0 else float(score)
        if conf < min_conf:
            continue

        pts = np.array(box, dtype=np.float32)
        if scale_factor != 1.0:
            pts = pts / scale_factor
        left = int(np.min(pts[:, 0]))
        top = int(np.min(pts[:, 1]))
        right = int(np.max(pts[:, 0]))
        bottom = int(np.max(pts[:, 1]))
        width = max(1, right - left)
        height = max(1, bottom - top)

        sub_words = str(text).strip().split()
        if not sub_words:
            continue

        # Distribute horizontal span proportionally across words
        total_len = max(1, len(text))
        curr_left = left
        for sw in sub_words:
            sw_w = max(1, int(width * (len(sw) / total_len)))
            words.append(
                Word(
                    text=sw,
                    left=curr_left,
                    top=top,
                    width=sw_w,
                    height=height,
                    conf=conf,
                    line_num=line_idx,
                    block_num=0,
                )
            )
            curr_left += sw_w + max(1, int(width * (1 / total_len)))
        confs.append(conf)

    raw_text = " ".join(w.text for w in words)
    mean_conf = float(np.mean(confs)) if confs else 0.0
    return OcrResult(words=words, raw_text=raw_text, mean_conf=mean_conf)


def find_fssai_paddle(image_input: bytes | np.ndarray) -> Optional[str]:
    """Extract a 14-digit FSSAI licence number from an image using PaddleOCR.
    
    Excels at fine print labels (e.g. 'Lic. No. 10012021000071') where vision
    models often confuse the 13-digit product barcode with FSSAI.
    """
    engine = get_paddle_engine()
    if engine is None:
        return None

    import cv2
    if isinstance(image_input, (bytes, bytearray)):
        arr = np.frombuffer(image_input, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            return None
    else:
        bgr = image_input

    # Downscale high-resolution photos to max dimension 1280 for fast (<1s) inference
    h, w = bgr.shape[:2]
    max_dim = max(h, w)
    if max_dim > 1280:
        scale = 1280.0 / float(max_dim)
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    try:
        results, _ = engine(bgr)
    except Exception as e:
        logger.error("PaddleOCR FSSAI scan error: %s", e)
        return None

    if not results:
        return None

    import re
    # 1. High-confidence: text line contains 'lic' or 'fssai' followed by a 14-digit number
    for item in results:
        text = str(item[1]).replace(" ", "").replace("-", "").replace(".", "")
        m = re.search(r"(?:lic|fssai|license|licence|regn?)[^\d]*([12]\d{13})\b", text, re.IGNORECASE)
        if m:
            return m.group(1)

    # 2. Medium-confidence: any standalone 14-digit number starting with 1 or 2
    for item in results:
        text = str(item[1]).replace(" ", "").replace("-", "")
        m = re.search(r"\b([12]\d{13})\b", text)
        if m:
            return m.group(1)

    return None
