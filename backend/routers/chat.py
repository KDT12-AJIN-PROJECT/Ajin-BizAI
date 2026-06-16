"""
v0.2 AI 보완 대화 API (PRD §16.5) — /api/chat/*

Phase 4-E:
  - POST /api/chat/draft-assist — 작성 중 대화형 보조 (질문별 초안 컨텍스트)

각 endpoint:
  - Provider (mock/anthropic/hybrid) 자동 분기 (AI_PROVIDER 환경변수)
  - audit_log 자동 기록
  - Failure Protocol retry (test_03 §3.7.2)

PRD §16.5 body 스펙:
  { question_id, message, draft_content }
  + session_id (audit log/세션 추적용으로 추가)
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.ai_provider import get_provider

router = APIRouter(prefix="/api/chat", tags=["chat"])


class DraftAssistRequest(BaseModel):
    """초안 작성 보조 대화 (PRD §16.5).

    chat_review provider 메서드 시그니처:
      chat_review(message, draft_content, notice_title, history)
    """
    session_id: str
    question_id: str
    message: str
    draft_content: str = ""
    notice_title: str = ""
    history: List[Dict[str, Any]] = []  # [{role: user|assistant, content}, ...]
    request_id: str = ""


@router.post("/draft-assist")
async def draft_assist(req: DraftAssistRequest) -> Dict[str, Any]:
    """초안 작성 보조 대화 (PRD §16.5).

    내부:
      - provider.chat_review 호출 (V1 호환 메서드)
      - history 누적 (Phase 4-G에서 DB 저장)

    Phase 4-E 단계: 단발 응답만. 멀티턴 history 영속화는 Phase 4-G.
    """
    provider = get_provider()
    response_text = await provider.chat_review(
        message=req.message,
        draft_content=req.draft_content,
        notice_title=req.notice_title,
        history=req.history,
    )
    return {
        "session_id": req.session_id,
        "question_id": req.question_id,
        "response": response_text,
        "history_appended": [
            {"role": "user", "content": req.message},
            {"role": "assistant", "content": response_text},
        ],
        "_note": "Phase 4-E mock — history DB 저장은 Phase 4-G",
    }
