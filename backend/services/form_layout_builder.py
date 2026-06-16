"""
FormParser v2 — P1 Layer 1: Layout IR Builder.

PDF → 구조화된 Layout IR (page_layout.json) + 사람용 dump (tables.md, visual.png) + source_map.json.

Dependencies: pdfplumber + pypdfium2 + Pillow (모두 설치 확인됨).
PyMuPDF / Camelot / Docling / Unstructured 미사용.

Public API:
    build_layout_for_pdf(pdf_bytes, out_dir, file_id, file_name) -> dict
        per-page Layout IR + 산출물 디스크 저장 + 통합 source_map.json 작성.
"""
from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ─── visual.png 색상 정책 ────────────────────────────────────────────
COLOR_HEADING = (220, 38, 38, 153)        # 빨강 (alpha 0.6)
COLOR_PARAGRAPH = (220, 38, 38, 102)      # 빨강 (alpha 0.4 — 본문은 옅게)
COLOR_TABLE_CELL = (37, 99, 235, 153)     # 파랑
COLOR_TABLE_EMPTY = (22, 163, 74, 153)    # 초록 (빈 셀)
COLOR_CHECKBOX = (202, 138, 4, 153)       # 노랑
COLOR_SIGNATURE = (147, 51, 234, 153)     # 보라
COLOR_LABEL_TEXT = (71, 85, 105, 255)     # 라벨 글자
COLOR_LABEL_BG = (255, 255, 255, 200)     # 라벨 배경

DEFAULT_DPI = 150
DEFAULT_FONT_SIZE = 9

# Heuristic 정규식
RE_CHECKBOX = re.compile(r"[□☐◻◼☑☒]")  # □ ☐ ▻ ▼ ☑ ☒
RE_SIGNATURE_HINT = re.compile(r"\((인|서명)\)|직인|자필서명|인\s*$")


def _try_load_korean_font(size: int = DEFAULT_FONT_SIZE) -> ImageFont.ImageFont:
    """Windows 한글 폰트 우선 시도, 실패 시 default."""
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/NanumGothic.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _to_pixel_bbox(
    pdf_bbox: Tuple[float, float, float, float],
    page_width_pt: float,
    page_height_pt: float,
    img_width_px: int,
    img_height_px: int,
) -> Tuple[int, int, int, int]:
    """PDF 좌표 (포인트, y-원점 좌하단 또는 좌상단 — pdfplumber는 좌상단) → 이미지 픽셀 좌표."""
    x0, y0, x1, y1 = pdf_bbox
    sx = img_width_px / page_width_pt
    sy = img_height_px / page_height_pt
    return (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))


def _cluster_words_to_paragraphs(
    words: List[Dict[str, Any]],
    line_height_threshold: float = 6.0,
) -> List[Dict[str, Any]]:
    """words → paragraph 블록 (line·column 단순 클러스터링).

    Heuristic: 같은 y0 ± threshold → 같은 line. 비어있는 line으로 분리되면 새 paragraph.
    block.bbox = 포함 words의 union.
    """
    if not words:
        return []

    # y0 기준 정렬
    sorted_w = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    # line 그룹핑
    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    last_top: Optional[float] = None
    for w in sorted_w:
        if last_top is None or abs(w["top"] - last_top) <= line_height_threshold:
            current.append(w)
            last_top = w["top"] if last_top is None else last_top
        else:
            lines.append(current)
            current = [w]
            last_top = w["top"]
    if current:
        lines.append(current)

    # line → paragraph (간단: line 사이 gap > threshold*2면 새 paragraph)
    paragraphs: List[Dict[str, Any]] = []
    cur_para_lines: List[List[Dict[str, Any]]] = []
    last_bottom: Optional[float] = None
    for line in lines:
        line_top = min(w["top"] for w in line)
        line_bottom = max(w["bottom"] for w in line)
        if last_bottom is not None and (line_top - last_bottom) > line_height_threshold * 2:
            if cur_para_lines:
                paragraphs.append(_lines_to_block(cur_para_lines))
            cur_para_lines = [line]
        else:
            cur_para_lines.append(line)
        last_bottom = line_bottom
    if cur_para_lines:
        paragraphs.append(_lines_to_block(cur_para_lines))
    return paragraphs


