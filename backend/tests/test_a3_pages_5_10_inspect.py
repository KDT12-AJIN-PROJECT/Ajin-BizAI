"""
AX 서식1 PDF 5-10페이지 표 존재 여부 직접 확인 (LLM 없이 layout IR만 사용)
"""
import sys, base64, os, pathlib, json
sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.form_layout_builder import build_layout_for_pdf
from services.form_llm_input_builder import build_llm_input_for_page

PDF = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)

import tempfile
with tempfile.TemporaryDirectory() as tmp:
    lr = build_layout_for_pdf(
        pdf_bytes=PDF.read_bytes(),
        out_dir=pathlib.Path(tmp),
        file_id="ax_inspect",
        file_name=PDF.name,
    )

pages = lr["pages"]
print(f"total pages = {len(pages)}\n")

for i, p in enumerate(pages[4:10], start=5):  # 5..10
    md = build_llm_input_for_page(p)
    has_table_marker = "|---" in md or "|--" in md or md.count("|") > 20
    table_blocks = (p.get("blocks") or [])
    table_count_raw = sum(1 for b in table_blocks if b.get("type") == "table")

    print(f"===================== PAGE {i} =====================")
    print(f"  blocks={len(table_blocks)}, table blocks (IR)={table_count_raw}")
    print(f"  md chars={len(md)}, has_gfm_table_marker={has_table_marker}, pipe_count={md.count('|')}")
    # excerpt
    excerpt = md[:1200]
    print(f"\n--- md excerpt (first 1200 chars) ---\n{excerpt}\n")
