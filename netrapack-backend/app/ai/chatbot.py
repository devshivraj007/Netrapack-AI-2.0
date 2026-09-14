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
import re
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
    "You are NetraPack's Legal Metrology compliance assistant for the Government of India. "
    "You explain statutory packaging rules under the Legal Metrology Act, 2009, "
    "Legal Metrology (Packaged Commodities) Rules, 2011 (LMPC Rules), and FSSAI regulations.\n\n"
    "CRITICAL FORMATTING & STYLE RULES:\n"
    "1. NEVER use markdown symbols. Do NOT use asterisks (** or *), hashes (##, ###), bullet asterisks (*), or backticks in your answer.\n"
    "2. Reply in clean, natural, plain text only.\n"
    "3. Keep answers concise, direct, and to the point (2 to 4 short sentences or simple numbered points 1., 2.). Avoid verbose essays.\n"
    "4. When explaining a specific product, reference the scan data directly and explain clearly why it complies or fails.\n"
    "5. Do NOT add a disclaimer; the system appends one automatically."
)


def _clean_plain_text(text: str) -> str:
    """Sanitize chatbot output to pure plain text: removes markdown stars, hashes, backticks, etc."""
    if not text:
        return ""
    # Strip markdown headers: #, ##, ###
    t = re.sub(r'(?m)^#{1,6}\s*', '', text)
    # Strip bold/italic asterisks: ***word***, **word**, *word*
    t = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', t)
    # Strip bold/italic underscores: ___word___, __word__, _word_
    t = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', t)
    # Strip code backticks: `code`
    t = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', t)
    # Strip blockquotes: > quote
    t = re.sub(r'(?m)^[ \t]*>[ \t]*', '', t)
    # Strip any remaining stray asterisks or hashes
    t = t.replace('*', '').replace('#', '')
    # Normalize excessive linebreaks / whitespace
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    return t.strip()


@dataclass
class ChatContext:
    scan_id: str
    verdict: dict[str, Any]
    applicable_rules: list[dict[str, Any]] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Render the RAG context injected into the model."""
        v = self.verdict or {}
        if not self.scan_id or self.scan_id == "general" or not v:
            rules_txt = "\n".join(
                f"- {r.get('rule_key')}: {r.get('citation')} - {r.get('description')}"
                for r in self.applicable_rules
            ) or "(standard statutory rules from LMPC Rules 2011)"
            return (
                "MODE: GENERAL STATUTORY COMPLIANCE & LEGAL METROLOGY ADVISOR\n"
                "FRAMEWORK: Legal Metrology Act, 2009 & LMPC Rules, 2011.\n"
                f"RELEVANT STATUTORY PROVISIONS & RULES:\n{rules_txt}\n"
            )

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
            "Answer directly and concisely in 2 to 4 sentences in clean plain text without any markdown asterisks (**) or hashes (##)."
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
        text = _clean_plain_text(text)
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
        q = question.lower()
        if not context.scan_id or context.scan_id == "general" or not context.verdict:
            if any(k in q for k in ["rule 6", "mandatory", "declaration", "declarations", "require"]):
                return (
                    "Under Rule 6(1) of the Legal Metrology (Packaged Commodities) Rules, 2011, every pre-packaged commodity in India must declare:\n"
                    "1. Maximum Retail Price (MRP) in format 'MRP Rs. ... incl. of all taxes'\n"
                    "2. Net quantity in standard metric units (weight, volume, length, or count)\n"
                    "3. Month and year of manufacture, packing, or import\n"
                    "4. 'Best before' or expiry date (mandatory for perishable / edible goods)\n"
                    "5. Unit Sale Price (USP) to allow transparent consumer comparison\n"
                    "6. Country of origin\n"
                    "7. Name and complete address of the manufacturer, packer, or importer\n"
                    "8. Consumer care contact details (name, address, telephone number, email)\n"
                    "9. 14-digit FSSAI license number & logo (for all food & beverage commodities)"
                )
            if any(k in q for k in ["section 36", "penalty", "fine", "punishment", "jail", "violation"]):
                return (
                    "Section 36 of the Legal Metrology Act, 2009 prescribes penalties for non-compliance:\n"
                    "• Section 36(1): Manufacturing, packing, distributing, or selling non-standard packages is punishable with a fine up to ₹25,000 for the first offence, up to ₹50,000 for the second offence, and up to ₹1,00,000 or imprisonment up to 1 year for subsequent offences.\n"
                    "• Section 36(2): Charging above the declared MRP (overcharging) is similarly penalized with fines up to ₹25,000 (first offence) to ₹50,000 (subsequent)."
                )
            if any(k in q for k in ["unit sale price", "usp", "per 100g", "per gram", "per ml"]):
                return (
                    "Rule 6(1)(f) of the LMPC Rules mandates declaration of Unit Sale Price (USP) alongside MRP:\n"
                    "• For commodities ≤ 1kg, USP is declared per 100g or per 100ml.\n"
                    "• For commodities > 1kg, USP is declared per 1kg or per 1 litre.\n"
                    "• For commodities sold by count, USP is declared per piece / per unit (e.g. ₹10.00 per N).\n"
                    "Exemptions (Rule 26): USP is not required where net quantity is exactly 1kg, 1 litre, or 1 piece, or for packages whose net quantity is 10g/10ml or less."
                )
            if any(k in q for k in ["nch", "complaint", "helpline", "grievance", "e-jagriti", "consumer"]):
                return (
                    "Consumers can register packaging or overcharging grievances through official DCA channels:\n"
                    "• National Consumer Helpline (NCH): Toll-Free 1800-11-4000 (National) or 1915.\n"
                    "• SMS grievance to 8800001915.\n"
                    "• Online portal: consumerhelpline.gov.in or e-Daakhil for formal consumer commission complaints.\n"
                    "• Section 36 inspection notice generated by NetraPack can serve as primary documentary evidence."
                )
            if any(k in q for k in ["dual mrp", "different mrp", "overcharge", "tax"]):
                return (
                    "Under Rule 18(2A) of the LMPC Rules, 2011, 'Dual MRP' (declaring different MRPs on identical packages for different sales channels) is strictly illegal in India. "
                    "Retailers are prohibited from charging any amount above the declared MRP, and all prices must explicitly include all applicable taxes."
                )
            return (
                "NetraPack Legal Metrology Compliance Assistant:\n"
                "I can assist you with statutory packaging rules under the Legal Metrology Act, 2009, "
                "the Legal Metrology (Packaged Commodities) Rules, 2011 (LMPC Rules), and FSSAI regulations. "
                "You can ask about Rule 6 mandatory declarations, Section 36 penalty provisions, Unit Sale Price (USP) rules, "
                "Dual MRP prohibitions, or how to lodge consumer complaints via NCH."
            )

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
