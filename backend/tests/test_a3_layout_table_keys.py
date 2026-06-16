"""
table block의 실제 dict 키 / 구조 확인
"""
import sys, pathlib, tempfile, json
sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.form_layout_builder import build_layout_for_pdf

PDF = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)

with tempfile.TemporaryDirectory() as tmp:
    lr = build_layout_for_pdf(
        pdf_bytes=PDF.read_bytes(),
        out_dir=pathlib.Path(tmp),
        file_id="keys",
        file_name=PDF.name,
    )

# p.7 (요약서-2 — 알려진 5컬럼)
p7 = lr["pages"][6]
print("p.7 keys:", list(p7.keys()))
blocks = p7.get("blocks") or []
tables = [b for b in blocks if b.get("type") == "table"]
if tables:
    t = tables[0]
    print(f"\np.7 table[0] keys: {list(t.keys())}")
    print(f"\nfull table[0] dict (truncated to 3000 chars):")
    s = json.dumps(t, ensure_ascii=False, indent=2)
    print(s[:3000])

# p.34
print("\n" + "=" * 70)
p34 = lr["pages"][33]
blocks34 = p34.get("blocks") or []
tables34 = [b for b in blocks34 if b.get("type") == "table"]
print(f"p.34 table count = {len(tables34)}")
for idx, t in enumerate(tables34):
    print(f"\np.34 table[{idx}] keys: {list(t.keys())}")
    s = json.dumps(t, ensure_ascii=False, indent=2)
    print(s[:2000])
