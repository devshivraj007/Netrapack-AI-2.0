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
    scan_id: str = Field(..., description="The scan to explain.")
    question: str = Field(..., description="Plain-language question.")


class ChatQueryResponse(BaseModel):
    scan_id: str
    question: str
    answer: str
    ai_source: str
    ai_level: str
    model: Optional[str] = None


@router.post("/query", response_model=ChatQueryResponse,
             summary="Ask a plain-language question about a scan's compliance")
def chat_query(req: ChatQueryRequest) -> ChatQueryResponse:
    scan = repository.get_latest_scan(req.scan_id)
    if not scan:
        raise HTTPException(status_code=404,
                            detail=f"No scan found for scan_id '{req.scan_id}'.")

    verdict = scan.get("verdict", {}) or {}
    rules = repository.get_rules_for_verdict(verdict)
    context = ChatContext(scan_id=req.scan_id, verdict=verdict,
                          applicable_rules=rules)

    result = _chatbot.answer(req.question, context)
    return ChatQueryResponse(
        scan_id=req.scan_id,
        question=req.question,
        answer=result["answer"],
        ai_source=result["ai_source"],
        ai_level=result["ai_level"],
        model=result.get("model"),
    )
