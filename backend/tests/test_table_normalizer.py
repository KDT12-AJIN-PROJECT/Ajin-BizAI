"""
A-4-2 — table_normalizer 단위 테스트.

fixture: backend/tests/fixtures/layout_ir/ax_form1_40p.json (A-4-1에서 생성됨)
"""
import sys
import json
import pathlib
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.table_normalizer import (
    normalize_layout_tables,
    NormalizedTable,
    _detect_multirow_header,
    _stack_multirow_headers,
    _judge_is_fragment,
    _compute_confidence,
    _infer_title_candidate,
    _build_header_paths,
)
from services.table_keywords import (
    is_toc_or_instruction,
    find_keyword_in_text,
    TABLE_TITLE_KEYWORDS,
)


FIXTURE = BACKEND / "tests" / "fixtures" / "layout_ir" / "ax_form1_40p.json"


def assert_eq(label: str, got, want):
    mark = "✓" if got == want else "✗"
    suffix = f"  got={got!r}, want={want!r}" if got != want else ""
    print(f"  {mark} {label}{suffix}")
    return got == want


def assert_true(label: str, cond: bool, note: str = ""):
    mark = "✓" if cond else "✗"
    suffix = f"  ({note})" if note else ""
    print(f"  {mark} {label}{suffix}")
    return cond


# ─────────────────────────────────────────────────────────────────────
# Unit tests on helper functions
# ─────────────────────────────────────────────────────────────────────

print("=== Test 1: table_keywords helpers ===")
assert_true("is_toc_or_instruction('목 차')", is_toc_or_instruction("목 차"))
assert_true("is_toc_or_instruction('Ⅰ. 개요')", is_toc_or_instruction("Ⅰ. 개요"))
assert_true("is_toc_or_instruction('※ 안내')", is_toc_or_instruction("※ 안내"))
assert_true("not is_toc('사업비 총괄표')", not is_toc_or_instruction("사업비 총괄표"))
assert_eq("find_keyword_in_text('사업비 총괄표')", find_keyword_in_text("사업비 총괄표"), "사업비")
assert_eq("find_keyword_in_text('관계없음')", find_keyword_in_text("관계없음"), None)


print("\n=== Test 2: _judge_is_fragment ===")
# columns == 1 → fragment
frag_1col = _judge_is_fragment(1, 3, [[{"text":"a"}],[{"text":"b"}],[{"text":"c"}]], 0, None, [], None)
assert_true("columns==1 → fragment", frag_1col)

# columns == 1, empty_count 3+, title 있음 → needs_review (not fragment)
frag_1col_special = _judge_is_fragment(
    1, 5, [[{"text":""}],[{"text":""}],[{"text":""}],[{"text":""}],[{"text":""}]],
    5, "기관현황표", [], None
)
assert_true("columns==1 + empty>=3 + title → not fragment", not frag_1col_special)

# columns == 2, rows == 3, all short → fragment
frag_2x3 = _judge_is_fragment(
    2, 3,
    [[{"text":"가"},{"text":"나"}],[{"text":"다"},{"text":"라"}],[{"text":"마"},{"text":"바"}]],
    0, None, [], None
)
assert_true("columns==2 & rows==3 & short → fragment", frag_2x3)

# columns 5, rows 10 → not fragment
not_frag = _judge_is_fragment(5, 10, [], 0, None, [], None)
assert_true("columns==5 → not fragment", not not_frag)


print("\n=== Test 3: _compute_confidence ===")
conf_min = _compute_confidence(None, 2, 1, 0, [])
assert_eq("conf 최소", round(conf_min, 1), 0.5)

conf_max = _compute_confidence("사업비 총괄표", 5, 10, 5, [["a"], ["b"]])
assert_eq("conf 최대 (5 가점)", round(conf_max, 1), 1.0)

conf_mid = _compute_confidence("사업비", 5, 1, 0, [])
assert_eq("conf 0.5 + title + cols>=3 = 0.7", round(conf_mid, 1), 0.7)

# fallback title은 가점 없음
conf_fb = _compute_confidence("표 p1-t1", 5, 5, 1, [])
assert_eq("conf fallback title 가점 없음", round(conf_fb, 1), 0.8)


