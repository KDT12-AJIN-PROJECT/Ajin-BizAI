"""form_parser 결과 후처리 (C-단계).

2026-05-18 신규 — form_parser_hybrid가 놓치는 패턴을 hint로 표시.

정책 (보수적):
  - 자동 변환 X — fill_mode를 강제로 바꾸지 않음 (false positive 위험)
  - hint metadata만 추가 (frontend가 사용자에게 보여줌)
  - 사용자가 트리 CRUD ✏️로 결정

지원 hint:
  - table_candidate: ai_text인데 표 가능성 높음
  - header_candidate: ai_text인데 단순 제목/표제 가능성
  - cluster_neighbor: 같은 페이지 표 묶음의 일부 가능성
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 표 마커 키워드
TABLE_KEYWORDS = ("표", "table", "행", "열", "□", "셀")
# 번호 패턴 ("1)", "2)", "1.", "ⅰ.", ...)
NUMBERED_PATTERN = re.compile(r"^\s*(\d+\)|\d+\.|[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]+\.|[가-하]\.)", re.MULTILINE)
# 작성요청 빈칸 패턴
BLANK_PATTERN = re.compile(r"~+\s*작성요청\s*~+|_{3,}|‾{3,}")


def _has_numbered_prefix(title: str) -> bool:
    """title이 "1)", "2.", "ⅰ." 같은 번호로 시작."""
    return bool(NUMBERED_PATTERN.match(title or ""))


def _has_table_keyword(text: str) -> bool:
    """텍스트에 표 마커 키워드."""
    t = (text or "").lower()
    return any(kw.lower() in t for kw in TABLE_KEYWORDS)


def _has_blank_marker(text: str) -> bool:
    """작성요청 빈칸 패턴."""
    return bool(BLANK_PATTERN.search(text or ""))


def _count_columns(q: Dict[str, Any]) -> int:
    """신/구 스키마 모두에서 column 개수."""
    tc = q.get("table_columns")
    if isinstance(tc, list) and tc:
        return len(tc)
    sc = (q.get("table_schema") or {}).get("columns") or []
    return len(sc)


def compute_hints_for_question(
    q: Dict[str, Any],
    *,
    section_questions: List[Dict[str, Any]],
    page_questions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """단일 question에 대한 hint 계산.

    Returns:
        {} 또는 {
          "table_candidate": True/False,
          "header_candidate": True/False,
          "blank_marker": True/False,
          "reasons": [...],
          "suggested_fill_mode": "table_input" or None,
        }
    """
    title = q.get("title") or ""
    orig = q.get("original_text") or ""
    fill_mode = q.get("fill_mode")
    # 2026-05-18: 사용자 트리 CRUD 후 fill_mode/is_table_item 정합성 깨질 수 있음
    # fill_mode를 진실로 (사용자가 명시적으로 설정한 값) — is_table_item은 무시
    is_table = (fill_mode == "table_input")

    # 이미 table_input이면 hint 불필요
    if is_table:
        return {}

    reasons: List[str] = []
    table_candidate = False
    header_candidate = False
    blank_marker = False

    # 1. 번호 패턴 + 같은 section/page에 table 항목 다수
    if _has_numbered_prefix(title):
        section_table_count = sum(
            1 for sq in section_questions
            if sq.get("is_table_item") or sq.get("fill_mode") == "table_input"
        )
        if section_table_count >= 2:
            reasons.append("같은 섹션에 표 항목 다수 + 번호 패턴")
            table_candidate = True

    # 2. title/original에 표 키워드
    combined = f"{title} {orig}"
    if _has_table_keyword(combined):
        if _has_numbered_prefix(title):
            reasons.append("번호 + 표 키워드")
            table_candidate = True
        else:
            reasons.append("표 키워드 등장")

    # 3. 같은 페이지에 table_input 항목 2+ → 인접 ai_text도 가능성
    page_table_count = sum(
        1 for pq in page_questions
        if pq.get("is_table_item") or pq.get("fill_mode") == "table_input"
    )
    if page_table_count >= 2 and _has_numbered_prefix(title):
        if "같은 페이지 표 항목 2+" not in reasons:
            reasons.append(f"같은 페이지({q.get('source_page')}) 표 항목 {page_table_count}개")
            table_candidate = True

    # 4. 빈칸 작성요청 패턴
    if _has_blank_marker(orig):
        blank_marker = True
        reasons.append("작성요청 빈칸 패턴")

    # 5. header_candidate — 매우 짧은 title (10자 미만) + content 없음 + max_length 0
    constraints = q.get("constraints") or {}
    if (
        len(title) < 15
        and not orig.strip()
        and (constraints.get("max_length") or 0) == 0
    ):
        header_candidate = True
        reasons.append("짧은 title + 본문 없음 + 글자수 한도 0")

    if not reasons:
        return {}

    hint: Dict[str, Any] = {
        "reasons": reasons,
    }
    if table_candidate:
        hint["table_candidate"] = True
        hint["suggested_fill_mode"] = "table_input"
    if header_candidate:
        hint["header_candidate"] = True
    if blank_marker:
        hint["blank_marker"] = True

    return hint


def annotate_form_schema(form_schema: Dict[str, Any]) -> Dict[str, Any]:
    """form_schema 전체에 hint 메타 추가.

    Returns:
        annotated form_schema (각 question에 _parser_hint 키 추가).
        원본 형식 그대로 유지 (sections + questions).
    """
    if not isinstance(form_schema, dict) or not form_schema.get("sections"):
        return form_schema

    # 페이지별 question 그루핑
    page_groups: Dict[int, List[Dict[str, Any]]] = {}
    for sec in form_schema["sections"]:
        for q in sec.get("questions") or []:
            page = q.get("source_page")
            if page is not None:
                page_groups.setdefault(page, []).append(q)

    annotated_sections = []
    total_hints = 0
    table_candidate_count = 0

    for sec in form_schema["sections"]:
        questions = sec.get("questions") or []
        annotated_qs = []
        for q in questions:
            page = q.get("source_page")
            page_qs = page_groups.get(page, []) if page is not None else []
            hint = compute_hints_for_question(
                q,
                section_questions=questions,
                page_questions=page_qs,
            )
            q_copy = dict(q)
            if hint:
                q_copy["_parser_hint"] = hint
                total_hints += 1
                if hint.get("table_candidate"):
                    table_candidate_count += 1
            annotated_qs.append(q_copy)
        sec_copy = dict(sec)
        sec_copy["questions"] = annotated_qs
        annotated_sections.append(sec_copy)

    out = dict(form_schema)
    out["sections"] = annotated_sections
    # 통계 메타 (디버그)
    out["_postprocessor_meta"] = {
        "total_hints": total_hints,
        "table_candidate_count": table_candidate_count,
        "version": "v1_2026-05-18",
    }
    return out


def get_summary(annotated: Dict[str, Any]) -> Dict[str, Any]:
    """annotated form_schema의 hint 요약 (디버그/로깅용)."""
    by_type: Dict[str, int] = {}
    examples: List[Dict[str, Any]] = []
    for sec in annotated.get("sections", []):
        for q in sec.get("questions", []):
            hint = q.get("_parser_hint") or {}
            for k in ("table_candidate", "header_candidate", "blank_marker"):
                if hint.get(k):
                    by_type[k] = by_type.get(k, 0) + 1
            if hint and len(examples) < 10:
                examples.append({
                    "qid": q.get("question_id"),
                    "title": (q.get("title") or "")[:50],
                    "fill_mode": q.get("fill_mode"),
                    "hint": hint,
                })
    return {
        "by_type": by_type,
        "examples": examples,
        "meta": annotated.get("_postprocessor_meta"),
    }
