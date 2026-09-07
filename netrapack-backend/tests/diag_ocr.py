"""Diagnose OCR on one real photo: print prep stats, word count, raw text."""
from __future__ import annotations

from app.ocr.image_prep import prepare_image
from app.ocr.pipeline import decode_image
from app.ocr.reader import read_words, tesseract_available


def main() -> None:
    print("tesseract_available:", tesseract_available())
    path = "tests/photos/08_KelloggsChocos_back.jpg"
    with open(path, "rb") as f:
        data = f.read()
    print("bytes:", len(data))

    bgr = decode_image(data)
    print("decoded shape:", None if bgr is None else bgr.shape)

    prepared = prepare_image(bgr)
    print("after prep shape:", prepared.image.shape,
          "glare%:", round(prepared.glare.glare_fraction * 100, 1),
          "too_much:", prepared.glare.too_much_glare,
          "skew:", prepared.deskew_angle_deg)

    ocr = read_words(prepared.image)
    print("word count:", len(ocr.words), "mean_conf:", ocr.mean_conf)
    print("raw_text[:500]:", repr(ocr.raw_text[:500]))


if __name__ == "__main__":
    main()
