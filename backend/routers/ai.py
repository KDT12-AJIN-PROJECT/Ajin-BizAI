"""
AI 작업 API — DEPRECATED (v0.2 이후 점진 폐기, PRD-13 §18.4)

V1 DraftPage 호환 endpoint. V2 화면은 호출 금지:
  V2 사용:  /api/analysis/* + /api/chat/draft-assist
  V2 금지:  /api/ai/* wrapper 호출

폐기 일정:
  - Phase 7 V1 화면 폐기 시 — generate-draft / improve / chat-review / check-completeness 제거
  - /api/ai/evaluate 만 v0.3 (Step 4 평가 엔진 분리) 까지 유지

위 6 endpoint signature는 V1 화면 회귀 방지 위해 변경 금지 (CLAUDE.md §4).
"""
from fastapi import APIRouter
from pydantic import BaseModel
from services.ai_provider import get_provider

router = APIRouter(prefix="/api/ai", tags=["ai"])


class GenerateDraftRequest(BaseModel):
    notice_text: str = ""
    profile: dict = {}
    section: str = "overview"   # overview | purpose | plan | effect | budget


class EvaluateRequest(BaseModel):
    draft_text: str
    notice_text: str = ""


class ImproveRequest(BaseModel):
    draft_text: str
    instruction: str


class CompletenessRequest(BaseModel):
    uploaded_docs: dict = {}    # {"파일명": "텍스트내용"}
    notice_text: str = ""


class ChatReviewRequest(BaseModel):
    message: str
    draft_content: str = ""
    notice_title: str = ""
    history: list = []


@router.post("/generate-draft")
async def generate_draft(req: GenerateDraftRequest):
    """섹션별 초안 생성"""
    provider = get_provider()
    result = await provider.generate_draft(req.notice_text, req.profile, req.section)
    return {"section": req.section, "text": result}


@router.post("/evaluate")
async def evaluate_draft(req: EvaluateRequest):
    """초안 평가"""
    provider = get_provider()
    return await provider.evaluate_draft(req.draft_text, req.notice_text)


@router.post("/improve")
async def improve_draft(req: ImproveRequest):
    """초안 개선"""
    provider = get_provider()
    result = await provider.improve_draft(req.draft_text, req.instruction)
    return {"text": result}


@router.post("/check-completeness")
async def check_completeness(req: CompletenessRequest):
    """업로드 자료 완성도 검사"""
    provider = get_provider()
    return await provider.check_completeness(req.uploaded_docs, req.notice_text)


@router.post("/chat-review")
async def chat_review(req: ChatReviewRequest):
    """사업계획서 검토 챗봇"""
    provider = get_provider()
    result = await provider.chat_review(req.message, req.draft_content, req.notice_title, req.history)
    return {"response": result}


class SimpleChatRequest(BaseModel):
    system: str = ""
    user: str
    max_tokens: int = 1024
    temperature: float = 0.4


@router.post("/chat")
async def simple_chat(req: SimpleChatRequest):
    """범용 단일 LLM 호출 — 프론트엔드 callLM 전용 (3줄 요약 등)."""
    provider = get_provider()
    result = await provider._chat(
        req.system,
        req.user,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    return {"content": result}


@router.get("/provider-info")
def provider_info():
    """현재 사용 중인 AI provider 확인"""
    import os
    name = os.getenv("AI_PROVIDER", "mock")
    return {"provider": name, "description": {
        "mock": "테스트용 Mock 응답 (LLM 없이 동작)",
        "local": "로컬 LLM (LM Studio / Ollama)",
        "openai": "OpenAI GPT API",
    }.get(name, name)}
