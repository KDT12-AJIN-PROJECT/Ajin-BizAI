"""
SQLAlchemy ORM 모델
"""
from sqlalchemy import Column, String, Float, DateTime, Text, Integer, JSON, Boolean, ForeignKey
from sqlalchemy.sql import func
from database import Base


class Notice(Base):
    """외부 API에서 가져온 공고 캐시"""
    __tablename__ = "notices"

    id = Column(String, primary_key=True)          # "{origin}-{title}-{period}"
    origin = Column(String, nullable=False)         # 출처 기관
    title = Column(String, nullable=False)
    full_title = Column(String, default="")
    target = Column(Text, default="")
    benefit = Column(Text, default="")
    limit = Column(Text, default="")
    documents = Column(Text, default="")
    region = Column(String, default="전국")
    url = Column(String, default="")
    period = Column(String, default="")
    date = Column(DateTime, nullable=True)
    content = Column(Text, default="")
    jrsd_instt_nm = Column(String, default="")
    exc_instt_nm = Column(String, default="")
    hash_tags = Column(String, default="")
    print_file_nm = Column(String, default="")
    print_flpth_nm = Column(String, default="")
    file_nm = Column(String, default="")
    flpth_nm = Column(String, default="")
    reqst_mth_papers_cn = Column(Text, default="")
    refrnc_nm = Column(String, default="")
    rcept_engn_hmpg_url = Column(String, default="")
    category = Column(String, default="")
    ajin_similarity = Column(Float, default=0.0)
    fetched_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Draft(Base):
    """사업계획서 초안 (버전 관리 지원)"""
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(String, nullable=False, index=True)
    notice_snapshot = Column(JSON, default={})
    current_step = Column(Integer, default=1)
    completed_steps = Column(JSON, default=[])
    uploads = Column(JSON, default={})
    drafts = Column(JSON, default={})

    # 버전 관리 (UNIQUE(notice_id, version)은 DB 레벨에서 설정됨)
    version = Column(Integer, nullable=False, default=1)

    # 상태 관리
    status = Column(String, default='작성중', index=True)
    submitted_at = Column(DateTime, nullable=True)
    result = Column(String, nullable=True)          # '채택' / '미채택' / None
    result_date = Column(DateTime, nullable=True)
    result_memo = Column(Text, nullable=True)
    parent_draft_id = Column(Integer, ForeignKey('drafts.id'), nullable=True)
    version_note = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Bookmark(Base):
    """북마크된 공고"""
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(String, nullable=False, unique=True, index=True)
    notice_snapshot = Column(JSON, default={})
    created_at = Column(DateTime, server_default=func.now())


