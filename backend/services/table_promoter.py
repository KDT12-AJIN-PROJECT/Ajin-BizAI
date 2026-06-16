"""
A-4-3 — Table Promoter MVP.

b4-8.md §3.4 (dedupe), §3.5 (LLM vs promoted), §3.7 (section matching),
§3.8 (promoted question 필드) 정책 구현.

입력:
  - normalized: List[NormalizedTable]
  - llm_schema: dict (form_parser 결과)

출력:
  - (modified_schema: dict, stats: dict)

핵심 책임:
- is_promotable=True인 normalized table을 FormQuestion(table_input)으로 승격
- LLM 결과와 dedupe — IoU 기준
- 충돌 시: question identity는 LLM 우선, table_schema는 layout 우선
- section_id 4단계 fallback
- deterministic question_id 생성
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from services.table_normalizer import NormalizedTable

logger = logging.getLogger(__name__)

# ─── 임계값 ────────────────────────────────────────────────────
IOU_THRESHOLD = 0.5         # §3.4 동일 table 판정 IoU
BBOX_ABS_TOLERANCE = 20.0   # §3.4 fallback (x1/y1 차이 < 20)

# §3.7 자동 section
AUTO_SECTION_ID = "S_AUTO_TABLES"
AUTO_SECTION_TITLE = "자동 추출된 표"
AUTO_SECTION_ORDER = 999

# §3.5 source_type
SOURCE_TYPE_PROMOTED = "layout_table_promoted"
SOURCE_TYPE_CORRECTED = "llm_table_schema_corrected_by_layout"

# §3.7 section matching: source_page 근접도 임계값
SECTION_NEAR_PAGE_TOLERANCE = 3


# ────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────

def promote_tables(
    normalized: List[NormalizedTable],
    llm_schema: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """promoted question을 LLM schema에 병합 (b4-8.md §3.5/§3.7/§3.8).

    Returns: (modified_llm_schema, promotion_stats)
    """
    if not isinstance(llm_schema, dict):
        raise TypeError("llm_schema must be dict")

    # LLM schema mutation 방지: 깊은 카피 없이 ref로 작업하되 sections를 보존
    schema = llm_schema
    sections = schema.get("sections") or []
    if not isinstance(sections, list):
        sections = []
    schema["sections"] = sections

    stats = {
        "layout_table_count": len(normalized),
        "normalized_table_count": len(normalized),
        "llm_table_input_count": _count_llm_table_inputs(sections),
        "promoted_table_count": 0,
        "skipped_fragment_table_count": sum(1 for n in normalized if n.is_fragment),
        "llm_schema_corrected_count": 0,
        "auto_section_used_count": 0,
        "skipped_non_promotable_table_count": 0,
        "table_promotion_rate": 0.0,
    }

    # 사용된 question_id (충돌 방지)
    used_ids = _collect_question_ids(sections)

    # promotable한 normalized table들을 순회
    page_table_counter: Dict[int, int] = {}
    for nt in normalized:
        if not nt.is_promotable:
            if not nt.is_fragment:
                stats["skipped_non_promotable_table_count"] += 1
            continue

        # 같은 page에서 N번째 (deterministic ID 생성용)
        page_table_counter[nt.source_page] = page_table_counter.get(nt.source_page, 0) + 1
        idx = page_table_counter[nt.source_page]

        # LLM question 매칭 시도
        matched = find_matching_llm_question(nt, sections)
        if matched:
            # §3.5: question identity는 LLM 우선, table_schema는 layout 우선 보정
            corrected = _correct_llm_table_schema(matched, nt)
            if corrected:
                stats["llm_schema_corrected_count"] += 1
            # 신규 question 추가는 하지 않음
        else:
            # 새 promoted question 생성
            section_id = assign_section_id(nt, sections, stats)
            promoted_q = make_promoted_question(
                nt,
                section_id=section_id,
                question_id=generate_question_id(nt.source_page, idx, used_ids),
            )
            used_ids.add(promoted_q["question_id"])
            _insert_question_to_section(sections, promoted_q, section_id)
            stats["promoted_table_count"] += 1

    # rate 계산: (llm_table_input_count + promoted) / normalized_table_count
    total_tables_in_schema = stats["llm_table_input_count"] + stats["promoted_table_count"]
    stats["table_promotion_rate"] = (
        total_tables_in_schema / stats["normalized_table_count"]
        if stats["normalized_table_count"] > 0
        else 0.0
    )

    logger.info(
        "[table_promoter] normalized=%d, llm_table=%d, promoted=%d, "
        "corrected=%d, skipped_fragment=%d, auto_section=%d, rate=%.2f",
        stats["normalized_table_count"],
        stats["llm_table_input_count"],
        stats["promoted_table_count"],
        stats["llm_schema_corrected_count"],
        stats["skipped_fragment_table_count"],
        stats["auto_section_used_count"],
        stats["table_promotion_rate"],
    )
    return (schema, stats)


# ────────────────────────────────────────────────────────────────
# §3.4 dedupe / 매칭
# ────────────────────────────────────────────────────────────────

def find_matching_llm_question(
    nt: NormalizedTable,
    sections: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """nt와 매칭되는 LLM table_input question 검색.

    §3.4: IoU >= 0.5 또는 (|x1-x1|<20 & |y1-y1|<20 & rows==rows & cols==cols).
    bbox 없으면 source_page + rows + columns + title 유사도.
    """
    for sec in sections:
        for q in (sec.get("questions") or []):
            if q.get("fill_mode") != "table_input":
                continue
            if q.get("source_page") != nt.source_page:
                continue
            if _is_same_table(nt, q):
                return q
    return None


def _is_same_table(nt: NormalizedTable, llm_q: Dict[str, Any]) -> bool:
    """nt와 LLM question이 같은 table인지 판정.

    우선순위:
    1. 둘 다 bbox 있으면: IoU 또는 x1/y1 + rows/cols 매칭
    2. 한쪽이라도 bbox 없으면: rows/cols 일치 또는 title 유사도+rows/cols 부분 일치
    """
    llm_table_schema = llm_q.get("table_schema") or {}
    llm_bbox = llm_q.get("bbox") or llm_table_schema.get("bbox")

    nt_has_bbox = nt.bbox is not None and len(nt.bbox) == 4
    llm_has_bbox = llm_bbox is not None and len(llm_bbox) == 4

    # Case 1: 둘 다 bbox 있음 — bbox 기준만 사용 (다른 표 false positive 방지)
    if nt_has_bbox and llm_has_bbox:
        if _iou(nt.bbox, llm_bbox) >= IOU_THRESHOLD:
            return True
        if (
            abs(nt.bbox[0] - llm_bbox[0]) < BBOX_ABS_TOLERANCE
            and abs(nt.bbox[1] - llm_bbox[1]) < BBOX_ABS_TOLERANCE
            and nt.rows == _llm_rows(llm_q)
            and nt.columns == _llm_columns(llm_q)
        ):
            return True
        return False  # bbox 있는데 안 맞으면 different table

    # Case 2: 한쪽이라도 bbox 없음 — rows/cols + title 유사도 휴리스틱
    if nt.rows == _llm_rows(llm_q) and nt.columns == _llm_columns(llm_q):
        return True
    if nt.title_candidate and llm_q.get("title"):
        if _title_similarity(nt.title_candidate, llm_q["title"]) > 0.7:
            if nt.rows == _llm_rows(llm_q) or nt.columns == _llm_columns(llm_q):
                return True

    return False


def _iou(a: List[float], b: List[float]) -> float:
    """bbox IoU. a/b = [x0, y0, x1, y1]."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    x_left = max(ax0, bx0)
    y_top = max(ay0, by0)
    x_right = min(ax1, bx1)
    y_bottom = min(ay1, by1)
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    intersection = (x_right - x_left) * (y_bottom - y_top)
    a_area = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
    b_area = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
    union = a_area + b_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _llm_rows(q: Dict[str, Any]) -> int:
    ts = q.get("table_schema") or {}
    if "row_count" in ts:
        return ts["row_count"]
    rows = ts.get("rows")
    if isinstance(rows, list):
        return len(rows)
    if isinstance(rows, int):
        return rows
    return 0


