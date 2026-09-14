"""Live end-to-end verification of GroqVisionProvider with the real GROQ_API_KEY.

Exercises:
  1. GroqVisionProvider availability and model identification.
  2. Single-image product category & shape recognition.
  3. Multi-image (front + back) field extraction.
  4. ComplianceChatbot live RAG answer.
  5. Safety gates (confidence gate and officer confirmation).
"""

from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from app.ai.chatbot import ChatContext, ComplianceChatbot
from app.ai.providers import GroqVisionProvider
from app.ai.recognizer import ProductRecognizer
from app.ai.types import AiSource, CONFIDENCE_THRESHOLD


def _create_synthetic_label(lines: list[str], size=(600, 300)) -> bytes:
    img = Image.new("RGB", size, color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 20
    for line in lines:
        d.text((25, y), line, fill=(0, 0, 0))
        y += 35
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main():
    print("============================================================")
    print("      NetraPack 2.0 - Groq Live Provider Verification      ")
    print("============================================================")

    provider = GroqVisionProvider()
    available, model = provider.is_available()
    print(f"1. Provider Status: available={available}, model={model}")
    if not available:
        print("[FAIL] GroqVisionProvider is not available (GROQ_API_KEY missing).")
        sys.exit(1)

    # 2. Live Product Recognition via ProductRecognizer (Chain Priority & Safety Gate)
    print("\n2. Testing ProductRecognizer with Groq as Level 1 primary...")
    recognizer = ProductRecognizer()
    front_jpeg = _create_synthetic_label([
        "Himalaya Purifying Neem Face Wash",
        "Net Vol: 150 ml",
        "Mfg Date: 03/2026",
    ])
    rec_result = recognizer.recognize(front_jpeg)
    print(f"   Category:          {rec_result.category.value}")
    print(f"   Effective Cat:     {rec_result.effective_category.value}")
    print(f"   Shape:             {rec_result.package_shape.value}")
    print(f"   Size:              {rec_result.package_size.value}")
    print(f"   Confidence:        {rec_result.confidence:.2%}")
    print(f"   Source:            {rec_result.ai_source.value}")
    print(f"   Model:             {rec_result.model_name}")
    print(f"   Confirmation note: {rec_result.note}")
    assert rec_result.ai_source == AiSource.CLOUD_GROQ, "Groq must be chosen first in fallback chain"
    if rec_result.confidence >= CONFIDENCE_THRESHOLD:
        assert not rec_result.below_confidence_threshold
        assert "Not yet confirmed" in rec_result.note
        print("   [PASS] 70% Confidence gate & officer confirmation note verified.")
    else:
        assert rec_result.below_confidence_threshold
        print("   [PASS] Below threshold gate triggered as designed.")

    import time
    time.sleep(2)

    # 3. Live Field Extraction via GroqVisionProvider
    print("\n3. Testing live field extraction via GroqVisionProvider...")
    back_jpeg = _create_synthetic_label([
        "Himalaya Purifying Neem Face Wash",
        "MRP Rs. 180.00 (incl. of all taxes)",
        "Net Vol: 150 ml",
        "Expiry: 02/2028",
        "Country of Origin: India",
        "Mfd by: The Himalaya Drug Company, Makali, Bengaluru 562162",
    ])
    ext = provider.extract_fields([back_jpeg])
    print(f"   Extracted MRP:         {ext.mrp}")
    print(f"   Extracted Net Qty:     {ext.net_quantity}")
    print(f"   Extracted Country:     {ext.country_of_origin}")
    print(f"   Extracted Mfg Details: {ext.manufacturer_details}")
    print(f"   Extraction Source:     {ext.ai_source.value}")
    print(f"   Model:                 {ext.model_name}")
    assert ext.ai_source == AiSource.CLOUD_GROQ
    assert ext.mrp == 180.0
    print("   [PASS] Live field extraction succeeded.")

    time.sleep(2)

    # 4. Live Compliance Chatbot
    print("\n4. Testing live compliance chatbot via Groq...")
    bot = ComplianceChatbot()
    ctx = ChatContext(
        scan_id="groq-test-01",
        verdict={
            "overall_status": "COMPLIANT",
            "rules_passed": 7,
            "rules_checked": 7,
            "parsed_fields": {
                "mrp": {"raw_input": "180.00"},
                "net_quantity": {"raw_input": "150 ml"},
            },
            "violations": [],
        },
        applicable_rules=[
            {
                "rule_key": "rule_6_mrp",
                "citation": "Rule 6(1)(e)",
                "description": "Every package shall bear MRP inclusive of all taxes.",
            }
        ],
    )
    answer = bot.answer("Does this product declare its MRP properly?", ctx)
    print(f"   Chat AI Source: {answer['ai_source']}")
    print(f"   Chat Model:     {answer['model']}")
    print(f"   Answer:         {answer['answer'][:160]}...")
    assert answer["ai_source"] == "cloud_groq"
    assert "Note: This AI explanation is for guidance only" in answer["answer"]
    print("   [PASS] Chatbot live Groq query succeeded with disclaimer.")

    print("\n============================================================")
    print("   ALL GROQ LIVE PROVIDER CHECKS PASSED SUCCESSFULLY!       ")
    print("============================================================")


if __name__ == "__main__":
    main()
