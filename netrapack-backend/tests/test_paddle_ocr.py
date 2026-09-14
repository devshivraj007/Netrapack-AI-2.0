"""Tests for PaddleOCR (PP-OCRv4 ONNX runtime) integration."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.ocr.paddle_reader import paddle_available, read_words_paddle
from app.ocr.pipeline import run_ocr_pipeline


def test_paddle_ocr_available():
    assert paddle_available() is True


def test_paddle_ocr_reads_synthetic_packaging_label():
    # Render a clear synthetic packaging label
    img = np.ones((200, 600, 3), dtype=np.uint8) * 255
    cv2.putText(img, "AMUL TAZA MILK", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(img, "PKD 07/AUG/26", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, "MRP Rs 17.00", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

    res = read_words_paddle(img, min_conf=30.0)
    assert len(res.words) > 0
    assert "PKD" in res.raw_text or "07/AUG/26" in res.raw_text
    assert res.mean_conf > 50.0


def test_paddle_ocr_in_pipeline():
    img = np.ones((200, 600, 3), dtype=np.uint8) * 220
    cv2.putText(img, "MRP Rs 17.00", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.putText(img, "Net Qty: 250 ml", (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    ok, buf = cv2.imencode(".jpg", img)
    assert ok

    pipeline_res = run_ocr_pipeline(buf.tobytes())
    assert pipeline_res.ok is True
    assert pipeline_res.retake_required is False
    assert len(pipeline_res.raw_text) > 0