print("\n=== Test 4: _detect_multirow_header — p.34 사업비 총괄표 sample ===")
# 진단에서 본 실제 데이터 패턴 재구성
p34_r1 = [
    {"text": "구 분", "bbox": [60, 220, 144, 280]},
    {"text": "정부지원금", "bbox": [144, 220, 220, 263]},
    {"text": "", "bbox": None},
    {"text": "기관부담금", "bbox": [220, 220, 443, 245]},  # wide
    {"text": "", "bbox": None},
    {"text": "", "bbox": None},
    {"text": "", "bbox": None},
    {"text": "", "bbox": None},
    {"text": "", "bbox": None},
    {"text": "합 계", "bbox": [443, 220, 535, 263]},
    {"text": "", "bbox": None},
]
p34_r2 = [
    {"text": "", "bbox": None}, {"text": "", "bbox": None}, {"text": "", "bbox": None},
    {"text": "현금", "bbox": [220, 245, 295, 263]},
    {"text": "", "bbox": None},
    {"text": "현물", "bbox": [295, 245, 368, 263]},
    {"text": "", "bbox": None},
    {"text": "소계", "bbox": [368, 245, 443, 263]},
    {"text": "", "bbox": None}, {"text": "", "bbox": None}, {"text": "", "bbox": None},
]
p34_r3 = [
    {"text": "", "bbox": None},
    {"text": "금 액", "bbox": [144, 263, 190, 285]},
    {"text": "%", "bbox": [190, 263, 220, 285]},
    {"text": "금 액", "bbox": [220, 263, 269, 285]},
    {"text": "%", "bbox": [269, 263, 295, 285]},
    {"text": "금 액", "bbox": [295, 263, 343, 285]},
    {"text": "%", "bbox": [343, 263, 368, 285]},
    {"text": "금 액", "bbox": [368, 263, 416, 285]},
    {"text": "%", "bbox": [416, 263, 443, 285]},
    {"text": "금 액", "bbox": [443, 263, 504, 285]},
    {"text": "%", "bbox": [504, 263, 535, 285]},
]
p34_cells = [p34_r1, p34_r2, p34_r3, [{"text":"data","bbox":None}]*11]
is_mr, hc = _detect_multirow_header(p34_cells)
assert_true("p.34 → multi-row 감지", is_mr, f"header_count={hc}")
# 첫 cell이 merged(bbox=None)면 header_row_count=2가 정상 (r3에 bbox 없는 cell 존재)
# 14r×12c 표처럼 r3 전체 cell이 bbox 있을 때만 3이 됨
assert_true("p.34 sample header_row_count >= 2", hc >= 2,
            f"merged 패턴에 따라 2 또는 3 (got {hc})")


print("\n=== Test 5: _stack_multirow_headers — p.34 path 검증 ===")
paths = _stack_multirow_headers(p34_cells, header_row_count=hc, columns=11)
# c2~c3: 정부지원금 → 금액/% (수직 merge: 현금 등은 정부지원금 column 위치 아님)
# c1: 구분 (단일)
assert_eq("c1 path", paths[0], ["구 분"])
# c2: 정부지원금 → ??? → 금 액
# r2의 c2는 빈 → 위 row "정부지원금" 상속
# r3의 c2는 "금 액"
assert_eq("c2 path[0] = 정부지원금", paths[1][0], "정부지원금")
# hc에 따라 path 깊이 달라짐 (hc=2: ['정부지원금'] / hc=3: [..., '금 액'])
if hc >= 3:
    assert_eq("c2 path[-1] = 금 액 (hc=3)", paths[1][-1], "금 액")
# c4 = 기관부담금 → 현금 → 금 액
assert_eq("c4 path[0] = 기관부담금", paths[3][0], "기관부담금")
assert_true("c4 path 포함 현금", "현금" in paths[3])
# c10 = 합계 → 금 액
assert_eq("c10 path[0] = 합 계", paths[9][0], "합 계")


print("\n=== Test 6: _detect_multirow_header — 단일 row table → no multi-row ===")
single = [[{"text":"a","bbox":[0,0,50,10]},{"text":"b","bbox":[50,0,100,10]}]]
is_mr2, hc2 = _detect_multirow_header(single)
assert_true("단일 row → single-level", not is_mr2 and hc2 == 1)


