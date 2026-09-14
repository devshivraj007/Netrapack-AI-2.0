"""Plain-language RAG compliance chatbot (Day 4).

Four-tier circuit breaker:
    Level 1: Groq cloud (qwen/qwen3.8-27b)    - ultra-fast LPU inference
    Level 2: Gemini cloud (gemini-3.6-flash)  - secondary cloud AI fallback
    Level 3: local Ollama (llama3.2:3b)       - offline edge assistant
    Level 4: deterministic rule-engine answer - always works, no AI

RAG context injection: for every query we retrieve the scan's verdict JSON
(extracted fields, declared values, detected violations) and the relevant LMPC
rule statutory text from the database, and inject both into the model context.

System-prompt lock: the assistant may ONLY explain this product's compliance
findings, statutory exemptions, net-quantity calculations, or overcharge rules.
It must refuse anything outside that scope.

Every response ends with the mandatory legal disclaimer (exact text).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .providers import GeminiVisionProvider, GroqVisionProvider, OllamaVisionProvider
from .types import AiSource

# Exact disclaimer required on every response payload.
LEGAL_DISCLAIMER = (
    "Note: This AI explanation is for guidance only and does not constitute a "
    "formal legal opinion under the Legal Metrology Act, 2009."
)

SYSTEM_PROMPT = (
    "You are NetraPack's Legal Metrology compliance assistant. You help a user "
    "understand the compliance findings for ONE specific scanned product. "
    "You may ONLY discuss: (a) this product's compliance findings and violations, "
    "(b) statutory exemptions that apply, (c) net-quantity / packaging-weight "
    "calculations, and (d) maximum-retail-price / overcharge rules. "
    "Use ONLY the SCAN DATA and RULE TEXT provided in the context. Do not invent "
    "legal provisions, citations, or facts beyond that context. If the question "
    "is outside this scope (general legal advice, other products, unrelated "
    "topics), politely decline and say you can only explain this scan's findings. "
    "Answer in plain, non-technical language, briefly. Do NOT add a disclaimer "
    "yourself; the system appends one."
)


@dataclass
class ChatContext:
    scan_id: str
    verdict: dict[str, Any]
    applicable_rules: list[dict[str, Any]] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Render the RAG context injected into the model."""
        v = self.verdict or {}
        parsed = v.get("parsed_fields", {}) or {}
        declared = {
            k: (pf.get("raw_input") if isinstance(pf, dict) else None)
            for k, pf in parsed.items()
        }
        violations = [
            {"field": x.get("field"), "citation": x.get("rule_citation"),
             "issue": x.get("description")}
            for x in (v.get("violations", []) or [])
        ]
        rules_txt = "\n".join(
            f"- {r.get('rule_key')}: {r.get('citation')} - {r.get('description')}"
            for r in self.applicable_rules
        ) or "(no specific rule text retrieved)"

        return (
            f"SCAN DATA (scan_id={self.scan_id}):\n"
            f"  overall_status: {v.get('overall_status')}\n"
            f"  rules_passed/checked: {v.get('rules_passed')}/{v.get('rules_checked')}\n"
            f"  declared_values: {json.dumps(declared, default=str)}\n"
            f"  violations: {json.dumps(violations, default=str)}\n\n"
            f"RELEVANT LMPC RULE TEXT:\n{rules_txt}\n"
        )


class ComplianceChatbot:
    """4-tier RAG chatbot."""

    def __init__(self, groq: Optional[GroqVisionProvider] = None,
                 gemini: Optional[GeminiVisionProvider] = None,
                 ollama: Optional[OllamaVisionProvider] = None):
        self.groq = groq or GroqVisionProvider()
        self.gemini = gemini or GeminiVisionProvider()
        self.ollama = ollama or OllamaVisionProvider()

    def answer(self, question: str, context: ChatContext) -> dict[str, Any]:
        """Return {answer, ai_source, model, level} with disclaimer appended."""
        user_prompt = (
            f"{context.to_prompt_block()}\n"
            f"USER QUESTION: {question}\n\n"
            "Answer using only the scan data and rule text above."
        )

        # Level 1: Groq cloud chat (primary).
        try:
            available, model = self.groq.is_available()
            if available:
                text = self.groq.chat(SYSTEM_PROMPT, user_prompt)
                if text:
                    return self._wrap(text, AiSource.CLOUD_GROQ, model, "cloud")
        except Exception:
            pass

        # Level 2: Gemini cloud chat (secondary fallback).
        try:
            available, model = self.gemini.is_available()
            if available:
                text = self.gemini.chat(SYSTEM_PROMPT, user_prompt)
                if text:
                    return self._wrap(text, AiSource.CLOUD_GEMINI, model, "cloud")
        except Exception:
            pass

        # Level 3: local Ollama chat (offline fallback).
        try:
            available, model = self.ollama.chat_available()
            if available:
                text = self.ollama.chat(SYSTEM_PROMPT, user_prompt)
                if text:
                    return self._wrap(text, AiSource.LOCAL_OLLAMA, model, "local_edge")
        except Exception:
            pass

        # Level 4: deterministic answer (no AI).
        return self._wrap(self._deterministic_answer(question, context),
                          AiSource.NONE, None, "rule_engine_only")

    def _wrap(self, text: str, source: AiSource, model: Optional[str],
              level: str) -> dict[str, Any]:
        text = text.strip()
        # Ensure the exact disclaimer is present exactly once, as a footer.
        if LEGAL_DISCLAIMER not in text:
            text = f"{text}\n\n{LEGAL_DISCLAIMER}"
        return {
            "answer": text,
            "ai_source": source.value,
            "model": model,
            "ai_level": level,
        }

    def _deterministic_answer(self, question: str, context: ChatContext) -> str:
        """Rule-based summary when no AI is available. Plain, factual."""
        v = context.verdict or {}
        status = v.get("overall_status", "unknown")
        violations = v.get("violations", []) or []
        lines = [
            f"For scan {context.scan_id}, the overall compliance status is "
            f"'{status}', with {v.get('rules_passed', 0)} of "
            f"{v.get('rules_checked', 0)} checks passed.",
        ]
        if violations:
            lines.append("The following issues were found:")
            for x in violations:
                lines.append(f"- {x.get('field')}: {x.get('description')} "
                             f"({x.get('rule_citation')})")
        else:
            lines.append("No violations were recorded for this product.")
        lines.append("(Local and cloud AI were unavailable, so this is a direct "
                     "summary of the recorded findings.)")
        return "\n".join(lines)
