"""
Pydantic 스키마
"""
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


# ── Notice ──────────────────────────────────────────────
class NoticeBase(BaseModel):
    id: str
    origin: str
    title: str
    full_title: str = ""
    target: str = ""
    benefit: str = ""
    limit: str = ""
    documents: str = ""
    region: str = "전국"
    url: str = ""
    period: str = ""
    date: Optional[datetime] = None
    content: str = ""
    jrsdInsttNm: str = ""
    excInsttNm: str = ""
    hashTags: str = ""
    printFileNm: str = ""
    printFlpthNm: str = ""
    fileNm: str = ""
    flpthNm: str = ""
    reqstMthPapersCn: str = ""
    refrncNm: str = ""
    rceptEngnHmpgUrl: str = ""
    category: str = ""
    ajin_similarity: float = 0.0


class NoticeCreate(NoticeBase):
    pass


class NoticeOut(NoticeBase):
    fetched_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Draft ──────────────────────────────────────────────
class DraftUpsert(BaseModel):
    notice_id: str
    notice_snapshot: dict = {}
    current_step: int = 1
    completed_steps: list = []
    uploads: dict = {}
    drafts: dict = {}
    status: Optional[str] = None  # Step5 완료 시 '작성완료' 전달 가능


class DraftOut(BaseModel):
    id: int
    notice_id: str
    notice_snapshot: dict = {}
    current_step: int
    completed_steps: list
    uploads: dict
    drafts: dict
    version: int = 1
    status: str = '작성중'
    submitted_at: Optional[datetime] = None
    result: Optional[str] = None
    result_date: Optional[datetime] = None
    result_memo: Optional[str] = None
    parent_draft_id: Optional[int] = None
    version_note: Optional[str] = None
    is_archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DraftStatusUpdate(BaseModel):
    status: str
    result_memo: Optional[str] = None


class DraftResultUpdate(BaseModel):
    result: str                      # '채택' | '미채택'
    result_date: Optional[datetime] = None
    result_memo: Optional[str] = None


class DraftVersionCreate(BaseModel):
    version_note: Optional[str] = None
    replace_version: Optional[int] = None  # v4 시도 시 교체할 버전 번호


class DraftListItem(BaseModel):
    """MyDraftsPage 목록용 — notice_id 그룹의 최신 버전"""
    id: int
    notice_id: str
    notice_snapshot: dict = {}
    current_step: int
    version: int = 1
    status: str = '작성중'
    submitted_at: Optional[datetime] = None
    result: Optional[str] = None
    result_date: Optional[datetime] = None
    result_memo: Optional[str] = None
    is_archived: bool = False
    updated_at: Optional[datetime] = None
    all_versions: list = []  # 동일 notice_id의 전체 버전 목록 (최신→구버전)

    class Config:
        from_attributes = True


# ── Bookmark ────────────────────────────────────────────
class BookmarkCreate(BaseModel):
    notice_id: str
    notice_snapshot: dict = {}


class BookmarkOut(BaseModel):
    id: int
    notice_id: str
    notice_snapshot: dict = {}
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Profile ─────────────────────────────────────────────
class ProfileUpsert(BaseModel):
    company_name: str = "아진산업(주)"
    representative: str = ""
    biz_number: str = ""
    founded_date: str = ""
    region: str = "경남"
    address: str = ""
    industry: str = "제조업"
    sub_industry: str = "자동차 부품"
    employees: str = "1200"
    revenue_range: str = "1천억~5천억"
    certifications: list = []
    match_keywords: str = "자동차, 스마트공장, DX, 프레스, 에너지"
    exclude_keywords: str = ""
    sales: str = "약 5,000억 원"
    field: str = "자동차 부품, DX"
    summary: str = "자동차 차체 부품 및 스마트 팩토리 선도"
    strategy: str = "미래 모빌리티 전환"
    achievements: str = ""
    core_tech: str = ""
    core_team: str = ""


class ProfileOut(ProfileUpsert):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