class Profile(Base):
    """기업 프로필 (단일 행 — 항상 id=1)"""
    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, default=1)
    company_name = Column(String, default="아진산업(주)")
    representative = Column(String, default="")
    biz_number = Column(String, default="")
    founded_date = Column(String, default="")
    region = Column(String, default="경남")
    address = Column(String, default="")
    industry = Column(String, default="제조업")
    sub_industry = Column(String, default="자동차 부품")
    employees = Column(String, default="1200")
    revenue_range = Column(String, default="1천억~5천억")
    certifications = Column(JSON, default=[])
    match_keywords = Column(String, default="자동차, 스마트공장, DX, 프레스, 에너지")
    exclude_keywords = Column(String, default="")
    sales = Column(String, default="약 5,000억 원")
    field = Column(String, default="자동차 부품, DX")
    summary = Column(String, default="자동차 차체 부품 및 스마트 팩토리 선도")
    strategy = Column(String, default="미래 모빌리티 전환")
    achievements = Column(String, default="")
    core_tech = Column(String, default="")
    core_team = Column(String, default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AICallLog(Base):
    """LLM 호출 감사 로그 (ai_call_logs 테이블)"""
    __tablename__ = "ai_call_logs"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    run_id            = Column(String, nullable=False)          # 개별 호출 UUID
    request_id        = Column(String, nullable=False, index=True)  # 사용자 요청 묶음 UUID
    task_type         = Column(String, nullable=False, index=True)  # notice_analyst / draft_writer 등
    input_objects     = Column(Text, nullable=True)             # JSON 배열 — 입력 객체 ID 참조
    output_object     = Column(Text, nullable=True)             # 출력 객체 ID
    prompt_version    = Column(String, nullable=True)           # 예: "draft_writer_v1.0"
    model_provider    = Column(String, nullable=True)           # mock / local / openai / anthropic
    model_name        = Column(String, nullable=True)           # 예: "gpt-4o-mini"
    input_hash        = Column(String, nullable=True)           # 입력 SHA256 (중복 탐지)
    input_preview     = Column(Text, nullable=True)             # 입력 앞 500자
    output_json       = Column(Text, nullable=True)             # 파싱된 구조화 출력
    raw_output        = Column(Text, nullable=True)             # LLM 원본 출력
    status            = Column(String, nullable=True, index=True)   # success / parse_error / api_error / timeout
    error_message     = Column(Text, nullable=True)
    duration_ms       = Column(Integer, nullable=True)          # 호출 소요 ms
    token_usage_json  = Column(Text, nullable=True)             # provider 토큰 수 (OpenAI/Anthropic만)
    cost_estimate_krw = Column(Float, nullable=True)            # 추후 단가 매핑 시 채움
    # v0.2 보강 (test_03 §3.7.1, 16 필드 정합) — 마이그레이션 0007에서 ALTER
    data_classification = Column(String, nullable=True)         # PII / PHI / Public / Confidential
    policy_check_result = Column(String, nullable=True)         # passed / failed / skipped (v1.0+)
    created_at        = Column(DateTime, server_default=func.now(), index=True)


# ════════════════════════════════════════════════════════════════════════
# v0.2 신규 SQLAlchemy 모델 (PRD §13.1 11종 + §13.10 운영 보조)
# ════════════════════════════════════════════════════════════════════════


class ApplicationSession(Base):
    """공고 1개 작성 작업 단위 (PRD §13.9). 모든 산출물의 부모."""
    __tablename__ = "application_sessions"

    session_id = Column(String, primary_key=True)            # uuid
    user_id = Column(String, nullable=False, index=True)
    company_profile_id = Column(String, nullable=True)
    notice_file_id = Column(String, nullable=True)
    form_file_id = Column(String, nullable=True)
    reference_file_ids = Column(JSON, default=list)          # list[str]
    selected_company_file_ids = Column(JSON, default=list)   # list[str], CompanyFile 참조

    # status enum 8종 (created | analyzing | analysis_ready | step2_confirmed |
    #                  drafting | completed | abandoned | failed)
    status = Column(String, nullable=False, default="created", index=True)
    current_step = Column(Integer, nullable=False, default=1)  # 1~5

    # 분석 결과 캐시 (v0.2 단순화 — JSON 직렬화. 향후 별도 테이블 분리 검토)
    notice_schema_json = Column(JSON, default={})           # NoticeSchema
    form_schema_json = Column(JSON, default={})             # FormSchema
    company_schema_json = Column(JSON, default={})          # CompanySchema

    drafts_preservation_policy = Column(String, default="user_choice")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_activity_at = Column(DateTime, nullable=True)
    confirmed_step2_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    abandoned_at = Column(DateTime, nullable=True)

    # exported = 이벤트 (status 변경 X, PRD §13.9)
    exported_at = Column(DateTime, nullable=True)
    export_count = Column(Integer, default=0)
    last_export_file_id = Column(String, nullable=True)


class EvidenceItemRow(Base):
    """참고자료 evidence 단일 행 (PRD §13.3).
    EvidenceSchema.items의 각 항목을 별도 테이블로 정규화 (검색·임베딩 효율).
    embedding은 별도 vector store 또는 SQLite blob.
    """
    __tablename__ = "evidence_items"

    evidence_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True)
    source_file = Column(String, nullable=False)
    source_page = Column(Integer, nullable=True)
    source_block = Column(String, nullable=True)
    type = Column(String, default="etc")     # 보유 기술 / 정량 실적 / ...
    content = Column(Text, nullable=False)
    raw_text = Column(Text, nullable=True)
    matched_questions = Column(JSON, default=list)
    confidence_per_question = Column(JSON, default={})
    embedding_blob = Column(Text, nullable=True)   # bge-m3-ko 1024-dim, JSON 직렬화 (v0.3 vector store 분리)
    created_at = Column(DateTime, server_default=func.now())


class MappingResultRow(Base):
    """문항별 Evidence 매핑 (PRD §13.4).
    1 session : N 행 (문항별 1행).
    """
    __tablename__ = "mapping_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True)
    question_id = Column(String, nullable=False, index=True)
    matched_evidence_ids = Column(JSON, default=list)
    used_evidence_ids = Column(JSON, default=list)
    confidence_score = Column(Float, default=0.0)
    missing_evidence_types = Column(JSON, default=list)
    # match_status enum 4종 (auto_confirmed | user_confirmed | awaiting_user_confirm | excluded)
    match_status = Column(String, default="awaiting_user_confirm", index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MissingMaterial(Base):
    """부족자료 상태 관리 (PRD §13.5)."""
    __tablename__ = "missing_materials"

    missing_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True)
    question_id = Column(String, nullable=False, index=True)
    missing_type = Column(String, nullable=False)   # 설문/인터뷰 / 비교표 / 정량 데이터 / ...
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    input_type = Column(String, default="both")     # text / file / both
    # status enum 8종 (open | uploaded | analyzing | matched | resolved |
    #                  deferred | rejected | failed)
    status = Column(String, default="open", index=True)
    supplemental_ids = Column(JSON, default=list)   # SupplementalMaterial.supplemental_id 참조
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SupplementalMaterial(Base):
    """사용자 보완자료 원본 (PRD §13.6)."""
    __tablename__ = "supplemental_materials"

    supplemental_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True)
    question_id = Column(String, nullable=False)
    missing_id = Column(String, ForeignKey("missing_materials.missing_id"), nullable=True)
    type = Column(String, nullable=False)           # text / file
    content = Column(Text, nullable=True)           # type=text일 때
    file_id = Column(String, nullable=True)         # type=file일 때 (storage path 참조)
    evidence_ids = Column(JSON, default=list)       # 변환된 evidence 참조
    # status enum 4종 (uploaded | analyzed | converted | failed)
    status = Column(String, default="uploaded", index=True)
    created_at = Column(DateTime, server_default=func.now())


