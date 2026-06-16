"""
v0.2 분석 API (PRD §16) — /api/analysis/*

Phase 4-C: 분석 7 endpoint (parse-notice / parse-form / extract-evidence /
                              analyze-company / map-evidence / check-missing /
                              map-eval-criteria)
Phase 4-D: 부족자료 4 + 재분석 1 endpoint
  - POST /api/analysis/missing/text          — 직접 입력 (SupplementalMaterial type=text)
  - POST /api/analysis/missing/upload        — 파일 업로드 단일 (type=file)
  - POST /api/analysis/missing/bulk-upload   — 일괄 업로드 + AI 자동 분류
  - POST /api/analysis/missing/confirm       — 매칭 결과 확정 (맞음/다른 항목/제외)
  - POST /api/analysis/reanalyze             — 범위별 재분석 (target enum)

각 endpoint:
  - Provider (mock/anthropic/hybrid) 자동 분기 (AI_PROVIDER 환경변수)
  - audit_log 자동 기록 (provider 메서드 @audit_log 데코레이터)
  - 실패 시 Failure Protocol retry (test_03 §3.7.2)

ApplicationSession 연계 (PRD §13.9):
  - request_id / session_id 함께 전달
  - DB 통합은 Phase 4-G 시점 (frontend → 실제 API 교체와 함께)
"""
import copy
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from database import get_db
from models import AICallLog, ApplicationSession, EvalCriteriaMapping
from routers.files import parse_upload_bytes
from services.ai_provider import get_provider

logger = logging.getLogger(__name__)

# A-1.5 (P-5): layout-aware text 크기 상한 — PARSED_TEXT_SAFETY_CAP(files.py)과 분리
FORM_LAYOUT_TEXT_SAFETY_CAP = 200_000  # chars

# A-4-4 (b4-8.md §3.10): table_normalizer / table_promoter feature flag
FORM_NORMALIZE_TABLE = os.getenv("FORM_NORMALIZE_TABLE", "true").lower() == "true"
FORM_AUTO_PROMOTE_TABLE = os.getenv("FORM_AUTO_PROMOTE_TABLE", "true").lower() == "true"

# C-2 (b8.md §3): step2_confirmed gate precheck 예외 토글
# production은 false 고정. 개발/테스트 시 true로 precheck 모드 활성화.
ALLOW_PRECONFIRM_PRECHECK = os.getenv("ALLOW_PRECONFIRM_PRECHECK", "false").lower() == "true"

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ─── Request 모델 ──────────────────────────────────────────────────────


class ParseNoticeRequest(BaseModel):
    notice_text: str
    request_id: str = ""
    session_id: str = ""


class ParseFormRequest(BaseModel):
    form_text: str
    form_name: str = ""
    request_id: str = ""
    session_id: str = ""
    # 2026-05-18: parser_mode 선택
    #   "single" (default) = 기존 단일 호출 (mini 1회, ~3원, ~65초)
    #   "hybrid"           = regex chapter detect + chunk별 병렬 호출 (mini N회, ~3*N원, 병렬로 더 빠를 수 있음)
    parser_mode: Literal["single", "hybrid"] = "single"


class ExtractEvidenceRequest(BaseModel):
    ref_text: str
    source_file: str = ""
    source_page: int = 0
    request_id: str = ""
    session_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


class AnalyzeCompanyRequest(BaseModel):
    company_files: List[Dict[str, Any]] = []
    notice_schema: Dict[str, Any] = {}
    request_id: str = ""
    session_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


class MapEvidenceRequest(BaseModel):
    form_schema: Dict[str, Any]
    evidence_list: List[Dict[str, Any]] = []
    notice_schema: Dict[str, Any] = {}
    matching_threshold: float = 0.70
    request_id: str = ""
    session_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


class CheckMissingRequest(BaseModel):
    mapping_result: Dict[str, Any]
    request_id: str = ""
    session_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


class MapEvalCriteriaRequest(BaseModel):
    """parse-notice 다음 단계: FormSchema 확정 후 평가기준 ↔ 문항 매핑 재계산.
    PRD §16.1 책임 분리 정책.
    """
    notice_schema: Dict[str, Any]
    form_schema: Dict[str, Any]
    request_id: str = ""
    session_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


# ════════════════════════════════════════════════════════════════════════
# Phase 4-G-0.5: Session 생성 API (PRD §13.9 ApplicationSession)
#   POST /api/analysis/sessions — DB ApplicationSession row 생성
#
# 결정:
#   - status 초기값 = "created" (8-status enum 첫 단계)
#   - user_id 기본 = "anonymous" (auth 미구현, 추후 middleware에서 주입)
#   - notice_id는 notice_schema_json에 보존 (parse-notice 시 병합)
# ════════════════════════════════════════════════════════════════════════


