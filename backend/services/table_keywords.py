"""
A-4 — 표 title_candidate 추정용 키워드 사전.

b4-8.md §3.11: 키워드 사전은 normalizer/promoter 내부에 하드코딩하지 않고
별도 파일로 분리. 향후 form_id별 keyword set 지원 가능 구조.

MVP에서는 상수로 시작.
"""
from __future__ import annotations
from typing import Optional

# 표 제목 키워드 (form-agnostic 일반 키워드)
TABLE_TITLE_KEYWORDS: tuple[str, ...] = (
    "기관현황",
    "요약서",
    "사업비",
    "비목별",
    "인건비",
    "추진일정",
    "예산",
    "수행내용",
    "성과지표",
    "사업개요",
    "참여기관",
    "역할분담",
    "위험관리",
    "마일스톤",
    "산출물",
)

# 목차 / 안내문 / 주의문 패턴 — title_candidate 추정 시 제외
TOC_INSTRUCTION_PATTERNS: tuple[str, ...] = (
    "목 차",
    "목차",
    "Ⅰ.",
    "Ⅱ.",
    "Ⅲ.",
    "Ⅳ.",
    "Ⅴ.",
    "Ⅵ.",
    "Ⅶ.",
    "Ⅷ.",
    "Ⅸ.",
    "Ⅹ.",
    "<작성요령",
    "< 작성요령",
    "※",
    "주의:",
    "참고:",
    "안내:",
)


def is_toc_or_instruction(text: str) -> bool:
    """텍스트가 목차/안내문/주의문 패턴인지 판정."""
    if not text:
        return True
    text_stripped = text.strip()
    if not text_stripped:
        return True
    for p in TOC_INSTRUCTION_PATTERNS:
        if text_stripped.startswith(p) or p in text_stripped[:10]:
            return True
    return False


def find_keyword_in_text(text: str) -> Optional[str]:
    """텍스트에서 키워드를 발견하면 그 키워드를 반환, 없으면 None."""
    if not text:
        return None
    for kw in TABLE_TITLE_KEYWORDS:
        if kw in text:
            return kw
    return None
