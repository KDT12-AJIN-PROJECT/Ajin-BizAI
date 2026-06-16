"""
AJIN BizAI v0.2 — Lightweight Ontology Schemas (Pydantic)
출처: PRD v0.2 FINAL §13.1~§13.10

핵심 11종 (AI ontology):
  1. ApplicationSession  — 공고 1개 작성 작업 단위 (모든 산출물의 부모)
  2. CompanySchema       — 기업 정보
  3. NoticeSchema        — 공고 분석 결과
  4. FormSchema          — 제출양식 구조
  5. EvidenceSchema      — 참고자료 근거
  6. MappingResult       — 문항 ↔ Evidence 매칭
  7. MissingMaterial     — 부족자료 상태
  8. SupplementalMaterial — 사용자 보완자료 (원본)
  9. DraftItem           — 작성된 초안
  10. FitAnalysis        — 공고 적합성 (3축)
  11. EvalCriteriaMapping — 평가기준 ↔ 문항 매핑

운영 보조 (§13.10):
  - CompanyFile          — 기업프로필 자료 영구 메타데이터
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Status enum types ─────────────────────────────────────────────────

# ApplicationSession.status (PRD §13.9, 8 values)
ApplicationSessionStatus = Literal[
    "created",
    "analyzing",
    "analysis_ready",
    "step2_confirmed",
    "drafting",
    "completed",
    "abandoned",
    "failed",
]

# DraftItem.status (PRD §13.7, 6 values)
DraftItemStatus = Literal[
    "draft",
    "generated",
    "user_edited",
    "approved",
    "needs_revision",
    "abandoned",
]

# MissingMaterial.status (PRD §13.5, 8 values)
MissingMaterialStatus = Literal[
    "open",
    "uploaded",
    "analyzing",
    "matched",
    "resolved",
    "deferred",
    "rejected",
    "failed",
]

# SupplementalMaterial.status (PRD §13.6, 4 values)
SupplementalMaterialStatus = Literal["uploaded", "analyzed", "converted", "failed"]

# MappingResult.match_status (PRD §13.4, 4 values)
MappingMatchStatus = Literal[
    "auto_confirmed",
    "user_confirmed",
    "awaiting_user_confirm",
    "excluded",
]

# CompanyFile.status (PRD §13.10)
CompanyFileStatus = Literal["active", "expired", "review_needed", "archived"]

# Drafts preservation policy (PRD §13.9, 재분석 시 drafts 처리)
DraftsPreservationPolicy = Literal["preserve", "discard", "user_choice"]

# Reanalyze target (PRD §16.2)
ReanalyzeTarget = Literal[
    "notice", "form", "evidence", "company", "mapping", "missing", "all"
]

# Source display mode (Step 5 export, PRD §12 / test_06 §6.10)
SourceDisplayMode = Literal["footnote", "endnote", "none"]


# ─── 1. ApplicationSession (PRD §13.9) ────────────────────────────────

class ApplicationSession(BaseModel):
    """공고 1개에 대한 작성 작업 단위. 모든 산출물의 부모."""
    session_id: str
    user_id: str
    company_profile_id: Optional[str] = None
    notice_file_id: Optional[str] = None
    form_file_id: Optional[str] = None
    reference_file_ids: List[str] = Field(default_factory=list)
    selected_company_file_ids: List[str] = Field(default_factory=list)
    status: ApplicationSessionStatus = "created"
    current_step: int = Field(default=1, ge=1, le=5)
    created_at: datetime
    updated_at: datetime
    last_activity_at: Optional[datetime] = None
    confirmed_step2_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    abandoned_at: Optional[datetime] = None
    exported_at: Optional[datetime] = None
    export_count: int = 0
    last_export_file_id: Optional[str] = None
    drafts_preservation_policy: DraftsPreservationPolicy = "user_choice"


# ─── 2. CompanySchema (PRD §13.x) ──────────────────────────────────────

class Capability(BaseModel):
    """기업 역량 단일 항목"""
    capability_id: str
    name: str
    description: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Optional[str] = None


class CompanySchema(BaseModel):
    """기업 정보 (분석 결과)"""
    company_profile_id: str
    name: str
    representative: Optional[str] = None
    industry: Optional[str] = None
    founded: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    capabilities: List[Capability] = Field(default_factory=list)


# ─── 3. NoticeSchema (PRD §13.x) ───────────────────────────────────────

class EvalSubCriterion(BaseModel):
    """평가기준 세부 항목 (배점표 내 개별 평가 질문).
    v1.7 (2026-05-18) — Notice 평가표의 3단계 hierarchy 중 leaf level 표현.
    예: 부모 "스마트공장 구축 필요성 (30점)" 아래의 "데이터 수집·분석 활용도가 높은가? (15점)"."""
    text: str                                      # 본문 평가 질문 원문 (의역 금지)
    weight: int = Field(ge=0, le=100)              # 세부 배점 (본문 명시값)
    note: Optional[str] = None                     # 가이드/주석 (예: "정량평가")


class EvalCriterion(BaseModel):
    """평가기준 단일 항목 (NoticeSchema 안 + EvalCriteriaMapping 별도).
    v1.7 (2026-05-18): stage / stage_total / stage_order / criterion_type / sub_criteria 추가
      — 공고별 가변 평가구조 (서면+기술성+가점 등 다단계) + 3단계 hierarchy 대응."""
    name: str
    weight: int = Field(ge=0, le=100)
    scope: Literal["question", "section", "document"] = "section"
    # 평가단계 메타 (공고마다 단계명 다름 — 본문 그대로 자유, 정규화 금지)
    stage: Optional[str] = None                    # 예: "서면평가" / "기술성평가" / "1차 사전심사" / "가점" / "자격요건" / null
    stage_total: Optional[int] = None              # 해당 stage 총점 (예: 100, 5)
    stage_order: Optional[int] = None              # 평가 흐름상 순서 (1, 2, 3, ... — 없으면 LLM 응답 순)
    # 보편 분류 (다운스트림 집계용 — 4 enum 고정)
    criterion_type: Literal["score", "bonus", "penalty", "eligibility"] = "score"
    # 세부 평가 질문 (본문에 표 형식으로 있으면 모두 추출, 없으면 빈 list)
    sub_criteria: List[EvalSubCriterion] = Field(default_factory=list)


class NoticeExtraFact(BaseModel):
    """공고문 반정형 추출 항목 (extras).

    정형 14필드에 들어가지 않는 본문상 중요 정보를 LLM이 자유롭게 추출.
    공고 유형(R&D / 시설지원 / 컨설팅 / 해외진출)에 따라 항목이 달라짐.

    value는 Any (str / list / dict / bool / number) — value_type에 따라 형태가 다름:
      - text → str
      - list → List[str | dict]
      - table → List[Dict[str, Any]] (행 배열) 또는 2D List
      - date → str (YYYY-MM-DD 또는 YYYY-MM-DDTHH:MM)
      - amount → str (예: "2억원") 또는 number
      - boolean → bool
      - object → Dict[str, Any]
    """
    category: str                                       # 예: "가점", "사업 구조", "기술료", "추진체계"
    label: str                                          # 예: "비수도권 소재 기업 가점"
    value: Any                                          # value_type에 따라 다양한 형식
    value_type: Literal[
        "text", "list", "table", "date", "amount", "boolean", "object"
    ] = "text"
    source_page: Optional[int] = None
    source_quote: Optional[str] = None                  # 본문 원문 발췌 (40~120자 권장)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: Literal["high", "medium", "low"] = "medium"


class NoticeSchema(BaseModel):
    """공고문 분석 결과.

    v1.3 (2026-05-12) — extras(반정형) 도입, 가점은 extras category="가점"으로 통합.
    정형 필드는 보편 항목 (모든 공고 유형 공통). 공고별 특수 정보는 extras.
    """
    notice_id: Optional[str] = None
    target: str = ""
    benefit: str = ""                                   # 과제당 한도 위주 (총규모는 total_budget)
    total_budget: Optional[str] = None                  # 예: "195.5억원 (137개 과제)"
    deadline: Optional[str] = None                      # YYYY-MM-DD (접수 마감일)
    application_period_start: Optional[str] = None      # YYYY-MM-DD (접수 시작일)
    submission_system: Optional[str] = None             # 예: "IRIS (www.iris.go.kr)"
    evaluation_criteria: List[EvalCriterion] = Field(default_factory=list)
    process_steps: List[str] = Field(default_factory=list)  # 신청·평가 절차 단계 (순서)
    required_documents: List[str] = Field(default_factory=list)
    exclusion_conditions: List[str] = Field(default_factory=list)
    important_keywords: List[str] = Field(default_factory=list)
    ai_interpretation: Dict[str, List[str]] = Field(default_factory=dict)
    extras: List[NoticeExtraFact] = Field(default_factory=list)
    # source_pages: 정형 필드 → 본문 페이지 매핑. LLM이 모르면 키 자체 생략 권장.
    # Any 허용 (빈 dict / null도 통과) — LLM 응답 다양성 흡수.
    source_pages: Dict[str, Any] = Field(default_factory=dict)


# ─── 4. FormSchema (PRD §13.2) ─────────────────────────────────────────

class FormConstraints(BaseModel):
    max_length: int = 0
    min_length: int = 0
    format: Optional[str] = None
    page_limit: Optional[str] = None


class FormQuestion(BaseModel):
    """제출양식 단일 문항 (PRD §13.2).

    표 구조 (is_table_item=true 시):
      - table_columns: 원문 등장 순서대로 보존된 컬럼 헤더
      - table_rows: 원문 등장 순서대로 보존된 행 라벨
          · 빈 배열 → 자유 입력형 표 (작성자가 행 자유 추가)
          · 채워짐 → 행 고정형 표 (셀만 채우는 양식, 예: 매출 현황표 2023/2024/2025)
      - table_cell_hints: 컬럼명 → 단위·형식 힌트 (예: {"매출": "백만원", "비율": "%"})
    병합 셀(rowspan/colspan), 자동 산출 컬럼은 이 schema 범위 밖.
    """
    model_config = ConfigDict(extra="allow")
    question_id: str
    title: str
    original_text: Optional[str] = None
    requirement: Optional[str] = None
    writing_guidelines: List[str] = Field(default_factory=list)
    example_text: List[str] = Field(default_factory=list)
    constraints: FormConstraints = Field(default_factory=FormConstraints)
    required_evidence_types: List[str] = Field(default_factory=list)
    required_attachments: List[str] = Field(default_factory=list)
    do_not_include: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    source_page: Optional[int] = None
    source_block_id: Optional[str] = None
    is_required: bool = False
    is_table_item: bool = False
    table_columns: List[str] = Field(default_factory=list)
    table_rows: List[str] = Field(default_factory=list)
    table_cell_hints: Dict[str, Any] = Field(default_factory=dict)
    order: Optional[int] = None


class FormSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_id: str
    title: str
    order: int = 0
    questions: List[FormQuestion] = Field(default_factory=list)


class FormSchema(BaseModel):
    """제출양식 파싱 결과 (PRD §13.2)"""
    model_config = ConfigDict(extra="allow")

    form_id: str
    form_name: str
    source_file: Optional[str] = None
    sections: List[FormSection] = Field(default_factory=list)


# ─── 5. EvidenceSchema (PRD §13.3) ─────────────────────────────────────

EvidenceType = Literal["보유 기술", "정량 실적", "수행 역량", "시장 분석", "인증/특허", "etc"]


class EvidenceItem(BaseModel):
    """참고자료 단일 evidence (PRD §13.3)"""
    evidence_id: str
    source_file: str
    source_page: Optional[int] = None
    source_block: Optional[str] = None
    type: EvidenceType = "etc"
    content: str
    raw_text: Optional[str] = None
    matched_questions: List[str] = Field(default_factory=list)
    confidence_per_question: Dict[str, float] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None  # 1024-dim (bge-m3-ko)


class EvidenceSchema(BaseModel):
    """참고자료 추출 결과"""
    items: List[EvidenceItem] = Field(default_factory=list)


# ─── 6. MappingResult (PRD §13.4) ──────────────────────────────────────

class QuestionMapping(BaseModel):
    """문항 ↔ Evidence 매핑 단일 항목"""
    question_id: str
    matched_evidence_ids: List[str] = Field(default_factory=list)
    used_evidence_ids: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_evidence_types: List[str] = Field(default_factory=list)
    match_status: MappingMatchStatus = "awaiting_user_confirm"


class MappingResult(BaseModel):
    """전체 매핑 결과 (모든 문항)"""
    session_id: str
    question_mappings: List[QuestionMapping] = Field(default_factory=list)
    overall_missing_count: int = 0
    coverage_rate: float = Field(default=0.0, ge=0.0, le=1.0)


# ─── 7. MissingMaterial (PRD §13.5) ────────────────────────────────────

class MissingMaterial(BaseModel):
    """부족자료 (상태 관리만)"""
    missing_id: str
    session_id: str
    question_id: str
    missing_type: str  # 설문/인터뷰 / 비교표 / 정량 데이터 / ...
    name: str
    description: Optional[str] = None
    input_type: Literal["text", "file", "both"] = "both"
    status: MissingMaterialStatus = "open"
    supplemental_ids: List[str] = Field(default_factory=list)
    resolved_at: Optional[datetime] = None


# ─── 8. SupplementalMaterial (PRD §13.6) ───────────────────────────────

class SupplementalMaterial(BaseModel):
    """사용자 보완자료 (원본 데이터)"""
    supplemental_id: str
    session_id: str
    question_id: str
    missing_id: Optional[str] = None
    type: Literal["text", "file"] = "file"
    content: Optional[str] = None
    file_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    status: SupplementalMaterialStatus = "uploaded"
    created_at: datetime


# ─── 9. DraftItem (PRD §13.7) ──────────────────────────────────────────

class DraftItemAIMetadata(BaseModel):
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    generated_at: Optional[datetime] = None


class DraftItem(BaseModel):
    """문항별 초안 단일 항목 (PRD §13.7)"""
    draft_id: str
    session_id: Optional[str] = None
    question_id: str
    content: str = ""
    table_data: List[Dict[str, Any]] = Field(default_factory=list)
    used_evidence_ids: List[str] = Field(default_factory=list)
    char_count: int = 0
    status: DraftItemStatus = "draft"
    warnings: List[str] = Field(default_factory=list)
    ai_metadata: DraftItemAIMetadata = Field(default_factory=DraftItemAIMetadata)
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None


class DraftSchema(BaseModel):
    """초안 생성 결과 (모든 문항)"""
    session_id: str
    items: List[DraftItem] = Field(default_factory=list)


# ─── 10. FitAnalysis (PRD §13.x) ───────────────────────────────────────

FitLevel = Literal["높음", "중간", "낮음"]
FitColor = Literal["success", "warning", "error"]


class FitAxis(BaseModel):
    """평가기준 1축 (예: 기술성/사업성/수행역량)"""
    name: str
    weight: int = Field(ge=0, le=100)
    score: int = Field(ge=0, le=100)
    level: FitLevel
    level_color: FitColor
    description: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    recommendation: Optional[str] = None


class FitAnalysis(BaseModel):
    """공고 적합성 (PRD §13.x)"""
    session_id: str
    company_profile_id: str
    axes: List[FitAxis] = Field(default_factory=list)
    overall_score: Optional[int] = None


# ─── 11. EvalCriteriaMapping (PRD §13.8) ───────────────────────────────

EvalScope = Literal["question", "section", "document"]
EvalMappingType = Literal["direct", "indirect", "context"]
EvalMappedBy = Literal["ai", "user"]


class EvalCriteriaMapping(BaseModel):
    """평가기준 ↔ 문항 매핑"""
    criteria_id: str
    session_id: Optional[str] = None
    criteria_name: str
    weight: int = Field(ge=0, le=100)
    scope: EvalScope = "section"
    mapped_questions: List[str] = Field(default_factory=list)
    mapping_type: EvalMappingType = "direct"
    mapped_by: EvalMappedBy = "ai"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: Optional[str] = None
    source_page: Optional[int] = None


# ─── 운영 보조 (PRD §13.10) ─────────────────────────────────────────────

CompanyFileType = Literal[
    "회사소개서", "재무제표", "사업자등록증", "인증서", "특허", "실적", "기타"
]


class CompanyFile(BaseModel):
    """기업프로필 자료 영구 파일 메타데이터 (PRD §13.10.1)
    AI ontology 11종과 분리된 운영 보조 entity.
    Step 1에서 직접 업로드 X, 기업설정/기업자료실에서만 관리.
    ApplicationSession.selected_company_file_ids[]는 본 file_id 참조.
    """
    file_id: str
    company_profile_id: str
    file_name: str
    file_size_bytes: int = 0
    file_storage_path: Optional[str] = None
    file_type: CompanyFileType = "기타"
    uploaded_at: datetime
    updated_at: Optional[datetime] = None
    uploaded_by: Optional[str] = None
    status: CompanyFileStatus = "active"
    expires_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)


# ─── Prompt hint 상수 (Phase 4-C 시점에 prompts/*.md 참조용) ─────────────

NOTICE_SCHEMA_PROMPT_HINT = (
    "공고문에서 NoticeSchema를 추출하라: target / benefit / deadline / "
    "evaluation_criteria (name, weight, scope) / required_documents / "
    "exclusion_conditions / important_keywords / source_pages"
)

FORM_SCHEMA_PROMPT_HINT = (
    "제출양식에서 FormSchema를 추출하라: form_id / form_name / source_file / "
    "sections[].questions[] (question_id, title, requirement, constraints, "
    "is_required, is_table_item, source_page 등)"
)

EVIDENCE_SCHEMA_PROMPT_HINT = (
    "참고자료 chunk에서 EvidenceItem을 추출하라: evidence_id / source_file / "
    "source_page / type (보유 기술 / 정량 실적 / 수행 역량 / 시장 분석 / 인증·특허) / "
    "content / raw_text / embedding (1024-dim bge-m3-ko)"
)

DRAFT_SCHEMA_PROMPT_HINT = (
    "문항별 DraftItem을 작성하라: draft_id / question_id / content (글자수 준수) / "
    "used_evidence_ids (환각 방지 — matched 외 사용 금지) / status / warnings"
)


__all__ = [
    # Status enums
    "ApplicationSessionStatus", "DraftItemStatus", "MissingMaterialStatus",
    "SupplementalMaterialStatus", "MappingMatchStatus", "CompanyFileStatus",
    "DraftsPreservationPolicy", "ReanalyzeTarget", "SourceDisplayMode",
    # Core schemas (11)
    "ApplicationSession",
    "CompanySchema", "Capability",
    "NoticeSchema", "EvalCriterion",
    "FormSchema", "FormSection", "FormQuestion", "FormConstraints",
    "EvidenceSchema", "EvidenceItem", "EvidenceType",
    "MappingResult", "QuestionMapping",
    "MissingMaterial",
    "SupplementalMaterial",
    "DraftItem", "DraftItemAIMetadata", "DraftSchema",
    "FitAnalysis", "FitAxis", "FitLevel", "FitColor",
    "EvalCriteriaMapping", "EvalScope", "EvalMappingType", "EvalMappedBy",
    # Operational (§13.10)
    "CompanyFile", "CompanyFileType",
    # Prompt hints
    "NOTICE_SCHEMA_PROMPT_HINT", "FORM_SCHEMA_PROMPT_HINT",
    "EVIDENCE_SCHEMA_PROMPT_HINT", "DRAFT_SCHEMA_PROMPT_HINT",
]
