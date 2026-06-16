"""E-2 Phase 5 — item_query_builder.

각 form question에 대해 vector search query를 생성한다.
query는 embedder로 embedding된 후 evidence_store.search에 사용.

전략:
  - title은 항상 포함 (핵심)
  - writing_guidelines가 있으면 가중 (질문 의도 보강)
  - required_evidence_types 명시 (어떤 종류 자료 찾는지)
  - original_text는 너무 길어 head 200자만 (LLM이 생성한 예시 문구)

질문 타입별 변형:
  - is_table_item / fill_mode=table_input: "표 형식 데이터" 명시
  - is_required: weight 변경 (matcher 측에서 처리)
"""
from __future__ import annotations

from typing import Any, Dict, List


def get_table_columns(question: Dict[str, Any]) -> List[str]:
    """table_columns (구 스키마) 또는 table_schema.columns (신 스키마)에서 컬럼명 추출.

    2026-05-18: form_parser가 신 스키마(table_schema.columns)로 반환하는 경우 대응.
    """
    cols = question.get("table_columns") or []
    if cols:
        return [
            str(c) if isinstance(c, str)
            else (c.get("name") or (c.get("header_path") or [""])[0] or "")
            for c in cols if c
        ]
    schema = question.get("table_schema") or {}
    schema_cols = schema.get("columns") or []
    out = []
    for c in schema_cols:
        if not isinstance(c, dict):
            continue
        hp = c.get("header_path") or []
        name = hp[0] if hp else (c.get("name") or c.get("field_id") or "")
        if name:
            out.append(str(name))
    return out


def build_query(question: Dict[str, Any]) -> str:
    """단일 question → search query string.

    Returns:
        한 줄의 query string (embedder가 그대로 embedding).
        빈 question이면 빈 string.
    """
    if not isinstance(question, dict):
        return ""

    parts: List[str] = []

    title = (question.get("title") or "").strip()
    if title:
        parts.append(title)

    # writing_guidelines — 작성 지침. 의미 보강에 매우 도움됨.
    guidelines = question.get("writing_guidelines") or []
    if isinstance(guidelines, list) and guidelines:
        g_text = " ".join(str(g) for g in guidelines[:5])  # 최대 5개
        if g_text.strip():
            parts.append(f"작성 지침: {g_text[:300]}")

    # required_evidence_types — 어떤 자료 타입 필요
    req_types = question.get("required_evidence_types") or question.get("required_evidence_type") or []
    if isinstance(req_types, list) and req_types:
        parts.append(f"필요 자료 유형: {', '.join(str(t) for t in req_types[:5])}")

    # original_text — form_parser가 추출한 원본 빈칸 텍스트 (예시 문구)
    orig = (question.get("original_text") or "").strip()
    if orig and len(orig) > 5:
        parts.append(f"양식 원문: {orig[:200]}")

    # table 문항 hint (신/구 스키마 모두 지원)
    if question.get("is_table_item") or question.get("fill_mode") == "table_input":
        cols = get_table_columns(question)
        if cols:
            col_text = ", ".join(cols[:8])
            parts.append(f"표 컬럼: {col_text}")

    return " | ".join(parts)


def build_queries(form_questions: List[Dict[str, Any]]) -> Dict[str, str]:
    """form_questions list → {question_id: query} 매핑.

    빈 query는 결과에서 제외.
    """
    out: Dict[str, str] = {}
    for q in form_questions or []:
        if not isinstance(q, dict):
            continue
        qid = q.get("question_id")
        if not qid:
            continue
        query = build_query(q)
        if query.strip():
            out[qid] = query
    return out


def flatten_form_questions(form_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """form_schema.sections[].questions[] → flat list (section_id/section_title 첨부).

    section_title을 question에 첨부해 query 생성 시 활용 가능.
    """
    out: List[Dict[str, Any]] = []
    for sec in (form_schema or {}).get("sections") or []:
        if not isinstance(sec, dict):
            continue
        sec_id = sec.get("section_id")
        sec_title = sec.get("title") or ""
        for q in sec.get("questions") or []:
            if not isinstance(q, dict):
                continue
            q_copy = dict(q)
            q_copy["section_id"] = sec_id
            q_copy["section_title"] = sec_title
            out.append(q_copy)
    return out
