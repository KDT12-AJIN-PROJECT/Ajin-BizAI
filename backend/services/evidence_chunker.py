"""E-2 Phase 2 — evidence_chunker.

parsed_text를 RAG/embedding에 적합한 작은 단위(chunk)로 분리.

전략:
  1. 페이지 마커 (=== PAGE N ===) 인식 — 있으면 페이지 단위로 1차 분리
  2. 각 페이지/문서 내에서 chunk_chars 단위로 2차 분리
  3. 단어/줄바꿈 경계에서 가능한 한 자르기 (의미 단위 보존)
  4. overlap_chars로 경계 정보 손실 방지

토큰 ↔ 한국어 char 변환 (대략):
  - 영어: 1 token ≈ 4 chars
  - 한국어: 1 token ≈ 1.5~2 chars
  - DEFAULT 500 토큰 ≈ 한국어 1000~1500 chars

발주 e-2: 외부 검색 금지, 사용자 자료만, 근거 없는 사실 생성 금지.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

# 한국어 기준 권장값 (사용자 결정: 원안 500토큰 + overlap 50, 테스트 후 조정)
DEFAULT_CHUNK_CHARS = 1500    # ≈ 500 토큰 (한국어)
DEFAULT_OVERLAP_CHARS = 150   # ≈ 50 토큰

PAGE_MARKER_RE = re.compile(r"^=== PAGE (\d+) ===", re.MULTILINE)

# 2026-05-18 Phase 9-A: chunk quality filter
# 목차/표제/노이즈 chunk를 자동 reject — 매칭 정확도 ↑
HANGUL_RE = re.compile(r"[가-힣]")
TOC_DOT_RE = re.compile(r"\.{4,}")  # 점선 4개+ ("...........")
TOC_DOT_CHARS = re.compile(r"[.·…]")

# chunk_quality_score < 이 값이면 store에 안 넣음
DEFAULT_QUALITY_THRESHOLD = 0.4


def chunk_quality_score(content: str) -> float:
    """chunk 내용 품질 점수 (0~1).

    낮은 점수 (~0.0~0.3) = 목차/표제/점선/노이즈 chunk → reject 권장
    중간 점수 (0.3~0.6) = 일부 의미 있지만 약함 (재무 표 등)
    높은 점수 (0.6~1.0) = 본문 chunk

    체크:
      - 점선 비율 (............)
      - 한국어 비율 (의미 있는 텍스트)
      - 목차 패턴 (주석 N., ........숫자)
    """
    if not content or len(content.strip()) < 30:
        return 0.0

    # 1. 점선 노이즈 — 가장 큰 신호
    dot_count = len(TOC_DOT_CHARS.findall(content))
    dot_ratio = dot_count / max(1, len(content))
    if dot_ratio > 0.25:
        return 0.05  # 점선 위주 = 거의 0
    if dot_ratio > 0.15:
        return 0.2

    # 2. 목차 패턴 — "주석 N." "표 N." "......숫자"
    toc_dot_hits = len(TOC_DOT_RE.findall(content))
    has_juseok = "주석" in content and any(c.isdigit() for c in content)
    if toc_dot_hits >= 3 or (has_juseok and toc_dot_hits >= 2):
        return 0.15

    # 3. 한국어 비율 — 너무 낮으면 영어 약어/숫자 위주
    hangul_count = len(HANGUL_RE.findall(content))
    hangul_ratio = hangul_count / len(content)

    # 4. 숫자 비율
    digit_count = sum(1 for c in content if c.isdigit())
    digit_ratio = digit_count / len(content)

    # 재무표 — 숫자/콤마 위주 + 한국어 약간
    if hangul_ratio < 0.1 and digit_ratio > 0.4:
        return 0.45  # 재무 표 (의미 있지만 매칭은 약함)

    # 표제만 — 한국어 적고 숫자도 적음 → 영문/약어
    if hangul_ratio < 0.05 and digit_ratio < 0.2:
        return 0.25

    # 정상 본문
    if hangul_ratio >= 0.3:
        return 0.9
    if hangul_ratio >= 0.15:
        return 0.7
    return 0.5


def _find_page_at(pos: int, page_marks: List[tuple]) -> Optional[int]:
    """주어진 pos에서 가장 가까운 (이전 또는 같은) 페이지 번호."""
    page: Optional[int] = None
    for pos_m, p_num in page_marks:
        if pos_m <= pos:
            page = p_num
        else:
            break
    return page


def _find_soft_cut(text: str, start: int, target_end: int) -> int:
    """단어/문장/줄바꿈 경계에서 자를 위치 결정.

    target_end 부근 ~200 chars 범위 내에서 줄바꿈/마침표/공백 순으로 검색.
    못 찾으면 target_end 그대로 반환.
    """
    if target_end >= len(text):
        return len(text)
    search_start = max(start + 1, target_end - 200)

    # 우선순위: 줄바꿈 > 마침표 > 공백
    for sep in ("\n\n", "\n", ". ", "다.", "다. ", "다.\n", " "):
        pos = text.rfind(sep, search_start, target_end)
        if pos > start:
            return pos + len(sep)
    return target_end


def chunk_text(
    text: str,
    source_file: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    session_id: str = "",
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """parsed_text 단일 문서 → chunks 분리.

    Returns:
        list of {
          chunk_id, source_file, page, start_char, end_char,
          content, content_chars, session_id,
        }
    """
    if not text or not text.strip():
        return []
    if chunk_chars <= 0:
        chunk_chars = DEFAULT_CHUNK_CHARS
    if overlap_chars < 0 or overlap_chars >= chunk_chars:
        overlap_chars = min(DEFAULT_OVERLAP_CHARS, chunk_chars // 4)

    # 페이지 마커 위치 (오름차순)
    page_marks: List[tuple] = [
        (m.start(), int(m.group(1))) for m in PAGE_MARKER_RE.finditer(text)
    ]

    chunks: List[Dict[str, Any]] = []
    pos = 0
    text_len = len(text)

    while pos < text_len:
        target_end = min(pos + chunk_chars, text_len)
        end = _find_soft_cut(text, pos, target_end)
        # 무한 루프 방지
        if end <= pos:
            end = min(pos + chunk_chars, text_len)

        content = text[pos:end].strip()
        # 페이지 마커 자체가 chunk가 되는 케이스 방지
        if content and not PAGE_MARKER_RE.fullmatch(content):
            # 2026-05-18 Phase 9-A: quality filter
            q_score = chunk_quality_score(content)
            if q_score >= quality_threshold:
                chunks.append({
                    "chunk_id": f"ch_{uuid.uuid4().hex[:10]}",
                    "session_id": session_id,
                    "source_file": source_file,
                    "page": _find_page_at(pos, page_marks),
                    "start_char": pos,
                    "end_char": end,
                    "content": content,
                    "content_chars": len(content),
                    "quality_score": round(q_score, 3),
                })
            # else: reject (목차/표제/노이즈)

        if end >= text_len:
            break
        # overlap 적용 후 다음 chunk
        next_pos = end - overlap_chars
        if next_pos <= pos:
            next_pos = pos + 1
        pos = next_pos

    return chunks


def chunk_attachments(
    attachments: List[Dict[str, Any]],
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    session_id: str = "",
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """여러 attachments → 모든 chunks 합쳐 반환.

    attachment shape: {file_name, parsed_text, ...}
    quality_threshold: chunk quality score 미달 chunk reject.
    """
    all_chunks: List[Dict[str, Any]] = []
    for att in attachments or []:
        if not isinstance(att, dict):
            continue
        text = att.get("parsed_text") or ""
        if not text:
            continue
        fname = att.get("file_name") or att.get("filename") or "unknown"
        all_chunks.extend(
            chunk_text(
                text, fname,
                chunk_chars=chunk_chars,
                overlap_chars=overlap_chars,
                session_id=session_id,
                quality_threshold=quality_threshold,
            )
        )
    return all_chunks


def stats(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """chunks 통계 — 디버그/로깅용."""
    if not chunks:
        return {"count": 0, "total_chars": 0, "avg_chars": 0, "by_source": {}}
    total = sum(c["content_chars"] for c in chunks)
    by_source: Dict[str, int] = {}
    for c in chunks:
        sf = c.get("source_file") or "unknown"
        by_source[sf] = by_source.get(sf, 0) + 1
    return {
        "count": len(chunks),
        "total_chars": total,
        "avg_chars": round(total / len(chunks)),
        "by_source": by_source,
    }
