"""
C-3 — BackgroundTasks mapping pipeline.

Step 2 확정 후 mapping pipeline을 backend에서 비동기로 5단계 실행한다.

5단계:
  1. analyze_company
  2. extract_evidence
  3. map_evidence
  4. map_eval_criteria
  5. check_missing

저장: session.form_schema_json["mapping_pipeline"]

핵심 정책:
  - BackgroundTask 내부에서 새 DB session (SessionLocal()) 사용
  - 각 단계 완료 시 commit (status 전이 기록)
  - 사용자 보강 #1: status="running"이면 중복 task 차단 (endpoint 진입부에서 처리)
  - 사용자 보강 #3: retry 시 done 단계 skip, failed_step부터 재실행
  - 사용자 보강 #5: announcement_signals / evaluation_rubric을 context에 포함

금지:
  - frontend polling 구현 (이번 phase 외)
  - Evidence Mapping 고도화 / RAG / embedding / draft_writer / evaluator
  - DB migration
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm.attributes import flag_modified

from database import SessionLocal
from models import ApplicationSession
from services.ai_provider import get_provider, call_with_retry

logger = logging.getLogger(__name__)


# 5단계 순서 (발주문 §"pipeline 단계")
PIPELINE_STEPS = (
    "analyze_company",
    "extract_evidence",
    "map_evidence",
    "map_eval_criteria",
    "check_missing",
)


def init_mapping_pipeline(now_iso: Optional[str] = None) -> Dict[str, Any]:
    """초기 mapping_pipeline 구조 (status=running, 모든 step=pending).

    저장 구조는 발주문 §"저장 구조" + Q1 권장(results 추가) 반영.
    """
    if now_iso is None:
        now_iso = datetime.utcnow().isoformat()
    return {
        "status": "running",
        "started_at": now_iso,
        "completed_at": None,
        "steps": {step: "pending" for step in PIPELINE_STEPS},
        "failed_step": None,
        "error_message": None,
        "results": {step: None for step in PIPELINE_STEPS},
    }


def _collect_context(session: ApplicationSession) -> Dict[str, Any]:
    """pipeline 입력 context 수집 (발주문 §"pipeline 입력" + 보강 #5).

    보강 #5: announcement_signals / evaluation_rubric 포함.
    """
    fsj = session.form_schema_json or {}
    if not isinstance(fsj, dict):
        fsj = {}
    nsj = session.notice_schema_json or {}
    if not isinstance(nsj, dict):
        nsj = {}

    selected = session.selected_company_file_ids
    if not isinstance(selected, list):
        selected = []

    # 2026-05-18: confirmed_schema에서 excluded_question_ids 필터링
    # 사용자가 "작성 제외" 표시한 항목은 mapping/draft에서 완전 skip
    # PATCH endpoint는 form_schema_json.schema 또는 confirmed_schema 에 저장 — 둘 다 확인
    confirmed = fsj.get("confirmed_schema") or {}
    schema_excl = (fsj.get("schema") or {}).get("excluded_question_ids") or []
    confirmed_excl = confirmed.get("excluded_question_ids") or []
    top_excl = fsj.get("excluded_question_ids") or []
    excluded_ids = set(schema_excl) | set(confirmed_excl) | set(top_excl)
    if excluded_ids and isinstance(confirmed, dict) and confirmed.get("sections"):
        import copy
        confirmed = copy.deepcopy(confirmed)
        for sec in confirmed.get("sections") or []:
            sec["questions"] = [
                q for q in (sec.get("questions") or [])
                if q.get("question_id") not in excluded_ids
            ]

    return {
        "confirmed_schema": confirmed,
        "draft_items": fsj.get("draft_items") or [],
        "reference_attachments": fsj.get("reference_attachments") or [],
        "selected_company_file_ids": selected,
        # C-1.5
        "announcement_signals": fsj.get("announcement_signals") or {},
        # C-1.6
        "evaluation_rubric": fsj.get("evaluation_rubric") or {},
        # notice
        "notice_schema": nsj.get("schema") or {},
        # NOAPI-P3 D3: company_profile_input — JSON 저장. 값 없으면 None.
        "company_profile_input": fsj.get("company_profile_input"),
        # NOAPI-P3: session_id 노출 (resolver 입력)
        "_session_id": session.session_id,
        # 2026-05-18: excluded list — matcher/draft_writer가 추가 참조 가능
        "excluded_question_ids": list(excluded_ids),
    }


def _save_pipeline(db, session: ApplicationSession, pipeline: Dict[str, Any]) -> None:
    """form_schema_json["mapping_pipeline"]에 pipeline 저장 + commit."""
    fsj = dict(session.form_schema_json or {})
    fsj["mapping_pipeline"] = pipeline
    session.form_schema_json = fsj
    flag_modified(session, "form_schema_json")
    db.commit()


# ────────────────────────────────────────────────────────────────────
# 5단계 실행 (각 step은 async, provider 메서드 호출)
# ────────────────────────────────────────────────────────────────────

async def _step_analyze_company(context: Dict[str, Any], provider) -> Dict[str, Any]:
    """analyze_company step.

    NOAPI-P3 변경:
      - selected_company_file_ids → resolver로 parsed_text 포함 company_context 변환
      - call_with_retry로 retry 정책 격리 (D2 — pipeline 외부 무영향)
      - mock provider는 insufficient_company_data raise하지 않음 (mock fallback safety)
      - real provider만 insufficient_company_data → NonRetryableError raise
    """
    from services.company_context_resolver import resolve_company_context

    # mock fallback safety: provider_name="mock"이면 raise 안 함 (회귀 보호)
    is_mock = getattr(provider, "provider_name", "mock") == "mock"

    # 2026-05-18 디버그: fallback 작동 검증용
    _refs = context.get("reference_attachments") or []
    logger.warning(
        "[DEBUG_FALLBACK] _step_analyze_company entry: refs=%d, selected_company_file_ids=%s, profile_input=%s",
        len(_refs),
        context.get("selected_company_file_ids"),
        bool(context.get("company_profile_input")),
    )
    for i, r in enumerate(_refs):
        logger.warning(
            "[DEBUG_FALLBACK]   ref[%d]: name=%s, parsed_text_chars=%d, parse_success=%s",
            i,
            (r or {}).get("file_name"),
            len((r or {}).get("parsed_text") or ""),
            (r or {}).get("parse_success"),
        )

    db = SessionLocal()
    try:
        company_context = resolve_company_context(
            db=db,
            session_id=context.get("_session_id") or "",
            company_profile_input=context.get("company_profile_input"),
            selected_company_file_ids=context.get("selected_company_file_ids") or [],
            # 2026-05-18: 참고자료 슬롯에 올라온 회사정보 fallback
            # (Step 1 카드 4번 "기업프로필 자료" v0.3 페이지 미구현 — 현재 유일한 회사파일 등록 경로)
            reference_attachments=context.get("reference_attachments") or [],
            raise_on_insufficient=not is_mock,
        )
    finally:
        db.close()
    logger.warning(
        "[DEBUG_FALLBACK] resolver result: company_files=%d, has_profile=%s",
        len(company_context.get("company_files") or []),
        bool(company_context.get("structured_company_profile")),
    )

    # D2: retry는 analyze_company 단계 내부에만 격리.
    return await call_with_retry(
        provider.company_analyzer,
        company_context,
        context["notice_schema"],
        request_id="c3_pipeline",
        session_id=context.get("_session_id") or "",
    )


async def _step_extract_evidence(context: Dict[str, Any], provider) -> List[Dict[str, Any]]:
    """reference_attachments → chunks (E-2 vector RAG, 2026-05-18).

    기존 LLM evidence_extractor 대체:
      1. chunker로 모든 attachment chunk 분리
      2. embedder로 vector 변환
      3. evidence_store.upsert (session collection)

    Returns:
        evidence list (chunk를 evidence shape으로 변환):
          [{evidence_id (=chunk_id), source_file, source_page, type, content, ...}]
    """
    from services.evidence_chunker import chunk_attachments, stats as chunk_stats
    from services.evidence_embedder import get_embedder
    from services.evidence_store import get_store

    session_id = context.get("_session_id") or ""
    refs = context.get("reference_attachments") or []

    if not refs:
        logger.info("[extract_evidence E-2] no reference_attachments → 빈 결과")
        return []

    # 1. chunking
    chunks = chunk_attachments(refs, session_id=session_id)
    logger.info("[extract_evidence E-2] chunks=%d (stats=%s)",
                len(chunks), chunk_stats(chunks))

    if not chunks:
        return []

    # 2. embedding (batch)
    embedder = get_embedder()
    vectors = await embedder.embed([c["content"] for c in chunks])
    logger.info("[extract_evidence E-2] embedded %d vectors (dim=%d) via %s",
                len(vectors), embedder.dim, embedder.name)

    # 3. evidence_store upsert (session collection)
    store = get_store()
    n = store.upsert(session_id, chunks, vectors)
    logger.info("[extract_evidence E-2] stored %d chunks in session=%s (total=%d)",
                n, session_id, store.count(session_id))

    # 4. evidence list 형식으로 반환 (chunk_id를 evidence_id로)
    evidence_list: List[Dict[str, Any]] = []
    for c in chunks:
        evidence_list.append({
            "evidence_id": c["chunk_id"],
            "source_file": c.get("source_file") or "",
            "source_page": c.get("page") if c.get("page") is not None else 0,
            "type": "chunk",   # Phase 7에서 LLM 분류 가능
            "content": c.get("content") or "",
            "raw_text": c.get("content") or "",
            "start_char": c.get("start_char"),
            "end_char": c.get("end_char"),
            "content_chars": c.get("content_chars"),
        })
    return evidence_list


async def _step_map_evidence(
    context: Dict[str, Any], provider, evidence_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """form × evidence 매칭 (E-2 vector RAG + 4-feature scoring, 2026-05-18).

    evidence_list는 _step_extract_evidence 결과 (chunks를 evidence shape으로).
    실제 vector search는 chromadb (evidence_store)에 이미 upsert된 chunks 활용.

    기존 provider.evidence_mapper (LLM 1회 호출) 대체:
      1. confirmed_schema → flatten questions (section_title 포함)
      2. evidence_matcher.match_questions (chromadb top-k + 4-feature scoring)
      3. 결과는 기존 question_mappings 형식 유지 (frontend 호환)
    """
    from services.evidence_matcher import match_questions, THRESHOLD_REVIEW
    from services.item_query_builder import flatten_form_questions

    session_id = context.get("_session_id") or ""

    # evidence_list가 비었으면 (extract_evidence가 빈 결과) — store도 비었음
    # → matcher가 알아서 no_match로 처리
    confirmed_schema = context.get("confirmed_schema") or {}
    flat_qs = flatten_form_questions(confirmed_schema)

    # announcement_signals (Phase 7 통합 시 활용)
    ann_signals = context.get("announcement_signals") or {}

    return await match_questions(
        session_id=session_id,
        form_questions=flat_qs,
        announcement_signals=ann_signals or None,
        top_k=5,
        threshold=THRESHOLD_REVIEW,  # 0.50
    )


def _step_map_eval_criteria(context: Dict[str, Any]) -> Dict[str, Any]:
    """평가기준 ↔ 문항 매핑 (provider 메서드 없음, 직접 매핑).

    analysis.py의 map_eval_criteria endpoint 내부 로직과 동일 패턴.
    """
    notice = context["notice_schema"]
    form = context["confirmed_schema"]
    criteria = notice.get("evaluation_criteria") or []
    form_questions = []
    for sec in (form.get("sections") or []):
        for q in (sec.get("questions") or []):
            qid = q.get("question_id")
            if qid:
                form_questions.append(qid)

    mappings = []
    for c in criteria:
        if not isinstance(c, dict):
            continue
        scope = c.get("scope", "section")
        mapped = form_questions[:3] if scope == "section" else form_questions[:2]
        mappings.append({
            "criteria_id": f"crit_{c.get('name', 'unknown')}",
            "criteria_name": c.get("name", ""),
            "weight": c.get("weight", 0),
            "scope": scope,
            "mapped_questions": mapped,
            "mapping_type": "direct",
            "mapped_by": "ai",
        })
    return {
        "mappings": mappings,
        "total": len(mappings),
    }


async def _step_check_missing(
    context: Dict[str, Any], provider, mapping_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """근거 부족 question 추출."""
    result = await provider.missing_material(
        mapping_result,
        request_id="c3_pipeline",
        session_id="",
    )
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        items = result.get("items")
        if isinstance(items, list):
            return items
    return []


# ────────────────────────────────────────────────────────────────────
# Public: BackgroundTask main
# ────────────────────────────────────────────────────────────────────

async def run_mapping_pipeline(
    session_id: str,
    start_from: Optional[str] = None,
) -> None:
    """BackgroundTask 진입점.

    새 SessionLocal()로 DB session 생성 (보강 #4).
    각 단계: pending → running → done/failed.
    실패 시 status=failed + failed_step + error_message 기록 후 종료.

    start_from (보강 #3):
      None이면 처음부터.
      단계명이면 그 이전 done은 skip, start_from부터 실행 (재실행).
    """
    db = SessionLocal()
    try:
        session = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == session_id
        ).first()
        if not session:
            logger.warning("[run_mapping_pipeline] session not found: %s", session_id)
            return

        fsj = dict(session.form_schema_json or {})
        pipeline = fsj.get("mapping_pipeline") or init_mapping_pipeline()
        if not isinstance(pipeline, dict):
            pipeline = init_mapping_pipeline()

        # context 수집 (보강 #5 announcement_signals + evaluation_rubric 포함)
        context = _collect_context(session)
        provider = get_provider()

        # skip 결정: start_from 명시 시 그 이전 done은 skip
        skip_until = start_from
        results = pipeline.get("results") or {step: None for step in PIPELINE_STEPS}
        steps_state = pipeline.get("steps") or {step: "pending" for step in PIPELINE_STEPS}

        # 결과 변수 (단계 간 의존성)
        evidence_list: List[Dict[str, Any]] = (
            results.get("extract_evidence") or [] if isinstance(results, dict) else []
        )
        mapping_result: Dict[str, Any] = (
            results.get("map_evidence") or {} if isinstance(results, dict) else {}
        )

        for step_name in PIPELINE_STEPS:
            # done 단계 skip (보강 #3)
            if skip_until is not None and step_name != skip_until:
                if steps_state.get(step_name) == "done":
                    logger.info("[run_mapping_pipeline] skip done step: %s", step_name)
                    continue
            if step_name == skip_until:
                # start_from 단계 도달 → 더 이상 skip 안 함
                skip_until = None

            # running 상태로 전이
            steps_state[step_name] = "running"
            pipeline["steps"] = steps_state
            pipeline["results"] = results
            _save_pipeline(db, session, pipeline)

            try:
                if step_name == "analyze_company":
                    result = await _step_analyze_company(context, provider)
                elif step_name == "extract_evidence":
                    result = await _step_extract_evidence(context, provider)
                    evidence_list = result if isinstance(result, list) else []
                elif step_name == "map_evidence":
                    result = await _step_map_evidence(context, provider, evidence_list)
                    mapping_result = result if isinstance(result, dict) else {}
                elif step_name == "map_eval_criteria":
                    result = _step_map_eval_criteria(context)
                elif step_name == "check_missing":
                    result = await _step_check_missing(context, provider, mapping_result)
                else:
                    raise RuntimeError(f"unknown step: {step_name}")

                results[step_name] = result
                steps_state[step_name] = "done"
                pipeline["steps"] = steps_state
                pipeline["results"] = results
                _save_pipeline(db, session, pipeline)

            except Exception as e:
                logger.exception(
                    "[run_mapping_pipeline] step failed: %s session=%s",
                    step_name, session_id,
                )
                steps_state[step_name] = "failed"
                pipeline["steps"] = steps_state
                pipeline["status"] = "failed"
                pipeline["failed_step"] = step_name
                pipeline["error_message"] = str(e)
                pipeline["completed_at"] = datetime.utcnow().isoformat()
                _save_pipeline(db, session, pipeline)
                return

        # 모든 단계 성공
        pipeline["status"] = "success"
        pipeline["failed_step"] = None
        pipeline["error_message"] = None
        pipeline["completed_at"] = datetime.utcnow().isoformat()
        _save_pipeline(db, session, pipeline)
        logger.info("[run_mapping_pipeline] success session=%s", session_id)

    except Exception as e:
        logger.exception(
            "[run_mapping_pipeline] unexpected error session=%s: %s",
            session_id, e,
        )
    finally:
        db.close()