class FitAnalysis(Base):
    """공고 적합성 3축 (PRD §13.x)."""
    __tablename__ = "fit_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True, unique=True)
    company_profile_id = Column(String, nullable=False)
    axes_json = Column(JSON, default=list)          # FitAxis[] (기술성/사업성/수행역량)
    overall_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EvalCriteriaMapping(Base):
    """평가기준 ↔ 문항 매핑 (PRD §13.8).
    parse-notice = 초기 후보, map-eval-criteria = 재계산·보강 (PRD §16.1).
    """
    __tablename__ = "eval_criteria_mappings"

    criteria_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True)
    criteria_name = Column(String, nullable=False)
    weight = Column(Integer, default=0)
    scope = Column(String, default="section")       # question / section / document
    mapped_questions = Column(JSON, default=list)
    mapping_type = Column(String, default="direct") # direct / indirect / context
    mapped_by = Column(String, default="ai")        # ai / user (v0.2.1+ user 편집)
    confidence = Column(Float, default=0.0)
    reason = Column(Text, nullable=True)
    source_page = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    # v0.2.1 V2 (migration 0005) — 변경 이력 JSON (PRD-13 §19.3 옵션 A)
    history = Column(JSON, default=list)


class DraftItem(Base):
    """문항별 초안 (PRD §13.7).
    기존 Draft 테이블 (drafts, v1)과 별개. v0.2는 ApplicationSession 단위.
    drafts 테이블은 CLAUDE.md §4 보호 정책으로 v0.2.1까지 그대로 유지.
    """
    __tablename__ = "draft_items"

    draft_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("application_sessions.session_id"), nullable=False, index=True)
    question_id = Column(String, nullable=False, index=True)
    content = Column(Text, default="")
    table_data = Column(JSON, default=list)
    used_evidence_ids = Column(JSON, default=list)
    char_count = Column(Integer, default=0)
    # status enum 6종 (draft | generated | user_edited | approved |
    #                  needs_revision | abandoned)
    status = Column(String, default="draft", index=True)
    warnings = Column(JSON, default=list)
    ai_metadata = Column(JSON, default={})          # {model, prompt_version, generated_at}
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── 운영 보조 (PRD §13.10) ─────────────────────────────────────────────


class CompanyFile(Base):
    """기업프로필 자료 영구 메타데이터 (PRD §13.10.1).
    AI ontology 11종과 분리된 운영 보조 entity.
    Step 1에서 직접 업로드 X, 기업설정/기업자료실에서만 관리.
    ApplicationSession.selected_company_file_ids[]에서 본 file_id 참조.

    Phase 4-H A3 (migration 0004): parsed_text + safety cap 메타 추가.
    저장 구조: 메타+parsed_text → SQLite, 원본 BLOB → 디스크.
    """
    __tablename__ = "company_files"

    file_id = Column(String, primary_key=True)
    company_profile_id = Column(String, nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_size_bytes = Column(Integer, default=0)
    file_storage_path = Column(String, nullable=True)
    file_type = Column(String, default="기타")     # 회사소개서 / 재무제표 / 사업자등록증 / 인증서 / 특허 / 실적 / 기타
    uploaded_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    uploaded_by = Column(String, nullable=True)
    # status enum (active | expired | review_needed | archived)
    status = Column(String, default="active", index=True)
    expires_at = Column(DateTime, nullable=True)
    tags = Column(JSON, default=list)

    # Phase 4-H A3 (migration 0004) — parsed_text + safety cap 메타
    ext = Column(String, default="")
    parsed_text = Column(Text, default="")              # ≤200K (A1 safety cap 정합)
    char_count = Column(Integer, default=0)
    parsed_text_stored_char_count = Column(Integer, default=0)
    parsed_text_truncated = Column(Boolean, default=False)
    parse_success = Column(Boolean, default=True)
    warning = Column(String, nullable=True)