class CreateSessionRequest(BaseModel):
    user_id: str = "anonymous"
    # notice_id: 현재 DB 계약(Notice.id = String PK, "{origin}-{title}-{period}" 합성)에 맞춰 str.
    # 후속 부채: TODO_polish.md "ID-M1 — Notice Identifier Contract 정리" (v1.1+).
    notice_id: Optional[str] = None
    notice_snapshot: Optional[Dict[str, Any]] = None
    initial_step: int = 1


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """ApplicationSession 생성 (PRD §13.9).

    Step 1 진입 후 Step 2로 넘어가기 전 호출.
    이후 모든 analysis API는 반환된 session_id 사용.

    notice_id / notice_snapshot은 notice_schema_json에 저장.
    parse-notice 실행 시 같은 필드에 NoticeSchema 병합 (notice_id 보존).
    """
    session_id = uuid.uuid4().hex

    notice_payload: Dict[str, Any] = {}
    if req.notice_id is not None:
        notice_payload["notice_id"] = req.notice_id
    if req.notice_snapshot:
        notice_payload["snapshot"] = req.notice_snapshot

    session = ApplicationSession(
        session_id=session_id,
        user_id=req.user_id,
        status="created",
        current_step=req.initial_step,
        notice_schema_json=notice_payload,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.session_id,
        "status": session.status,
        "current_step": session.current_step,
        "user_id": session.user_id,
        "notice_id": req.notice_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """ApplicationSession soft delete — status='abandoned' 변경 (사이드바 X 버튼)."""
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    session.status = "abandoned"
    session.abandoned_at = datetime.utcnow()
    db.commit()
    return {"session_id": session_id, "status": "abandoned", "deleted": True}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """ApplicationSession 단일 조회 (PRD §13.9).

    용도:
      - 새로고침 시 frontend status 복원
      - "기존 세션 이어가기" UI 진입 (Notice:Session = 1:N)
      - status 전이 추적
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        return {"error": "session not found", "session_id": session_id}

    # 2026-05-18 C-단계: form_schema에 parser hint 자동 주입 (자동 변환 X, hint만).
    # frontend 트리가 "💡 표 가능성" 등 표시 → 사용자가 ✏️로 수정 결정.
    from services.form_parser_postprocessor import annotate_form_schema
    fsj_raw = dict(session.form_schema_json or {})
    for schema_key in ("schema", "confirmed_schema"):
        if isinstance(fsj_raw.get(schema_key), dict):
            try:
                fsj_raw[schema_key] = annotate_form_schema(fsj_raw[schema_key])
            except Exception as e:
                logger.warning("[parser_hints] annotate 실패 %s: %s", schema_key, e)

    # 2026-05-18: excluded_question_ids 최상위로 promote (frontend가 한 곳에서 접근)
    # PATCH 액션이 schema.excluded_question_ids에 저장하지만 frontend는 confirmed_schema 우선 → 누락 방지
    _schema_excl = (fsj_raw.get("schema") or {}).get("excluded_question_ids") or []
    _confirmed_excl = (fsj_raw.get("confirmed_schema") or {}).get("excluded_question_ids") or []
    _top_excl = fsj_raw.get("excluded_question_ids") or []
    merged_excl = list(set(_schema_excl) | set(_confirmed_excl) | set(_top_excl))
    fsj_raw["excluded_question_ids"] = merged_excl
    # 양쪽 schema에도 동일하게 복사 (frontend가 어느 schema 보든 동일)
    for schema_key in ("schema", "confirmed_schema"):
        if isinstance(fsj_raw.get(schema_key), dict):
            fsj_raw[schema_key]["excluded_question_ids"] = merged_excl

    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "status": session.status,
        "current_step": session.current_step,
        "notice_schema_json": session.notice_schema_json or {},
        "form_schema_json": fsj_raw,
        "company_schema_json": session.company_schema_json or {},
        "drafts_preservation_policy": session.drafts_preservation_policy,
        # C-1 (b7.md §4-3): reference / selected_company file_ids 응답 확장
        "reference_file_ids": session.reference_file_ids
            if isinstance(session.reference_file_ids, list) else [],
        "selected_company_file_ids": session.selected_company_file_ids
            if isinstance(session.selected_company_file_ids, list) else [],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
        "confirmed_step2_at": session.confirmed_step2_at.isoformat() if session.confirmed_step2_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "exported_at": session.exported_at.isoformat() if session.exported_at else None,
        "export_count": session.export_count or 0,
    }


# ════════════════════════════════════════════════════════════════════════
# Part B-2 (b6.md): Step 3 진입 게이트 + confirmed_schema 재조회
#   GET /api/analysis/sessions/{session_id}/step3-ready
#
# 책임:
#   1. B-1에서 저장한 confirmed_schema 안정적 재조회
#   2. step3_ready=true/false 판단 (8조건)
#   3. parser_metadata + quality_metrics 보존 반환
#
# 정책:
#   - session_not_found → 404 + ok=false + reason
#   - 그 외 사유 → 200 + ok=false + reason
#   - table_count 기준 = fill_mode == "table_input" 단독 (B-1과 다름, b6.md §3)
#   - quality_metrics는 top-level로도 복사 (parser_metadata 내부 보존)
# ════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════
# Part C-2 (b8.md): step2_confirmed gate helper
#
# 정책:
#   - session.status == "step2_confirmed" → 통과
#   - 그 외 → HTTP 409 (ok=false, reason=step2_not_confirmed)
#   - precheck 예외: allow_preconfirm=True AND ALLOW_PRECONFIRM_PRECHECK=true → 통과
#   - production은 ALLOW_PRECONFIRM_PRECHECK=false 고정 (precheck 비활성)
# ════════════════════════════════════════════════════════════════════════


def _require_step2_confirmed(
    session: ApplicationSession,
    allow_preconfirm: bool = False,
) -> None:
    """C-2 step2_confirmed gate (b8.md §3).

    Raises HTTPException(409) if gate fails.
    """
    if session.status == "step2_confirmed":
        return
    if allow_preconfirm and ALLOW_PRECONFIRM_PRECHECK:
        return  # precheck 모드 통과
    raise HTTPException(
        status_code=409,
        detail={
            "ok": False,
            "session_id": session.session_id,
            "session_status": session.status,
            "reason": "step2_not_confirmed",
            "detail": "step2_confirmed 상태가 아닙니다. confirm-step2 호출 후 재시도하세요.",
        },
    )


def _resolve_session_for_gate(
    db: Session, session_id: str,
) -> ApplicationSession:
    """gate 적용 endpoint 공통 — session_id 검증 + DB 조회.

    - session_id 빈 문자열 → 422
    - session not found → 404
    """
    if not session_id:
        raise HTTPException(
            status_code=422,
            detail="session_id is required",
        )
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"session not found: {session_id}",
        )
    return session


def _count_step3_schema(confirmed_schema: Dict[str, Any]) -> Dict[str, int]:
    """confirmed_schema의 section/question/table 수 집계 (b6.md §3).

    table_count 기준: fill_mode == "table_input" 단독 (is_table_item 미사용).
    """
    sections = confirmed_schema.get("sections", []) or []
    all_questions = [q for s in sections for q in (s.get("questions", []) or [])]
    return {
        "section_count": len(sections),
        "question_count": len(all_questions),
        "table_count": sum(
            1 for q in all_questions if q.get("fill_mode") == "table_input"
        ),
    }


def _evaluate_step3_ready(
    session: ApplicationSession,
) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """B-2 §2-2 판단 — step3 진입 가능 여부 + reason + confirmed_schema 반환.

    B-2 endpoint와 B-3 endpoint가 공통으로 사용 (b6_b3.md §2-2 재사용).
    session 존재 검증은 호출자가 사전 처리 (404은 호출자 책임).

    Returns:
      (is_ready, reason_if_not_ready, confirmed_schema_if_ready)
    """
    is_step2_confirmed = (
        session.status == "step2_confirmed"
        and (session.current_step or 0) >= 3
        and session.confirmed_step2_at is not None
    )
    if not is_step2_confirmed:
        return False, "step2_not_confirmed", None

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}

    if fsj.get("schema_status") != "confirmed":
        return False, "schema_status_not_confirmed", None

    confirmed_schema = fsj.get("confirmed_schema")
    if not confirmed_schema or not isinstance(confirmed_schema, dict):
        return False, "confirmed_schema_missing", None

    sections = confirmed_schema.get("sections", []) or []
    all_questions = [q for s in sections for q in (s.get("questions", []) or [])]
    if not sections or len(all_questions) < 1:
        return False, "confirmed_schema_empty", None

    return True, None, confirmed_schema


# ════════════════════════════════════════════════════════════════════════
# Part C-1.5 (v3.2): announcement_signals 정규화
#   POST /api/analysis/sessions/{session_id}/announcement-signals/normalize
#
# 책임: notice_schema_json["schema"] → form_schema_json["announcement_signals"]
#   6 슬롯: criteria / bonuses / preferences / eligibility /
#           emphasis_keywords / compliance_constraints
# strength 정책: 사용자 확정안 (3-case criteria + importance fallback)
# 금지: default rubric 생성 (C-1.6 범위) / Evidence Mapping / Draft Writer / Evaluator
# ════════════════════════════════════════════════════════════════════════


def _clamp_strength(value: float) -> float:
    """strength 범위 [0.0, 1.0] 안전망 (Q4 사용자 정책)."""
    return max(0.0, min(1.0, value))


# importance fallback 테이블 (Q4 사용자 정책)
_IMPORTANCE_BONUS = {"high": 0.9, "medium": 0.7, "low": 0.5}
_IMPORTANCE_PREFERENCE = {"high": 0.5, "medium": 0.4, "low": 0.3}
_IMPORTANCE_KEYWORD = {"high": 0.3, "medium": 0.2, "low": 0.1}


def _extract_bonus_points(item: dict) -> Optional[float]:
    """extras item에서 가점 점수(N점) 추출. 실패 시 None."""
    import re
    for key in ("value", "label"):
        text = str(item.get(key) or "")
        m = re.search(r"(\d+(?:\.\d+)?)\s*점", text)
        if m:
            try:
                return float(m.group(1))
            except (TypeError, ValueError):
                pass
    return None


def _criteria_strength(item: dict, criteria_list: list) -> float:
    """criteria strength 3-case (Q4 사용자 확정안):
      case 1: total_positive_weight = 0 → 0.6 (정성)
      case 2: weight > 0 AND total > 0 → weight / total_positive_weight
      case 3: weight 누락/0 AND total > 0 → 0.2 (과대 반영 방지)
    """
    positive_weights = [
        (c.get("weight") or 0)
        for c in criteria_list
        if (c.get("weight") or 0) > 0
    ]
    total_positive_weight = sum(positive_weights)
    weight = item.get("weight") or 0

    if total_positive_weight <= 0:
        return 0.6
    if weight > 0:
        return _clamp_strength(weight / total_positive_weight)
    return 0.2


def _bonus_strength(item: dict) -> float:
    """bonus strength: 점수 추출 → max(0.5, min(p/5, 1.0)). 실패 시 importance fallback."""
    points = _extract_bonus_points(item)
    if points is not None:
        return _clamp_strength(max(0.5, min(points / 5.0, 1.0)))
    importance = (item.get("importance") or "unknown").lower()
    return _clamp_strength(_IMPORTANCE_BONUS.get(importance, 0.5))


def _preference_strength(item: dict) -> float:
    """preference strength: importance 기반 (high:0.5/medium:0.4/low:0.3/unknown:0.3)."""
    importance = (item.get("importance") or "unknown").lower()
    return _clamp_strength(_IMPORTANCE_PREFERENCE.get(importance, 0.3))


def _emphasis_keyword_strength(item: dict) -> float:
    """emphasis_keyword strength: importance 기반 (high:0.3/medium:0.2/low:0.1/unknown:0.1)."""
    importance = (item.get("importance") or "unknown").lower()
    return _clamp_strength(_IMPORTANCE_KEYWORD.get(importance, 0.1))


def _extras_by_category(extras: list, category: str) -> list:
    """extras 중 특정 category 항목만 필터링."""
    out = []
    for ex in (extras or []):
        if not isinstance(ex, dict):
            continue
        if ex.get("category") == category:
            out.append(ex)
    return out


def _enrich_criteria_with_extras(criteria_item: dict, extras: list) -> dict:
    """criteria(name/weight/scope)에 extras의 같은 name 매칭 보강 시도 (Q3).

    extras에 같은 label로 매칭되는 항목 있으면 source_page/source_quote/confidence 보강.
    매칭 없으면 빈 값.
    """
    name = (criteria_item.get("name") or "").strip()
    matched = None
    for ex in (extras or []):
        if not isinstance(ex, dict):
            continue
        label = (ex.get("label") or "").strip()
        if name and (label == name or name in label or label in name):
            matched = ex
            break
    return {
        "source_page": (matched.get("source_page") if matched else None),
        "quote": (matched.get("source_quote") if matched else ""),
        "confidence": (matched.get("confidence") if matched else None),
    }


def _extract_announcement_signals(
    notice_schema: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """notice schema → announcement_signals 정규화 (6 슬롯).

    Returns:
        {
            "criteria": [...], "bonuses": [...], "preferences": [...],
            "eligibility": [...], "emphasis_keywords": [...],
            "compliance_constraints": [...],
            "source": "notice_analysis",
            "status": "normalized" | "empty" | "no_signals_found",
        }
    """
    # None 또는 dict 아님 → empty (분석 결과 자체가 없음)
    # 빈 dict는 통과 → 슬롯 추출 시도 (모두 빈이면 no_signals_found)
    if notice_schema is None or not isinstance(notice_schema, dict):
        return _empty_signals(status="empty")

    extras = notice_schema.get("extras") or []
    eval_criteria_raw = notice_schema.get("evaluation_criteria") or []

    # 1. criteria
    criteria = []
    for c in eval_criteria_raw:
        if not isinstance(c, dict):
            continue
        enrichment = _enrich_criteria_with_extras(c, extras)
        criteria.append({
            "name": c.get("name") or "",
            "weight": c.get("weight"),
            "scope": c.get("scope") or "section",
            "source_page": enrichment["source_page"],
            "quote": enrichment["quote"],
            "confidence": enrichment["confidence"],
            "strength": _criteria_strength(c, eval_criteria_raw),
        })

    # 2. bonuses (extras category="가점")
    bonuses = []
    for ex in _extras_by_category(extras, "가점"):
        bonuses.append({
            "name": ex.get("label") or "",
            "value": ex.get("value"),
            "source_page": ex.get("source_page"),
            "quote": ex.get("source_quote") or "",
            "confidence": ex.get("confidence"),
            "importance": ex.get("importance"),
            "strength": _bonus_strength(ex),
        })

    # 3. preferences (extras category="우대")
    preferences = []
    for ex in _extras_by_category(extras, "우대"):
        preferences.append({
            "name": ex.get("label") or "",
            "value": ex.get("value"),
            "source_page": ex.get("source_page"),
            "quote": ex.get("source_quote") or "",
            "confidence": ex.get("confidence"),
            "importance": ex.get("importance"),
            "strength": _preference_strength(ex),
        })

    # 4. eligibility (target + exclusion_conditions + extras "자격"/"제외")
    eligibility = []
    target = notice_schema.get("target")
    if target:
        eligibility.append({
            "name": "대상",
            "value": target,
            "kind": "target",
            "strength": 1.0,
        })
    for cond in (notice_schema.get("exclusion_conditions") or []):
        if cond:
            eligibility.append({
                "name": "제외 조건",
                "value": cond,
                "kind": "exclusion",
                "strength": 1.0,
            })
    for ex in _extras_by_category(extras, "자격"):
        eligibility.append({
            "name": ex.get("label") or "",
            "value": ex.get("value"),
            "source_page": ex.get("source_page"),
            "quote": ex.get("source_quote") or "",
            "kind": "extras",
            "strength": 1.0,
        })

    # 5. emphasis_keywords (important_keywords + extras "강조")
    emphasis_keywords = []
    for kw in (notice_schema.get("important_keywords") or []):
        if kw:
            emphasis_keywords.append({
                "keyword": kw,
                "source": "important_keywords",
                "importance": "unknown",
                "strength": _emphasis_keyword_strength({"importance": "unknown"}),
            })
    for ex in _extras_by_category(extras, "강조"):
        emphasis_keywords.append({
            "keyword": ex.get("label") or "",
            "value": ex.get("value"),
            "source": "extras",
            "importance": ex.get("importance"),
            "strength": _emphasis_keyword_strength(ex),
        })

    # 6. compliance_constraints (required_documents + deadline + submission_system + extras "제출"/"형식")
    compliance_constraints = []
    for doc in (notice_schema.get("required_documents") or []):
        if doc:
            compliance_constraints.append({
                "kind": "required_document",
                "value": doc,
            })
    deadline = notice_schema.get("deadline")
    if deadline:
        compliance_constraints.append({
            "kind": "deadline",
            "value": deadline,
        })
    submission = notice_schema.get("submission_system")
    if submission:
        compliance_constraints.append({
            "kind": "submission_system",
            "value": submission,
        })
    for ex in (_extras_by_category(extras, "제출")
               + _extras_by_category(extras, "형식")):
        compliance_constraints.append({
            "kind": "extras",
            "name": ex.get("label") or "",
            "value": ex.get("value"),
            "source_page": ex.get("source_page"),
            "quote": ex.get("source_quote") or "",
        })

    # status 판정
    all_slots = (
        criteria + bonuses + preferences + eligibility
        + emphasis_keywords + compliance_constraints
    )
    status = "normalized" if all_slots else "no_signals_found"

    return {
        "criteria": criteria,
        "bonuses": bonuses,
        "preferences": preferences,
        "eligibility": eligibility,
        "emphasis_keywords": emphasis_keywords,
        "compliance_constraints": compliance_constraints,
        "source": "notice_analysis",
        "status": status,
    }


def _empty_signals(status: str) -> Dict[str, Any]:
    """빈 announcement_signals 구조 (status=empty or no_signals_found)."""
    return {
        "criteria": [],
        "bonuses": [],
        "preferences": [],
        "eligibility": [],
        "emphasis_keywords": [],
        "compliance_constraints": [],
        "source": "notice_analysis",
        "status": status,
    }


@router.post("/sessions/{session_id}/announcement-signals/normalize")
async def normalize_announcement_signals(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """C-1.5: notice 분석 결과 → form_schema_json["announcement_signals"] 정규화.

    응답 정책:
      - session_not_found → 404
      - notice_schema 없음 → 200 + status=empty
      - notice 있으나 모든 슬롯 빈 → 200 + status=no_signals_found
      - 정상 → 200 + status=normalized + announcement_signals 본문
    """
    session = _resolve_session_for_gate(db, session_id)

    nsj = session.notice_schema_json or {}
    notice_schema = nsj.get("schema") if isinstance(nsj, dict) else None

    now_iso = datetime.utcnow().isoformat()
    if not notice_schema:
        signals = _empty_signals(status="empty")
    else:
        signals = _extract_announcement_signals(notice_schema)

    signals["created_at"] = signals.get("created_at") or now_iso
    signals["updated_at"] = now_iso

    # form_schema_json["announcement_signals"]에 저장 (Q1 발주 명시)
    fsj = dict(session.form_schema_json or {})
    # 기존 created_at 보존 (재호출 시)
    existing = fsj.get("announcement_signals")
    if isinstance(existing, dict) and existing.get("created_at"):
        signals["created_at"] = existing["created_at"]
    fsj["announcement_signals"] = signals
    session.form_schema_json = fsj
    flag_modified(session, "form_schema_json")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[normalize_announcement_signals] DB commit 실패 session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"DB commit 실패: {e}")

    return {
        "ok": True,
        "session_id": session.session_id,
        "status": signals["status"],
        "announcement_signals": signals,
        "criteria_count": len(signals["criteria"]),
        "bonuses_count": len(signals["bonuses"]),
        "preferences_count": len(signals["preferences"]),
        "eligibility_count": len(signals["eligibility"]),
        "emphasis_keywords_count": len(signals["emphasis_keywords"]),
        "compliance_constraints_count": len(signals["compliance_constraints"]),
    }


# ════════════════════════════════════════════════════════════════════════
# Part C-1.6 (v3.2): evaluation_rubric resolver
#   POST /api/analysis/sessions/{session_id}/evaluation-rubric/resolve
#
# 책임: Source of Truth 우선순위로 evaluation_rubric 확정
#   1. announcement_signals.criteria 있음 → source="announcement"
#   2. criteria 없음 + 사업 유형 감지 → source="default_template"
#   3. 유형 불명확 → source="general"
# 저장: session.form_schema_json["evaluation_rubric"]
# ════════════════════════════════════════════════════════════════════════


@router.post("/sessions/{session_id}/evaluation-rubric/resolve")
async def resolve_evaluation_rubric_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """C-1.6: evaluation_rubric 확정 (작성/평가 기준 일치)."""
    from services.rubric_resolver import resolve_evaluation_rubric

    session = _resolve_session_for_gate(db, session_id)

    nsj = session.notice_schema_json or {}
    fsj = session.form_schema_json or {}
    notice_schema = nsj.get("schema") if isinstance(nsj, dict) else None
    confirmed_schema = fsj.get("confirmed_schema") if isinstance(fsj, dict) else None
    announcement_signals = (
        fsj.get("announcement_signals") if isinstance(fsj, dict) else None
    )

    rubric = resolve_evaluation_rubric(
        notice_schema, confirmed_schema, announcement_signals
    )
    rubric["resolved_at"] = datetime.utcnow().isoformat()

    new_fsj = dict(fsj or {})
    new_fsj["evaluation_rubric"] = rubric
    session.form_schema_json = new_fsj
    flag_modified(session, "form_schema_json")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[resolve_evaluation_rubric] DB commit 실패 session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"DB commit 실패: {e}")

    return {
        "ok": True,
        "session_id": session.session_id,
        "source": rubric["source"],
        "template_type": rubric["template_type"],
        "axes_count": len(rubric["axes"]),
        "scored_axes_count": sum(1 for a in rubric["axes"] if a.get("is_scored")),
        "total_weight": round(
            sum(a["weight"] for a in rubric["axes"] if a.get("is_scored")), 6
        ),
        "evaluation_rubric": rubric,
    }


# ════════════════════════════════════════════════════════════════════════
# Part C-3 (v3.2 c-3): BackgroundTasks mapping pipeline
#   POST /api/analysis/run-step2-mapping     — 즉시 running 반환, 5단계 비동기 실행
#   POST /api/analysis/retry-step2-mapping   — done 단계 skip, failed_step부터 재실행
#
# 사용자 보강 7건 반영:
#   #1 status="running"이면 중복 task 차단
#   #2 C-2 _require_step2_confirmed gate 재사용 (run/retry 둘 다)
#   #3 retry는 done 단계 skip, failed_step부터
#   #4 BackgroundTask 내부에서 새 DB session (mapping_pipeline.run_mapping_pipeline)
#   #5 announcement_signals + evaluation_rubric을 context에 포함
#   #6 frontend polling 미구현
#   #7 Evidence Mapping 고도화 / RAG / draft_writer / evaluator / migration 금지
# ════════════════════════════════════════════════════════════════════════


class RunStep2MappingRequest(BaseModel):
    """C-3 run-step2-mapping 요청."""
    session_id: str
    request_id: str = ""


class RetryStep2MappingRequest(BaseModel):
    """C-3 retry-step2-mapping 요청."""
    session_id: str
    request_id: str = ""


@router.post("/run-step2-mapping")
async def run_step2_mapping(
    req: RunStep2MappingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """C-3: mapping pipeline 비동기 시작 (5단계).

    응답: 즉시 status="running" 반환. BackgroundTask가 5단계 순차 실행.
    """
    from services.mapping_pipeline import init_mapping_pipeline, run_mapping_pipeline

    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session)  # 보강 #2

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    pipeline = fsj.get("mapping_pipeline") or {}
    if not isinstance(pipeline, dict):
        pipeline = {}

    # 보강 #1: status="running" 이면 새 task 만들지 않음
    if pipeline.get("status") == "running":
        return {
            "ok": True,
            "status": "running",
            "session_id": session.session_id,
            "mapping_pipeline": pipeline,
            "note": "이미 running 중. 새 BackgroundTask 시작 안 함.",
        }

    now_iso = datetime.utcnow().isoformat()
    initial = init_mapping_pipeline(now_iso)

    new_fsj = dict(fsj)
    new_fsj["mapping_pipeline"] = initial
    session.form_schema_json = new_fsj
    flag_modified(session, "form_schema_json")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[run_step2_mapping] DB commit 실패 session=%s", req.session_id)
        raise HTTPException(status_code=500, detail=f"DB commit 실패: {e}")

    # BackgroundTask 내부에서 새 SessionLocal() 사용 (보강 #4)
    background_tasks.add_task(run_mapping_pipeline, session.session_id, None)

    return {
        "ok": True,
        "status": "running",
        "session_id": session.session_id,
        "mapping_pipeline": initial,
    }


@router.post("/retry-step2-mapping")
async def retry_step2_mapping(
    req: RetryStep2MappingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """C-3: failed pipeline 재실행 — done 단계 skip, failed_step부터 (보강 #3)."""
    from services.mapping_pipeline import run_mapping_pipeline

    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session)  # 보강 #2

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    pipeline = fsj.get("mapping_pipeline") or {}
    if not isinstance(pipeline, dict) or not pipeline:
        raise HTTPException(
            status_code=422,
            detail="mapping_pipeline이 없습니다. run-step2-mapping을 먼저 호출하세요.",
        )

    # 보강 #1: 이미 running 중이면 새 task 만들지 않음
    if pipeline.get("status") == "running":
        return {
            "ok": True,
            "status": "running",
            "session_id": session.session_id,
            "mapping_pipeline": pipeline,
            "note": "이미 running 중. retry 무시.",
        }

    # Q4 권장: success 상태는 422 거부 (재실행은 run-step2-mapping)
    if pipeline.get("status") == "success":
        raise HTTPException(
            status_code=422,
            detail="이미 success 상태. 재실행하려면 run-step2-mapping을 사용하세요.",
        )

    # failed_step부터 재실행 (None이면 처음부터)
    start_from = pipeline.get("failed_step")

    # status reset (running, error_message/failed_step 초기화)
    new_pipeline = dict(pipeline)
    new_pipeline["status"] = "running"
    new_pipeline["error_message"] = None
    new_pipeline["failed_step"] = None
    new_pipeline["completed_at"] = None

    new_fsj = dict(fsj)
    new_fsj["mapping_pipeline"] = new_pipeline
    session.form_schema_json = new_fsj
    flag_modified(session, "form_schema_json")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[retry_step2_mapping] DB commit 실패 session=%s", req.session_id)
        raise HTTPException(status_code=500, detail=f"DB commit 실패: {e}")

    background_tasks.add_task(run_mapping_pipeline, session.session_id, start_from)

    return {
        "ok": True,
        "status": "running",
        "session_id": session.session_id,
        "retry_from_step": start_from,
        "mapping_pipeline": new_pipeline,
    }


@router.get("/sessions/{session_id}/step3-ready")
async def get_session_step3_ready(
    session_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Step 3 진입 게이트 + confirmed_schema 재조회 (b6.md §2-1, §2-2).

    응답 정책:
      - session_not_found → 404 (HTTPException)
      - 그 외 reason → 200 + ok=false + reason
      - 정상 ready → 200 + ok=true + 전체 정보
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        # b6.md 정책: session_not_found는 404 + ok=false + reason
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "session_id": session_id,
                "step3_ready": False,
                "reason": "session_not_found",
            },
        )

    # B-3에서 helper 추출 — 동일 판단 로직을 _evaluate_step3_ready로 단일화
    is_ready, reason, confirmed_schema = _evaluate_step3_ready(session)
    if not is_ready:
        return {
            "ok": False,
            "session_id": session_id,
            "step3_ready": False,
            "reason": reason,
        }

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}

    # counts 계산 (confirmed_schema는 _evaluate_step3_ready가 반환)
    counts = _count_step3_schema(confirmed_schema)

    # parser_metadata + quality_metrics 추출 (top-level 복사, 원본 보존)
    parser_metadata = fsj.get("parser_metadata") or {}
    if not isinstance(parser_metadata, dict):
        parser_metadata = {}
    # quality_metrics는 parser_metadata 안에 nested되어 있음 → top-level로 복사
    quality_metrics = parser_metadata.get("quality_metrics") or {}
    if not isinstance(quality_metrics, dict):
        quality_metrics = {}

    return {
        "ok": True,
        "session_id": session.session_id,
        "session_status": session.status,
        "current_step": session.current_step,
        "step3_ready": True,
        "schema_status": fsj.get("schema_status"),
        "confirmed_at": fsj.get("confirmed_at"),
        "confirmed_step2_at": (
            session.confirmed_step2_at.isoformat()
            if session.confirmed_step2_at else None
        ),
        "confirmed_schema": confirmed_schema,
        "confirmed_schema_question_count": counts["question_count"],
        "confirmed_schema_section_count": counts["section_count"],
        "confirmed_schema_table_count": counts["table_count"],
        "parser_metadata": parser_metadata,
        "quality_metrics": quality_metrics,
        "next_step": "step3_draft",
    }


# ════════════════════════════════════════════════════════════════════════
# Part C-4 (v3.2 c-4): mapping result readiness / status
#   GET /api/analysis/sessions/{session_id}/mapping-status
#
# 책임: C-3 pipeline 결과 + form_schema_json 데이터 존재 여부 응답.
# 정책 (사용자 보강):
#   - C-2 gate 미적용 (GET, step2 확정 전에도 조회 가능)
#   - session 없음만 404, 그 외 200 + mapping_ready=false
#   - not_ready_reasons 10종 enum
#   - missing_material_exists는 빈 list도 true (유효 결과)
# ════════════════════════════════════════════════════════════════════════


