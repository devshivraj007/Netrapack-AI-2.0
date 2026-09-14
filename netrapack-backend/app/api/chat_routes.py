"""RAG compliance chatbot route (Day 4).

POST /api/v1/chat/query
    Answers a plain-language question about ONE scanned product, using the
    3-tier circuit breaker (local llama3.2 -> Gemini -> deterministic). The
    scan's verdict JSON and relevant LMPC rule text are injected as context.
    Every response carries the mandatory legal disclaimer.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai.chatbot import ChatContext, ComplianceChatbot
from app.db import repository

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

_chatbot = ComplianceChatbot()


class ChatQueryRequest(BaseModel):
    scan_id: Optional[str] = Field("general", description="The scan to explain, or 'general' for statutory guidance.")
    question: str = Field(..., description="Plain-language question.")


class ChatQueryResponse(BaseModel):
    scan_id: str
    question: str
    answer: str
    ai_source: str
    ai_level: str
    model: Optional[str] = None


@router.post("/query", response_model=ChatQueryResponse,
             summary="Ask a plain-language question about a scan or Legal Metrology rules")
def chat_query(req: ChatQueryRequest) -> ChatQueryResponse:
    target_scan_id = (req.scan_id or "general").strip()
    verdict = {}
    rules = []

    if target_scan_id and target_scan_id != "general":
        scan = repository.get_latest_scan(target_scan_id)
        if not scan:
            raise HTTPException(status_code=404,
                                detail=f"No scan found for scan_id '{target_scan_id}'.")
        verdict = scan.get("verdict", {}) or {}
        rules = repository.get_rules_for_verdict(verdict)
    else:
        target_scan_id = "general"
        rules = repository.get_all_rules()

    context = ChatContext(scan_id=target_scan_id, verdict=verdict, applicable_rules=rules)
    result = _chatbot.answer(req.question, context)
    return ChatQueryResponse(
        scan_id=target_scan_id,
        question=req.question,
        answer=result["answer"],
        ai_source=result["ai_source"],
        ai_level=result["ai_level"],
        model=result.get("model"),
    )
