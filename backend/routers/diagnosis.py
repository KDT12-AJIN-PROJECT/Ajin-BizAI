"""
AI 진단 API
업로드된 자료의 충족도를 분석합니다.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from services.diagnosis import calculate_completeness

router = APIRouter(prefix="/api", tags=["diagnosis"])


class DiagnosisRequest(BaseModel):
    notice_text: str = ""           # 공고문 텍스트
    uploaded_docs: dict = {}        # {"파일명": "텍스트내용", ...}
    interview_answers: dict = {}    # {"질문키": "답변", ...}


@router.post("/diagnosis")
async def run_diagnosis(req: DiagnosisRequest):
    """
    업로드된 자료를 분석해서 작성 가능률을 계산합니다.

    반환값:
    - total: 전체 작성 가능률 (0~100%)
    - by_section: 섹션별 준비도
    - missing_required: 필수 보완 항목 목록
    - missing_optional: 선택 보완 항목 목록
    """
    result = calculate_completeness(
        notice_text=req.notice_text,
        uploaded_docs=req.uploaded_docs,
        interview_answers=req.interview_answers,
    )
    return result
