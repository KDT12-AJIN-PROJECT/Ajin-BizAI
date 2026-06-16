"""
NOAPI-P3 — company_context resolver.

selected_company_file_ids → CompanyFile DB query → parsed_text 포함 company_files 변환.

정책 (NOAPI-P1 §2~§4 + NOAPI-P3 보완 1):
  - selected_company_file_ids는 LLM 입력이 아닌 resolver 입력
  - parsed_text가 있는 파일만 LLM 본문 포함 (parse_success=True 필터)
  - company_profile_input이 있으면 structured_company_profile로 정규화
  - structured_company_profile vs parsed_text 충돌 시 parsed_text 출처 우선
  - profile + files 모두 비어있으면 insufficient_company_data warning + NonRetryableError raise
  - 출처 없는 값은 확정 사실로 표현 금지 (prompt 책임)
  - DB migration 없음. 기존 CompanyFile 컬럼만 사용.

병합 우선순위 (NOAPI-P1 §3-3):
  1. 회사소개서 / 사업소개서
  2. 제품소개서 / 서비스소개서
  3. 정부과제 수행실적
  4. 인증서 / 특허 / 수상
  5. 재무 / 매출 / 수출 / 고용
  6. 기타
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import CompanyFile
from services.ai_provider import NonRetryableError

logger = logging.getLogger(__name__)


# 파일 우선순위 (file_type 기반)
FILE_TYPE_PRIORITY: Dict[str, int] = {
    "회사소개서": 1,
    "사업소개서": 1,
    "제품소개서": 2,
    "서비스소개서": 2,
    "실적": 3,
    "특허": 4,
    "인증서": 4,
    "수상": 4,
    "재무제표": 5,
    "사업자등록증": 5,
    "기타": 6,
}

# token budget (NOAPI-P1 §3-5)
DEFAULT_MAX_CHARS_PER_FILE = 12_000
DEFAULT_MAX_CHARS_TOTAL = 60_000

# document_type 분류 (P1 §3-3)
FILE_TYPE_TO_DOCUMENT_TYPE: Dict[str, str] = {
    "회사소개서": "company_profile",
    "사업소개서": "company_profile",
    "제품소개서": "product",
    "서비스소개서": "product",
    "실적": "government_project",
    "인증서": "certification",
    "특허": "patent",
    "수상": "award",
    "재무제표": "financial",
    "사업자등록증": "financial",
    "기타": "other",
}


def _classify_document_type(file_type: Optional[str], filename: Optional[str]) -> str:
    """file_type 우선, 그 다음 filename keyword 추론."""
    if file_type and file_type in FILE_TYPE_TO_DOCUMENT_TYPE:
        return FILE_TYPE_TO_DOCUMENT_TYPE[file_type]
    name = (filename or "").lower()
    if any(k in name for k in ("회사소개", "기업소개", "사업소개")):
        return "company_profile"
    if any(k in name for k in ("제품", "서비스")):
        return "product"
    if any(k in name for k in ("특허",)):
        return "patent"
    if any(k in name for k in ("인증",)):
        return "certification"
    if any(k in name for k in ("재무", "결산", "매출")):
        return "financial"
    return "other"


def _normalize_company_profile_input(raw: Any) -> Optional[Dict[str, Any]]:
    """company_profile_input → structured_company_profile.

    값이 dict이면 그대로 통과 (필드 키는 prompt가 알아서 사용).
    None / 빈 dict면 None.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        logger.warning("[resolver] company_profile_input이 dict 아님: %s", type(raw).__name__)
        return None
    if not raw:
        return None
    return dict(raw)


def _truncate_head(text: str, max_chars: int) -> tuple[str, bool]:
    """head_only truncation (기존 fallback). NOAPI-P1 §4-3 권장 section_priority_then_head는
    P3 범위에서 simplification — 후속 작업으로 분리.
    """
    if not text:
        return "", False
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip(), True


