"""
non-fragment but non-promotable 2개 표의 제외 사유 추적.
"""
import sys, json, pathlib
sys.stdout.reconfigure(encoding="utf-8")
BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.table_normalizer import normalize_layout_tables

FIXTURE = BACKEND / "tests" / "fixtures" / "layout_ir" / "ax_form1_40p.json"
data = json.loads(FIXTURE.read_text(encoding="utf-8"))
normalized = normalize_layout_tables(data["pages"])

print(f"총 normalized: {len(normalized)}")
fragment = [n for n in normalized if n.is_fragment]
promotable = [n for n in normalized if n.is_promotable]
skipped_non_promo = [n for n in normalized if not n.is_fragment and not n.is_promotable]
print(f"  fragment: {len(fragment)}")
print(f"  promotable: {len(promotable)}")
print(f"  non-fragment & non-promotable: {len(skipped_non_promo)}")

print("\n=== non-fragment & non-promotable 표 상세 ===")
for n in skipped_non_promo:
    # is_promotable = not is_fragment AND columns>=3 AND rows>=2 AND empty_field_count>=1
    reasons = []
    if n.columns < 3:
        reasons.append(f"columns<3 (got {n.columns})")
    if n.rows < 2:
        reasons.append(f"rows<2 (got {n.rows})")
    if n.empty_field_count < 1:
        reasons.append(f"empty_field_count<1 (got {n.empty_field_count})")
    print(f"  p.{n.source_page:>2} {n.table_id} : {n.rows}r×{n.columns}c empty={n.empty_field_count}")
    print(f"    title: {n.title_candidate!r}")
    print(f"    header_paths[0..2]: {n.header_paths[:3]}")
    print(f"    제외 사유: {', '.join(reasons) or '(기준 모두 충족인데도 promotable=False?)'}")

print("\n=== fragment 7개 상세 ===")
for n in fragment:
    reasons = []
    if n.columns == 1:
        reasons.append("columns==1")
    if n.columns == 2 and n.rows <= 3:
        reasons.append(f"columns==2 & rows<=3 (rows={n.rows})")
    print(f"  p.{n.source_page:>2} {n.table_id} : {n.rows}r×{n.columns}c empty={n.empty_field_count}  "
          f"reasons={reasons or ['TOC/instruction context']}")
