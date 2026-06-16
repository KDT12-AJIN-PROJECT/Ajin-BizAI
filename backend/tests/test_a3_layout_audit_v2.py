"""
AX 서식1 40p 전체 layout_builder 표 검출 audit v2 — row_count / col_count 사용.
"""
import sys, pathlib, tempfile
sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.form_layout_builder import build_layout_for_pdf

PDF = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)

KEY_PAGES = {
    4: "기관현황",
    7: "요약서-2 (5컬럼)",
    34: "사업비 총괄표 (≥5컬럼)",
    35: "비목별 총괄표 (≥5컬럼)",
    36: "인건비 표",
}

with tempfile.TemporaryDirectory() as tmp:
    lr = build_layout_for_pdf(
        pdf_bytes=PDF.read_bytes(),
        out_dir=pathlib.Path(tmp),
        file_id="audit_v2",
        file_name=PDF.name,
    )
pages = lr["pages"]
print(f"총 페이지: {len(pages)}\n")

def t_stats(t):
    """row_count / col_count / EMPTY 셀 수"""
    r = t.get("row_count", 0)
    c = t.get("col_count", 0)
    rows = t.get("rows") or []
    empties = sum(1 for row in rows for cell in (row.get("cells") or []) if cell.get("is_empty"))
    total = sum(1 for row in rows for _ in (row.get("cells") or []))
    return r, c, empties, total

total_tables = 0
total_cols_dist = []
total_rows_sum = 0
total_empty_cells = 0
total_cells_sum = 0
pages_with_tables = 0
key_results = {}

print(f"{' ':2}{'P':>3} | {'tab':>3} | {'표 상세 (rows × cols, empty/total)':<48} | {'페이지 의미'}")
print("-" * 110)

for i, p in enumerate(pages, start=1):
    tables = [b for b in (p.get("blocks") or []) if b.get("type") == "table"]
    n = len(tables)
    total_tables += n
    if n > 0:
        pages_with_tables += 1

    details = []
    for t in tables:
        r, c, e, tot = t_stats(t)
        total_cols_dist.append(c)
        total_rows_sum += r
        total_empty_cells += e
        total_cells_sum += tot
        details.append(f"{r}r×{c}c {e}/{tot}E")
    details_str = ", ".join(details) if details else "-"

    label = KEY_PAGES.get(i, "")
    marker = "★ " if i in KEY_PAGES else "  "
    if i in KEY_PAGES:
        key_results[i] = (n, [t_stats(t) for t in tables])
    print(f"{marker}{i:>2} | {n:>3} | {details_str:<48} | {label}")

print()
print(f"=== 통계 ===")
print(f"총 page                  : {len(pages)}")
print(f"표 있는 page             : {pages_with_tables}")
print(f"총 table block 수        : {total_tables}")
print(f"평균 rows/table          : {total_rows_sum / max(total_tables,1):.1f}")
print(f"총 cell 수               : {total_cells_sum:,}")
print(f"빈(empty) cell 수        : {total_empty_cells:,} ({total_empty_cells/max(total_cells_sum,1)*100:.1f}%)")
cc = Counter(total_cols_dist)
print(f"columns 분포             : {dict(sorted(cc.items()))}")
print(f"columns ≥ 5인 표         : {sum(1 for c in total_cols_dist if c >= 5)} / {total_tables}")
print(f"columns ≥ 3인 표         : {sum(1 for c in total_cols_dist if c >= 3)} / {total_tables}")
print(f"columns == 2인 표        : {sum(1 for c in total_cols_dist if c == 2)} / {total_tables}")

print(f"\n=== 핵심 표 5종 결과 ===")
for pg, name in KEY_PAGES.items():
    n, stats = key_results.get(pg, (0, []))
    if not stats:
        print(f"  p.{pg:>2} {name:<28} → ❌ table 0개 (미검출)")
        continue
    parts = []
    for r, c, e, tot in stats:
        parts.append(f"{r}r×{c}c (empty {e}/{tot})")
    print(f"  p.{pg:>2} {name:<28} → {n}개: {' + '.join(parts)}")
