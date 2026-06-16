"""
A-4-2 — Table Normalizer MVP.

b4-8.md §3.1~§3.3, §3.11, §3.14 정책 구현.

입력: layout IR `pages[*].blocks[type=table]`
출력: `List[NormalizedTable]` — table_promoter가 소비할 정규화된 후보

핵심 책임:
- table_id, source_page, bbox, rows, columns 보존
- header_paths 추정 (single-level 기본, 다단헤더 휴리스틱 적용)
- title_candidate 추정 (5단계 우선순위)
- empty_field_count 집계
- is_fragment 판정
- confidence + is_promotable 계산
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional, Dict

from services.table_keywords import (
    is_toc_or_instruction,
    find_keyword_in_text,
)

logger = logging.getLogger(__name__)

# ─── 휴리스틱 임계값 ───────────────────────────────────────────
WIDE_CELL_RATIO = 1.3            # 다단헤더: anchor cell width >= avg * 이 비율
SHORT_TEXT_MAX = 6               # multi-row header 판정: row의 cell text 평균 ≤ N자
TITLE_PARAGRAPH_MIN_LEN = 1
TITLE_PARAGRAPH_MAX_LEN = 40


@dataclass
class NormalizedTable:
    """promoter가 소비할 정규화된 table 후보."""
    table_id: str
    source_page: int
    bbox: Optional[List[float]]
    rows: int
    columns: int
    header_paths: List[List[str]] = field(default_factory=list)
    title_candidate: Optional[str] = None
    empty_field_count: int = 0
    is_fragment: bool = False
    confidence: float = 0.0
    is_promotable: bool = False
    # 추가 진단 정보 (debug 용)
    header_row_count: int = 1
    cells_raw: List[List[Dict[str, Any]]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # cells_raw는 promoter가 직접 사용 안 함 — debug 외 노출 제거
        d.pop("cells_raw", None)
        return d


# ────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────

def normalize_layout_tables(pages: List[Dict[str, Any]]) -> List[NormalizedTable]:
    """layout IR pages → normalized table 후보 리스트."""
    out: List[NormalizedTable] = []
    for page in pages:
        page_num = page.get("page_number", 0)
        blocks = page.get("blocks", []) or []
        # 같은 page의 paragraph blocks (title 추정용)
        para_blocks = [b for b in blocks if b.get("type") != "table"]
        table_blocks = [b for b in blocks if b.get("type") == "table"]

        for t_idx, tb in enumerate(table_blocks):
            nt = _normalize_one(tb, page_num, t_idx, para_blocks)
            out.append(nt)

    logger.info(
        "[table_normalizer] normalized %d tables across %d pages",
        len(out), len(pages),
    )
    return out


# ────────────────────────────────────────────────────────────────
# 내부 helper
# ────────────────────────────────────────────────────────────────

def _normalize_one(
    table_block: Dict[str, Any],
    page_num: int,
    table_index: int,
    para_blocks: List[Dict[str, Any]],
) -> NormalizedTable:
    table_id = table_block.get("table_id") or f"p{page_num}_t{table_index + 1}"
    bbox = table_block.get("bbox")
    rows = table_block.get("row_count", 0) or 0
    columns = table_block.get("col_count", 0) or 0
    raw_rows = table_block.get("rows", []) or []

    # 1. cells 평탄화 (debug 용 보존)
    cells_raw = [
        [c for c in (row.get("cells", []) or [])]
        for row in raw_rows
    ]

    # 2. empty_field_count
    empty_count = sum(
        1 for row in cells_raw for c in row
        if c.get("is_empty") or not (c.get("text") or "").strip()
    )

    # 3. header_paths + header_row_count
    header_paths, header_row_count = _build_header_paths(cells_raw)

    # 4. title_candidate (5단계)
    title_candidate = _infer_title_candidate(
        page_num=page_num,
        table_index=table_index,
        table_bbox=bbox,
        para_blocks=para_blocks,
        first_row_cells=cells_raw[0] if cells_raw else [],
    )

    # 5. is_fragment
    is_fragment = _judge_is_fragment(
        columns=columns,
        rows=rows,
        cells_raw=cells_raw,
        empty_count=empty_count,
        title_candidate=title_candidate,
        para_blocks=para_blocks,
        table_bbox=bbox,
    )

    # 6. confidence
    confidence = _compute_confidence(
        title_candidate=title_candidate,
        columns=columns,
        rows=rows,
        empty_count=empty_count,
        header_paths=header_paths,
    )

    # 7. is_promotable
    is_promotable = (
        (not is_fragment)
        and columns >= 3
        and rows >= 2
        and empty_count >= 1
    )

    return NormalizedTable(
        table_id=table_id,
        source_page=page_num,
        bbox=list(bbox) if bbox else None,
        rows=rows,
        columns=columns,
        header_paths=header_paths,
        title_candidate=title_candidate,
        empty_field_count=empty_count,
        is_fragment=is_fragment,
        confidence=confidence,
        is_promotable=is_promotable,
        header_row_count=header_row_count,
        cells_raw=cells_raw,
    )


def _build_header_paths(
    cells_raw: List[List[Dict[str, Any]]],
) -> tuple[List[List[str]], int]:
    """header_paths + header_row_count 추정.

    A-4-1 진단 결론:
    - bbox=null cell은 horizontally merged hidden, vertically merged, 또는 builder 한계 혼재
    - 확신 낮으면 single-level fallback

    알고리즘:
    1. 첫 row의 wide cell (width >= avg × 1.3)이 있으면 multi-row 후보
    2. 두 번째 row의 평균 text 길이가 짧고 빈 cell 패턴이면 multi-row 확정
    3. 세 번째 row까지 확장 시 동일 패턴 적용
    4. 그 외엔 single-level (첫 row만 header)
    """
    if not cells_raw:
        return ([], 1)
    columns = len(cells_raw[0]) if cells_raw else 0
    if columns == 0:
        return ([], 1)

    # 단일 row면 single-level
    if len(cells_raw) == 1:
        return (
            [[(c.get("text") or "").strip() or ""] for c in cells_raw[0]],
            1,
        )

    # multi-row 후보 판정
    is_multirow, header_row_count = _detect_multirow_header(cells_raw)

    if is_multirow:
        # 다단헤더: 각 column에 대해 N개 header row의 text를 stack
        # 단, bbox=null cell은 좌측 가장 가까운 bbox 있는 cell의 text 상속 (horizontally merged)
        # 그리고 빈 text는 상위 row의 text 상속 (vertically merged)
        header_paths = _stack_multirow_headers(cells_raw, header_row_count, columns)
    else:
        # single-level
        first_row = cells_raw[0]
        header_paths = [
            [(c.get("text") or "").strip() or ""]
            for c in first_row
        ]
        header_row_count = 1

    return (header_paths, header_row_count)


def _detect_multirow_header(
    cells_raw: List[List[Dict[str, Any]]],
) -> tuple[bool, int]:
    """다단헤더 여부와 header row 수를 추정.

    Returns: (is_multirow, header_row_count)
    """
    if len(cells_raw) < 2:
        return (False, 1)

    first_row = cells_raw[0]
    # 첫 row의 cell width 평균 (bbox 있는 cell만)
    widths = []
    for c in first_row:
        bb = c.get("bbox")
        if bb and len(bb) == 4:
            widths.append(bb[2] - bb[0])
    if not widths:
        return (False, 1)

    avg_w = sum(widths) / len(widths)
    has_wide_cell = any(w >= avg_w * WIDE_CELL_RATIO for w in widths)
    if not has_wide_cell:
        return (False, 1)

    # 두 번째 row가 짧은 text + 빈 cell 패턴인지
    second_row = cells_raw[1]
    non_empty_texts = [
        (c.get("text") or "").strip()
        for c in second_row
        if (c.get("text") or "").strip()
    ]
    if not non_empty_texts:
        # 모두 빈 cell → multi-row 가능성 낮음 (실제 data row일 수도)
        return (False, 1)

    avg_text_len = sum(len(t) for t in non_empty_texts) / len(non_empty_texts)
    if avg_text_len > SHORT_TEXT_MAX:
        return (False, 1)

    # 두 번째 row OK → 3-row header 검토
    if len(cells_raw) >= 3:
        third_row = cells_raw[2]
        third_non_empty_texts = [
            (c.get("text") or "").strip()
            for c in third_row
            if (c.get("text") or "").strip()
        ]
        if third_non_empty_texts:
            third_avg_len = sum(len(t) for t in third_non_empty_texts) / len(third_non_empty_texts)
            # 세 번째 row가 모든 cell에 bbox 있고 짧으면 3-row header
            third_has_bbox_all = all(c.get("bbox") for c in third_row)
            if third_avg_len <= SHORT_TEXT_MAX and third_has_bbox_all:
                return (True, 3)

    return (True, 2)


def _stack_multirow_headers(
    cells_raw: List[List[Dict[str, Any]]],
    header_row_count: int,
    columns: int,
) -> List[List[str]]:
    """N-row header를 column별로 path stack.

    규칙:
    - bbox=null cell은 좌측 가장 가까운 bbox 있는 cell의 text 상속 (horizontally merged)
    - 빈 text는 위 row의 text 상속 (vertically merged 추정) — header 영역 내에서만
    """
    # 1. horizontally merged 보정 — 각 row에 대해 좌측 fill
    h_filled: List[List[str]] = []
    for r in range(min(header_row_count, len(cells_raw))):
        row = cells_raw[r]
        filled: List[str] = []
        last_text = ""
        for ci in range(min(columns, len(row))):
            c = row[ci]
            text = (c.get("text") or "").strip()
            bbox = c.get("bbox")
            if bbox is None and not text:
                # horizontally merged hidden → 좌측 text 상속
                filled.append(last_text)
            else:
                filled.append(text)
                if text:
                    last_text = text
        # 짧으면 패딩
        while len(filled) < columns:
            filled.append("")
        h_filled.append(filled)

    # 2. vertically merged 보정 — header rows 내에서 위 → 아래로 빈 cell fill
    for r in range(1, len(h_filled)):
        for ci in range(columns):
            if not h_filled[r][ci]:
                h_filled[r][ci] = h_filled[r - 1][ci]

    # 3. path stack
    paths: List[List[str]] = []
    for ci in range(columns):
        path = []
        for r in range(header_row_count):
            t = h_filled[r][ci] if r < len(h_filled) else ""
            if t:
                # 중복 제거 (수직 merge 후 같은 값이 stack됨)
                if not path or path[-1] != t:
                    path.append(t)
        paths.append(path)
    return paths


def _infer_title_candidate(
    page_num: int,
    table_index: int,
    table_bbox: Optional[List[float]],
    para_blocks: List[Dict[str, Any]],
    first_row_cells: List[Dict[str, Any]],
) -> Optional[str]:
    """5단계 우선순위 title_candidate 추정 (b4-8.md §3.2)."""
    # 1. table 직전 paragraph block
    title_from_para = _find_preceding_paragraph_title(table_bbox, para_blocks)
    if title_from_para:
        return title_from_para

    # 2. table 내부 첫 행이 제목형 구조 (1 cell만 text 있고 나머지 비어있음)
    title_from_first_row = _find_first_row_title(first_row_cells)
    if title_from_first_row:
        return title_from_first_row

    # 3. nearby heading (paragraph blocks 중 heading type)
    heading = _find_nearby_heading(table_bbox, para_blocks)
    if heading:
        return heading

    # 4. 키워드 매칭 (1단계 paragraph에 키워드 발견)
    title_kw = _find_keyword_title(para_blocks)
    if title_kw:
        return title_kw

    # 5. fallback
    return f"표 p{page_num}-t{table_index + 1}"


def _find_preceding_paragraph_title(
    table_bbox: Optional[List[float]],
    para_blocks: List[Dict[str, Any]],
) -> Optional[str]:
    """table 직전 paragraph block의 text가 1~40자, 목차/안내문 아니면 사용."""
    if not table_bbox or len(table_bbox) != 4:
        return None
    table_y0 = table_bbox[1]
    candidates = []
    for pb in para_blocks:
        pbb = pb.get("bbox")
        if not pbb or len(pbb) != 4:
            continue
        # paragraph가 table 위에 있는가 (y1 <= table.y0)
        if pbb[3] > table_y0:
            continue
        text = (pb.get("text") or "").strip()
        if not text:
            continue
        if not (TITLE_PARAGRAPH_MIN_LEN <= len(text) <= TITLE_PARAGRAPH_MAX_LEN):
            continue
        if is_toc_or_instruction(text):
            continue
        candidates.append((pbb[3], text))  # y1 (가장 가까운 것 우선)
    if not candidates:
        return None
    # y1이 큰(table에 가까운) 것 우선
    candidates.sort(reverse=True)
    return candidates[0][1]


def _find_first_row_title(first_row_cells: List[Dict[str, Any]]) -> Optional[str]:
    """첫 행이 제목형 구조면 그 text 사용.

    제목형 = 1개 cell만 text 있고 나머지 비어있음 + text 길이 1~40
    """
    if not first_row_cells:
        return None
    non_empty = [
        (c.get("text") or "").strip()
        for c in first_row_cells
        if (c.get("text") or "").strip()
    ]
    if len(non_empty) != 1:
        return None
    text = non_empty[0]
    if not (TITLE_PARAGRAPH_MIN_LEN <= len(text) <= TITLE_PARAGRAPH_MAX_LEN):
        return None
    if is_toc_or_instruction(text):
        return None
    return text


def _find_nearby_heading(
    table_bbox: Optional[List[float]],
    para_blocks: List[Dict[str, Any]],
) -> Optional[str]:
    """가장 가까운 heading type block (위쪽)."""
    if not table_bbox or len(table_bbox) != 4:
        return None
    table_y0 = table_bbox[1]
    candidates = []
    for pb in para_blocks:
        if pb.get("type") != "heading":
            continue
        pbb = pb.get("bbox")
        if not pbb or len(pbb) != 4:
            continue
        if pbb[3] > table_y0:
            continue
        text = (pb.get("text") or "").strip()
        if not text or len(text) > TITLE_PARAGRAPH_MAX_LEN:
            continue
        candidates.append((pbb[3], text))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _find_keyword_title(para_blocks: List[Dict[str, Any]]) -> Optional[str]:
    """paragraph 중 키워드 포함된 것 첫 번째."""
    for pb in para_blocks:
        text = (pb.get("text") or "").strip()
        kw = find_keyword_in_text(text)
        if kw:
            return kw
    return None


def _judge_is_fragment(
    columns: int,
    rows: int,
    cells_raw: List[List[Dict[str, Any]]],
    empty_count: int,
    title_candidate: Optional[str],
    para_blocks: List[Dict[str, Any]],
    table_bbox: Optional[List[float]],
) -> bool:
    """b4-8.md §3.1 is_fragment 판정.

    is_fragment = (
        columns == 1
        or (columns == 2 and rows <= 3 and all_cells_are_short_text)
        or (nearby_paragraph_is_toc_or_instruction
            and cells_are_word_fragments
            and empty_field_count == 0)
    )

    예외: columns == 1이라도 empty_field_count 많고 title_candidate 명확하면 needs_review
    """
    # 예외 케이스 먼저
    if columns == 1 and empty_count >= 3 and title_candidate and \
       not title_candidate.startswith("표 p"):
        return False  # needs_review로 남김 (=is_fragment=False)

    if columns == 1:
        return True

    if columns == 2 and rows <= 3:
        # all_cells_are_short_text: 모든 cell text가 ≤ 8자
        all_short = True
        for row in cells_raw:
            for c in row:
                t = (c.get("text") or "").strip()
                if len(t) > 8:
                    all_short = False
                    break
            if not all_short:
                break
        if all_short:
            return True

    # TOC/instruction context + word fragments + no empty field
    if empty_count == 0 and table_bbox:
        # 직전 paragraph가 목차/안내문인지
        nearby_toc = False
        for pb in para_blocks:
            pbb = pb.get("bbox")
            if not pbb or len(pbb) != 4:
                continue
            if pbb[3] > table_bbox[1]:
                continue
            text = (pb.get("text") or "").strip()
            if is_toc_or_instruction(text):
                nearby_toc = True
                break
        if nearby_toc:
            # cells가 word fragments인지 (모든 cell text ≤ 6자, 또는 빈)
            word_fragments = True
            for row in cells_raw:
                for c in row:
                    t = (c.get("text") or "").strip()
                    if len(t) > 6:
                        word_fragments = False
                        break
                if not word_fragments:
                    break
            if word_fragments:
                return True

    return False


def _compute_confidence(
    title_candidate: Optional[str],
    columns: int,
    rows: int,
    empty_count: int,
    header_paths: List[List[str]],
) -> float:
    """b4-8.md §3.3 confidence 산식.

    confidence = 0.5
              + 0.1 * bool(title_candidate)
              + 0.1 * (columns >= 3)
              + 0.1 * (rows >= 3)
              + 0.1 * (empty_field_count >= 1)
              + 0.1 * header_paths_are_consistent

    header_paths_are_consistent: 모든 column의 header path 깊이가 동일
    """
    c = 0.5
    # title이 fallback이 아닌 경우만 가점
    if title_candidate and not title_candidate.startswith("표 p"):
        c += 0.1
    if columns >= 3:
        c += 0.1
    if rows >= 3:
        c += 0.1
    if empty_count >= 1:
        c += 0.1
    if header_paths:
        depths = [len(p) for p in header_paths]
        if depths and len(set(depths)) == 1:
            c += 0.1
    return max(0.0, min(1.0, c))