@router.get("/sessions/{session_id}/mapping-status")
async def get_mapping_status(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """C-4: mapping pipeline 결과 재조회 + readiness 판정."""
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"session not found: {session_id}",
        )

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    pipeline = fsj.get("mapping_pipeline") or {}
    if not isinstance(pipeline, dict):
        pipeline = {}
    results = pipeline.get("results") or {}
    if not isinstance(results, dict):
        results = {}

    # *_exists 5종
    company_analysis_exists = results.get("analyze_company") is not None
    evidence_exists = bool(results.get("extract_evidence"))
    mapping_result_exists = bool(results.get("map_evidence"))
    # missing_material_exists: 빈 list도 true (유효 결과)
    missing_material_exists = results.get("check_missing") is not None

    rubric = fsj.get("evaluation_rubric")
    evaluation_rubric_exists = (
        isinstance(rubric, dict)
        and bool(rubric.get("axes"))
    )

    # readiness 판정 + not_ready_reasons 10종 enum
    not_ready_reasons: List[str] = []

    if not pipeline:
        not_ready_reasons.append("pipeline_missing")
    else:
        status = pipeline.get("status")
        if status == "running":
            not_ready_reasons.append("pipeline_status_running")
        elif status == "failed":
            not_ready_reasons.append("pipeline_status_failed")
        # status가 success도 아니고 위 둘도 아니면 pipeline_missing 또는 unknown

    if not fsj.get("confirmed_schema"):
        not_ready_reasons.append("confirmed_schema_missing")
    if not fsj.get("draft_items"):
        not_ready_reasons.append("draft_items_missing")
    if not evaluation_rubric_exists:
        not_ready_reasons.append("evaluation_rubric_missing")

    # pipeline.status=success일 때만 results 5종 체크 (run 안 했으면 보고 불필요)
    if pipeline.get("status") == "success":
        if not company_analysis_exists:
            not_ready_reasons.append("company_analysis_missing")
        if not evidence_exists:
            not_ready_reasons.append("evidence_missing")
        if not mapping_result_exists:
            not_ready_reasons.append("mapping_result_missing")
        if not missing_material_exists:
            not_ready_reasons.append("check_missing_not_completed")

    mapping_ready = len(not_ready_reasons) == 0

    return {
        "ok": True,
        "session_id": session_id,
        "mapping_ready": mapping_ready,
        "mapping_pipeline": pipeline,
        "company_analysis_exists": company_analysis_exists,
        "evidence_exists": evidence_exists,
        "mapping_result_exists": mapping_result_exists,
        "missing_material_exists": missing_material_exists,
        "evaluation_rubric_exists": evaluation_rubric_exists,
        "not_ready_reasons": not_ready_reasons,
        "next_step": "step3_draft_write" if mapping_ready else "wait_for_mapping",
    }


@router.get("/sessions")
async def list_sessions(
    user_id: Optional[str] = None,
    notice_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """ApplicationSession 목록 (PRD §13.9 Notice:Session = 1:N).

    "기존 세션 이어가기" UI에서 사용:
      - 사용자가 같은 공고로 진입 → notice_id 필터로 기존 세션 검색
      - status 필터로 "drafting / step2_confirmed" 등 활성 세션 선택
    """
    query = db.query(ApplicationSession)
    if user_id:
        query = query.filter(ApplicationSession.user_id == user_id)
    if status:
        query = query.filter(ApplicationSession.status == status)
    sessions = query.order_by(ApplicationSession.created_at.desc()).limit(limit).all()

    items = []
    for s in sessions:
        snj = s.notice_schema_json or {}
        # notice_id 필터 (notice_schema_json 안에 보존되어 있어 in-Python 필터)
        if notice_id is not None and snj.get("notice_id") != notice_id:
            continue
        items.append({
            "session_id": s.session_id,
            "user_id": s.user_id,
            "status": s.status,
            "current_step": s.current_step,
            "notice_id": snj.get("notice_id"),
            "notice_title": snj.get("snapshot", {}).get("title"),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })

    return {
        "items": items,
        "total": len(items),
        "filters": {"user_id": user_id, "notice_id": notice_id, "status": status},
    }


# ─── Endpoint 7개 ──────────────────────────────────────────────────────


@router.post("/parse-notice")
async def parse_notice(
    req: ParseNoticeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """공고문 → NoticeSchema (PRD §13.x).
    이 단계는 EvalCriteriaMapping 초기 후보 생성도 포함 (PRD §16.1).
    map-eval-criteria 단계에서 FormSchema 기반 재계산.

    notice_text가 비어있거나 placeholder면 session.attachments(kind=notice)의
    parsed_text를 자동으로 join해서 사용 (PDF→text 추출은 files/upload 시점에 이미 수행됨).
    """
    notice_text = (req.notice_text or "").strip()
    if not notice_text or notice_text.startswith("[v0.2 mock"):
        if not req.session_id:
            raise HTTPException(
                status_code=422,
                detail="notice_text가 비어있고 session_id도 없어 첨부 PDF에서 추출할 수 없습니다",
            )
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == req.session_id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"session not found: {req.session_id}")
        items = _get_attachments(session, "notice")
        parts = [(it.get("parsed_text") or "").strip() for it in items]
        notice_text = "\n\n".join(p for p in parts if p)
        if not notice_text:
            raise HTTPException(
                status_code=422,
                detail="공고문 텍스트도 첨부 PDF의 추출 결과도 비어있습니다",
            )

    provider = get_provider()
    result = await provider.notice_analyst(
        notice_text,
        request_id=req.request_id,
        session_id=req.session_id,
    )

    # ─── parse-notice 결과 DB 영속화 (form_prd/2.md 패턴 미러링) ───
    # 기존 notice_schema_json["attachments"], ["notice_id"], ["snapshot"]는 절대 덮어쓰지 않음
    # notice_schema_json["schema"]에 NoticeSchema 저장
    # notice_schema_json["parser_metadata"]에 provider/model/parsed_at 저장
    schema_data = dict(result)

    if not req.session_id:
        result["saved"] = False
        result["save_skipped_reason"] = "missing_session_id"
        return result

    try:
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == req.session_id
        ).first()
        if not session:
            result["saved"] = False
            result["save_error"] = f"session not found after parse: {req.session_id}"
            return result

        current = dict(session.notice_schema_json or {})
        current["schema"] = schema_data
        current["parser_metadata"] = {
            "provider": getattr(provider, "provider_name", "unknown"),
            "model": getattr(provider, "model_name", "unknown"),
            "parsed_at": datetime.utcnow().isoformat(),
            "status": "success",
            "evaluation_criteria_count": len(schema_data.get("evaluation_criteria", []) or []),
            "required_documents_count": len(schema_data.get("required_documents", []) or []),
        }
        session.notice_schema_json = current
        flag_modified(session, "notice_schema_json")
        db.commit()
        result["saved"] = True
    except Exception as e:
        db.rollback()
        logger.exception("[parse_notice] DB commit failed for session %s", req.session_id)
        result["saved"] = False
        result["save_error"] = f"DB commit failed: {e}"

    return result


@router.post("/parse-form")
async def parse_form(
    req: ParseFormRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """제출양식 → FormSchema (PRD §13.2).

    form_text가 비어있거나 placeholder([제출양식 파일])면 session.attachments(kind=form)의
    parsed_text를 자동으로 join해서 사용 (PDF→text 추출은 files/upload 시점에 이미 수행됨).
    """
    # A-3: parser_mode tracking
    parser_mode: str = "direct_input"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    layout_meta: dict = {}
    # A-4-4: layout pages (table_normalizer 입력)
    layout_pages: list = []

    form_text = (req.form_text or "").strip()
    # placeholder 패턴: "[제출양식 파일]" 또는 "[v0.2 mock"
    if not form_text or form_text.startswith("[제출양식 파일]") or form_text.startswith("[v0.2 mock"):
        if not req.session_id:
            raise HTTPException(
                status_code=422,
                detail="form_text가 비어있고 session_id도 없어 첨부 파일에서 추출할 수 없습니다",
            )
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == req.session_id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"session not found: {req.session_id}")
        items = _get_attachments(session, "form")

        # A-1: layout-aware 우선 시도 → 실패 시 parsed_text fallback
        # A-1.5: tuple 언패킹 (form_text, layout_meta)
        # A-3: parser_mode / fallback_used / fallback_reason 추적
        # A-4-4: layout_pages 추가 (table_normalizer 입력)
        form_text, layout_meta, layout_pages = _build_layout_aware_text(items)
        if layout_meta.get("layout_text_truncated"):
            logger.info(
                "[parse_form] layout-aware cap 적용: %d chars → %d chars (%d/%d pages 포함)",
                layout_meta["layout_text_original_chars"],
                layout_meta["layout_text_returned_chars"],
                layout_meta["pages_included"],
                layout_meta["pages_total"],
            )
        if form_text:
            parser_mode = "layout_aware"
            fallback_used = False
            fallback_reason = None
        else:
            parts = [(it.get("parsed_text") or "").strip() for it in items]
            form_text = "\n\n".join(p for p in parts if p)
            parser_mode = "plain_text_fallback"
            fallback_used = True
            fallback_reason = layout_meta.get("fallback_reason") or "empty_layout_text"

        if not form_text:
            raise HTTPException(
                status_code=422,
                detail="제출양식 텍스트도 첨부 파일의 추출 결과도 비어있습니다",
            )

    provider = get_provider()

    # 2026-05-18: parser_mode 분기
    if req.parser_mode == "hybrid":
        from services.form_parser_hybrid import parse_form_hybrid
        result = await parse_form_hybrid(
            form_text,
            req.form_name,
            provider,
            request_id=req.request_id,
            session_id=req.session_id,
        )
        # hybrid는 table_normalizer/promoter 적용 안 함 (각 chunk가 자체 처리)
        hybrid_meta = result.pop("_hybrid_meta", {}) if isinstance(result, dict) else {}
        logger.info("[parse_form] hybrid mode: %s", hybrid_meta)
    else:
        result = await provider.form_parser(
            form_text,
            req.form_name,
            request_id=req.request_id,
            session_id=req.session_id,
        )
        hybrid_meta = {}

    # ─── A-4-4: Table Normalizer + Table Promoter ────────────────────────
    # b4-8.md §3.10 feature flag로 제어. layout_pages가 비어있으면 (parsed_text fallback) 스킵.
    # 2026-05-18: hybrid mode는 table normalizer/promoter 스킵 (각 chunk가 자체 처리, merger가 ID 재할당)
    promotion_stats: Dict[str, Any] = {}
    normalized_tables: list = []
    if req.parser_mode == "hybrid":
        logger.info("[parse_form] hybrid mode — table_normalizer/promoter skip")
    elif FORM_NORMALIZE_TABLE and layout_pages:
        try:
            from services.table_normalizer import normalize_layout_tables
            normalized_tables = normalize_layout_tables(layout_pages)
            logger.info("[parse_form] table_normalizer: %d tables normalized", len(normalized_tables))
        except Exception as e:
            logger.warning("[parse_form] table_normalizer 실패: %s", e)
            normalized_tables = []

    if req.parser_mode != "hybrid" and FORM_AUTO_PROMOTE_TABLE and normalized_tables:
        try:
            from services.table_promoter import promote_tables
            result, promotion_stats = promote_tables(normalized_tables, result)
            logger.info(
                "[parse_form] table_promoter: %d promoted, %d corrected, %d auto_section",
                promotion_stats.get("promoted_table_count", 0),
                promotion_stats.get("llm_schema_corrected_count", 0),
                promotion_stats.get("auto_section_used_count", 0),
            )
        except Exception as e:
            logger.warning("[parse_form] table_promoter 실패: %s", e)
            promotion_stats = {}

    # ─── A-2: Quality gate + 1-pass repair ───────────────────────────────
    page_count = layout_meta.get("pages_total", 0) or _count_page_markers(form_text)
    quality_metrics = _compute_form_quality_metrics(result, form_text, page_count=page_count)
    result["quality_metrics"] = quality_metrics

    suspect_text = _extract_suspect_pages(form_text, result, quality_metrics)
    layout_truncated = bool(layout_meta.get("layout_text_truncated"))
    if quality_metrics["needs_repair"] and suspect_text and not layout_truncated:
        try:
            repair_result = await provider.form_parser(
                suspect_text,
                req.form_name,
                request_id=req.request_id,
                session_id=req.session_id,
            )
            result = _merge_repair_schema(result, repair_result)
            _log_repair_call(db, req.session_id, req.request_id)
            post_metrics = _compute_form_quality_metrics(result, form_text, page_count=page_count)
            post_metrics["repaired"] = True
            result["quality_metrics"] = post_metrics
            result["quality_status"] = (
                "needs_manual_review" if post_metrics["needs_repair"] else "ok"
            )
        except Exception as e:
            logger.warning("[parse_form] repair pass 실패: %s", e)
            result["quality_status"] = "repair_failed"
    elif quality_metrics["needs_repair"]:
        result["quality_status"] = "needs_manual_review"
    else:
        result["quality_status"] = "ok"

    # layout_text_truncated=true → 최소 warning (success로만 표시 금지)
    if layout_truncated and result.get("quality_status") == "ok":
        result["quality_status"] = "warning_truncated"

    # ─── PRD form_prd/2.md: parse-form 결과 DB 영속화 ───
    # 기존 form_schema_json["attachments"]는 절대 덮어쓰지 않음
    # form_schema_json["schema"]에 FormSchema 저장
    # form_schema_json["parser_metadata"]에 provider/model/parsed_at 저장
    schema_data = dict(result)  # response-only 필드(saved/save_error) 추가 전 clean snapshot

    if not req.session_id:
        result["saved"] = False
        result["save_skipped_reason"] = "missing_session_id"
        return result

    try:
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == req.session_id
        ).first()
        if not session:
            result["saved"] = False
            result["save_error"] = f"session not found after parse: {req.session_id}"
            return result

        current = dict(session.form_schema_json or {})
        current["schema"] = schema_data
        sections = schema_data.get("sections", []) or []
        question_count = sum(len(s.get("questions", []) or []) for s in sections)
        current["parser_metadata"] = {
            "provider": getattr(provider, "provider_name", "unknown"),
            "model": getattr(provider, "model_name", "unknown"),
            "parsed_at": datetime.utcnow().isoformat(),
            "status": "success",
            "section_count": len(sections),
            "question_count": question_count,
            # A-3: parser_mode / fallback (input mode: layout_aware / plain_text_fallback / direct_input)
            "parser_mode": parser_mode,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            # 2026-05-18: parser_strategy (single / hybrid) — 사용자 선택 모드
            "parser_strategy": req.parser_mode,
            "hybrid_meta": hybrid_meta,
            # A-3: A-1.5 cap meta 병합
            "layout_text_original_chars": layout_meta.get("layout_text_original_chars", 0),
            "layout_text_returned_chars": layout_meta.get("layout_text_returned_chars", 0),
            "layout_text_truncated": layout_meta.get("layout_text_truncated", False),
            "truncated_after_page": layout_meta.get("truncated_after_page"),
            "omitted_page_count": layout_meta.get("omitted_page_count", 0),
            "pages_total": layout_meta.get("pages_total", 0),
            "pages_included": layout_meta.get("pages_included", 0),
            "layout_text_safety_cap": layout_meta.get("layout_text_safety_cap", FORM_LAYOUT_TEXT_SAFETY_CAP),
            # A-4-4: table normalizer + promoter stats (§3.6 / §3.9)
            "layout_table_count": promotion_stats.get("layout_table_count", 0),
            "normalized_table_count": promotion_stats.get("normalized_table_count", 0),
            "llm_table_input_count": promotion_stats.get("llm_table_input_count", 0),
            "promoted_table_count": promotion_stats.get("promoted_table_count", 0),
            "skipped_fragment_table_count": promotion_stats.get("skipped_fragment_table_count", 0),
            "skipped_non_promotable_table_count": promotion_stats.get("skipped_non_promotable_table_count", 0),
            "llm_schema_corrected_count": promotion_stats.get("llm_schema_corrected_count", 0),
            "auto_section_used_count": promotion_stats.get("auto_section_used_count", 0),
            "table_promotion_rate": promotion_stats.get("table_promotion_rate", 0.0),
            "normalize_table_enabled": FORM_NORMALIZE_TABLE,
            "auto_promote_table_enabled": FORM_AUTO_PROMOTE_TABLE,
            # quality
            "quality_status": result.get("quality_status", "unknown"),
            "quality_metrics": result.get("quality_metrics", {}),
        }
        session.form_schema_json = current
        flag_modified(session, "form_schema_json")
        db.commit()
        result["saved"] = True
    except Exception as e:
        db.rollback()
        logger.exception("[parse_form] DB commit failed for session %s", req.session_id)
        result["saved"] = False
        result["save_error"] = f"DB commit failed: {e}"

    return result


# ════════════════════════════════════════════════════════════════════════
# form_prd/4.md + 5.md: FormSchema 항목 수정 UI/API v0.1
# PATCH /api/analysis/form-schema/question
#   action: "update" | "add" | "exclude"
#   - update:  question 부분 수정 (whitelist 필드)
#   - add:     section_id에 USER-{uuid8} question 추가
#   - exclude: question_id를 schema["excluded_question_ids"]에 추가/제거 (실제 삭제 X)
#
# 저장 위치:
#   form_schema_json["schema"]["sections"]           ← update / add
#   form_schema_json["schema"]["excluded_question_ids"]  ← exclude
#   form_schema_json["schema"]["user_question_metadata"] ← add (USER-* 메타)
# attachments / parser_metadata 절대 미변경.
# ════════════════════════════════════════════════════════════════════════

_FORM_QUESTION_UPDATE_WHITELIST = {
    "title",
    "source_page",
    "is_required",
    "is_table_item",
    "requirement",
    "writing_guidelines",
    "constraints",
    "required_evidence_types",
    "required_attachments",
    "warnings",
}


class FormQuestionPatchRequest(BaseModel):
    session_id: str
    action: Literal["update", "add", "exclude", "move", "delete"]
    question_id: Optional[str] = None
    section_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    excluded: Optional[bool] = None
    # 2026-05-18: add 시 특정 위치에 삽입 (before/after question_id) — 미지정 시 섹션 끝에 append
    insert_position: Optional[Dict[str, str]] = None  # {"before": qid} or {"after": qid}
    # 2026-05-18: move — 다른 섹션으로 이동
    target_section_id: Optional[str] = None
    target_index: Optional[int] = None              # 미지정 시 끝에 append


