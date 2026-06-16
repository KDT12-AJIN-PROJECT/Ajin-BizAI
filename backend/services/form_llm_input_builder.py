"""
FormParser v2 — P1 Layer 2: LLM Input Builder (Semantic Markdown Builder).

Layout IR (page_N_layout.json) → page_N_llm_input.md (LLM 친화 + semantic markers).

Semantic markers:
  - <EMPTY_FIELD id="..."> / <WRITE_HERE id="..."> — 빈 입력 셀
  - [ ] option / [√] option              — 체크박스
  - <SIGNATURE_FIELD id="...">           — 서명·날인
  - === PAGE N ===                        — 페이지 구분
  - <!-- block: ..., type: ... -->        — block 메타 (HTML comment)

bbox 숫자는 LLM 입력에 포함하지 않음 (source_map.json에 보관).

Vision fallback은 TODO/interface만 — 실제 구현 없음.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

# 체크박스 옵션 추출 정규식: "□유 / □무" → ["유", "무"]
RE_CHECKBOX_OPT = re.compile(r"[□☐◻](?:\s*)([^\s□☐◻/,()]+)")
RE_SIGNATURE_HINT = re.compile(r"\((인|서명)\)|직인|자필서명")


# ─── Vision fallback interface (P1 범위 외 — stub) ──────────────────
class VisionFallbackInterface:
    """이미지 기반 추출 (P1에서는 구현 안 함, P3 이후 검토).

    TODO: PDF 페이지 image → LLM Vision 호출 → table/text 추출.
    Layout IR 정확도 낮은 페이지에 대해 fallback으로 사용 예정.
    """

    def should_fallback(self, layout: Dict[str, Any]) -> bool:
        # TODO: 신호 정의 (예: chars_count < 50, tables_count == 0이지만 lines 많음)
        return False

    def extract_via_vision(self, page_image_path: str) -> Dict[str, Any]:
        raise NotImplementedError("Vision fallback은 P1 범위 외")


# ─── Semantic Markdown Builder ─────────────────────────────────────


def _render_table_block(block: Dict[str, Any]) -> List[str]:
    """table block → GFM 표 + semantic markers."""
    table_id = block.get("table_id", "T?")
    page = block.get("_page", "?")
    lines = [f"<!-- block: {block['block_id']}, type: table, table_id: {table_id}, page: {page} -->"]

    rows = block.get("rows", [])
    if not rows:
        lines.append(f"<!-- (empty table {table_id}) -->")
        return lines

    # 모든 row의 cell 수가 같다고 가정 (다르면 max에 맞춤)
    n_cols = max((len(r["cells"]) for r in rows), default=0)

    def render_cell(cell: Dict[str, Any]) -> str:
        text = (cell.get("text") or "").strip()
        cid = cell.get("cell_id", "?")
        if not text or cell.get("is_empty"):
            # 빈 셀 → semantic marker
            return f'<EMPTY_FIELD id="{cid}">'
        # 체크박스 옵션 셀
        opts = RE_CHECKBOX_OPT.findall(text)
        if opts:
            rendered = []
            # 원문 □·☐ 위치 그대로 [ ] 표기로
            t = text.replace("□", "[ ]").replace("☐", "[ ]").replace("◻", "[ ]")
            return t
        # 서명 셀
        if RE_SIGNATURE_HINT.search(text):
            return f'<SIGNATURE_FIELD id="{cid}"> {text}'
        # 일반 텍스트 셀 (개행은 <br>로)
        return text.replace("\n", " <br> ").replace("|", "\\|")

    # 첫 행을 header로 (관용)
    first = rows[0]["cells"]
    header_cells = [render_cell(c) for c in first]
    # 부족분은 공백
    while len(header_cells) < n_cols:
        header_cells.append("")
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("| " + " | ".join(["---"] * n_cols) + " |")

    for row in rows[1:]:
        cells = [render_cell(c) for c in row["cells"]]
        while len(cells) < n_cols:
            cells.append("")
        lines.append("| " + " | ".join(cells) + " |")

    return lines


def _render_text_block(block: Dict[str, Any]) -> List[str]:
    """text block (heading / paragraph / signature) → markdown."""
    btype = block.get("type", "paragraph")
    page = block.get("_page", "?")
    text = block.get("text") or ""
    text_stripped = text.strip()
    if not text_stripped:
        return []

    lines = [f"<!-- block: {block['block_id']}, type: {btype}, page: {page} -->"]

    if btype == "heading":
        # 글꼴 크기로 H 레벨 결정 (단순)
        font = block.get("font_size_avg", 12)
        h_level = "#" if font >= 16 else ("##" if font >= 13 else "###")
        # heading은 한 줄로
        single_line = text_stripped.replace("\n", " ")
        lines.append(f"{h_level} {single_line}")
        return lines

    if btype == "signature":
        # 서명 영역
        single_line = text_stripped.replace("\n", " ")
        lines.append(f"{single_line} <SIGNATURE_FIELD id=\"{block['block_id']}.sig\">")
        return lines

    # paragraph — 체크박스 변환 + 그대로
    rendered = text_stripped.replace("□", "[ ]").replace("☐", "[ ]").replace("◻", "[ ]")
    rendered = rendered.replace("[√]", "[x]").replace("[v]", "[x]")
    lines.append(rendered)
    return lines


def build_llm_input_for_page(layout: Dict[str, Any]) -> str:
    """단일 페이지 Layout IR → page_N_llm_input.md."""
    page_n = layout["page_number"]
    out: List[str] = [f"=== PAGE {page_n} ==="]
    # raw counts을 페이지 시작 주석으로 (LLM에게 페이지 규모 힌트)
    raw = layout.get("raw", {})
    out.append(
        f"<!-- raw_counts: chars={raw.get('chars_count', 0)}, "
        f"words={raw.get('words_count', 0)}, "
        f"tables={raw.get('tables_count', 0)} -->"
    )
    out.append("")

    for blk in layout.get("blocks", []):
        blk_with_page = {**blk, "_page": page_n}
        if blk["type"] == "table":
            out.extend(_render_table_block(blk_with_page))
        else:
            out.extend(_render_text_block(blk_with_page))
        out.append("")  # blocks 간 빈 줄

    return "\n".join(out).rstrip() + "\n"


def build_llm_inputs_for_pdf(
    pages_layout: List[Dict[str, Any]],
    out_dir: Path,
) -> Dict[str, Any]:
    """모든 페이지에 대해 page_N_llm_input.md 생성.

    Returns:
        {"page_N": {"path": ..., "size_chars": ...}, ...}
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {}

    # 통합 파일도 생성 (전체 PDF llm_input.md) — P3에서 페이지 단위로 분할 사용
    combined: List[str] = []
    for layout in pages_layout:
        md = build_llm_input_for_page(layout)
        p = layout["page_number"]
        path = out_dir / f"page_{p}_llm_input.md"
        path.write_text(md, encoding="utf-8")
        combined.append(md)
        result[f"page_{p}"] = {
            "path": str(path),
            "size_chars": len(md),
        }

    combined_path = out_dir / "all_pages_llm_input.md"
    combined_path.write_text("\n\n".join(combined), encoding="utf-8")
    result["_combined"] = {
        "path": str(combined_path),
        "size_chars": sum(r["size_chars"] for r in result.values()),
    }

    return result