def _lines_to_block(lines: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    flat = [w for line in lines for w in line]
    x0 = min(w["x0"] for w in flat)
    x1 = max(w["x1"] for w in flat)
    y0 = min(w["top"] for w in flat)
    y1 = max(w["bottom"] for w in flat)
    text = "\n".join(" ".join(w["text"] for w in line) for line in lines)
    sizes = [w.get("size", 0) for w in flat if w.get("size")]
    font_size_avg = sum(sizes) / len(sizes) if sizes else 0
    return {
        "bbox": [x0, y0, x1, y1],
        "text": text,
        "font_size_avg": round(font_size_avg, 1),
        "line_count": len(lines),
    }


def _classify_block(block: Dict[str, Any], median_font: float) -> str:
    """heading / paragraph / signature 분류 (table은 별도 처리)."""
    text = block.get("text", "")
    font = block.get("font_size_avg", 0)
    # signature 후보
    if RE_SIGNATURE_HINT.search(text):
        return "signature"
    # heading 후보: font_size_avg가 median + 2pt 초과 + 1~2 line
    if font and font >= median_font + 2 and block.get("line_count", 1) <= 2:
        return "heading"
    return "paragraph"


def _find_checkboxes_in_text(text: str) -> List[str]:
    """본문 텍스트에서 체크박스 문자 위치 목록 (간이)."""
    return RE_CHECKBOX.findall(text or "")


def _build_page_layout(
    page: pdfplumber.page.Page,
    page_number: int,
    img_width_px: int,
    img_height_px: int,
    dpi: int,
) -> Dict[str, Any]:
    """단일 page → Layout IR dict."""
    page_w = float(page.width)
    page_h = float(page.height)

    # 1. raw counts (sanity)
    chars = page.chars or []
    try:
        words = page.extract_words() or []
    except Exception as e:
        logger.warning("[extract_words] failed page=%d: %s", page_number, e)
        words = []
    lines = page.lines or []
    rects = page.rects or []

    # 2. tables
    try:
        raw_tables = page.extract_tables() or []
    except Exception as e:
        logger.warning("[extract_tables] failed page=%d: %s", page_number, e)
        raw_tables = []
    try:
        table_objs = page.find_tables() or []
    except Exception as e:
        logger.warning("[find_tables] failed page=%d: %s", page_number, e)
        table_objs = []

    # 3. table blocks (셀 bbox 매핑)
    table_blocks: List[Dict[str, Any]] = []
    # find_tables() → bbox 가짐. extract_tables() → 셀 텍스트 가짐. 둘을 zip.
    n = min(len(raw_tables), len(table_objs)) if table_objs else 0
    table_cell_bboxes = set()  # paragraph 필터링용
    for ti in range(n):
        t_obj = table_objs[ti]
        t_data = raw_tables[ti]
        rows_out: List[Dict[str, Any]] = []
        try:
            t_bbox = list(t_obj.bbox)
        except Exception:
            t_bbox = [0, 0, 0, 0]
        # find_tables의 cell bbox는 t_obj.cells (list of (x0,y0,x1,y1) per cell)
        cell_bboxes = getattr(t_obj, "cells", None) or []
        # cells는 평탄 list — row × col 매트릭스로 재구성: rows[r][c]
        # pdfplumber Table.rows 도 사용 가능
        try:
            tbl_rows = t_obj.rows  # list of Row objects with .cells
        except Exception:
            tbl_rows = []

        for ri, row_data in enumerate(t_data):
            cells_out: List[Dict[str, Any]] = []
            row_cells_bboxes: List[Any] = []
            if ri < len(tbl_rows):
                try:
                    row_cells_bboxes = list(tbl_rows[ri].cells)
                except Exception:
                    row_cells_bboxes = []
            for ci, cell_text in enumerate(row_data):
                cell_bbox = None
                if ci < len(row_cells_bboxes) and row_cells_bboxes[ci]:
                    cell_bbox = list(row_cells_bboxes[ci])
                    if len(cell_bbox) == 4:
                        table_cell_bboxes.add(tuple(round(x, 1) for x in cell_bbox))
                cell_text_clean = (cell_text or "").strip() if cell_text else ""
                cells_out.append({
                    "cell_id": f"T{ti + 1}.r{ri + 1}.c{ci + 1}",
                    "bbox": cell_bbox,
                    "text": cell_text_clean,
                    "is_empty": not bool(cell_text_clean),
                })
            rows_out.append({
                "row_id": f"T{ti + 1}.r{ri + 1}",
                "cells": cells_out,
            })

        table_blocks.append({
            "block_id": f"B_T{ti + 1}",
            "type": "table",
            "table_id": f"T{ti + 1}",
            "bbox": t_bbox,
            "row_count": len(rows_out),
            "col_count": (len(rows_out[0]["cells"]) if rows_out else 0),
            "rows": rows_out,
        })

    # 4. text blocks (paragraph / heading / signature) — words 클러스터링, 표 셀 영역 제외
    def _word_in_table(w: Dict[str, Any]) -> bool:
        wx, wy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
        for tb in table_blocks:
            x0, y0, x1, y1 = tb["bbox"]
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                return True
        return False

    words_outside = [w for w in words if not _word_in_table(w)]
    para_blocks_raw = _cluster_words_to_paragraphs(words_outside)

    # median font (heading 분류용)
    all_fonts = [b.get("font_size_avg", 0) for b in para_blocks_raw if b.get("font_size_avg", 0) > 0]
    median_font = sorted(all_fonts)[len(all_fonts) // 2] if all_fonts else 10

    text_blocks: List[Dict[str, Any]] = []
    for idx, b in enumerate(para_blocks_raw):
        block_type = _classify_block(b, median_font)
        text_blocks.append({
            "block_id": f"B_P{idx + 1}",
            "type": block_type,
            "bbox": b["bbox"],
            "text": b["text"],
            "font_size_avg": b["font_size_avg"],
            "line_count": b["line_count"],
            "checkbox_count": len(_find_checkboxes_in_text(b["text"])),
        })

    # 5. all blocks: text blocks + table blocks 합쳐서 y0 기준 정렬
    all_blocks = text_blocks + table_blocks
    all_blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

    return {
        "page_number": page_number,
        "page_size": {
            "width_pt": page_w,
            "height_pt": page_h,
            "img_width_px": img_width_px,
            "img_height_px": img_height_px,
            "dpi": dpi,
        },
        "blocks": all_blocks,
        "raw": {
            "chars_count": len(chars),
            "words_count": len(words),
            "lines_count": len(lines),
            "rects_count": len(rects),
            "tables_count": len(table_blocks),
        },
    }


def _render_page_image(
    pdf_bytes: bytes,
    page_index: int,
    dpi: int = DEFAULT_DPI,
) -> Image.Image:
    """pypdfium2로 페이지 PIL.Image 렌더링."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        page = pdf[page_index]
        scale = dpi / 72.0
        img = page.render(scale=scale).to_pil()
        return img
    finally:
        pdf.close()


def _draw_visual(
    base_img: Image.Image,
    layout: Dict[str, Any],
) -> Image.Image:
    """Layout IR의 blocks를 base 이미지 위에 overlay."""
    img = base_img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _try_load_korean_font(DEFAULT_FONT_SIZE)

    pw = layout["page_size"]["width_pt"]
    ph = layout["page_size"]["height_pt"]
    iw, ih = img.size

    for blk in layout["blocks"]:
        bbox_pt = blk.get("bbox") or [0, 0, 0, 0]
        if not bbox_pt or len(bbox_pt) != 4:
            continue
        px_bbox = _to_pixel_bbox(tuple(bbox_pt), pw, ph, iw, ih)
        btype = blk.get("type", "paragraph")

        if btype == "heading":
            color = COLOR_HEADING
            width = 3
        elif btype == "signature":
            color = COLOR_SIGNATURE
            width = 2
        elif btype == "table":
            color = COLOR_TABLE_CELL
            width = 2
        else:
            color = COLOR_PARAGRAPH
            width = 1

        draw.rectangle(px_bbox, outline=color, width=width)

        # 표 셀별 추가 처리
        if btype == "table":
            for row in blk.get("rows", []):
                for cell in row.get("cells", []):
                    cb = cell.get("bbox")
                    if not cb or len(cb) != 4:
                        continue
                    cell_px = _to_pixel_bbox(tuple(cb), pw, ph, iw, ih)
                    cell_color = COLOR_TABLE_EMPTY if cell.get("is_empty") else COLOR_TABLE_CELL
                    draw.rectangle(cell_px, outline=cell_color, width=1)

        # 라벨 (block_id) 좌상단
        label = blk.get("block_id", "")
        if label:
            lx, ly = px_bbox[0] + 2, max(0, px_bbox[1] - 12)
            try:
                tb = draw.textbbox((lx, ly), label, font=font)
                draw.rectangle(tb, fill=COLOR_LABEL_BG)
                draw.text((lx, ly), label, fill=COLOR_LABEL_TEXT, font=font)
            except Exception:
                pass

    return Image.alpha_composite(img, overlay).convert("RGB")


def _layout_to_tables_md(layout: Dict[str, Any]) -> str:
    """page_N_tables.md — 사람용 표 dump (GFM 표 + block 메타)."""
    lines = [f"# Page {layout['page_number']} — Tables\n"]
    table_blocks = [b for b in layout["blocks"] if b["type"] == "table"]
    if not table_blocks:
        lines.append("(이 페이지에 추출된 표 없음)\n")
        return "\n".join(lines)
    for tb in table_blocks:
        lines.append(f"## Table {tb['table_id']} ({tb['row_count']}행 × {tb['col_count']}열)")
        lines.append(f"- bbox: `{tb['bbox']}`")
        lines.append("")
        # GFM 표 헤더 (첫 행을 헤더로)
        rows = tb["rows"]
        if not rows:
            continue
        first_row = rows[0]
        headers = [c["text"] or "<EMPTY>" for c in first_row["cells"]]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows[1:]:
            cells = [c["text"] or "<EMPTY>" for c in row["cells"]]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def build_layout_for_pdf(
    pdf_bytes: bytes,
    out_dir: Path,
    file_id: str,
    file_name: str,
    max_pages: int = 50,
    dpi: int = DEFAULT_DPI,
) -> Dict[str, Any]:
    """PDF → Layout IR + 산출물 디스크 저장.

    Returns:
        {
            "file_id": ...,
            "file_name": ...,
            "page_count": N,
            "pages": [layout_per_page, ...],
            "artifacts": {"page_N": {"layout": path, "tables_md": path, "visual": path}, ...},
        }
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    pages_layout: List[Dict[str, Any]] = []
    artifacts: Dict[str, Dict[str, str]] = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        n_pages = min(len(pdf.pages), max_pages)
        for i in range(n_pages):
            page = pdf.pages[i]
            page_number = i + 1

            # 페이지 이미지 (먼저 render — 크기 추출용)
            img = _render_page_image(pdf_bytes, i, dpi=dpi)
            img_w, img_h = img.size

            # Layout IR
            layout = _build_page_layout(page, page_number, img_w, img_h, dpi)
            layout["file_id"] = file_id
            layout["file_name"] = file_name
            pages_layout.append(layout)

            # 산출물 저장
            layout_path = out_dir / f"page_{page_number}_layout.json"
            layout_path.write_text(
                json.dumps(layout, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            tables_md_path = out_dir / f"page_{page_number}_tables.md"
            tables_md_path.write_text(_layout_to_tables_md(layout), encoding="utf-8")

            visual_path = out_dir / f"page_{page_number}_visual.png"
            visual_img = _draw_visual(img, layout)
            visual_img.save(visual_path, "PNG")

            artifacts[f"page_{page_number}"] = {
                "layout": str(layout_path),
                "tables_md": str(tables_md_path),
                "visual": str(visual_path),
            }

    # source_map.json — block/cell_id → bbox + page 통합
    source_map: Dict[str, Any] = {
        "file_id": file_id,
        "file_name": file_name,
        "page_count": len(pages_layout),
        "blocks": {},  # block_id → {page, bbox, type, ...}
        "cells": {},   # cell_id → {page, bbox, ...}
    }
    for layout in pages_layout:
        p = layout["page_number"]
        for blk in layout["blocks"]:
            source_map["blocks"][blk["block_id"]] = {
                "page": p,
                "bbox": blk.get("bbox"),
                "type": blk.get("type"),
                "table_id": blk.get("table_id"),
            }
            if blk["type"] == "table":
                for row in blk.get("rows", []):
                    for cell in row.get("cells", []):
                        source_map["cells"][cell["cell_id"]] = {
                            "page": p,
                            "bbox": cell.get("bbox"),
                            "table_id": blk["table_id"],
                            "row_id": row["row_id"],
                            "is_empty": cell.get("is_empty"),
                        }
    source_map_path = out_dir / "source_map.json"
    source_map_path.write_text(
        json.dumps(source_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "file_id": file_id,
        "file_name": file_name,
        "page_count": len(pages_layout),
        "pages": pages_layout,
        "artifacts": artifacts,
        "source_map_path": str(source_map_path),
    }
