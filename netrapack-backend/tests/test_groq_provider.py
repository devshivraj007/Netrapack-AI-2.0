"""Unit tests for GroqVisionProvider and the 4-tier fallback chain."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx

from app.ai.chatbot import ChatContext, ComplianceChatbot
from app.ai.providers import GroqVisionProvider
from app.ai.recognizer import ProductRecognizer
from app.ai.types import (
    AiSource,
    ProductCategory,
    RecognitionResult,
)


class TestGroqVisionProvider(unittest.TestCase):
    def test_availability(self):
        p_no_key = GroqVisionProvider(api_key="")
        avail, model = p_no_key.is_available()
        self.assertFalse(avail)
        self.assertIsNone(model)

        p_with_key = GroqVisionProvider(api_key="gsk_test_key_12345", model="qwen/qwen3.8-27b")
        avail, model = p_with_key.is_available()
        self.assertTrue(avail)
        self.assertEqual(model, "qwen/qwen3.8-27b")

    @patch("httpx.post")
    def test_recognize_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"category": "food_and_beverage", "package_size": "standard", "package_shape": "pouch", "confidence": 0.95}'
                    }
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        provider = GroqVisionProvider(api_key="gsk_test", model="qwen/qwen3.8-27b")
        res = provider.recognize(b"fake_jpeg_bytes")

        self.assertEqual(res.category, ProductCategory.FOOD_AND_BEVERAGE)
        self.assertEqual(res.confidence, 0.95)
        self.assertEqual(res.ai_source, AiSource.CLOUD_GROQ)
        self.assertEqual(res.model_name, "qwen/qwen3.8-27b")

    @patch("httpx.post")
    def test_recognize_fallback_on_429(self, mock_post):
        err_resp = MagicMock()
        err_resp.status_code = 429
        err_call = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=err_resp)

        succ_resp = MagicMock()
        succ_resp.status_code = 200
        succ_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"category": "household", "package_size": "standard", "package_shape": "bottle", "confidence": 0.88}'
                    }
                }
            ]
        }
        succ_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [err_call, succ_resp]

        provider = GroqVisionProvider(
            api_key="gsk_test",
            model="qwen/qwen3.8-27b",
            fallback_model="qwen/qwen3.6-27b",
        )
        res = provider.recognize(b"fake_bytes")

        self.assertEqual(res.category, ProductCategory.HOUSEHOLD)
        self.assertEqual(res.ai_source, AiSource.CLOUD_GROQ)
        self.assertEqual(res.model_name, "qwen/qwen3.6-27b")
        self.assertEqual(mock_post.call_count, 2)

    @patch("httpx.post")
    def test_extract_fields(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"mrp": 90.0, "mrp_all_prices": [90.0], "net_quantity": "200g", '
                            '"fssai_license_number": "10012021000071", "country_of_origin": "India"}'
                        )
                    }
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        provider = GroqVisionProvider(api_key="gsk_test", model="qwen/qwen3.8-27b")
        ext = provider.extract_fields([b"front_img", b"back_img"])

        self.assertEqual(ext.mrp, 90.0)
        self.assertEqual(ext.net_quantity, "200g")
        self.assertEqual(ext.fssai_license_number, "10012021000071")
        self.assertEqual(ext.country_of_origin, "India")
        self.assertEqual(ext.ai_source, AiSource.CLOUD_GROQ)

    @patch("httpx.post")
    def test_chat_strips_thinking(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>Processing legal query...</think>Under Rule 6, MRP declaration is mandatory."
                    }
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        provider = GroqVisionProvider(api_key="gsk_test")
        ans = provider.chat("system", "user query")
        self.assertEqual(ans, "Under Rule 6, MRP declaration is mandatory.")


class TestFallbackChainPriority(unittest.TestCase):
    def test_recognizer_groq_leads(self):
        mock_groq = MagicMock()
        mock_groq.is_available.return_value = (True, "qwen/qwen3.8-27b")
        mock_groq.recognize.return_value = RecognitionResult(
            category=ProductCategory.FOOD_AND_BEVERAGE,
            confidence=0.92,
            ai_source=AiSource.CLOUD_GROQ,
            model_name="qwen/qwen3.8-27b",
        )

        mock_gemini = MagicMock()
        mock_gemini.is_available.return_value = (True, "gemini-flash-latest")
        mock_gemini.recognize.return_value = RecognitionResult(
            category=ProductCategory.PERSONAL_CARE,
            confidence=0.85,
            ai_source=AiSource.CLOUD_GEMINI,
            model_name="gemini-flash-latest",
        )

        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = (True, "qwen2.5vl:3b")

        rec = ProductRecognizer(groq=mock_groq, gemini=mock_gemini, ollama=mock_ollama)
        result = rec.recognize(b"test")

        self.assertEqual(result.ai_source, AiSource.CLOUD_GROQ)
        self.assertEqual(result.category, ProductCategory.FOOD_AND_BEVERAGE)
        self.assertFalse(result.below_confidence_threshold)
        mock_gemini.recognize.assert_not_called()
        mock_ollama.recognize.assert_not_called()

    def test_recognizer_falls_back_to_gemini(self):
        mock_groq = MagicMock()
        mock_groq.is_available.return_value = (False, None)

        mock_gemini = MagicMock()
        mock_gemini.is_available.return_value = (True, "gemini-flash-latest")
        mock_gemini.recognize.return_value = RecognitionResult(
            category=ProductCategory.PERSONAL_CARE,
            confidence=0.85,
            ai_source=AiSource.CLOUD_GEMINI,
            model_name="gemini-flash-latest",
        )

        rec = ProductRecognizer(groq=mock_groq, gemini=mock_gemini)
        result = rec.recognize(b"test")

        self.assertEqual(result.ai_source, AiSource.CLOUD_GEMINI)
        mock_gemini.recognize.assert_called_once()

    def test_confidence_gate_enforced_for_groq(self):
        mock_groq = MagicMock()
        mock_groq.is_available.return_value = (True, "qwen/qwen3.8-27b")
        mock_groq.recognize.return_value = RecognitionResult(
            category=ProductCategory.FOOD_AND_BEVERAGE,
            confidence=0.50,
            ai_source=AiSource.CLOUD_GROQ,
            model_name="qwen/qwen3.8-27b",
        )

        rec = ProductRecognizer(groq=mock_groq)
        result = rec.recognize(b"test")

        self.assertTrue(result.below_confidence_threshold)
        self.assertEqual(result.effective_category, ProductCategory.GENERAL)
        self.assertIn("below the 70% threshold", result.note)

    def test_chatbot_groq_leads(self):
        mock_groq = MagicMock()
        mock_groq.is_available.return_value = (True, "qwen/qwen3.8-27b")
        mock_groq.chat.return_value = "Groq explanation of violations."

        mock_gemini = MagicMock()
        mock_gemini.is_available.return_value = (True, "gemini-flash-latest")

        bot = ComplianceChatbot(groq=mock_groq, gemini=mock_gemini)
        ctx = ChatContext(scan_id="test-1", verdict={"overall_status": "COMPLIANT"})
        ans = bot.answer("Why is it compliant?", ctx)

        self.assertEqual(ans["ai_source"], "cloud_groq")
        self.assertEqual(ans["model"], "qwen/qwen3.8-27b")
        self.assertIn("Groq explanation", ans["answer"])
        mock_gemini.chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
