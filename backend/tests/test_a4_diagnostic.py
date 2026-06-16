"""
A-4-1 진단 — layout_builder 동작 확인 + fixture cache 생성

목적:
1. AX 40p PDF의 layout IR을 한 번 빌드하고 JSON으로 캐시
   - 위치: backend/tests/fixtures/layout_ir/ax_form1_40p.json
   - 이후 A-4-2/A-4-3 단위 테스트가 0.1s 안에 로드 가능 (PDF 재처리 비용 8s 회피)

2. bbox=null cell 패턴 분석
   - merged cell hidden sub-region 추정
   - 다단헤더 추정 가능성 진단

3. 핵심 표 5종 검출 통계 + 컬럼 분포 재확인
"""
import sys
import json
import time
import pathlib
import tempfile
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.form_layout_builder import build_layout_for_pdf

PDF = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples"
    r"\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문"
    r"\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)

FIXTURE = BACKEND / "tests" / "fixtures" / "layout_ir" / "ax_form1_40p.json"

KEY_PAGES = {
    4:  "기관현황",
    7:  "요약서-2 (5컬럼)",
    34: "사업비 총괄표",
    35: "비목별 총괄표",
    36: "인건비 표",
}


def build_or_load_fixture(force: bool = False) -> dict:
    """fixture가 있으면 로드, 없으면 build 후 저장."""
    if FIXTURE.exists() and not force:
        print(f"[fixture] LOAD {FIXTURE.relative_to(BACKEND)}")
        t0 = time.time()
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        print(f"  loaded in {time.time()-t0:.2f}s, pages={len(data['pages'])}")
        return data

    print(f"[fixture] BUILD from {PDF.name}")
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        lr = build_layout_for_pdf(
            pdf_bytes=PDF.read_bytes(),
            out_dir=pathlib.Path(tmp),
            file_id="ax_form1",
            file_name=PDF.name,
        )
    # artifact 경로는 fixture에 저장하지 않음 (tmp 경로)
    lite = {
        "file_id": lr["file_id"],
        "file_name": lr["file_name"],
        "page_count": lr["page_count"],
        "pages": lr["pages"],
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(lite, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  built+saved in {time.time()-t0:.2f}s ({FIXTURE.stat().st_size:,} bytes)")
    return lite


def analyze_bbox_null_pattern(pages: list) -> dict:
    """bbox=null cell 패턴 분석.

    가설: bbox=None cell은 horizontally merged cell의 hidden sub-region.
    검증: bbox=None cell이 발생할 때, 같은 row의 좌측에 bbox 폭이 넓은 cell이 있는가?
    """
    total_cells = 0
    bbox_null_cells = 0
    bbox_null_with_wide_left = 0
    bbox_null_isolated = 0  # 좌측 인접에 wide cell이 없는 경우
    rows_with_any_null = 0
    rows_total = 0

    for page in pages:
        for blk in page.get("blocks", []):
            if blk.get("type") != "table":
                continue
            for row in blk.get("rows", []) or []:
                rows_total += 1
                cells = row.get("cells", []) or []
                row_has_null = False
                for ci, cell in enumerate(cells):
                    total_cells += 1
                    if cell.get("bbox") is None:
                        bbox_null_cells += 1
                        row_has_null = True
                        # 좌측 cell 중 bbox가 있고 폭이 평균 cell 폭보다 1.5배 이상인 것?
                        avg_cell_w = None
                        widths = []
                        for prev in cells:
                            pb = prev.get("bbox")
                            if pb and len(pb) == 4:
                                widths.append(pb[2] - pb[0])
                        if widths:
                            avg_cell_w = sum(widths) / len(widths)
                        wide_left_found = False
                        for cj in range(ci - 1, -1, -1):
                            pb = cells[cj].get("bbox")
                            if pb and len(pb) == 4:
                                w = pb[2] - pb[0]
                                if avg_cell_w and w >= avg_cell_w * 1.3:
                                    wide_left_found = True
                                break
                        if wide_left_found:
                            bbox_null_with_wide_left += 1
                        else:
                            bbox_null_isolated += 1
                if row_has_null:
                    rows_with_any_null += 1

    return {
        "total_cells": total_cells,
        "bbox_null_cells": bbox_null_cells,
        "bbox_null_ratio": bbox_null_cells / max(total_cells, 1),
        "bbox_null_with_wide_left": bbox_null_with_wide_left,
        "bbox_null_isolated": bbox_null_isolated,
        "merged_pattern_ratio": bbox_null_with_wide_left / max(bbox_null_cells, 1),
        "rows_total": rows_total,
        "rows_with_any_null": rows_with_any_null,
    }


def analyze_columns_distribution(pages: list) -> dict:
    """전체 표의 col_count 분포."""
    col_counts = []
    row_counts = []
    fragment_candidates = 0
    for page in pages:
        for blk in page.get("blocks", []):
            if blk.get("type") != "table":
                continue
            c = blk.get("col_count", 0)
            r = blk.get("row_count", 0)
            col_counts.append(c)
            row_counts.append(r)
            if c == 1 or (c == 2 and r <= 3):
                fragment_candidates += 1
    return {
        "table_count": len(col_counts),
        "col_distribution": dict(sorted(Counter(col_counts).items())),
        "row_distribution": dict(sorted(Counter(row_counts).items())),
        "cols_ge_5": sum(1 for c in col_counts if c >= 5),
        "cols_ge_3": sum(1 for c in col_counts if c >= 3),
        "cols_eq_2": sum(1 for c in col_counts if c == 2),
        "cols_eq_1": sum(1 for c in col_counts if c == 1),
        "fragment_candidates": fragment_candidates,
    }


def check_key_tables(pages: list) -> dict:
    """핵심 표 5종 검출 확인."""
    result = {}
    for pg_num, name in KEY_PAGES.items():
        page = pages[pg_num - 1]
        tables = [b for b in page.get("blocks", []) if b.get("type") == "table"]
        result[pg_num] = {
            "name": name,
            "table_count": len(tables),
            "tables": [
                {"row_count": t["row_count"], "col_count": t["col_count"]}
                for t in tables
            ],
        }
    return result


def inspect_sample_multirow_header(pages: list) -> dict:
    """다단헤더 추정 가능성 — p.34 사업비 총괄표 1행 분석."""
    page = pages[33]  # p.34
    tables = [b for b in page.get("blocks", []) if b.get("type") == "table"]
    if not tables:
        return {"error": "no tables on p.34"}
    t = tables[0]
    rows = t.get("rows", []) or []
    if not rows:
        return {"error": "no rows"}

    sample = []
    for ri, row in enumerate(rows[:3]):  # 첫 3행
        cells_info = []
        for cell in row.get("cells", []) or []:
            bbox = cell.get("bbox")
            cells_info.append({
                "cell_id": cell.get("cell_id"),
                "text": cell.get("text", "")[:30],
                "bbox_null": bbox is None,
                "bbox_width": round(bbox[2] - bbox[0], 1) if bbox and len(bbox) == 4 else None,
            })
        sample.append({"row_id": row.get("row_id"), "cells": cells_info})
    return {"page": 34, "table_id": t.get("table_id"), "sample_rows": sample}


def main():
    print("=" * 70)
    print("A-4-1 진단 — layout_builder 동작 확인 + fixture 생성")
    print("=" * 70)

    # 1. fixture build or load
    lr = build_or_load_fixture()
    pages = lr["pages"]
    print(f"\n[stage 1] fixture: pages={len(pages)}")

    # 2. bbox=null 패턴 분석
    print("\n[stage 2] bbox=null cell 패턴 분석")
    null_pat = analyze_bbox_null_pattern(pages)
    print(f"  total_cells               = {null_pat['total_cells']:,}")
    print(f"  bbox_null_cells           = {null_pat['bbox_null_cells']:,} ({null_pat['bbox_null_ratio']*100:.1f}%)")
    print(f"  bbox_null_with_wide_left  = {null_pat['bbox_null_with_wide_left']:,}")
    print(f"  bbox_null_isolated        = {null_pat['bbox_null_isolated']:,}")
    print(f"  merged_pattern_ratio      = {null_pat['merged_pattern_ratio']*100:.1f}% (높을수록 merged cell 가설 강함)")
    print(f"  rows_with_any_null        = {null_pat['rows_with_any_null']} / {null_pat['rows_total']}")

    # 3. col 분포
    print("\n[stage 3] 컬럼 분포")
    col_dist = analyze_columns_distribution(pages)
    print(f"  table_count            = {col_dist['table_count']}")
    print(f"  col_distribution       = {col_dist['col_distribution']}")
    print(f"  cols >= 5              = {col_dist['cols_ge_5']}")
    print(f"  cols >= 3              = {col_dist['cols_ge_3']}")
    print(f"  cols == 2              = {col_dist['cols_eq_2']}")
    print(f"  cols == 1              = {col_dist['cols_eq_1']}")
    print(f"  fragment_candidates    = {col_dist['fragment_candidates']}  (is_fragment 휴리스틱)")

    # 4. 핵심 표 5종
    print("\n[stage 4] 핵심 표 5종 검출")
    key_results = check_key_tables(pages)
    for pg, info in key_results.items():
        line = f"  p.{pg:>2} {info['name']:<22}"
        if info["table_count"] == 0:
            print(line + " → ❌ 미검출")
        else:
            sizes = ", ".join(f"{t['row_count']}r×{t['col_count']}c" for t in info["tables"])
            print(line + f" → ✓ {info['table_count']}개 ({sizes})")

    # 5. 다단헤더 sample 분석
    print("\n[stage 5] 다단헤더 추정 sample (p.34 사업비 총괄표)")
    sample = inspect_sample_multirow_header(pages)
    if "error" in sample:
        print(f"  error: {sample['error']}")
    else:
        for row in sample["sample_rows"]:
            print(f"  {row['row_id']}:")
            for c in row["cells"]:
                bbox_str = "bbox=None" if c["bbox_null"] else f"width={c['bbox_width']}"
                print(f"    {c['cell_id']:<12} {bbox_str:<22} text={c['text']!r}")

    print("\n" + "=" * 70)
    print("진단 완료")
    print("=" * 70)


if __name__ == "__main__":
    main()