print("\n=== Test 7: single-level header (간단한 표) ===")
simple_rows = [
    [{"text":"이름","bbox":[0,0,50,10]},{"text":"점수","bbox":[50,0,100,10]}],
    [{"text":"홍길동","bbox":[0,10,50,20]},{"text":"90","bbox":[50,10,100,20]}],
]
paths, hc = _build_header_paths(simple_rows)
assert_eq("simple paths c1", paths[0], ["이름"])
assert_eq("simple paths c2", paths[1], ["점수"])
assert_eq("simple header_row_count", hc, 1)


# ─────────────────────────────────────────────────────────────────────
# Integration test — AX 40p fixture
# ─────────────────────────────────────────────────────────────────────

print("\n=== Test 8: Integration — AX 40p fixture normalize ===")
if not FIXTURE.exists():
    print(f"  ✗ fixture not found: {FIXTURE}")
    sys.exit(1)

data = json.loads(FIXTURE.read_text(encoding="utf-8"))
pages = data["pages"]
print(f"  fixture pages = {len(pages)}")

normalized = normalize_layout_tables(pages)
print(f"  normalized tables = {len(normalized)}")

# 1. 총 개수
assert_eq("총 normalized = 46", len(normalized), 46)

# 2. fragment 분류
n_fragment = sum(1 for n in normalized if n.is_fragment)
n_promotable = sum(1 for n in normalized if n.is_promotable)
print(f"  fragment count = {n_fragment}")
print(f"  promotable count = {n_promotable}")
assert_true("fragment >= 5", n_fragment >= 5, "(c==1 표 5개 이상)")
assert_true("promotable >= 30", n_promotable >= 30, "(38 candidate 중 대부분)")

# 3. 핵심 표 5종 확인
key_pages = {4: "기관현황", 7: "요약서-2", 34: "사업비 총괄표", 35: "비목별 총괄표", 36: "인건비 표"}
print(f"\n  [핵심 표 5종 normalize 결과]")
for pg, name in key_pages.items():
    nts = [n for n in normalized if n.source_page == pg]
    n_promo = [n for n in nts if n.is_promotable]
    print(f"  p.{pg:>2} {name:<15} → {len(nts)}개 (promotable {len(n_promo)})")
    for n in nts:
        h0 = n.header_paths[0] if n.header_paths else []
        title_short = (n.title_candidate or "?")[:30]
        print(f"           {n.rows}r×{n.columns}c conf={n.confidence:.2f} promo={n.is_promotable} "
              f"hcount={n.header_row_count} title={title_short!r}")
    assert_true(f"p.{pg} promotable >= 1", len(n_promo) >= 1)

# 4. p.34 다단헤더 검증
p34_promo = [n for n in normalized if n.source_page == 34 and n.is_promotable]
assert_true("p.34 promotable table 1+개", len(p34_promo) >= 1)
if p34_promo:
    p34_first = p34_promo[0]
    assert_true("p.34 columns >= 11", p34_first.columns >= 11,
                f"got {p34_first.columns}")
    assert_true("p.34 header_row_count >= 2", p34_first.header_row_count >= 2,
                f"got {p34_first.header_row_count}")
    # header_paths 첫 column에 "구분" 또는 비슷한 값
    hp0 = p34_first.header_paths[0] if p34_first.header_paths else []
    assert_true("p.34 c1 header 비어있지 않음", bool(hp0))

# 5. fragment 표가 모두 is_promotable=False 인지
fragment_promotable = [n for n in normalized if n.is_fragment and n.is_promotable]
assert_eq("fragment & promotable 동시 = 0", len(fragment_promotable), 0)


# ─────────────────────────────────────────────────────────────────────
# 분포 요약
# ─────────────────────────────────────────────────────────────────────

print(f"\n=== 분포 요약 ===")
header_row_counts = Counter(n.header_row_count for n in normalized)
print(f"  header_row_count 분포: {dict(sorted(header_row_counts.items()))}")
confidences = [n.confidence for n in normalized]
print(f"  confidence: min={min(confidences):.2f}, max={max(confidences):.2f}, "
      f"avg={sum(confidences)/len(confidences):.2f}")
fragment_pages = [n.source_page for n in normalized if n.is_fragment]
print(f"  fragment 표가 있는 페이지: {sorted(set(fragment_pages))}")

print(f"\n=== A-4-2 단위 테스트 완료 ===")