def _llm_columns(q: Dict[str, Any]) -> int:
    ts = q.get("table_schema") or {}
    if "col_count" in ts:
        return ts["col_count"]
    cols = ts.get("columns")
    if isinstance(cols, list):
        return len(cols)
    if isinstance(cols, int):
        return cols
    return 0


def _title_similarity(a: str, b: str) -> float:
    """간이 title 유사도 (overlap ratio)."""
    if not a or not b:
        return 0.0
    a_set = set(a.replace(" ", ""))
    b_set = set(b.replace(" ", ""))
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / max(len(a_set | b_set), 1)


# ────────────────────────────────────────────────────────────────
# §3.5 LLM table_schema 보정
# ────────────────────────────────────────────────────────────────

def _correct_llm_table_schema(
    llm_q: Dict[str, Any],
    nt: NormalizedTable,
) -> bool:
    """LLM question의 table_schema를 layout 사실값으로 보정.

    제안 1 적용: promoted.columns/rows가 llm과 다르면 보정 (양방향).
    layout이 ground truth라는 정책 정신.

    Returns: 보정 발생 시 True
    """
    llm_cols = _llm_columns(llm_q)
    llm_rows = _llm_rows(llm_q)
    if (nt.columns, nt.rows) == (llm_cols, llm_rows):
        # 동일하면 보정 안 함
        return False

    new_table_schema = build_table_schema(nt)
    llm_q["table_schema"] = new_table_schema
    llm_q["source_type"] = SOURCE_TYPE_CORRECTED
    md = llm_q.setdefault("metadata", {})
    if not isinstance(md, dict):
        md = {}
        llm_q["metadata"] = md
    md["corrected_by"] = "table_promoter"
    md["corrected_columns"] = {"from": llm_cols, "to": nt.columns}
    md["corrected_rows"] = {"from": llm_rows, "to": nt.rows}
    return True