def _gen_user_question_id(schema: Dict[str, Any], max_tries: int = 10) -> str:
    """USER-{uuid8} 형식 ID 생성. 전체 schema에서 중복 체크."""
    existing = set()
    for sec in schema.get("sections", []) or []:
        for q in sec.get("questions", []) or []:
            qid = q.get("question_id")
            if qid:
                existing.add(qid)
    for _ in range(max_tries):
        candidate = f"USER-{uuid.uuid4().hex[:8]}"
        if candidate not in existing:
            return candidate
    raise HTTPException(status_code=409, detail="USER question_id 생성 충돌이 반복되어 고유 ID 생성 실패")


@router.patch("/form-schema/question")
async def patch_form_schema_question(
    req: FormQuestionPatchRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """form_prd/4.md + 5.md — FormSchema question 부분 수정/추가/제외."""
    # 1. session 조회
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == req.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {req.session_id}")

    current = dict(session.form_schema_json or {})
    schema = current.get("schema")
    if not isinstance(schema, dict) or not schema.get("sections"):
        raise HTTPException(status_code=422, detail="form_schema_json.schema가 없습니다. parse-form을 먼저 실행하세요.")
    schema = dict(schema)  # 얕은 복사 (sections는 mutation 후 재할당)
    sections = list(schema.get("sections", []) or [])

    # 2. action 분기
    if req.action == "update":
        if not req.question_id or not isinstance(req.payload, dict):
            raise HTTPException(status_code=422, detail="update: question_id 와 payload 필수")
        # 허용 필드만 추출
        clean = {}
        for k, v in req.payload.items():
            if k not in _FORM_QUESTION_UPDATE_WHITELIST:
                continue
            if v is None:
                continue  # None = 무시
            # source_page 정수 검증
            if k == "source_page" and v != "":
                try:
                    clean[k] = int(v)
                except (TypeError, ValueError):
                    raise HTTPException(status_code=422, detail=f"source_page는 정수여야 합니다: {v!r}")
                continue
            clean[k] = v
        # question 찾아서 부분 갱신
        found = False
        new_sections = []
        for sec in sections:
            sec_copy = dict(sec)
            questions = list(sec_copy.get("questions", []) or [])
            new_questions = []
            for q in questions:
                if q.get("question_id") == req.question_id:
                    found = True
                    new_q = dict(q)
                    new_q.update(clean)
                    new_questions.append(new_q)
                else:
                    new_questions.append(q)
            sec_copy["questions"] = new_questions
            new_sections.append(sec_copy)
        if not found:
            raise HTTPException(status_code=404, detail=f"question_id not found: {req.question_id}")
        sections = new_sections

    elif req.action == "add":
        if not req.section_id or not isinstance(req.payload, dict):
            raise HTTPException(status_code=422, detail="add: section_id 와 payload 필수")
        # title 필수 (5.md §2)
        title_val = req.payload.get("title")
        if not isinstance(title_val, str) or not title_val.strip():
            raise HTTPException(status_code=422, detail="add: payload.title 필수 (비공백 문자열)")
        # source_page int 검증 (있을 때만)
        src_page = req.payload.get("source_page")
        if src_page is not None and src_page != "":
            try:
                src_page = int(src_page)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"add: source_page는 정수여야 합니다: {src_page!r}")
        else:
            src_page = None

        # section 찾기
        section_idx = None
        for i, sec in enumerate(sections):
            if sec.get("section_id") == req.section_id:
                section_idx = i
                break
        if section_idx is None:
            raise HTTPException(status_code=404, detail=f"section_id not found: {req.section_id}")

        # USER-{uuid8} 생성
        new_qid = _gen_user_question_id(schema)
        new_question = {
            "question_id": new_qid,
            "title": title_val.strip(),
            "source_page": src_page,
            "is_required": bool(req.payload.get("is_required", False)),
            "is_table_item": bool(req.payload.get("is_table_item", False)),
            "requirement": req.payload.get("requirement") or None,
            "writing_guidelines": req.payload.get("writing_guidelines") or [],
            "constraints": req.payload.get("constraints") or {
                "max_length": 0, "min_length": 0, "format": None, "page_limit": None,
            },
            "required_evidence_types": req.payload.get("required_evidence_types") or [],
            "required_attachments": req.payload.get("required_attachments") or [],
            "warnings": req.payload.get("warnings") or [],
        }
        new_sec = dict(sections[section_idx])
        new_questions = list(new_sec.get("questions", []) or [])
        # 2026-05-18: insert_position 처리 — {"before": qid} 또는 {"after": qid}
        insert_at = None
        if isinstance(req.insert_position, dict):
            before_qid = req.insert_position.get("before")
            after_qid = req.insert_position.get("after")
            if before_qid:
                for i, q in enumerate(new_questions):
                    if q.get("question_id") == before_qid:
                        insert_at = i
                        break
            elif after_qid:
                for i, q in enumerate(new_questions):
                    if q.get("question_id") == after_qid:
                        insert_at = i + 1
                        break
        if insert_at is not None:
            new_questions.insert(insert_at, new_question)
        else:
            new_questions.append(new_question)
        new_sec["questions"] = new_questions
        sections[section_idx] = new_sec

        # user_question_metadata 별도 저장 (Pydantic 검증 우회)
        meta = dict(schema.get("user_question_metadata", {}) or {})
        meta[new_qid] = {
            "created_by": "user",
            "created_at": datetime.utcnow().isoformat(),
        }
        schema["user_question_metadata"] = meta

    elif req.action == "move":
        # 2026-05-18: 문항을 다른 section으로 이동
        if not req.question_id or not req.target_section_id:
            raise HTTPException(status_code=422, detail="move: question_id 와 target_section_id 필수")
        # source section 에서 question 찾아 제거
        moved_q = None
        new_sections = []
        for sec in sections:
            sec_copy = dict(sec)
            questions = list(sec_copy.get("questions", []) or [])
            remaining = []
            for q in questions:
                if q.get("question_id") == req.question_id and moved_q is None:
                    moved_q = dict(q)
                else:
                    remaining.append(q)
            sec_copy["questions"] = remaining
            new_sections.append(sec_copy)
        if moved_q is None:
            raise HTTPException(status_code=404, detail=f"move: question_id not found: {req.question_id}")
        # target section 찾기
        target_idx = None
        for i, sec in enumerate(new_sections):
            if sec.get("section_id") == req.target_section_id:
                target_idx = i
                break
        if target_idx is None:
            raise HTTPException(status_code=404, detail=f"move: target_section_id not found: {req.target_section_id}")
        target_sec = dict(new_sections[target_idx])
        target_questions = list(target_sec.get("questions", []) or [])
        # target_index 위치에 삽입 (None이면 끝에 append)
        if req.target_index is not None and 0 <= req.target_index <= len(target_questions):
            target_questions.insert(req.target_index, moved_q)
        else:
            target_questions.append(moved_q)
        target_sec["questions"] = target_questions
        new_sections[target_idx] = target_sec
        sections = new_sections

    elif req.action == "delete":
        # 2026-05-18: 문항 DB에서 완전 제거 (exclude는 soft hide, delete는 hard remove)
        if not req.question_id:
            raise HTTPException(status_code=422, detail="delete: question_id 필수")
        found = False
        new_sections = []
        for sec in sections:
            sec_copy = dict(sec)
            questions = list(sec_copy.get("questions", []) or [])
            remaining = []
            for q in questions:
                if q.get("question_id") == req.question_id:
                    found = True
                    continue
                remaining.append(q)
            sec_copy["questions"] = remaining
            new_sections.append(sec_copy)
        if not found:
            raise HTTPException(status_code=404, detail=f"delete: question_id not found: {req.question_id}")
        sections = new_sections
        # excluded_question_ids 에서도 제거 (있을 경우)
        excluded_ids = list(schema.get("excluded_question_ids", []) or [])
        if req.question_id in excluded_ids:
            excluded_ids = [x for x in excluded_ids if x != req.question_id]
            schema["excluded_question_ids"] = excluded_ids
        # user_question_metadata 에서도 제거
        meta = dict(schema.get("user_question_metadata", {}) or {})
        if req.question_id in meta:
            del meta[req.question_id]
            schema["user_question_metadata"] = meta

    elif req.action == "exclude":
        if not req.question_id or req.excluded is None:
            raise HTTPException(status_code=422, detail="exclude: question_id 와 excluded 필수")
        # question_id 존재 확인
        exists = False
        for sec in sections:
            for q in sec.get("questions", []) or []:
                if q.get("question_id") == req.question_id:
                    exists = True
                    break
            if exists:
                break
        if not exists:
            raise HTTPException(status_code=404, detail=f"question_id not found: {req.question_id}")

        excluded_ids = list(schema.get("excluded_question_ids", []) or [])
        if req.excluded:
            if req.question_id not in excluded_ids:
                excluded_ids.append(req.question_id)
        else:
            excluded_ids = [x for x in excluded_ids if x != req.question_id]
        schema["excluded_question_ids"] = excluded_ids

    else:
        raise HTTPException(status_code=400, detail=f"unsupported action: {req.action}")

    # 3. DB 저장 (attachments / parser_metadata 보존)
    schema["sections"] = sections
    current["schema"] = schema
    session.form_schema_json = current
    flag_modified(session, "form_schema_json")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[patch_form_schema_question] DB commit failed for session %s", req.session_id)
        raise HTTPException(status_code=500, detail=f"DB commit failed: {e}")

    return {
        "session_id": req.session_id,
        "action": req.action,
        "saved": True,
        "updated_schema": schema,
    }


# ════════════════════════════════════════════════════════════════════════
# 2026-05-18 — Section CRUD endpoint
# PATCH /api/analysis/form-schema/section
#   action: "add" | "rename" | "delete" | "reorder"
# ════════════════════════════════════════════════════════════════════════

class FormSectionPatchRequest(BaseModel):
    session_id: str
    action: Literal["add", "rename", "delete", "reorder"]
    section_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None  # add/rename: {title, instruction_notes?}
    target_index: Optional[int] = None         # reorder: 새 위치 (0-based)
    insert_position: Optional[Dict[str, str]] = None  # add: {before/after: section_id}
    force: Optional[bool] = False              # delete: true 면 하위 question 포함 삭제


def _gen_user_section_id(schema: Dict[str, Any], max_tries: int = 50) -> str:
    """기존 section_id와 중복 안 되는 S{nnn} 생성. 가장 큰 S 번호 + 1."""
    existing = set()
    max_n = 0
    for sec in schema.get("sections", []) or []:
        sid = sec.get("section_id") or ""
        existing.add(sid)
        # S001 형식 파싱
        if sid.startswith("S") and sid[1:].isdigit():
            try:
                n = int(sid[1:])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    for n in range(max_n + 1, max_n + 1 + max_tries):
        candidate = f"S{n:03d}"
        if candidate not in existing:
            return candidate
    raise HTTPException(status_code=409, detail="section_id 생성 충돌")


@router.patch("/form-schema/section")
async def patch_form_schema_section(
    req: FormSectionPatchRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """FormSchema section CRUD (add / rename / delete / reorder)."""
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == req.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {req.session_id}")

    current = dict(session.form_schema_json or {})
    schema = current.get("schema")
    if not isinstance(schema, dict) or schema.get("sections") is None:
        raise HTTPException(status_code=422, detail="form_schema_json.schema가 없습니다. parse-form을 먼저 실행하세요.")
    schema = dict(schema)
    sections = list(schema.get("sections", []) or [])

    if req.action == "add":
        if not isinstance(req.payload, dict):
            raise HTTPException(status_code=422, detail="add: payload 필수")
        title = (req.payload.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="add: payload.title 필수 (비공백)")
        new_sid = _gen_user_section_id(schema)
        new_sec = {
            "section_id": new_sid,
            "title": title,
            "order": 0,  # 아래 reindex
            "instruction_notes": req.payload.get("instruction_notes") or None,
            "questions": [],
        }
        # insert_position 처리
        insert_at = None
        if isinstance(req.insert_position, dict):
            before_sid = req.insert_position.get("before")
            after_sid = req.insert_position.get("after")
            if before_sid:
                for i, sec in enumerate(sections):
                    if sec.get("section_id") == before_sid:
                        insert_at = i
                        break
            elif after_sid:
                for i, sec in enumerate(sections):
                    if sec.get("section_id") == after_sid:
                        insert_at = i + 1
                        break
        if insert_at is not None:
            sections.insert(insert_at, new_sec)
        else:
            sections.append(new_sec)
        # order reindex
        for i, sec in enumerate(sections):
            sec["order"] = i + 1
        result_message = f"section added: {new_sid}"

    elif req.action == "rename":
        if not req.section_id or not isinstance(req.payload, dict):
            raise HTTPException(status_code=422, detail="rename: section_id 와 payload 필수")
        title = (req.payload.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="rename: payload.title 필수 (비공백)")
        found = False
        for sec in sections:
            if sec.get("section_id") == req.section_id:
                sec["title"] = title
                if "instruction_notes" in req.payload:
                    sec["instruction_notes"] = req.payload.get("instruction_notes") or None
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"rename: section_id not found: {req.section_id}")
        result_message = f"section renamed: {req.section_id}"

    elif req.action == "delete":
        if not req.section_id:
            raise HTTPException(status_code=422, detail="delete: section_id 필수")
        target_idx = None
        for i, sec in enumerate(sections):
            if sec.get("section_id") == req.section_id:
                target_idx = i
                break
        if target_idx is None:
            raise HTTPException(status_code=404, detail=f"delete: section_id not found: {req.section_id}")
        target_sec = sections[target_idx]
        q_count = len(target_sec.get("questions", []) or [])
        if q_count > 0 and not req.force:
            raise HTTPException(
                status_code=422,
                detail=f"delete: section에 question {q_count}개 존재. force=true 로 강제 삭제하거나 question을 먼저 이동/삭제하세요.",
            )
        sections.pop(target_idx)
        # order reindex
        for i, sec in enumerate(sections):
            sec["order"] = i + 1
        result_message = f"section deleted: {req.section_id} (questions {q_count}개 함께 제거)"

    elif req.action == "reorder":
        if not req.section_id or req.target_index is None:
            raise HTTPException(status_code=422, detail="reorder: section_id 와 target_index 필수")
        if req.target_index < 0 or req.target_index >= len(sections):
            raise HTTPException(status_code=422, detail=f"reorder: target_index 범위 외 (0~{len(sections)-1})")
        # 현재 위치 찾기
        current_idx = None
        for i, sec in enumerate(sections):
            if sec.get("section_id") == req.section_id:
                current_idx = i
                break
        if current_idx is None:
            raise HTTPException(status_code=404, detail=f"reorder: section_id not found: {req.section_id}")
        # pop + insert
        moved = sections.pop(current_idx)
        sections.insert(req.target_index, moved)
        # order reindex
        for i, sec in enumerate(sections):
            sec["order"] = i + 1
        result_message = f"section reordered: {req.section_id} → idx {req.target_index}"

    else:
        raise HTTPException(status_code=400, detail=f"unsupported action: {req.action}")

    # DB 저장
    schema["sections"] = sections
    current["schema"] = schema
    session.form_schema_json = current
    flag_modified(session, "form_schema_json")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[patch_form_schema_section] DB commit failed for session %s", req.session_id)
        raise HTTPException(status_code=500, detail=f"DB commit failed: {e}")

    return {
        "session_id": req.session_id,
        "action": req.action,
        "saved": True,
        "message": result_message,
        "section_count": len(sections),
        "updated_schema": schema,
    }


