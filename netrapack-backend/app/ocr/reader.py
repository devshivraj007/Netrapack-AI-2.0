"""Tesseract OCR wrapper producing word-level boxes.

We keep word geometry (bounding boxes) because spatial grouping needs to know
where each word sits to reconstruct multi-line blocks like a manufacturer's
name + address, especially on curved surfaces where line spacing is uneven.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
import pytesseract


@dataclass
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    line_num: int
    block_num: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def cx(self) -> float:
        return self.left + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.top + self.height / 2.0


@dataclass
class OcrResult:
    words: list[Word] = field(default_factory=list)
    raw_text: str = ""
    mean_conf: float = 0.0


def _configure_tesseract_path() -> Optional[str]:
    """Locate the tesseract binary.

    Honours TESSERACT_CMD if set, otherwise checks PATH and the default
    UB-Mannheim install location on Windows.
    """
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.exists(env_cmd):
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return env_cmd

    on_path = shutil.which("tesseract")
    if on_path:
        pytesseract.pytesseract.tesseract_cmd = on_path
        return on_path

    default_win = os.path.join(
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        "Tesseract-OCR", "tesseract.exe",
    )
    if os.path.exists(default_win):
        pytesseract.pytesseract.tesseract_cmd = default_win
        return default_win

    return None


def tesseract_available() -> bool:
    return _configure_tesseract_path() is not None


def read_words(bgr: np.ndarray, min_conf: float = 30.0) -> OcrResult:
    """Run Tesseract and return words with geometry above a confidence floor."""
    _configure_tesseract_path()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # Light adaptive threshold improves OCR on uneven lighting.
    proc = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    data = pytesseract.image_to_data(
        proc, output_type=pytesseract.Output.DICT, config="--oem 3 --psm 6"
    )

    words: list[Word] = []
    confs: list[float] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < min_conf:
            continue
        words.append(
            Word(
                text=text,
                left=int(data["left"][i]),
                top=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                conf=conf,
                line_num=int(data["line_num"][i]),
                block_num=int(data["block_num"][i]),
            )
        )
        confs.append(conf)

    raw_text = " ".join(w.text for w in words)
    mean_conf = float(np.mean(confs)) if confs else 0.0
    return OcrResult(words=words, raw_text=raw_text, mean_conf=mean_conf)