def resolve_company_context(
    db: Session,
    session_id: str,
    company_profile_input: Optional[Dict[str, Any]] = None,
    selected_company_file_ids: Optional[List[str]] = None,
    *,
    reference_attachments: Optional[List[Dict[str, Any]]] = None,
    max_chars_per_file: int = DEFAULT_MAX_CHARS_PER_FILE,
    max_chars_total: int = DEFAULT_MAX_CHARS_TOTAL,
    raise_on_insufficient: bool = True,
) -> Dict[str, Any]:
    """company_context 단일 dict 반환.

    Returns:
        {
          "structured_company_profile": dict | None,
          "company_files": [
            {
              "file_id", "filename", "document_type",
              "parsed_text", "text_preview", "metadata",
              "parse_success",
              "truncated", "original_chars", "returned_chars",
            },
            ...
          ],
          "selected_company_file_ids": [...],
          "warnings": [
            {"warning_code": "company_file_text_missing"|
             "company_file_truncated"|
             "insufficient_company_data", ...}
          ],
        }

    Raises:
        NonRetryableError: profile + files 모두 비어있고 raise_on_insufficient=True일 때
    """
    # 2026-05-18 디버그: fallback 진단용
    logger.warning(
        "[DEBUG_RESOLVER] entry: session=%s, has_profile_input=%s, file_ids_count=%d, refs_count=%d, raise_on_insufficient=%s",
        session_id,
        bool(company_profile_input),
        len(selected_company_file_ids or []),
        len(reference_attachments or []),
        raise_on_insufficient,
    )

    profile = _normalize_company_profile_input(company_profile_input)
    file_ids = list(selected_company_file_ids or [])
    warnings: List[Dict[str, Any]] = []
    company_files: List[Dict[str, Any]] = []
    # 2026-05-18: total_chars를 함수 scope로 끌어올림 — file_ids 블록과 reference 블록이 budget 공유
    total_chars = 0

    if file_ids:
        # DB query — 순서 보존
        rows = db.query(CompanyFile).filter(CompanyFile.file_id.in_(file_ids)).all()
        rows_by_id = {r.file_id: r for r in rows}

        # 입력 순서로 정렬 + 누락 file_id warning
        ordered: List[CompanyFile] = []
        for fid in file_ids:
            row = rows_by_id.get(fid)
            if row is None:
                warnings.append({
                    "warning_code": "company_file_not_found",
                    "file_id": fid,
                })
            else:
                ordered.append(row)

        # 병합 우선순위 정렬 (file_type 기반)
        ordered.sort(key=lambda r: FILE_TYPE_PRIORITY.get(r.file_type or "기타", 6))

        for row in ordered:
            parse_ok = bool(row.parse_success)
            ptext = row.parsed_text or ""

            if not parse_ok or not ptext:
                warnings.append({
                    "warning_code": "company_file_text_missing",
                    "file_id": row.file_id,
                    "filename": row.file_name,
                    "parse_success": parse_ok,
                    "existing_warning": row.warning,
                })
                continue

            # 파일별 truncation
            truncated_already = bool(row.parsed_text_truncated)
            text_after_file_trunc, was_trunc_file = _truncate_head(ptext, max_chars_per_file)

            # 전체 budget 적용
            remaining = max(0, max_chars_total - total_chars)
            if remaining <= 0:
                warnings.append({
                    "warning_code": "company_file_skipped_budget",
                    "file_id": row.file_id,
                    "filename": row.file_name,
                })
                continue
            text_final, was_trunc_total = _truncate_head(text_after_file_trunc, remaining)
            total_chars += len(text_final)

            any_truncated = truncated_already or was_trunc_file or was_trunc_total
            if any_truncated:
                warnings.append({
                    "warning_code": "company_file_truncated",
                    "file_id": row.file_id,
                    "filename": row.file_name,
                    "original_chars": len(ptext),
                    "returned_chars": len(text_final),
                    "truncation_policy": "head_only",
                })

            company_files.append({
                "file_id": row.file_id,
                "filename": row.file_name,
                "document_type": _classify_document_type(row.file_type, row.file_name),
                "parsed_text": text_final,
                "text_preview": text_final[:200],
                "metadata": {
                    "file_type": row.file_type,
                    "ext": row.ext,
                    "tags": list(row.tags or []),
                    "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
                },
                "parse_success": True,
                "truncated": any_truncated,
                "original_chars": len(ptext),
                "returned_chars": len(text_final),
            })

    # 2026-05-18: reference_attachments도 company_files로 병합.
    # 사용자가 회사정보(회사소개서/사업보고서 등)를 참고자료 슬롯에 올린 경우 자동 활용.
    # ※ Step 1 카드 4번 "기업프로필 자료"는 v0.3 페이지 미구현 상태라 직접 업로드 불가.
    #   이 fallback이 없으면 사용자는 회사정보를 시스템에 등록할 방법이 없음.
    # M-2 자료실 분리(정식)는 후속 작업.
    if reference_attachments:
        existing_filenames = {cf.get("filename") for cf in company_files if cf.get("filename")}
        for att in reference_attachments:
            if not isinstance(att, dict):
                continue
            ptext = att.get("parsed_text") or ""
            if not ptext:
                continue
            fname = att.get("file_name") or att.get("filename") or ""
            # 동일 filename이 이미 company_files에 있으면 skip (중복 회피)
            if fname and fname in existing_filenames:
                continue

            text_after_file_trunc, was_trunc_file = _truncate_head(ptext, max_chars_per_file)
            remaining = max(0, max_chars_total - total_chars)
            if remaining <= 0:
                warnings.append({
                    "warning_code": "reference_skipped_budget",
                    "filename": fname,
                })
                continue
            text_final, was_trunc_total = _truncate_head(text_after_file_trunc, remaining)
            total_chars += len(text_final)

            any_truncated = was_trunc_file or was_trunc_total
            if any_truncated:
                warnings.append({
                    "warning_code": "reference_truncated_for_company",
                    "filename": fname,
                    "original_chars": len(ptext),
                    "returned_chars": len(text_final),
                })

            company_files.append({
                "file_id": att.get("file_id") or f"ref_{len(company_files)}",
                "filename": fname,
                "document_type": _classify_document_type(None, fname),
                "parsed_text": text_final,
                "text_preview": text_final[:200],
                "metadata": {
                    "source_slot": "reference",  # 출처 표시 — prompt 책임 (사용자 입력임을 명시)
                    "ext": att.get("ext"),
                },
                "parse_success": True,
                "truncated": any_truncated,
                "original_chars": len(ptext),
                "returned_chars": len(text_final),
            })
            if fname:
                existing_filenames.add(fname)

    # 2026-05-18 디버그: insufficient 판단 직전 상태
    logger.warning(
        "[DEBUG_RESOLVER] before insufficient check: company_files_count=%d, total_chars=%d, profile_set=%s",
        len(company_files),
        total_chars,
        bool(profile),
    )

    # insufficient 검사
    has_profile = profile is not None and bool(profile)
    has_files = bool(company_files)
    if not has_profile and not has_files:
        warnings.append({
            "warning_code": "insufficient_company_data",
            "session_id": session_id,
            "hint": "company_profile_input 또는 parsed_text 있는 company file 최소 1개 필요",
        })
        if raise_on_insufficient:
            raise NonRetryableError(
                f"company_analyzer: insufficient_company_data (session={session_id})"
            )

    return {
        "structured_company_profile": profile,
        "company_files": company_files,
        "selected_company_file_ids": file_ids,
        "warnings": warnings,
    }