@router.post("/extract-evidence")
async def extract_evidence(
    req: ExtractEvidenceRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """참고자료 chunk → EvidenceSchema (PRD §13.3).
    embedding은 1024-dim (bge-m3-ko). 임베딩 모델은 별도 (Phase 4-C.x).
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    provider = get_provider()
    return await provider.evidence_extractor(
        req.ref_text,
        req.source_file,
        req.source_page,
        request_id=req.request_id,
        session_id=req.session_id,
    )


@router.post("/analyze-company")
async def analyze_company(
    req: AnalyzeCompanyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """기업정보 → CompanySchema + FitAnalysis (PRD §13.x).
    응답 구조: { company: CompanySchema, fit_analysis: FitAnalysis }
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    provider = get_provider()
    return await provider.company_analyzer(
        req.company_files,
        req.notice_schema,
        request_id=req.request_id,
        session_id=req.session_id,
    )


@router.post("/map-evidence")
async def map_evidence(
    req: MapEvidenceRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """문항 × evidence RAG 매칭 → MappingResult (PRD §13.4).
    matching_threshold (default 0.70) 이상 = auto_confirmed,
    이하 = awaiting_user_confirm 또는 excluded.
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    provider = get_provider()
    return await provider.evidence_mapper(
        req.form_schema,
        req.evidence_list,
        req.notice_schema,
        req.matching_threshold,
        request_id=req.request_id,
        session_id=req.session_id,
    )


@router.post("/check-missing")
async def check_missing(
    req: CheckMissingRequest,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """근거 부족 문항 → MissingMaterial[] (PRD §13.5).
    8 status enum 초기값 = "open".
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    provider = get_provider()
    return await provider.missing_material(
        req.mapping_result,
        request_id=req.request_id,
        session_id=req.session_id,
    )


@router.post("/map-eval-criteria")
async def map_eval_criteria(
    req: MapEvalCriteriaRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """평가기준 ↔ 문항 매핑 재계산·보강 (PRD §16.1 책임 분리).

    parse-notice = 초기 후보 (FormSchema 미확정 시 scope만 추정).
    map-eval-criteria = FormSchema 확정 후 mapped_questions 정확하게 채움.
    같은 EvalCriteriaMapping 레코드 갱신 (별도 생성 X).

    Phase 4-C 단계: provider에 별도 메서드 없음 (notice_analyst 결과 재활용).
    Phase 4-C.x에서 별도 evaluator 모듈 추가 시 정교화.
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    # 임시: notice_schema의 evaluation_criteria + form_schema의 question_id를 단순 매칭
    # TODO Phase 4-C.x: provider.eval_criteria_mapper(notice_schema, form_schema) 별도 메서드
    criteria = req.notice_schema.get("evaluation_criteria", [])
    form_questions = []
    for sec in req.form_schema.get("sections", []):
        for q in sec.get("questions", []):
            form_questions.append(q.get("question_id", ""))

    mappings = []
    for c in criteria:
        # 단순 mock 매핑 — Phase 4-C.x에서 RAG 기반 정밀 매칭으로 교체
        mappings.append({
            "criteria_id": f"crit_{c.get('name', 'unknown')}",
            "session_id": req.session_id,
            "criteria_name": c.get("name", ""),
            "weight": c.get("weight", 0),
            "scope": c.get("scope", "section"),
            "mapped_questions": form_questions[:3] if c.get("scope") == "section" else form_questions[:2],
            "mapping_type": "direct",
            "mapped_by": "ai",
            "confidence": 0.75,
            "reason": f"{c.get('name', '')} 평가기준 → 양식 문항 매핑 (mock)",
            "source_page": None,
        })

    return {
        "session_id": req.session_id,
        "mappings": mappings,
        "total": len(mappings),
    }


# ────────────────────────────────────────────────────────────────────────
# v0.2.1 V1: 평가기준 매핑 사용자 편집 (PRD §13.8 / PRD v0.2.1 정의)
#   PATCH /api/analysis/eval-criteria-mappings/{criteria_id}
#
# 정책:
#   - upsert (없으면 생성, 있으면 갱신)
#   - mapped_by 강제 "user" (사용자 편집 표시)
#   - 수정 가능 필드: scope / mapped_questions / mapping_type / confidence / reason / weight
#   - criteria_name / session_id 변경 불가 (path/body로 받되 검증만)
#   - 변경 이력 (V2)은 별도 작업, V1 범위 외
# ────────────────────────────────────────────────────────────────────────


class PatchEvalCriteriaMappingRequest(BaseModel):
    """평가기준 매핑 사용자 편집 (v0.2.1 V1)."""
    session_id: str
    criteria_name: Optional[str] = None
    scope: Optional[Literal["question", "section", "document"]] = None
    mapped_questions: Optional[List[str]] = None
    mapping_type: Optional[Literal["direct", "indirect", "context"]] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    weight: Optional[int] = None


@router.patch("/eval-criteria-mappings/{criteria_id}")
def patch_eval_criteria_mapping(
    criteria_id: str,
    req: PatchEvalCriteriaMappingRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """평가기준 매핑 사용자 편집 (v0.2.1 V1).

    upsert: criteria_id + session_id로 조회, 없으면 생성.
    mapped_by="user" 자동 기록 (AI 생성과 구분).
    """
    # session 존재 확인
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == req.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {req.session_id}")

    # confidence 범위 검증
    if req.confidence is not None and not (0.0 <= req.confidence <= 1.0):
        raise HTTPException(
            status_code=422,
            detail=f"confidence는 0.0~1.0 범위여야 합니다: {req.confidence}",
        )

    # upsert
    row = db.query(EvalCriteriaMapping).filter(
        EvalCriteriaMapping.criteria_id == criteria_id,
        EvalCriteriaMapping.session_id == req.session_id,
    ).first()

    if row is None:
        # 신규 — criteria_name 필수
        if not req.criteria_name:
            raise HTTPException(
                status_code=422,
                detail="신규 매핑 생성 시 criteria_name 필수",
            )
        initial_history = [{
            "at": datetime.utcnow().isoformat(),
            "by": "user",
            "action": "create",
            "snapshot": {
                "criteria_name": req.criteria_name,
                "scope": req.scope or "section",
                "mapped_questions": req.mapped_questions or [],
                "mapping_type": req.mapping_type or "direct",
                "confidence": req.confidence if req.confidence is not None else 0.0,
                "weight": req.weight or 0,
                "reason": req.reason,
            },
        }]
        row = EvalCriteriaMapping(
            criteria_id=criteria_id,
            session_id=req.session_id,
            criteria_name=req.criteria_name,
            weight=req.weight or 0,
            scope=req.scope or "section",
            mapped_questions=req.mapped_questions or [],
            mapping_type=req.mapping_type or "direct",
            mapped_by="user",
            confidence=req.confidence if req.confidence is not None else 0.0,
            reason=req.reason,
            history=initial_history,
        )
        db.add(row)
        created = True
    else:
        # 갱신 — None 아닌 필드만 + history append (PRD-13 §19.3 옵션 A)
        changes: Dict[str, Any] = {}
        if req.criteria_name is not None and req.criteria_name != row.criteria_name:
            changes["criteria_name"] = [row.criteria_name, req.criteria_name]
            row.criteria_name = req.criteria_name
        if req.scope is not None and req.scope != row.scope:
            changes["scope"] = [row.scope, req.scope]
            row.scope = req.scope
        if req.mapped_questions is not None and req.mapped_questions != (row.mapped_questions or []):
            changes["mapped_questions"] = [row.mapped_questions or [], req.mapped_questions]
            row.mapped_questions = req.mapped_questions
        if req.mapping_type is not None and req.mapping_type != row.mapping_type:
            changes["mapping_type"] = [row.mapping_type, req.mapping_type]
            row.mapping_type = req.mapping_type
        if req.confidence is not None and req.confidence != row.confidence:
            changes["confidence"] = [row.confidence, req.confidence]
            row.confidence = req.confidence
        if req.reason is not None and req.reason != row.reason:
            changes["reason"] = [row.reason, req.reason]
            row.reason = req.reason
        if req.weight is not None and req.weight != (row.weight or 0):
            changes["weight"] = [row.weight or 0, req.weight]
            row.weight = req.weight

        if changes:
            history_list = list(row.history or [])
            history_list.append({
                "at": datetime.utcnow().isoformat(),
                "by": "user",
                "action": "update",
                "changes": changes,
            })
            row.history = history_list
            flag_modified(row, "history")

        row.mapped_by = "user"
        created = False

    db.commit()
    db.refresh(row)

    return {
        "criteria_id": row.criteria_id,
        "session_id": row.session_id,
        "criteria_name": row.criteria_name,
        "weight": row.weight or 0,
        "scope": row.scope,
        "mapped_questions": row.mapped_questions or [],
        "mapping_type": row.mapping_type,
        "mapped_by": row.mapped_by,
        "confidence": row.confidence,
        "reason": row.reason,
        "history": row.history or [],
        "history_count": len(row.history or []),
        "created": created,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/eval-criteria-mappings")
def list_eval_criteria_mappings(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """session 내 사용자 편집된 EvalCriteriaMapping 목록 (v0.2.1 V1).

    mock 분석 결과 (map-eval-criteria)는 DB 저장 X — 본 endpoint는 사용자가
    편집한 row만 반환. frontend는 mock 결과 + 본 응답을 merge (user 편집 우선).
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    rows = db.query(EvalCriteriaMapping).filter(
        EvalCriteriaMapping.session_id == session_id
    ).order_by(EvalCriteriaMapping.updated_at.desc()).all()

    return {
        "session_id": session_id,
        "total": len(rows),
        "items": [
            {
                "criteria_id": r.criteria_id,
                "criteria_name": r.criteria_name,
                "weight": r.weight or 0,
                "scope": r.scope,
                "mapped_questions": r.mapped_questions or [],
                "mapping_type": r.mapping_type,
                "mapped_by": r.mapped_by,
                "confidence": r.confidence,
                "reason": r.reason,
                "history_count": len(r.history or []),
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 4-D: 부족자료 4 + 재분석 1 endpoint (PRD §16.2 / §16.3)
# ════════════════════════════════════════════════════════════════════════


# ─── Request 모델 (Phase 4-D) ──────────────────────────────────────────


class MissingTextRequest(BaseModel):
    """직접 입력 — SupplementalMaterial type=text 생성."""
    session_id: str
    question_id: str
    missing_id: Optional[str] = None
    content: str
    request_id: str = ""


class MissingUploadRequest(BaseModel):
    """파일 업로드 단일 (mock — 실제 multipart는 Phase 4-G)."""
    session_id: str
    question_id: str
    missing_id: Optional[str] = None
    file_name: str
    file_size_bytes: int = 0
    request_id: str = ""


class MissingBulkUploadRequest(BaseModel):
    """일괄 업로드 — 다수 파일 + AI 자동 분류."""
    session_id: str
    files: List[Dict[str, Any]] = []  # [{file_name, file_size_bytes}]
    target_question_id: Optional[str] = None  # 사용자 지정 시
    request_id: str = ""


class MissingConfirmRequest(BaseModel):
    """매칭 결과 확정 — 사용자 [맞음/다른 항목/제외] 클릭."""
    session_id: str
    supplemental_id: str
    action: Literal["correct", "different", "exclude"]
    new_question_id: Optional[str] = None  # action=different 시
    request_id: str = ""


class ReanalyzeRequest(BaseModel):
    """범위별 재분석 (PRD §16.2)."""
    session_id: str
    target: Literal["notice", "form", "evidence", "company", "mapping", "missing", "all"]
    force: bool = False  # 사용자 확인 없이 강제 (target=all 시)
    drafts_policy: Optional[Literal["preserve", "discard", "user_choice"]] = None  # PRD §13.9
    request_id: str = ""


class SetDraftsPolicyRequest(BaseModel):
    """drafts_preservation_policy 영속화 전용 (PRD §13.9, A2)."""
    drafts_policy: Literal["preserve", "discard", "user_choice"]


# ─── Endpoint 5개 (Phase 4-D) ──────────────────────────────────────────


@router.post("/missing/text")
async def missing_text(req: MissingTextRequest) -> Dict[str, Any]:
    """직접 입력 → SupplementalMaterial 생성 (type=text).
    내부 흐름 (PRD §13.6):
      1. SupplementalMaterial 생성 (status=uploaded)
      2. AI 분석 → Evidence 변환 (status=analyzed → converted)
      3. MappingResult 재계산
      4. MissingMaterial.status 갱신 (open → matched/resolved)

    Phase 4-D 단계: stub mock 응답. DB 통합은 Phase 4-G.
    """
    supplemental_id = f"supp_{uuid.uuid4().hex[:8]}"
    return {
        "supplemental_id": supplemental_id,
        "session_id": req.session_id,
        "question_id": req.question_id,
        "missing_id": req.missing_id,
        "type": "text",
        "content": req.content[:500],  # preview
        "status": "uploaded",
        "created_at": datetime.utcnow().isoformat(),
        "next_steps": [
            "AI 분석 (status: uploaded → analyzed)",
            "Evidence 변환 + MappingResult 재계산 (status: → converted)",
            "MissingMaterial.status 갱신 (open → resolved)",
        ],
        "_note": "Phase 4-D mock. DB 통합은 Phase 4-G에서.",
    }


@router.post("/missing/upload")
async def missing_upload(req: MissingUploadRequest) -> Dict[str, Any]:
    """파일 업로드 단일 → SupplementalMaterial 생성 (type=file).

    Phase 4-D 단계: 파일 메타만 받음. 실제 multipart upload는 Phase 4-G.
    """
    supplemental_id = f"supp_{uuid.uuid4().hex[:8]}"
    file_id = f"file_{uuid.uuid4().hex[:8]}"
    return {
        "supplemental_id": supplemental_id,
        "session_id": req.session_id,
        "question_id": req.question_id,
        "missing_id": req.missing_id,
        "type": "file",
        "file_id": file_id,
        "file_name": req.file_name,
        "file_size_bytes": req.file_size_bytes,
        "status": "uploaded",
        "created_at": datetime.utcnow().isoformat(),
        "_note": "Phase 4-D mock. 실제 multipart upload는 Phase 4-G.",
    }


@router.post("/missing/bulk-upload")
async def missing_bulk_upload(req: MissingBulkUploadRequest) -> Dict[str, Any]:
    """일괄 업로드 + AI 자동 분류.

    target_question_id 없으면 AI가 question_id 추론.
    confidence < 0.70 → status=uploaded (사용자 확인 필요).
    confidence ≥ 0.70 → status=analyzed (자동 진행).
    """
    results = []
    for i, f in enumerate(req.files):
        confidence = 0.85 if req.target_question_id else 0.65  # 사용자 지정 시 자동 확정
        status = "analyzed" if confidence >= 0.70 else "uploaded"
        results.append({
            "supplemental_id": f"supp_{uuid.uuid4().hex[:8]}",
            "file_name": f.get("file_name", f"file_{i}"),
            "file_size_bytes": f.get("file_size_bytes", 0),
            "target_question_id": req.target_question_id or f"AI_inferred_q_{i}",
            "confidence": confidence,
            "status": status,
            "auto_match": confidence >= 0.70,
        })
    return {
        "session_id": req.session_id,
        "total_files": len(req.files),
        "auto_matched": sum(1 for r in results if r["auto_match"]),
        "pending_user_confirm": sum(1 for r in results if not r["auto_match"]),
        "results": results,
        "_note": "Phase 4-D mock. 실제 AI 분류는 Phase 4-G.",
    }


@router.post("/missing/confirm")
async def missing_confirm(req: MissingConfirmRequest) -> Dict[str, Any]:
    """매칭 결과 확정 (PRD §13.6 처리 흐름).

    action 처리:
      - "correct"   : SupplementalMaterial.status → converted, MissingMaterial.status → resolved
      - "different" : new_question_id로 재매핑
      - "exclude"   : MissingMaterial.status → rejected
    """
    if req.action == "correct":
        return {
            "supplemental_id": req.supplemental_id,
            "session_id": req.session_id,
            "supplemental_status": "converted",
            "missing_status": "resolved",
            "evidence_ids_added": [f"ev_{uuid.uuid4().hex[:8]}"],
            "_note": "Phase 4-D mock — 실제 Evidence 변환 + MappingResult 재계산은 Phase 4-G",
        }
    elif req.action == "different":
        if not req.new_question_id:
            return {"error": "action=different 시 new_question_id 필수"}
        return {
            "supplemental_id": req.supplemental_id,
            "session_id": req.session_id,
            "supplemental_status": "uploaded",  # 재매핑 위해 다시 분석 대기
            "remapped_to": req.new_question_id,
            "_note": "Phase 4-D mock — 재매핑 후 AI 재분석",
        }
    elif req.action == "exclude":
        return {
            "supplemental_id": req.supplemental_id,
            "session_id": req.session_id,
            "supplemental_status": "uploaded",
            "missing_status": "rejected",
            "_note": "Phase 4-D mock",
        }
    return {"error": f"unknown action: {req.action}"}


@router.post("/reanalyze")
async def reanalyze(
    req: ReanalyzeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """범위별 재분석 (PRD §16.2).

    target enum 7개:
      - notice   : NoticeSchema 재추출 (notice_analyst)
      - form     : FormSchema 재추출 (form_parser)
      - evidence : EvidenceSchema 재추출 (참고자료 chunk 재처리)
      - company  : CompanySchema + FitAnalysis 재계산
      - mapping  : MappingResult 재계산 (RAG)
      - missing  : MissingMaterial 재진단
      - all      : 8 모듈 전체 재호출 (비용 폭주 방지: force=True 필요)

    의존 단계 자동 무효화:
      - notice 재분석 → mapping/missing도 재계산
      - form 재분석 → mapping/missing 재계산
      - evidence 재분석 → mapping/missing 재계산

    A2: drafts_policy 전달 시 ApplicationSession.drafts_preservation_policy 갱신.
        실제 DraftItem 무효화는 v0.2 범위 외 (Phase 5).
    """
    affected = {
        "notice": ["mapping", "missing"],
        "form": ["mapping", "missing"],
        "evidence": ["mapping", "missing"],
        "company": ["fit_analysis"],
        "mapping": ["missing"],
        "missing": [],
        "all": ["notice", "form", "evidence", "company", "mapping", "missing"],
    }

    if req.target == "all" and not req.force:
        return {
            "session_id": req.session_id,
            "target": req.target,
            "status": "confirmation_required",
            "warning": "target=all은 비용 폭주 위험. force=true 필요",
            "estimated_cost_krw": 900,
        }

    # A2: drafts_policy 영속화 (전달된 경우)
    applied_policy = req.drafts_policy
    if applied_policy is not None:
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == req.session_id
        ).first()
        if session:
            session.drafts_preservation_policy = applied_policy
            db.commit()
    else:
        # 미전달 시 기존 session 값 또는 user_choice default
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == req.session_id
        ).first()
        applied_policy = (session.drafts_preservation_policy if session else None) or "user_choice"

    return {
        "session_id": req.session_id,
        "target": req.target,
        "status": "queued",
        "affected_targets": affected.get(req.target, []),
        "drafts_preservation_policy": applied_policy,  # PRD §13.9
        "started_at": datetime.utcnow().isoformat(),
        "_note": "Phase 4-D mock — 실제 비동기 재분석은 Phase 4-G",
    }


# ════════════════════════════════════════════════════════════════════════
# Part C-1 (b7.md §3): PATCH /sessions/{session_id}
#   현재 범위: selected_company_file_ids만 업데이트
#   향후 확장 시 Optional 필드 추가
#
# 정책 (Q5 결정):
#   - extra="forbid": 명시 필드 외 추가 키 → 422
#   - StrictStr: int/None 원소 → 422
#   - null 또는 미지정 → 변경 없음 (no-op)
#   - [] → 빈 배열 저장 (비움)
#   - 중복 제거 (순서 보존)
# ════════════════════════════════════════════════════════════════════════


from pydantic import StrictStr, ConfigDict


class UpdateSessionRequest(BaseModel):
    """PATCH /sessions/{session_id} 요청 모델 (C-1).

    selected_company_file_ids 외 다른 필드는 422 (extra="forbid").
    원소는 StrictStr — int/None 자동 변환 금지.
    """
    model_config = ConfigDict(extra="forbid")
    selected_company_file_ids: Optional[List[StrictStr]] = None


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in items:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: str,
    req: UpdateSessionRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """ApplicationSession 부분 업데이트 (C-1 §3).

    범위:
      - selected_company_file_ids만 (현재 phase)
    정책:
      - null/미지정 → 변경 없음 (no-op)
      - [] → 빈 배열 저장
      - 중복 제거 + 순서 보존
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    if req.selected_company_file_ids is not None:
        normalized = _dedupe_preserve_order(req.selected_company_file_ids)
        session.selected_company_file_ids = normalized
        flag_modified(session, "selected_company_file_ids")
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.exception("[update_session] DB commit 실패 session=%s", session_id)
            raise HTTPException(status_code=500, detail=f"DB commit 실패: {e}")
        committed = normalized
    else:
        # null 또는 미지정 → 변경 없음 (PATCH semantics)
        existing = session.selected_company_file_ids
        committed = existing if isinstance(existing, list) else []

    return {
        "ok": True,
        "session_id": session.session_id,
        "selected_company_file_ids": committed,
    }


@router.patch("/sessions/{session_id}/drafts-policy")
def set_drafts_policy(
    session_id: str,
    req: SetDraftsPolicyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """drafts_preservation_policy 영속화 전용 endpoint (A2, PRD §13.9).

    재분석 실행과 분리 — 모달 선택 시점에 호출, 이후 reanalyze는 별도.
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    session.drafts_preservation_policy = req.drafts_policy
    db.commit()
    return {
        "session_id": session_id,
        "drafts_preservation_policy": session.drafts_preservation_policy,
        "updated_at": datetime.utcnow().isoformat(),
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 4-E: 초안 작성 API 4 endpoint (PRD §16.4)
#   POST /api/analysis/write-draft-item       — 질문별 초안 생성 (draft_writer)
#   POST /api/analysis/rewrite-draft-item     — 초안 재작성 (draft_rewriter)
#   POST /api/analysis/approve-draft-item     — DraftItem.status → approved
#   GET  /api/analysis/draft-items/{session_id} — 질문별 DraftItem 목록
# ════════════════════════════════════════════════════════════════════════


# ─── Request 모델 (Phase 4-E) ──────────────────────────────────────────


class WriteDraftItemRequest(BaseModel):
    """질문별 초안 생성 (draft_writer 호출).

    AnthropicProvider.draft_writer(question, matched_evidence, company_schema,
                                    notice_schema, writing_guidelines, constraints)
    """
    session_id: str
    question: Dict[str, Any]  # {question_id, prompt_text, max_chars, ...}
    matched_evidence: List[Dict[str, Any]] = []
    company_schema: Dict[str, Any] = {}
    notice_schema: Dict[str, Any] = {}
    writing_guidelines: Optional[List[str]] = None
    constraints: Optional[Dict[str, Any]] = None
    request_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


class RewriteDraftItemRequest(BaseModel):
    """초안 재작성 (draft_rewriter 호출 — 사용자 chat 메시지 기반)."""
    session_id: str
    question_id: str
    current_draft: str
    user_message: str
    evidence_list: List[Dict[str, Any]] = []
    request_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


class ApproveDraftItemRequest(BaseModel):
    """DraftItem.status → approved (PRD §13.5).

    승인 시 lock 적용 (재분석 시 drafts_preservation_policy=lock_approved 후보).
    """
    session_id: str
    question_id: str
    draft_item_id: Optional[str] = None  # 명시 시 우선, 없으면 question_id로 조회
    request_id: str = ""
    allow_preconfirm: bool = False   # C-2 (b8.md §3) precheck 예외


# ─── 공통 헬퍼: draft_item을 form_schema_json.draft_items에 저장 ──────────

def _update_draft_item_in_fsj(
    session: ApplicationSession,
    question_id: str,
    updates: Dict[str, Any],
    db: Session,
) -> None:
    """form_schema_json.draft_items에서 question_id 항목을 찾아 updates 적용 후 commit."""
    fsj = dict(session.form_schema_json or {})
    items = fsj.get("draft_items") or []
    if not isinstance(items, list):
        items = []
    now_iso = datetime.utcnow().isoformat()
    found = False
    for item in items:
        if isinstance(item, dict) and item.get("question_id") == question_id:
            item.update(updates)
            item["updated_at"] = now_iso
            found = True
            break
    if not found:
        # skeleton이 없으면 최소 레코드 생성
        new_item = {"question_id": question_id, "created_at": now_iso, "updated_at": now_iso}
        new_item.update(updates)
        items.append(new_item)
    fsj["draft_items"] = items
    session.form_schema_json = fsj
    flag_modified(session, "form_schema_json")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[_update_draft_item_in_fsj] commit 실패 qid=%s session=%s", question_id, session.session_id)
        raise HTTPException(status_code=500, detail=f"초안 저장 실패: {e}")


# ─── Endpoint 4개 (Phase 4-E) ──────────────────────────────────────────


@router.post("/write-draft-item")
async def write_draft_item(
    req: WriteDraftItemRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """질문별 초안 생성 (PRD §16.4).

    내부 흐름:
      1. provider.draft_writer 호출 (Sonnet 기본, Opus는 premium_final_writer 전용)
      2. DraftItem 생성/갱신 (status=draft, version+=1)
      3. cost / token usage 기록 (audit_log)

    Phase 4-E 단계: provider 호출 결과 그대로 반환. DB 저장은 Phase 4-G.
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)

    # 2026-05-18 E-3 정책: session에서 evaluation_rubric + announcement_signals 직접 로드.
    # frontend가 전달 안 해도 backend가 보장 — LLM이 평가기준 기반 작성.
    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    evaluation_rubric = fsj.get("evaluation_rubric") or {}
    announcement_signals = fsj.get("announcement_signals") or {}

    # 2026-05-18: excluded 항목 차단 — 사용자가 "작성 제외" 표시한 항목은 LLM 호출 안 함.
    # PATCH endpoint는 schema.excluded_question_ids에 저장 — 모든 경로 확인.
    qid_excl_check = (req.question or {}).get("question_id", "")
    _schema_excl = (fsj.get("schema") or {}).get("excluded_question_ids") or []
    _confirmed_excl = (fsj.get("confirmed_schema") or {}).get("excluded_question_ids") or []
    _top_excl = fsj.get("excluded_question_ids") or []
    excluded_set = set(_schema_excl) | set(_confirmed_excl) | set(_top_excl)
    if qid_excl_check and qid_excl_check in excluded_set:
        return {
            "session_id": req.session_id,
            "question_id": qid_excl_check,
            "draft_item_id": f"di_{uuid.uuid4().hex[:8]}",
            "status": "excluded",
            "version": 0,
            "result": {
                "draft_id": f"draft_excl_{uuid.uuid4().hex[:8]}",
                "session_id": req.session_id,
                "question_id": qid_excl_check,
                "content": "",
                "table_data": [],
                "used_evidence_ids": [],
                "char_count": 0,
                "status": "excluded",
                "warnings": [{
                    "code": "excluded_no_action",
                    "message": "사용자가 '작성 제외'로 표시한 항목 — LLM 호출 안 함. 직접 작성 가능.",
                }],
                "ai_metadata": {"model": "none", "prompt_version": None, "generated_at": datetime.utcnow().isoformat()},
            },
            "_note": "excluded — no LLM call",
        }

    # 2026-05-18 E-2 통합: matched_evidence를 mapping_pipeline에서 자동 fetch.
    # frontend가 빈 배열 보내도 backend가 mapping result에서 question_id별 evidence 추출 → draft_writer에 전달.
    # E-3 정책 "used_evidence_ids 필수" 충족 보장.
    qid = (req.question or {}).get("question_id", "")
    matched_evidence = list(req.matched_evidence or [])
    if not matched_evidence and qid:
        # mapping_pipeline.results.map_evidence.question_mappings에서 qid 매칭 chunks 가져옴
        mp_results = (fsj.get("mapping_pipeline") or {}).get("results") or {}
        me = mp_results.get("map_evidence") or {}
        for qm in (me.get("question_mappings") or []):
            if qm.get("question_id") == qid:
                # evidence_matcher의 matched_evidence는 chunk shape — evidence shape로 변환
                # (draft_writer의 validate_used_evidence_ids는 evidence_id 키 검증)
                matched_evidence = [
                    {
                        "evidence_id": h.get("chunk_id"),
                        "source_file": h.get("source_file"),
                        "source_page": h.get("page"),
                        "content": h.get("content"),
                        "score": h.get("final_score"),
                        "type": "chunk",
                    }
                    for h in (qm.get("matched_evidence") or [])
                    if isinstance(h, dict) and h.get("chunk_id")
                ]
                break

    provider = get_provider()
    result = await provider.draft_writer(
        question=req.question,
        matched_evidence=matched_evidence,
        company_schema=req.company_schema,
        notice_schema=req.notice_schema,
        writing_guidelines=req.writing_guidelines,
        constraints=req.constraints,
        evaluation_rubric=evaluation_rubric,
        announcement_signals=announcement_signals,
        request_id=req.request_id,
        session_id=req.session_id,
    )
    question_id = req.question.get("question_id", "unknown")
    draft_item_id = f"DI_{question_id}"
    content = result.get("content", "") if isinstance(result, dict) else ""
    table_data = result.get("table_data", []) if isinstance(result, dict) else []
    used_ids = [e.get("evidence_id") for e in matched_evidence if e.get("evidence_id")]
    _update_draft_item_in_fsj(session, question_id, {
        "draft_item_id": draft_item_id,
        "draft_text": content,
        "table_draft_data": table_data,
        "matched_evidence_ids": used_ids,
        "status": "draft",
        "version": 1,
    }, db)
    return {
        "session_id": req.session_id,
        "question_id": question_id,
        "draft_item_id": draft_item_id,
        "status": "draft",
        "version": 1,
        "result": result,
    }


@router.post("/write-draft-item-stream")
async def write_draft_item_stream(
    req: WriteDraftItemRequest,
    db: Session = Depends(get_db),
):
    """write-draft-item 스트리밍 버전 — SSE로 토큰 즉시 전송."""
    from fastapi.responses import StreamingResponse
    import json as _json

    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)

    from prompts import load_prompt
    from services.openai_provider import _build_draft_writer_user_prompt

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    evaluation_rubric = fsj.get("evaluation_rubric") or {}
    announcement_signals = fsj.get("announcement_signals") or {}

    qid = (req.question or {}).get("question_id", "")
    matched_evidence = list(req.matched_evidence or [])
    if not matched_evidence and qid:
        mp_results = (fsj.get("mapping_pipeline") or {}).get("results") or {}
        me = mp_results.get("map_evidence") or {}
        for qm in (me.get("question_mappings") or []):
            if qm.get("question_id") == qid:
                matched_evidence = [
                    {"evidence_id": h.get("chunk_id"), "source_file": h.get("source_file"),
                     "content": h.get("content"), "score": h.get("final_score")}
                    for h in (qm.get("matched_evidence") or []) if isinstance(h, dict) and h.get("chunk_id")
                ]
                break

    system, _ = load_prompt("draft_writer")
    user = _build_draft_writer_user_prompt(
        req.question, matched_evidence, req.company_schema, req.notice_schema,
        req.writing_guidelines, req.constraints,
        evaluation_rubric=evaluation_rubric,
        announcement_signals=announcement_signals,
    )

    provider = get_provider()

    async def event_stream():
        try:
            if hasattr(provider, "_chat_stream"):
                async for chunk in provider._chat_stream(system, user, temperature=0.3, max_tokens=2048):
                    yield f"data: {_json.dumps({'delta': chunk})}\n\n"
            else:
                raw = await provider._chat(system, user, temperature=0.3, max_tokens=2048)
                yield f"data: {_json.dumps({'delta': raw})}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/rewrite-draft-item")
async def rewrite_draft_item(
    req: RewriteDraftItemRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """초안 재작성 (PRD §16.4).

    내부:
      1. provider.draft_rewriter 호출
      2. DraftItem.version += 1, status 유지 (draft)
      3. revision history append
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    provider = get_provider()
    result = await provider.draft_rewriter(
        question_id=req.question_id,
        current_draft=req.current_draft,
        user_message=req.user_message,
        evidence_list=req.evidence_list,
        request_id=req.request_id,
        session_id=req.session_id,
    )
    content = result.get("suggestion") or result.get("content", "") if isinstance(result, dict) else ""
    draft_item_id = f"DI_{req.question_id}"
    _update_draft_item_in_fsj(session, req.question_id, {
        "draft_item_id": draft_item_id,
        "draft_text": content,
        "status": "draft",
    }, db)
    return {
        "session_id": req.session_id,
        "question_id": req.question_id,
        "draft_item_id": draft_item_id,
        "status": "draft",
        "version": 2,
        "result": result,
    }


@router.post("/approve-draft-item")
async def approve_draft_item(
    req: ApproveDraftItemRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """DraftItem 승인 (PRD §13.5 status: draft → approved).

    승인 후:
      - status = approved
      - approved_at 기록
      - 재분석 시 drafts_preservation_policy=lock_approved 후보
    C-2: step2_confirmed gate.
    """
    session = _resolve_session_for_gate(db, req.session_id)
    _require_step2_confirmed(session, allow_preconfirm=req.allow_preconfirm)
    approved_at = datetime.utcnow().isoformat()
    draft_item_id = req.draft_item_id or f"DI_{req.question_id}"
    _update_draft_item_in_fsj(session, req.question_id, {
        "draft_item_id": draft_item_id,
        "status": "approved",
        "approved_at": approved_at,
        "lock_on_reanalyze": True,
    }, db)
    return {
        "session_id": req.session_id,
        "question_id": req.question_id,
        "draft_item_id": draft_item_id,
        "status": "approved",
        "approved_at": approved_at,
        "lock_on_reanalyze": True,
    }


# ════════════════════════════════════════════════════════════════════════
# Part B-3 (b6_b3.md): confirmed_schema → DraftItem skeleton
#   POST /api/analysis/sessions/{session_id}/draft-items/initialize
#   GET  /api/analysis/draft-items/{session_id}  (mock 제거, 실제 조회로 교체)
#
# 저장 정책: JSON MVP (DB migration 금지). form_schema_json["draft_items"]
# Idempotency: status=="empty" + draft_text=="" 일 때만 skeleton 갱신, 그 외 보존
# ════════════════════════════════════════════════════════════════════════


def _build_draft_item_skeleton(
    session_id: str,
    section_id: str,
    question: Dict[str, Any],
    now_iso: str,
) -> Dict[str, Any]:
    """confirmed_schema의 단일 question을 DraftItem skeleton으로 변환 (b6_b3.md §3, §4).

    fill_mode == "table_input" 이면 table_draft 생성 (columns 보존, rows=[]).
    그 외는 일반 text skeleton (draft_text="", table_draft=null).
    """
    fill_mode = question.get("fill_mode")
    is_table = fill_mode == "table_input"
    table_draft = None
    if is_table:
        ts = question.get("table_schema") or {}
        # A-4 다단헤더 columns 보존 (축소 금지 — b6_b3.md §4-2)
        table_draft = {
            "columns": copy.deepcopy(ts.get("columns", []) or []),
            "rows": [],  # row_count 있어도 빈 배열 (실제 값은 채우지 않음)
            "source": "table_schema",
        }
    return {
        "draft_item_id": f"DI_{question.get('question_id')}",
        "session_id": session_id,
        "section_id": section_id,
        "question_id": question.get("question_id"),
        "question_title": question.get("title", "") or "",
        "question_text": question.get("requirement", "") or "",
        "fill_mode": fill_mode,
        "source_page": question.get("source_page"),
        "status": "empty",
        "draft_text": "",
        "table_draft": table_draft,
        # spec 출력 키는 단수형. 입력은 A-3 복수형 fallback.
        "required_evidence_type": (
            question.get("required_evidence_types")
            or question.get("required_evidence_type")
            or []
        ),
        "matched_evidence_ids": [],
        "missing_material_ids": [],
        "created_from": "confirmed_schema",
        "created_at": now_iso,
        "updated_at": now_iso,
    }


def _is_skeleton_replaceable(existing: Dict[str, Any]) -> bool:
    """기존 draft_item이 빈 skeleton 상태인지 (= 사용자 작업 흔적 없음).

    Idempotency policy (b6_b3.md §3 + 의문3 결정):
      status == "empty" AND draft_text == "" AND
      (table_draft is None OR table_draft.rows == [])
    """
    if existing.get("status") != "empty":
        return False
    if (existing.get("draft_text") or "") != "":
        return False
    td = existing.get("table_draft")
    if td is None:
        return True
    if not isinstance(td, dict):
        return False
    if td.get("rows"):  # rows에 데이터가 있으면 보존
        return False
    return True


class InitializeDraftItemsRequest(BaseModel):
    """B-3 initialize 요청. body는 빈 dict로 호출 가능."""
    request_id: str = ""


@router.post("/sessions/{session_id}/draft-items/initialize")
async def initialize_draft_items(
    session_id: str,
    req: InitializeDraftItemsRequest = InitializeDraftItemsRequest(),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """confirmed_schema → DraftItem skeleton 생성 (b6_b3.md §2-1).

    응답 정책:
      - session_not_found → 404
      - Step 3 미준비 → 200 + ok=false + reason
      - 정상 → 200 + ok=true + draft_items 본문
    Idempotency: 같은 question_id에 대해 skeleton-only 상태면 갱신, 사용자 작업 있으면 보존.
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "session_id": session_id,
                "step3_ready": False,
                "reason": "session_not_found",
            },
        )

    # B-2 helper 재사용
    is_ready, reason, confirmed_schema = _evaluate_step3_ready(session)
    if not is_ready:
        return {
            "ok": False,
            "session_id": session_id,
            "step3_ready": False,
            "reason": reason,
        }

    now_iso = datetime.utcnow().isoformat()
    fsj = dict(session.form_schema_json or {})

    # 기존 draft_items를 question_id로 인덱싱
    existing_items = fsj.get("draft_items") or []
    if not isinstance(existing_items, list):
        existing_items = []
    existing_by_qid: Dict[str, Dict[str, Any]] = {
        item.get("question_id"): item
        for item in existing_items
        if isinstance(item, dict) and item.get("question_id")
    }

    new_items: List[Dict[str, Any]] = []
    sections = confirmed_schema.get("sections", []) or []
    for sec in sections:
        section_id = sec.get("section_id") or ""
        for q in (sec.get("questions") or []):
            qid = q.get("question_id")
            if not qid:
                continue
            existing = existing_by_qid.get(qid)
            if existing is not None:
                # 기존 있음 → idempotent 정책 적용
                if _is_skeleton_replaceable(existing):
                    # skeleton-only 상태: created_at 보존, updated_at 갱신
                    fresh = _build_draft_item_skeleton(session_id, section_id, q, now_iso)
                    fresh["created_at"] = existing.get("created_at", now_iso)
                    # updated_at만 갱신 (이미 now_iso로 생성됨)
                    new_items.append(fresh)
                else:
                    # 사용자/AI 작업 흔적 보존 — 변경 없음
                    new_items.append(existing)
            else:
                # 신규 추가
                new_items.append(
                    _build_draft_item_skeleton(session_id, section_id, q, now_iso)
                )

    # form_schema_json 업데이트
    fsj["draft_items"] = new_items
    fsj["draft_items_status"] = "initialized"
    fsj["draft_items_initialized_at"] = now_iso
    session.form_schema_json = fsj
    flag_modified(session, "form_schema_json")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[initialize_draft_items] DB commit 실패 session=%s", session_id)
        raise HTTPException(status_code=500, detail=f"DB commit 실패: {e}")

    text_count = sum(1 for i in new_items if i.get("fill_mode") != "table_input")
    table_count = sum(1 for i in new_items if i.get("fill_mode") == "table_input")

    return {
        "ok": True,
        "session_id": session.session_id,
        "session_status": session.status,
        "current_step": session.current_step,
        "draft_items_status": "initialized",
        "draft_item_count": len(new_items),
        "table_draft_item_count": table_count,
        "text_draft_item_count": text_count,
        "draft_items": new_items,
        "next_step": "step3_draft_write",
    }


@router.get("/draft-items/{session_id}")
async def get_draft_items(
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """세션의 DraftItem 목록 조회 (b6_b3.md §7).

    B-3 이후: form_schema_json["draft_items"]에서 실제 데이터 반환.
    initialize endpoint와 달리 새로 생성하지 않음 (조회 전용).
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "ok": False,
                "session_id": session_id,
                "reason": "session_not_found",
            },
        )

    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    items = fsj.get("draft_items") or []
    if not isinstance(items, list):
        items = []
    status = fsj.get("draft_items_status") or "uninitialized"

    return {
        "ok": True,
        "session_id": session_id,
        "draft_items_status": status,
        "draft_item_count": len(items),
        "draft_items": items,
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 4-F: 분석 확정 / Export (PRD §16.6) — no LLM 정책 (test_03 §3.11.5)
#   POST /api/analysis/confirm-step2 — Step 2 분석 확정
#   POST /api/analysis/export-docx   — Step 5 export (no LLM 게이트)
# ════════════════════════════════════════════════════════════════════════


# ─── Request 모델 (Phase 4-F) ──────────────────────────────────────────


class ConfirmStep2Request(BaseModel):
    """Step 2 분석 확정 (no LLM).

    ApplicationSession.status: analyzing → confirmed
    EvalCriteriaMapping 확정 (mapped_questions 고정).
    이후 Step 3 이동 가능.
    """
    session_id: str
    eval_criteria_mapping_id: Optional[str] = None  # 확정할 매핑 ID
    confirmed_form_schema: Optional[Dict[str, Any]] = None  # 사용자 수정본
    request_id: str = ""


class ExportDocxRequest(BaseModel):
    """Step 5 export (no LLM 정책 게이트, test_03 §3.11.5).

    모든 DraftItem.status = approved 여야 export 가능.
    unapproved 항목 있으면 422 반환.

    Phase 4-F: mock 파일 URL 반환. 실제 docx 생성은 Phase 4-G.
    """
    session_id: str
    include_table_data: bool = True
    request_id: str = ""


# ─── Endpoint 2개 (Phase 4-F) ──────────────────────────────────────────


@router.post("/confirm-step2")
async def confirm_step2(
    req: ConfirmStep2Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Step 2 분석 확정 (PRD §16.6, no LLM).

    Part B-1 (b5.md):
      1. DB session 조회 (없으면 404)
      2. schema 소스: req.confirmed_form_schema → session.form_schema_json["schema"] → 422
      3. deep copy snapshot (shallow copy 금지)
      4. session.form_schema_json["confirmed_schema"] / schema_status / confirmed_at
      5. session.status="step2_confirmed", current_step=3, confirmed_step2_at=now
      6. db.commit()
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == req.session_id
    ).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"session not found: {req.session_id}",
        )

    # schema 소스 선택
    source_schema: Optional[Dict[str, Any]] = None
    if req.confirmed_form_schema:
        source_schema = req.confirmed_form_schema
    else:
        existing = session.form_schema_json or {}
        if isinstance(existing, dict) and existing.get("schema"):
            source_schema = existing["schema"]

    if not source_schema:
        raise HTTPException(
            status_code=422,
            detail="confirmed_form_schema가 없고 session.form_schema_json.schema도 비어있습니다",
        )

    # deep copy snapshot (b5.md: shallow copy 금지)
    confirmed_snapshot = copy.deepcopy(source_schema)
    confirmed_at_iso = datetime.utcnow().isoformat()

    # form_schema_json 업데이트
    form_schema_json = dict(session.form_schema_json or {})
    form_schema_json["confirmed_schema"] = confirmed_snapshot
    form_schema_json["schema_status"] = "confirmed"
    form_schema_json["confirmed_at"] = confirmed_at_iso
    session.form_schema_json = form_schema_json
    flag_modified(session, "form_schema_json")

    # session 필드 업데이트
    session.status = "step2_confirmed"
    session.current_step = 3
    session.confirmed_step2_at = datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("[confirm_step2] DB commit 실패 session=%s", req.session_id)
        raise HTTPException(
            status_code=500,
            detail=f"DB commit 실패: {e}",
        )

    # 응답 집계
    sections = confirmed_snapshot.get("sections", []) or []
    all_questions = [q for s in sections for q in (s.get("questions", []) or [])]
    question_count = len(all_questions)
    section_count = len(sections)
    table_count = sum(
        1 for q in all_questions
        if q.get("fill_mode") == "table_input" or q.get("is_table_item")
    )

    return {
        "ok": True,
        "session_id": session.session_id,
        "session_status": "step2_confirmed",
        "current_step": 3,
        "confirmed_at": confirmed_at_iso,
        "confirmed_schema": confirmed_snapshot,
        "confirmed_schema_question_count": question_count,
        "confirmed_schema_section_count": section_count,
        "confirmed_schema_table_count": table_count,
        "next_step": "step3_draft",
    }


@router.post("/export-docx")
async def export_docx(req: ExportDocxRequest) -> Dict[str, Any]:
    """Step 5 export (PRD §16.6, no LLM 게이트 — test_03 §3.11.5).

    no LLM 정책: export 자체에 AI 호출 없음.
    unapproved DraftItem 존재 시 422 반환 (Phase 4-G에서 DB 검증).

    Phase 4-F: mock 파일 URL 반환. 실제 python-docx 생성은 Phase 4-G.
    """
    export_id = f"exp_{uuid.uuid4().hex[:8]}"
    return {
        "session_id": req.session_id,
        "export_id": export_id,
        "status": "ready",
        "file_url": f"/api/files/export/{export_id}.docx",  # Phase 4-G에서 실제 파일 서빙
        "file_name": f"사업계획서_{req.session_id}_{export_id}.docx",
        "exported_at": datetime.utcnow().isoformat(),
        "include_table_data": req.include_table_data,
        "unapproved_items": [],  # Phase 4-G에서 DB 조회 후 비어있지 않으면 422
        "_note": "Phase 4-F mock — no LLM. 실제 docx 생성(python-docx)은 Phase 4-G",
    }


# ════════════════════════════════════════════════════════════════════════
# Phase 4-H A1: Step 1 multipart 파일 업로드 (영속화)
#
# storage 모델: JSON-piggyback
#   notice → ApplicationSession.notice_schema_json["attachments"]
#   form   → ApplicationSession.form_schema_json["attachments"]
#
# 저장 내용: 메타데이터 + 추출 텍스트 (원본 bytes 폐기)
#   - file_id, file_name, ext, size_bytes, uploaded_at
#   - parsed_text (≤10K char), parse_success, warning
#
# A3에서 정식 SessionAttachment 테이블 + 디스크 BLOB로 승격 예정.
# references는 A3 범위 (현재 미지원).
# ════════════════════════════════════════════════════════════════════════


_FILE_KIND_TO_FIELD = {
    "notice": "notice_schema_json",
    "form": "form_schema_json",
    # C-1 (b7.md §2-1): reference 파일은 form_schema_json["reference_attachments"]에 저장
    "reference": "form_schema_json",
}

# C-1 (b7.md §Q4): list_files 무필터 시 기본 kind 목록 (기존 계약 보존).
# reference는 명시적으로 kind=reference 호출 시만 반환됨.
_DEFAULT_LIST_KINDS = ("notice", "form")


def _attachments_subkey(kind: str) -> str:
    """kind별 form_schema_json 내 sub-key (b7.md §2-1).

    notice/form → "attachments" (기존)
    reference  → "reference_attachments" (C-1 신규)
    """
    return "reference_attachments" if kind == "reference" else "attachments"


def _get_attachments(session: ApplicationSession, kind: str) -> list:
    field = _FILE_KIND_TO_FIELD[kind]
    schema = getattr(session, field) or {}
    return schema.get(_attachments_subkey(kind), [])


def _set_attachments(session: ApplicationSession, kind: str, items: list) -> None:
    field = _FILE_KIND_TO_FIELD[kind]
    schema = dict(getattr(session, field) or {})
    schema[_attachments_subkey(kind)] = items
    setattr(session, field, schema)
    flag_modified(session, field)  # SQLAlchemy JSON mutation 감지


def _build_layout_aware_text(items: list) -> tuple[str, dict, list]:
    """form 첨부파일 목록에서 raw_b64 → layout_builder → semantic markdown 생성.

    A-1.5 (P-5): FORM_LAYOUT_TEXT_SAFETY_CAP 적용, page boundary 기준 truncation.
    A-3: fallback_reason 추가 — 호출자가 parser_mode / fallback_used 판단에 사용.
    A-4-4: layout_pages 추가 반환 — table_normalizer/promoter 입력으로 사용.
    반환: (text, meta, layout_pages).
      text="" 이면 호출자가 parsed_text fallback 처리.
      layout_pages=[] 이면 layout-aware 실패 (normalize/promote 스킵).
    """
    import base64
    import tempfile
    from pathlib import Path
    from services.form_layout_builder import build_layout_for_pdf
    from services.form_llm_input_builder import build_llm_input_for_page

    _empty_meta: dict = {
        "layout_text_original_chars": 0,
        "layout_text_returned_chars": 0,
        "layout_text_truncated": False,
        "truncated_after_page": None,
        "omitted_page_count": 0,
        "pages_total": 0,
        "pages_included": 0,
        "layout_text_safety_cap": FORM_LAYOUT_TEXT_SAFETY_CAP,
        "fallback_reason": None,
    }

    has_any_raw_b64 = any(it.get("raw_b64") for it in items)
    if not has_any_raw_b64:
        meta = dict(_empty_meta)
        meta["fallback_reason"] = "missing_raw_b64"
        return "", meta, []

    last_error_reason = "layout_builder_error"

    for it in items:
        raw_b64 = it.get("raw_b64")
        if not raw_b64:
            continue
        try:
            pdf_bytes = base64.b64decode(raw_b64)
            with tempfile.TemporaryDirectory() as tmp:
                lr = build_layout_for_pdf(
                    pdf_bytes=pdf_bytes,
                    out_dir=Path(tmp),
                    file_id=it.get("file_id", ""),
                    file_name=it.get("file_name", ""),
                )

            pages = lr["pages"]
            pages_total = len(pages)

            # page boundary truncation
            page_mds: list[str] = []
            total_chars = 0
            pages_included = 0
            truncated_after_page = None
            omitted_page_count = 0

            for page_data in pages:
                page_md = build_llm_input_for_page(page_data)
                if total_chars + len(page_md) > FORM_LAYOUT_TEXT_SAFETY_CAP:
                    truncated_after_page = pages_included
                    omitted_page_count = pages_total - pages_included
                    break
                page_mds.append(page_md)
                total_chars += len(page_md)
                pages_included += 1

            original_chars = sum(len(build_llm_input_for_page(p)) for p in pages)
            combined = "\n\n".join(page_mds)

            if not combined.strip():
                last_error_reason = "empty_layout_text"
                continue

            meta = {
                "layout_text_original_chars": original_chars,
                "layout_text_returned_chars": total_chars,
                "layout_text_truncated": truncated_after_page is not None,
                "truncated_after_page": truncated_after_page,
                "omitted_page_count": omitted_page_count,
                "pages_total": pages_total,
                "pages_included": pages_included,
                "layout_text_safety_cap": FORM_LAYOUT_TEXT_SAFETY_CAP,
                "fallback_reason": None,
            }

            logger.info(
                "[parse_form] layout-aware 성공: %d/%d pages, %d chars%s",
                pages_included,
                pages_total,
                total_chars,
                f" (cap 적용: {omitted_page_count}p 생략)" if truncated_after_page is not None else "",
            )
            # A-4-4: layout_pages는 truncation 적용된 페이지만 반환 (normalizer 입력)
            return combined, meta, pages[:pages_included]

        except Exception as e:
            logger.warning("[parse_form] layout_builder 실패, fallback 진행: %s", e)
            last_error_reason = "layout_builder_error"

    meta = dict(_empty_meta)
    meta["fallback_reason"] = last_error_reason
    return "", meta, []


# ─── A-2: Quality gate helpers ────────────────────────────────────────────

def _count_page_markers(form_text: str) -> int:
    """form_text 내 '=== PAGE N ===' 마커 수 반환 (page_count 추정용)."""
    import re
    return len(re.findall(r"=== PAGE \d+ ===", form_text or ""))


def _compute_form_quality_metrics(
    schema_result: dict, form_text: str, page_count: int = 0
) -> dict:
    """parse-form 결과의 품질 지표 계산 및 repair 필요 여부 판단.

    A-3: page_count 기반 동적 gate 기준.
      page_count >= 20 (대형): question_count<40 OR table_count<10 → repair
      page_count < 20  (소형): 구조 누락(missing_source_page/fill_mode)만 → repair
        question_count<40 / table_count<10 단독으로 실패 금지
    """
    import re

    sections = schema_result.get("sections", []) or []
    all_questions = [q for s in sections for q in (s.get("questions", []) or [])]

    question_count = len(all_questions)
    table_questions = [
        q for q in all_questions
        if q.get("fill_mode") == "table_input" or q.get("is_table_item")
    ]
    table_count = len(table_questions)
    # A-4-4 (§3.9): LLM 추출 vs promoter 보정 분리
    promoted_table_count = sum(
        1 for q in table_questions
        if q.get("source_type") == "layout_table_promoted"
    )
    llm_table_count = table_count - promoted_table_count
    missing_source_page = sum(
        1 for q in all_questions
        if not q.get("source_page") and q.get("source_type") != "user_added"
    )
    missing_fill_mode = sum(1 for q in all_questions if not q.get("fill_mode"))

    empty_field_tags = len(re.findall(r"<EMPTY_FIELD", form_text or ""))
    unmapped_empty_field_count = max(0, empty_field_tags - question_count)

    # table 후보 탐지 (GFM 테이블 구분자)
    has_table_candidate = bool(re.search(r"\|[-:]+\|", form_text or ""))

    if page_count >= 20:
        # 대형 문서: 기존 엄격 기준
        needs_repair = (
            question_count < 40
            or table_count < 10
            or missing_source_page > 0
            or missing_fill_mode > 0
        )
    else:
        # 소형 문서: 구조 누락만 repair, question_count/table_count 단독 실패 금지
        needs_repair = (
            missing_source_page > 0
            or missing_fill_mode > 0
            or (has_table_candidate and table_count == 0)
        )

    return {
        "question_count": question_count,
        "table_count": table_count,
        # A-4-4 (§3.9): LLM 품질 가시화를 위해 분리 카운트
        "llm_table_count": llm_table_count,
        "promoted_table_count": promoted_table_count,
        "missing_source_page": missing_source_page,
        "missing_fill_mode": missing_fill_mode,
        "empty_field_tag_count": empty_field_tags,
        "unmapped_empty_field_count": unmapped_empty_field_count,
        "has_table_candidate": has_table_candidate,
        "page_count_used": page_count,
        "needs_repair": needs_repair,
        "repaired": False,
    }


def _extract_suspect_pages(form_text: str, schema_result: dict, metrics: dict) -> str:
    """repair pass 대상: 기존 questions에 없는 source_page 또는 EMPTY_FIELD 밀집 구간 추출."""
    import re

    if not form_text:
        return ""

    sections = schema_result.get("sections", []) or []
    covered_pages = {
        q.get("source_page")
        for s in sections
        for q in (s.get("questions", []) or [])
        if q.get("source_page")
    }

    # PAGE N 블록 분리
    page_blocks: list[tuple[int, str]] = []
    for m in re.finditer(r"=== PAGE (\d+) ===", form_text):
        page_num = int(m.group(1))
        start = m.end()
        next_m = re.search(r"=== PAGE \d+ ===", form_text[start:])
        block = form_text[start: start + next_m.start()] if next_m else form_text[start:]
        page_blocks.append((page_num, block))

    suspect_parts: list[str] = []
    for page_num, block in page_blocks:
        has_empty_field = "<EMPTY_FIELD" in block
        not_covered = page_num not in covered_pages
        if has_empty_field or (not_covered and block.strip()):
            suspect_parts.append(f"=== PAGE {page_num} ===\n{block}")

    return "\n".join(suspect_parts)


_REPAIR_PATCHABLE_FIELDS = {"source_page", "fill_mode", "table_schema", "profile_mapping"}


def _merge_repair_schema(base: dict, repair: dict) -> dict:
    """repair 결과를 base에 병합.

    A-3 merge 정책:
    1. 기존 question_id 유지 (삭제/변경 금지)
    2. 기존 값이 있고 repair 값이 충돌하면 기존 값 우선
    3. 기존 값이 null/empty이고 repair 값이 있으면 repair 값으로 보정
    4. 신규 question은 추가
    5. 기존 question_id 삭제/변경 금지
    """
    base_sections = base.get("sections", []) or []
    repair_sections = repair.get("sections", []) or []

    # 기존 question_id → question 객체 맵 (null/empty 필드 보정용)
    existing_q_map: dict = {
        q.get("question_id"): q
        for s in base_sections
        for q in (s.get("questions", []) or [])
        if q.get("question_id")
    }
    existing_ids = set(existing_q_map.keys())

    added = 0
    patched = 0

    for r_section in repair_sections:
        r_sid = r_section.get("section_id")
        new_questions = []

        for r_q in (r_section.get("questions", []) or []):
            r_qid = r_q.get("question_id")
            if not r_qid:
                continue

            if r_qid in existing_ids:
                # 기존 question: null/empty 필드만 보정
                base_q = existing_q_map[r_qid]
                for field in _REPAIR_PATCHABLE_FIELDS:
                    if field in r_q and r_q[field] is not None and r_q[field] != "":
                        if not base_q.get(field):
                            base_q[field] = r_q[field]
                            patched += 1
            else:
                # 신규 question
                new_questions.append(r_q)

        if not new_questions:
            continue

        matched = next((s for s in base_sections if s.get("section_id") == r_sid), None)
        if matched:
            matched.setdefault("questions", []).extend(new_questions)
        else:
            base_sections.append({**r_section, "questions": new_questions})

        for q in new_questions:
            existing_ids.add(q["question_id"])
        added += len(new_questions)

    base["sections"] = base_sections
    logger.info(
        "[parse_form] repair merge: %d new questions added, %d fields patched",
        added, patched,
    )
    return base


def _log_repair_call(db: "Session", session_id: str, request_id: str) -> None:
    """ai_call_logs에 form_parser_repair 태스크 타입으로 최소 기록."""
    import json as _json
    try:
        log_entry = AICallLog(
            run_id=str(uuid.uuid4()),
            request_id=(request_id + "_repair") if request_id else str(uuid.uuid4()),
            task_type="form_parser_repair",
            input_objects=None,
            output_object=None,
            prompt_version=None,
            model_provider=None,
            model_name=None,
            input_hash=None,
            input_preview=f"session_id={session_id}",
            output_json=None,
            raw_output=None,
            status="success",
            error_message=None,
            duration_ms=0,
            token_usage_json=None,
            cost_estimate_krw=None,
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.warning("[parse_form] repair log 기록 실패: %s", e)
        db.rollback()


@router.post("/files/upload")
async def upload_file(
    session_id: str = Form(...),
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Step 1 파일 업로드 (notice / form / reference).

    multipart/form-data — kind ∈ {notice, form, reference}.
    parse-file 로직 재사용해 텍스트 추출 + JSON-piggyback 영속화.
    C-1: reference kind 추가. reference는 raw_b64 미저장 (보안 + 용량).
    """
    if kind not in _FILE_KIND_TO_FIELD:
        raise HTTPException(
            status_code=422,
            detail=f"kind는 notice/form/reference 중 하나여야 합니다: {kind}",
        )

    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    content = await file.read()
    parsed = parse_upload_bytes(file.filename or "", content)

    file_id = f"f_{uuid.uuid4().hex[:12]}"
    uploaded_at_iso = datetime.utcnow().isoformat()

    if kind == "reference":
        # C-1 (b7.md §2-3): reference는 raw_b64 미저장, parse_status/text_preview/metadata 추가
        parsed_text = parsed["parsed_text"] or ""
        text_preview = parsed_text[:300] if parsed_text else ""
        attachment = {
            "file_id": file_id,
            "kind": "reference",
            "file_name": parsed["filename"],
            "ext": parsed["ext"],
            "size_bytes": parsed["size_bytes"],
            "size_kb": parsed["size_kb"],
            "content_type": file.content_type or "",
            "parsed_text": parsed_text,
            "char_count": parsed["char_count"],
            "parsed_text_stored_char_count": parsed["parsed_text_stored_char_count"],
            "parsed_text_truncated": parsed["parsed_text_truncated"],
            "parse_success": parsed["parse_success"],
            "parse_status": "parsed" if parsed["parse_success"] else "parse_failed",
            "warning": parsed["warning"],
            "text_preview": text_preview,
            "metadata": {},
            "uploaded_at": uploaded_at_iso,
            "source": "upload",
            # raw_b64 명시 미저장 (b7.md §2-3 raw binary 저장 금지)
        }

        # form_schema_json["reference_attachments"]에 중복 방지 append
        items = _get_attachments(session, "reference")
        existing_ids = {it.get("file_id") for it in items if isinstance(it, dict)}
        if file_id not in existing_ids:
            items.append(attachment)
            _set_attachments(session, "reference", items)

        # session.reference_file_ids 갱신 (None → [] 정규화, 중복 방지)
        ref_ids = session.reference_file_ids
        if not isinstance(ref_ids, list):
            ref_ids = []
        if file_id not in ref_ids:
            ref_ids = list(ref_ids) + [file_id]
        session.reference_file_ids = ref_ids
        flag_modified(session, "reference_file_ids")

        db.commit()

        return {
            "ok": True,
            "session_id": session_id,
            "kind": "reference",
            "file_id": file_id,
            "file_name": attachment["file_name"],
            "ext": attachment["ext"],
            "size_bytes": attachment["size_bytes"],
            "parse_success": attachment["parse_success"],
            "parse_status": attachment["parse_status"],
            "warning": attachment["warning"],
            "char_count": attachment["char_count"],
            "parsed_text_stored_char_count": attachment["parsed_text_stored_char_count"],
            "parsed_text_truncated": attachment["parsed_text_truncated"],
            "uploaded_at": attachment["uploaded_at"],
            "reference_file_ids": ref_ids,
            "reference_attachment_count": len(items),
        }

    # notice / form: 기존 흐름 (raw bytes를 base64로 attachment에 저장 — PDF 미리보기용)
    import base64
    RAW_BYTES_MAX = 10 * 1024 * 1024  # 10MB 제한
    raw_b64 = (
        base64.b64encode(content).decode("ascii")
        if len(content) <= RAW_BYTES_MAX else None
    )
    attachment = {
        "file_id": file_id,
        "kind": kind,
        "file_name": parsed["filename"],
        "ext": parsed["ext"],
        "size_bytes": parsed["size_bytes"],
        "size_kb": parsed["size_kb"],
        # parsed_text 전체 (≤200K) + truncation 메타 — preview(`text`)는 저장 안 함
        "parsed_text": parsed["parsed_text"],
        "char_count": parsed["char_count"],
        "parsed_text_stored_char_count": parsed["parsed_text_stored_char_count"],
        "parsed_text_truncated": parsed["parsed_text_truncated"],
        "parse_success": parsed["parse_success"],
        "warning": parsed["warning"],
        "uploaded_at": uploaded_at_iso,
        # raw bytes — base64 (10MB 미만만). 다운로드 endpoint에서 사용. list_files에는 미포함.
        "raw_b64": raw_b64,
    }

    items = _get_attachments(session, kind)
    items.append(attachment)
    _set_attachments(session, kind, items)
    db.commit()

    return {
        "session_id": session_id,
        "kind": kind,
        "file_id": file_id,
        "file_name": attachment["file_name"],
        "ext": attachment["ext"],
        "size_bytes": attachment["size_bytes"],
        "parse_success": attachment["parse_success"],
        "warning": attachment["warning"],
        "char_count": attachment["char_count"],
        "parsed_text_stored_char_count": attachment["parsed_text_stored_char_count"],
        "parsed_text_truncated": attachment["parsed_text_truncated"],
        "uploaded_at": attachment["uploaded_at"],
    }


class UploadFromUrlRequest(BaseModel):
    session_id: str
    kind: str = "notice"
    url: str
    filename: str = ""


@router.post("/files/upload-from-url")
async def upload_file_from_url(
    req: UploadFromUrlRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """외부 URL 파일을 backend가 직접 다운로드 → 세션에 저장 (공고 원문 자동 불러오기).

    JSON body: {session_id, kind, url, filename(선택)}
    """
    import httpx, base64
    from urllib.parse import urlparse, unquote

    if req.kind not in _FILE_KIND_TO_FIELD:
        raise HTTPException(status_code=422, detail=f"kind는 notice/form/reference 중 하나여야 합니다: {req.kind}")

    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == req.session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {req.session_id}")

    url = req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=422, detail=f"유효한 http(s) URL이 필요합니다: {url[:80]}")

    filename = req.filename.strip()
    if not filename:
        path = urlparse(url).path
        filename = unquote(path.rsplit("/", 1)[-1]) or "공고문"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"Referer": "https://www.bizinfo.go.kr/"})
            resp.raise_for_status()
            content = resp.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"파일 다운로드 실패: {e}")

    parsed = parse_upload_bytes(filename, content)
    file_id = f"f_{uuid.uuid4().hex[:12]}"
    uploaded_at_iso = datetime.utcnow().isoformat()
    RAW_BYTES_MAX = 10 * 1024 * 1024
    raw_b64 = base64.b64encode(content).decode("ascii") if len(content) <= RAW_BYTES_MAX else None

    attachment = {
        "file_id": file_id,
        "kind": req.kind,
        "file_name": parsed["filename"],
        "ext": parsed["ext"],
        "size_bytes": parsed["size_bytes"],
        "size_kb": parsed["size_kb"],
        "parsed_text": parsed["parsed_text"],
        "char_count": parsed["char_count"],
        "parsed_text_stored_char_count": parsed["parsed_text_stored_char_count"],
        "parsed_text_truncated": parsed["parsed_text_truncated"],
        "parse_success": parsed["parse_success"],
        "warning": parsed["warning"],
        "uploaded_at": uploaded_at_iso,
        "raw_b64": raw_b64,
        "source": "auto_url",
        "source_url": url,
    }

    items = _get_attachments(session, req.kind)
    items.append(attachment)
    _set_attachments(session, req.kind, items)
    db.commit()

    return {
        "ok": True,
        "session_id": req.session_id,
        "kind": req.kind,
        "file_id": file_id,
        "file_name": parsed["filename"],
        "size_bytes": parsed["size_bytes"],
        "size_kb": parsed["size_kb"],
        "ext": parsed["ext"],
        "char_count": parsed["char_count"],
        "parsed_text_stored_char_count": parsed["parsed_text_stored_char_count"],
        "parsed_text_truncated": parsed["parsed_text_truncated"],
        "parse_success": parsed["parse_success"],
        "warning": parsed["warning"],
        "uploaded_at": uploaded_at_iso,
    }


@router.get("/files")
def list_files(
    session_id: str,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Session에 영속된 attachments 목록 (복원용).

    kind 미지정 시 notice + form 반환 (기존 계약 보존, C-1 §Q4).
    reference는 명시적으로 kind=reference 호출 시만 반환.
    parsed_text는 포함 (Step 2 parse-notice/parse-form에 그대로 사용 가능).
    """
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    if kind is not None and kind not in _FILE_KIND_TO_FIELD:
        raise HTTPException(
            status_code=422,
            detail=f"kind는 notice/form/reference 중 하나여야 합니다: {kind}",
        )

    # 무필터 시 _DEFAULT_LIST_KINDS만 — reference 자동 포함 방지 (기존 계약 보존)
    kinds = [kind] if kind else list(_DEFAULT_LIST_KINDS)
    result = {}
    total = 0
    for k in kinds:
        items = _get_attachments(session, k)
        # raw_b64는 응답에서 제외 (응답 크기 폭발 방지). 별도 다운로드 endpoint 사용.
        clean_items = [{kk: vv for kk, vv in it.items() if kk != "raw_b64"} for it in items]
        result[k] = clean_items
        total += len(clean_items)

    return {
        "session_id": session_id,
        "total": total,
        "items": result,
    }


@router.get("/files/{file_id}/raw")
def download_file_raw(
    file_id: str,
    session_id: str,
    db: Session = Depends(get_db),
):
    """attachment의 raw bytes 응답 (PDF 미리보기 등에서 사용).

    attachment에 raw_b64로 저장된 base64 디코딩 후 binary 응답.
    파일이 너무 크면 (>10MB) 업로드 시 raw_b64=None 저장 → 404 반환.
    """
    import base64
    from fastapi.responses import Response

    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    for k in _FILE_KIND_TO_FIELD.keys():
        for it in _get_attachments(session, k):
            if it.get("file_id") == file_id:
                raw_b64 = it.get("raw_b64")
                if not raw_b64:
                    raise HTTPException(
                        status_code=404,
                        detail="raw bytes 미저장 (파일이 10MB 초과이거나 구 버전 업로드)",
                    )
                content = base64.b64decode(raw_b64)
                ext = (it.get("ext") or "").lower()
                ct = {
                    ".pdf": "application/pdf",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".csv": "text/csv",
                }.get(ext, "application/octet-stream")
                return Response(content=content, media_type=ct)

    raise HTTPException(status_code=404, detail=f"file not found: {file_id}")


@router.post("/build-form-layout")
def build_form_layout(
    session_id: str,
    file_id: str,
    page: Optional[int] = None,   # 특정 페이지만 처리 (1-based). None이면 전체.
    db: Session = Depends(get_db),
):
    """FormParser v2 — P1 검증용. Layout IR + LLM Input + debug 산출물 생성.

    FORM_PARSER_DEBUG=true 일 때만 활성. 디스크에 산출물 저장.

    Returns:
        {
            "session_id": ..., "file_id": ..., "out_dir": ...,
            "page_count": N, "pages_processed": [...],
            "artifacts": {"page_N": {"layout": ..., "tables_md": ..., "visual": ..., "llm_input": ...}},
            "source_map": ..., "combined_llm_input": ...,
        }
    """
    import os
    import base64
    from pathlib import Path

    if os.getenv("FORM_PARSER_DEBUG", "").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="FORM_PARSER_DEBUG=true 환경변수 필요",
        )

    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    # attachment에서 raw bytes 가져오기 (form / notice 어디든 OK)
    raw_b64 = None
    file_name = ""
    found_kind = None
    for k in _FILE_KIND_TO_FIELD.keys():
        for it in _get_attachments(session, k):
            if it.get("file_id") == file_id:
                raw_b64 = it.get("raw_b64")
                file_name = it.get("file_name") or ""
                found_kind = k
                break
        if raw_b64 is not None:
            break
    if not raw_b64:
        raise HTTPException(
            status_code=404,
            detail=f"file raw bytes not found for {file_id} (10MB 초과 또는 구버전 업로드)",
        )

    pdf_bytes = base64.b64decode(raw_b64)

    # 출력 디렉토리
    out_dir = Path(f"data/sessions/{session_id}/debug/form_parser")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Layout IR Builder
    from services.form_layout_builder import build_layout_for_pdf
    from services.form_llm_input_builder import build_llm_inputs_for_pdf

    layout_result = build_layout_for_pdf(
        pdf_bytes=pdf_bytes,
        out_dir=out_dir,
        file_id=file_id,
        file_name=file_name,
    )

    # 2. LLM Input Builder
    pages_to_process = layout_result["pages"]
    if page is not None:
        pages_to_process = [p for p in pages_to_process if p["page_number"] == page]
        if not pages_to_process:
            raise HTTPException(status_code=404, detail=f"page {page} not in PDF (총 {layout_result['page_count']}p)")

    llm_inputs = build_llm_inputs_for_pdf(pages_to_process, out_dir)

    # 페이지별 artifacts 통합
    artifacts = {}
    for p_layout in pages_to_process:
        n = p_layout["page_number"]
        key = f"page_{n}"
        artifacts[key] = {
            **layout_result["artifacts"].get(key, {}),
            "llm_input": llm_inputs.get(key, {}).get("path"),
            "llm_input_size": llm_inputs.get(key, {}).get("size_chars"),
            "raw_counts": p_layout.get("raw"),
            "block_count": len(p_layout.get("blocks", [])),
        }

    return {
        "session_id": session_id,
        "file_id": file_id,
        "file_name": file_name,
        "kind": found_kind,
        "out_dir": str(out_dir),
        "page_count_total": layout_result["page_count"],
        "pages_processed": [p["page_number"] for p in pages_to_process],
        "artifacts": artifacts,
        "source_map": layout_result["source_map_path"],
        "combined_llm_input": llm_inputs.get("_combined", {}).get("path"),
    }


@router.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    session_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """attachment 단일 삭제 (UI에서 X 버튼)."""
    session = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    for k in _FILE_KIND_TO_FIELD.keys():
        items = _get_attachments(session, k)
        new_items = [a for a in items if a.get("file_id") != file_id]
        if len(new_items) != len(items):
            _set_attachments(session, k, new_items)
            db.commit()
            return {"session_id": session_id, "file_id": file_id, "deleted": True, "kind": k}

    return {"session_id": session_id, "file_id": file_id, "deleted": False}
