"""Hybrid 2-pass form parser.

2026-05-18 신규 — form_parser quality 안정성 확보용 옵션 path.

Strategy:
  1. layout_text에서 chapter 헤더를 regex로 탐지 (LLM 호출 0)
  2. 각 chapter를 chunk로 분리
  3. 각 chunk를 provider.form_parser로 병렬 호출 (asyncio.gather)
  4. 결과 merge — section_id / question_id 재할당

장점:
  - 작은 chunk → mini가 안정적 처리
  - 병렬 호출로 시간 단축
  - section 누락 거의 없음 (regex가 모든 chapter 탐지)

단점:
  - 호출 횟수 N배 → 비용 증가 (mini 호출당 ~3원 × N chunks)
  - table_normalizer/promoter 적용 제외 (각 chunk가 자체 처리)
  - Chapter 경계가 모호한 form엔 약함

기존 단일 호출 path (provider.form_parser)는 무변경 — fallback / 빠른 모드로 보존.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ─── Chapter 탐지 패턴 ───────────────────────────────────────────
# 1. Numbered chapter: "1. 스마트공장 구축개요"
#    - sub-chapter (1.1, 1.2) 제외 위해 negative lookahead `(?!\d)`
RE_NUMBERED_CHAPTER = re.compile(
    r"^(\d{1,2})\.\s+(?!\d)([^\n]{2,80})", re.MULTILINE
)
# 2. 별지/서식 헤더: "서식 1", "[별지 제1호]", "Form-1"
RE_FORM_TEMPLATE = re.compile(
    r"^(서식\s*\d+|\[?별지\s*제?\d+호?\]?|Form[-\s]?\d+)\s*([^\n]{0,60})",
    re.MULTILINE,
)
# 3. □ 마커 chapter: "□ 기 수행 R&D과제 공급기술 개요"
RE_BOX_CHAPTER = re.compile(r"^□\s+([^\n]{2,80})", re.MULTILINE)
# 4. 페이지 마커
RE_PAGE_MARKER = re.compile(r"^=== PAGE (\d+) ===", re.MULTILINE)


def detect_chapters(layout_text: str) -> List[Dict[str, Any]]:
    """layout_text에서 chapter 헤더 탐지.

    Returns:
        [{'pos', 'title', 'kind', 'number', 'page'}, ...] (pos 오름차순)
    """
    # 페이지 마커 위치 (pos → page_num)
    page_markers: List[Tuple[int, int]] = []
    for m in RE_PAGE_MARKER.finditer(layout_text):
        page_markers.append((m.start(), int(m.group(1))))

    def find_page_at(pos: int) -> int:
        """주어진 pos에서 가장 가까운 (이전 또는 같은) 페이지 번호."""
        for p_pos, p_num in reversed(page_markers):
            if p_pos <= pos:
                return p_num
        return 1

    chapters: List[Dict[str, Any]] = []

    # Numbered chapter
    for m in RE_NUMBERED_CHAPTER.finditer(layout_text):
        chapters.append({
            "pos": m.start(),
            "title": f"{m.group(1)}. {m.group(2).strip()[:60]}",
            "kind": "numbered",
            "number": int(m.group(1)),
            "page": find_page_at(m.start()),
        })

    # Form template (서식N, 별지)
    for m in RE_FORM_TEMPLATE.finditer(layout_text):
        title = (m.group(1) + " " + (m.group(2) or "")).strip()
        chapters.append({
            "pos": m.start(),
            "title": title[:60],
            "kind": "form_template",
            "number": None,
            "page": find_page_at(m.start()),
        })

    # □ chapter
    for m in RE_BOX_CHAPTER.finditer(layout_text):
        chapters.append({
            "pos": m.start(),
            "title": m.group(1).strip()[:60],
            "kind": "box",
            "number": None,
            "page": find_page_at(m.start()),
        })

    # 정렬 + 중복 제거 (50자 이내는 같은 chapter로 간주)
    chapters.sort(key=lambda c: c["pos"])
    deduped: List[Dict[str, Any]] = []
    for c in chapters:
        if deduped and (c["pos"] - deduped[-1]["pos"] < 50):
            continue
        deduped.append(c)

    # 2026-05-18: 같은 chapter number 중복 제거 (테이블 내 "1." "2." 등 노이즈 차단)
    # 첫 등장만 유지 — 본문 흐름상 첫 등장이 chapter 헤더일 확률 높음
    seen_numbers = set()
    final: List[Dict[str, Any]] = []
    for c in deduped:
        if c["kind"] == "numbered":
            if c["number"] in seen_numbers:
                continue
            seen_numbers.add(c["number"])
        final.append(c)

    return final


def split_into_chunks(
    layout_text: str,
    chapters: List[Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    """layout_text를 chapter 경계로 chunk 분할.

    Returns:
        [(chunk_text, chapter_meta), ...]
    """
    if not chapters:
        return [(layout_text, {"title": "전체", "kind": "fallback", "page": 1})]

    chunks: List[Tuple[str, Dict[str, Any]]] = []

    # Pre-chunk: 첫 chapter 이전 (표지/기업정보) — 100자 이상이면 별도 chunk
    if chapters[0]["pos"] > 100:
        pre_text = layout_text[: chapters[0]["pos"]].strip()
        if pre_text:
            chunks.append((
                pre_text,
                {
                    "title": "표지 / 기업 기본정보",
                    "kind": "intro",
                    "number": None,
                    "page": 1,
                },
            ))

    # Chapter chunks
    for i, ch in enumerate(chapters):
        start = ch["pos"]
        end = chapters[i + 1]["pos"] if i + 1 < len(chapters) else len(layout_text)
        chunk_text = layout_text[start:end].strip()
        if chunk_text:
            chunks.append((chunk_text, ch))

    return chunks


async def parse_form_hybrid(
    layout_text: str,
    form_name: str,
    provider,
    request_id: str = "",
    session_id: str = "",
    max_chunks: int = 12,
) -> Dict[str, Any]:
    """Hybrid 2-pass form parser.

    Args:
        layout_text: 전체 양식 텍스트 (PAGE 마커 포함)
        form_name: 양식 파일명
        provider: AIProvider instance (provider.form_parser 호출)
        request_id / session_id: audit log용
        max_chunks: chunk 수 상한 (초과 시 단일 호출 fallback)

    Returns:
        FormSchema dict (기존 provider.form_parser와 동일 shape)
        + _hybrid_meta 필드 (chunks_total / chapters_detected / etc.)
    """
    chapters = detect_chapters(layout_text)
    logger.info(
        "[form_parser_hybrid] 탐지된 chapters: %d개 (kind 분포: %s)",
        len(chapters),
        {k: sum(1 for c in chapters if c["kind"] == k)
         for k in ("numbered", "form_template", "box")},
    )

    # Chapter가 너무 적으면 hybrid 의미 없음 → 단일 호출
    if len(chapters) < 2:
        logger.info("[form_parser_hybrid] chapters %d < 2, 단일 호출 fallback", len(chapters))
        result = await provider.form_parser(
            layout_text, form_name,
            request_id=request_id, session_id=session_id,
        )
        result["_hybrid_meta"] = {
            "chunks_total": 1,
            "chapters_detected": len(chapters),
            "fallback_to_single": True,
            "fallback_reason": f"insufficient_chapters ({len(chapters)})",
        }
        return result

    chunks = split_into_chunks(layout_text, chapters)
    logger.info("[form_parser_hybrid] 분할 chunks: %d개", len(chunks))

    # Chunk 수 상한 초과 시 fallback (비용 보호)
    if len(chunks) > max_chunks:
        logger.warning(
            "[form_parser_hybrid] chunks %d > max_chunks %d, 단일 호출 fallback",
            len(chunks), max_chunks,
        )
        result = await provider.form_parser(
            layout_text, form_name,
            request_id=request_id, session_id=session_id,
        )
        result["_hybrid_meta"] = {
            "chunks_total": len(chunks),
            "chapters_detected": len(chapters),
            "fallback_to_single": True,
            "fallback_reason": f"too_many_chunks ({len(chunks)} > {max_chunks})",
        }
        return result

    # 병렬 호출
    async def call_for_chunk(idx: int, chunk_text: str, meta: Dict[str, Any]):
        chunk_name = f"{form_name} [chunk{idx + 1}: {meta['title'][:30]}]"
        try:
            result = await provider.form_parser(
                chunk_text, chunk_name,
                request_id=f"{request_id}_c{idx}",
                session_id=session_id,
            )
            return (idx, meta, result, None)
        except Exception as e:
            logger.warning("[form_parser_hybrid] chunk %d 실패: %s", idx, e)
            return (idx, meta, None, str(e))

    tasks = [call_for_chunk(i, ct, m) for i, (ct, m) in enumerate(chunks)]
    chunk_results = await asyncio.gather(*tasks)

    # 결과 merge
    merged_sections: List[Dict[str, Any]] = []
    chunks_succeeded = 0
    chunks_failed = 0
    failure_details: List[Dict[str, Any]] = []

    for idx, meta, result, err in chunk_results:
        if result is None:
            chunks_failed += 1
            failure_details.append({"chunk_idx": idx, "title": meta.get("title"), "error": err})
            continue
        chunks_succeeded += 1

        # 각 chunk가 1+개 section 반환
        for sec in (result.get("sections") or []):
            new_sid = f"S{len(merged_sections) + 1:03d}"
            sec_copy = dict(sec)
            sec_copy["section_id"] = new_sid

            # chunk의 meta title이 의미 있으면 사용 (LLM이 빈 title 반환할 때)
            llm_title = sec.get("title") or ""
            if meta.get("title") and (not llm_title or len(llm_title) < 3):
                sec_copy["title"] = meta["title"]

            sec_copy["order"] = len(merged_sections) + 1

            # question_id 재할당: {new_sid}-Q{nnn} or {new_sid}-T{nnn}
            q_idx, t_idx = 1, 1
            new_questions = []
            for q in (sec.get("questions") or []):
                q_copy = dict(q)
                is_table = q.get("is_table_item") or q.get("fill_mode") == "table_input"
                if is_table:
                    q_copy["question_id"] = f"{new_sid}-T{t_idx:03d}"
                    t_idx += 1
                else:
                    q_copy["question_id"] = f"{new_sid}-Q{q_idx:03d}"
                    q_idx += 1
                new_questions.append(q_copy)
            sec_copy["questions"] = new_questions

            merged_sections.append(sec_copy)

    return {
        "form_id": "form_001",
        "form_name": form_name,
        "source_file": form_name,
        "instruction_notes": None,
        "sections": merged_sections,
        "_hybrid_meta": {
            "chunks_total": len(chunks),
            "chapters_detected": len(chapters),
            "chunks_succeeded": chunks_succeeded,
            "chunks_failed": chunks_failed,
            "failure_details": failure_details,
            "fallback_to_single": False,
        },
    }
