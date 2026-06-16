"""
AX 서식1 40p 전체 layout_builder 표 검출 audit.

페이지별로:
  - blocks 총 개수
  - table block 개수
  - 각 table block의 (rows, cols, EMPTY_FIELD 수, header 행 추정)
  - 핵심 표 위치(p.4, p.7, p.34, p.35, p.36) 강조 표시
"""
import sys, pathlib, tempfile
sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.form_layout_builder import build_layout_for_pdf

PDF = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)

KEY_PAGES = {
    4: "기관현황",
    7: "요약서-2 (5컬럼)",
    34: "사업비 총괄표",
    35: "비목별 총괄표",
    36: "인건비 표",
}

with tempfile.TemporaryDirectory() as tmp:
    lr = build_layout_for_pdf(
        pdf_bytes=PDF.read_bytes(),
        out_dir=pathlib.Path(tmp),
        file_id="audit",
        file_name=PDF.name,
    )

pages = lr["pages"]
print(f"총 페이지: {len(pages)}\n")

def analyze_table(t):
    """table block의 rows/cols 추정."""
    cells = t.get("cells") or []
    if not cells:
        rows = t.get("rows") or []
        if rows:
            rmax = len(rows)
            cmax = max(len(r) for r in rows) if rows else 0
            return rmax, cmax, sum(1 for r in rows for c in r if "EMPTY_FIELD" in str(c))
        return 0, 0, 0
    rmax = max((c.get("row", 0) for c in cells), default=-1) + 1
    cmax = max((c.get("col", 0) for c in cells), default=-1) + 1
    empties = sum(1 for c in cells if "EMPTY_FIELD" in str(c.get("text", "")))
    return rmax, cmax, empties

total_tables = 0
table_rows_sum = 0
table_cols_max_dist = []  # list of cols per table
pages_with_tables = 0
pages_with_no_tables = 0

print(f"{'P':>3} | {'blocks':>6} | {'tables':>6} | {'표 상세 (rows × cols, EMPTY)':<40} | {'페이지 의미'}")
print("-" * 110)

for i, p in enumerate(pages, start=1):
    blocks = p.get("blocks") or []
    tables = [b for b in blocks if b.get("type") == "table"]
    n_tables = len(tables)
    total_tables += n_tables
    if n_tables > 0:
        pages_with_tables += 1
    else:
        pages_with_no_tables += 1

    details = []
    for t in tables:
        r, c, e = analyze_table(t)
        table_rows_sum += r
        table_cols_max_dist.append(c)
        details.append(f"{r}x{c}/{e}E")
    details_str = ", ".join(details) if details else "-"

    label = KEY_PAGES.get(i, "")
    marker = "★ " if i in KEY_PAGES else "  "
    print(f"{marker}{i:>2} | {len(blocks):>6} | {n_tables:>6} | {details_str:<40} | {label}")

print()
print(f"=== 통계 ===")
print(f"총 page: {len(pages)}")
print(f"표가 있는 page: {pages_with_tables}")
print(f"표가 없는 page: {pages_with_no_tables}")
print(f"총 table block 수: {total_tables}")
if table_cols_max_dist:
    from collections import Counter
    cc = Counter(table_cols_max_dist)
    print(f"columns 분포: {dict(sorted(cc.items()))}")
    print(f"columns ≥ 5인 표: {sum(1 for c in table_cols_max_dist if c >= 5)}")
    print(f"columns ≥ 3인 표: {sum(1 for c in table_cols_max_dist if c >= 3)}")

# 핵심 표 5종 검증
print(f"\n=== 핵심 표 5종 layout_builder 검출 결과 ===")
for pg, name in KEY_PAGES.items():
    p = pages[pg - 1]
    blocks = p.get("blocks") or []
    tables = [b for b in blocks if b.get("type") == "table"]
    print(f"  p.{pg:>2} {name:<25} → table {len(tables)}개" + (
        ", " + ", ".join(f"{analyze_table(t)[0]}r×{analyze_table(t)[1]}c" for t in tables)
        if tables else ""
    ))