# ────────────────────────────────────────────────────────────────
# §3.7 section_id matching (4단계 fallback)
# ────────────────────────────────────────────────────────────────

def assign_section_id(
    nt: NormalizedTable,
    sections: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> str:
    """4단계 fallback section_id 매칭."""
    # 1. source_page 범위가 nt.source_page를 포함하는 section
    sid = _find_section_by_page_range(nt.source_page, sections)
    if sid:
        return sid

    # 2. source_page가 가장 가까운 section
    sid = _find_section_by_nearest_page(nt.source_page, sections)
    if sid:
        return sid

    # 3. title_candidate가 section title과 유사
    if nt.title_candidate:
        sid = _find_section_by_title_similarity(nt.title_candidate, sections)
        if sid:
            return sid

    # 4. 자동 section 생성
    stats["auto_section_used_count"] = stats.get("auto_section_used_count", 0) + 1
    _ensure_auto_section(sections)
    return AUTO_SECTION_ID


def _find_section_by_page_range(
    target_page: int,
    sections: List[Dict[str, Any]],
) -> Optional[str]:
    """section 내 question source_page 최소/최대 범위가 target_page 포함하면 매칭."""
    for sec in sections:
        if sec.get("section_id") == AUTO_SECTION_ID:
            continue
        qs = sec.get("questions") or []
        pages = [q.get("source_page") for q in qs if q.get("source_page")]
        if not pages:
            continue
        if min(pages) <= target_page <= max(pages):
            return sec.get("section_id")
    return None


def _find_section_by_nearest_page(
    target_page: int,
    sections: List[Dict[str, Any]],
) -> Optional[str]:
    """source_page가 가장 가까운 section (tolerance 이내)."""
    best_sid = None
    best_dist = None
    for sec in sections:
        if sec.get("section_id") == AUTO_SECTION_ID:
            continue
        qs = sec.get("questions") or []
        pages = [q.get("source_page") for q in qs if q.get("source_page")]
        if not pages:
            continue
        dist = min(abs(p - target_page) for p in pages)
        if dist > SECTION_NEAR_PAGE_TOLERANCE:
            continue
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_sid = sec.get("section_id")
    return best_sid


def _find_section_by_title_similarity(
    title: str,
    sections: List[Dict[str, Any]],
) -> Optional[str]:
    """title_candidate가 section title과 유사한 경우 (>0.5)."""
    best_sid = None
    best_sim = 0.0
    for sec in sections:
        if sec.get("section_id") == AUTO_SECTION_ID:
            continue
        s_title = (sec.get("title") or "").strip()
        if not s_title:
            continue
        sim = _title_similarity(title, s_title)
        if sim > best_sim and sim >= 0.5:
            best_sim = sim
            best_sid = sec.get("section_id")
    return best_sid


def _ensure_auto_section(sections: List[Dict[str, Any]]) -> None:
    """자동 section이 없으면 추가."""
    if any(sec.get("section_id") == AUTO_SECTION_ID for sec in sections):
        return
    sections.append({
        "section_id": AUTO_SECTION_ID,
        "title": AUTO_SECTION_TITLE,
        "order": AUTO_SECTION_ORDER,
        "source_type": SOURCE_TYPE_PROMOTED,
        "questions": [],
    })


def _insert_question_to_section(
    sections: List[Dict[str, Any]],
    question: Dict[str, Any],
    section_id: str,
) -> None:
    """section을 찾아 question 추가. 없으면 새 section 생성."""
    for sec in sections:
        if sec.get("section_id") == section_id:
            qs = sec.setdefault("questions", [])
            qs.append(question)
            return
    # section_id가 없는 경우 — 자동 section으로 fallback
    _ensure_auto_section(sections)
    for sec in sections:
        if sec.get("section_id") == AUTO_SECTION_ID:
            sec.setdefault("questions", []).append(question)
            return


# ────────────────────────────────────────────────────────────────
# §3.8 promoted question 생성
# ────────────────────────────────────────────────────────────────

def make_promoted_question(
    nt: NormalizedTable,
    section_id: str,
    question_id: str,
) -> Dict[str, Any]:
    """promoted FormQuestion dict 생성 (§3.8)."""
    return {
        "question_id": question_id,
        "section_id": section_id,
        "title": nt.title_candidate or f"표 p{nt.source_page}-t",
        "source_page": nt.source_page,
        "fill_mode": "table_input",
        "source_type": SOURCE_TYPE_PROMOTED,
        "is_required": True,
        "is_table_item": True,
        "requirement": "",
        "constraints": {},
        "table_schema": build_table_schema(nt),
        "metadata": {
            "promoted_by": "table_promoter",
            "confidence": nt.confidence,
            "is_promotable": nt.is_promotable,
            "header_row_count": nt.header_row_count,
        },
    }


def build_table_schema(nt: NormalizedTable) -> Dict[str, Any]:
    """NormalizedTable → table_schema dict (FormQuestion 호환).

    2026-05-19 Option C: data_rows / header_cells 추가 — 프론트가 실제 cell 그리드를
    렌더링하고 사용자/LLM이 빈 cell에 작성할 수 있도록 위치 정보 보존.
    """
    columns = []
    for ci in range(nt.columns):
        header_path = nt.header_paths[ci] if ci < len(nt.header_paths) else []
        columns.append({
            "name": (header_path[-1] if header_path else f"c{ci+1}") or f"c{ci+1}",
            "header_path": list(header_path),
        })

    # cells_raw → header_cells (헤더 row들) + data_rows (그 외 row들)
    header_n = max(1, nt.header_row_count)
    header_cells: List[List[Dict[str, Any]]] = []
    data_rows: List[Dict[str, Any]] = []
    for ri, row in enumerate(nt.cells_raw or []):
        # cell 객체 — frontend 렌더 최소 필드 (cell_id / text / is_empty / bbox)
        row_cells = [
            {
                "cell_id": c.get("cell_id") or f"{nt.table_id}.r{ri+1}.c{ci+1}",
                "text": (c.get("text") or "").strip(),
                "is_empty": bool(c.get("is_empty")) or not (c.get("text") or "").strip(),
                "bbox": list(c["bbox"]) if c.get("bbox") else None,
            }
            for ci, c in enumerate(row)
        ]
        if ri < header_n:
            header_cells.append(row_cells)
        else:
            data_rows.append({
                "row_id": f"{nt.table_id}.r{ri+1}",
                "row_index": ri,
                "cells": row_cells,
            })

    return {
        "table_id": nt.table_id,
        "row_count": nt.rows,
        "col_count": nt.columns,
        "columns": columns,
        "bbox": list(nt.bbox) if nt.bbox else None,
        "header_row_count": nt.header_row_count,
        # Option C: cell-level data
        "header_cells": header_cells,
        "data_rows": data_rows,
    }


# ────────────────────────────────────────────────────────────────
# question_id 생성 (deterministic)
# ────────────────────────────────────────────────────────────────

def generate_question_id(
    source_page: int,
    table_index: int,
    used_ids: set,
) -> str:
    """TQ_p{P:03d}_t{T:03d} deterministic ID 생성."""
    base = f"TQ_p{source_page:03d}_t{table_index:03d}"
    if base not in used_ids:
        return base
    # 충돌 시 suffix
    suffix = 1
    while True:
        candidate = f"{base}_{suffix}"
        if candidate not in used_ids:
            return candidate
        suffix += 1


def _collect_question_ids(sections: List[Dict[str, Any]]) -> set:
    ids = set()
    for sec in sections:
        for q in (sec.get("questions") or []):
            qid = q.get("question_id")
            if qid:
                ids.add(qid)
    return ids


def _count_llm_table_inputs(sections: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for sec in sections
        for q in (sec.get("questions") or [])
        if q.get("fill_mode") == "table_input"
    )
