"""
A-4-3 — table_promoter 단위 + 통합 테스트.

fixture: backend/tests/fixtures/layout_ir/ax_form1_40p.json
"""
import sys
import json
import pathlib

sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.table_normalizer import normalize_layout_tables, NormalizedTable
from services.table_promoter import (
    promote_tables,
    find_matching_llm_question,
    assign_section_id,
    make_promoted_question,
    build_table_schema,
    generate_question_id,
    _iou,
    _title_similarity,
    _is_same_table,
    AUTO_SECTION_ID,
    SOURCE_TYPE_PROMOTED,
    SOURCE_TYPE_CORRECTED,
)


FIXTURE = BACKEND / "tests" / "fixtures" / "layout_ir" / "ax_form1_40p.json"


def assert_eq(label, got, want):
    mark = "✓" if got == want else "✗"
    suffix = f"  got={got!r}, want={want!r}" if got != want else ""
    print(f"  {mark} {label}{suffix}")
    return got == want


def assert_true(label, cond, note=""):
    mark = "✓" if cond else "✗"
    suffix = f"  ({note})" if note else ""
    print(f"  {mark} {label}{suffix}")
    return cond


def make_nt(table_id="t1", page=10, rows=5, columns=8,
             bbox=None, empty=5, fragment=False, promotable=True,
             title="테스트표", header_paths=None, header_row_count=1,
             confidence=0.9):
    return NormalizedTable(
        table_id=table_id, source_page=page,
        bbox=bbox or [50.0, 100.0, 500.0, 400.0],
        rows=rows, columns=columns,
        header_paths=header_paths or [["c1"], ["c2"], ["c3"]],
        title_candidate=title, empty_field_count=empty,
        is_fragment=fragment, confidence=confidence,
        is_promotable=promotable, header_row_count=header_row_count,
        cells_raw=[],
    )


# ─────────────────────────────────────────────────────────────────────
# 1. IoU
# ─────────────────────────────────────────────────────────────────────
print("=== Test 1: _iou ===")
assert_eq("동일 bbox IoU=1", _iou([0,0,10,10], [0,0,10,10]), 1.0)
assert_eq("disjoint IoU=0", _iou([0,0,10,10], [20,20,30,30]), 0.0)
iou_half = _iou([0,0,10,10], [5,0,15,10])  # 절반 겹침
assert_true("절반 겹침 IoU ~0.33", 0.2 < iou_half < 0.4, f"got {iou_half:.3f}")


# ─────────────────────────────────────────────────────────────────────
# 2. title similarity
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 2: _title_similarity ===")
assert_eq("동일 title sim=1.0", _title_similarity("사업비총괄표", "사업비총괄표"), 1.0)
sim_partial = _title_similarity("사업비 총괄표", "사업비")
assert_true("부분 일치 sim>0.4", sim_partial > 0.4, f"got {sim_partial:.3f}")
assert_eq("관계없음 sim=0 처리", _title_similarity("", "abc"), 0.0)


# ─────────────────────────────────────────────────────────────────────
# 3. find_matching_llm_question
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 3: find_matching_llm_question ===")
# LLM에 매칭 후보 없음
nt1 = make_nt(table_id="A", page=10, rows=5, columns=8, bbox=[50,100,500,400])
sections = [{"section_id": "S1", "questions": [
    {"question_id": "Q1", "fill_mode": "ai_text", "source_page": 10},
]}]
m = find_matching_llm_question(nt1, sections)
assert_true("ai_text는 매칭 안 됨", m is None)

# LLM table_input + bbox IoU 매칭
sections2 = [{"section_id": "S1", "questions": [
    {"question_id": "Q2", "fill_mode": "table_input", "source_page": 10,
     "bbox": [60, 110, 510, 410], "table_schema": {"row_count": 5, "col_count": 8}},
]}]
m2 = find_matching_llm_question(nt1, sections2)
assert_true("bbox IoU 매칭", m2 is not None)
assert_eq("매칭된 question_id", m2["question_id"] if m2 else None, "Q2")

# 다른 page는 매칭 안 됨
sections3 = [{"section_id": "S1", "questions": [
    {"question_id": "Q3", "fill_mode": "table_input", "source_page": 99,
     "bbox": [50,100,500,400]},
]}]
m3 = find_matching_llm_question(nt1, sections3)
assert_true("다른 page 매칭 안 됨", m3 is None)

# bbox 없을 때 rows/columns로 매칭
nt_no_bbox = make_nt(table_id="B", page=10, rows=5, columns=8, bbox=None)
sections4 = [{"section_id": "S1", "questions": [
    {"question_id": "Q4", "fill_mode": "table_input", "source_page": 10,
     "table_schema": {"row_count": 5, "col_count": 8}},
]}]
m4 = find_matching_llm_question(nt_no_bbox, sections4)
assert_true("bbox 없을 때 rows/columns 매칭", m4 is not None)


# ─────────────────────────────────────────────────────────────────────
# 4. assign_section_id (4단계 fallback)
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 4: assign_section_id ===")
# 1단계: page range 포함
secs_with_qs = [
    {"section_id": "S_A", "title": "A", "questions": [
        {"question_id": "x1", "source_page": 5},
        {"question_id": "x2", "source_page": 10},
    ]},
    {"section_id": "S_B", "title": "B", "questions": [
        {"question_id": "y1", "source_page": 20},
        {"question_id": "y2", "source_page": 30},
    ]},
]
nt_p7 = make_nt(page=7)
stats1 = {}
sid1 = assign_section_id(nt_p7, secs_with_qs, stats1)
assert_eq("page 7 → S_A (5~10 범위)", sid1, "S_A")
assert_eq("auto_section_used 0", stats1.get("auto_section_used_count", 0), 0)

# 2단계: 가장 가까운 page (tolerance 3 이내)
nt_p11 = make_nt(page=11)
stats2 = {}
sid2 = assign_section_id(nt_p11, secs_with_qs, stats2)
assert_eq("page 11 → S_A (10에 가장 가까움, dist 1)", sid2, "S_A")

# 4단계: 매칭 실패 → S_AUTO_TABLES
nt_p99 = make_nt(page=99)
stats3 = {}
sid3 = assign_section_id(nt_p99, secs_with_qs, stats3)
assert_eq("page 99 → S_AUTO_TABLES", sid3, AUTO_SECTION_ID)
assert_eq("auto_section_used 1", stats3.get("auto_section_used_count", 0), 1)


# ─────────────────────────────────────────────────────────────────────
# 5. make_promoted_question / build_table_schema
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 5: make_promoted_question ===")
nt_full = make_nt(
    table_id="p34_t1", page=34, rows=8, columns=11,
    header_paths=[["구분"], ["정부지원금", "현금", "금 액"]],
    header_row_count=3, title="가. 사업비 총괄표",
)
pq = make_promoted_question(nt_full, section_id="S_X", question_id="TQ_p034_t001")
assert_eq("question_id", pq["question_id"], "TQ_p034_t001")
assert_eq("fill_mode", pq["fill_mode"], "table_input")
assert_eq("source_type", pq["source_type"], SOURCE_TYPE_PROMOTED)
assert_eq("is_required", pq["is_required"], True)
assert_eq("is_table_item", pq["is_table_item"], True)
assert_eq("source_page", pq["source_page"], 34)
assert_eq("section_id", pq["section_id"], "S_X")
assert_eq("title", pq["title"], "가. 사업비 총괄표")
assert_true("table_schema 존재", "table_schema" in pq)
assert_eq("table_schema.col_count", pq["table_schema"]["col_count"], 11)
assert_true("metadata.promoted_by", pq["metadata"]["promoted_by"] == "table_promoter")
assert_eq("metadata.confidence", pq["metadata"]["confidence"], 0.9)
assert_eq("metadata.header_row_count", pq["metadata"]["header_row_count"], 3)


# ─────────────────────────────────────────────────────────────────────
# 6. generate_question_id (deterministic)
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 6: generate_question_id ===")
used = set()
qid1 = generate_question_id(34, 1, used)
assert_eq("p34 t1 → TQ_p034_t001", qid1, "TQ_p034_t001")
used.add(qid1)
qid2 = generate_question_id(34, 2, used)
assert_eq("p34 t2 → TQ_p034_t002", qid2, "TQ_p034_t002")
# 동일 인자 재호출 → suffix
qid3 = generate_question_id(34, 1, used)
assert_eq("p34 t1 (충돌) → suffix", qid3, "TQ_p034_t001_1")

# deterministic: 다른 set 시작점에서 같은 ID
used_new = set()
assert_eq("재호출 → 같은 ID (deterministic)",
          generate_question_id(34, 1, used_new), "TQ_p034_t001")


# ─────────────────────────────────────────────────────────────────────
# 7. promote_tables — LLM에 없는 표만 추가
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 7: promote_tables — LLM에 없는 표만 추가 ===")
nts = [
    make_nt(table_id="T_p10", page=10),
    make_nt(table_id="T_p20", page=20, columns=11, rows=8,
            header_paths=[["구분"], ["c2"]] * 6),
]
llm_schema = {
    "form_id": "test",
    "sections": [
        {"section_id": "S1", "title": "section 1", "questions": [
            {"question_id": "EX1", "source_page": 10, "fill_mode": "ai_text"},
        ]},
    ],
}
schema_out, stats = promote_tables(nts, llm_schema)
all_qs = [q for sec in schema_out["sections"] for q in (sec.get("questions") or [])]
table_qs = [q for q in all_qs if q.get("fill_mode") == "table_input"]
assert_eq("promoted_table_count = 2", stats["promoted_table_count"], 2)
assert_eq("total table question", len(table_qs), 2)
assert_eq("source_type all promoted",
          all(q["source_type"] == SOURCE_TYPE_PROMOTED for q in table_qs), True)


# ─────────────────────────────────────────────────────────────────────
# 8. promote_tables — LLM에 이미 있으면 추가 안 함 + 보정
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 8: promote_tables — LLM 충돌 시 table_schema 보정 ===")
nt_p34 = make_nt(
    table_id="t34", page=34, rows=8, columns=11,
    bbox=[60, 220, 537, 395],
    header_paths=[["구분"], ["정부지원금", "금 액"]] * 6,
    header_row_count=2, title="사업비 총괄표",
)
# LLM이 같은 표를 columns=3으로 잘못 추출
llm_schema_with_wrong = {
    "form_id": "test",
    "sections": [
        {"section_id": "S_BUDGET", "title": "사업비 섹션", "questions": [
            {
                "question_id": "Q_BUDGET",
                "source_page": 34,
                "fill_mode": "table_input",
                "title": "사업비 총괄",
                "bbox": [60, 220, 540, 400],  # IoU 매칭
                "table_schema": {"row_count": 4, "col_count": 3,
                                  "columns": [{"name": "a"}, {"name": "b"}, {"name": "c"}]},
            },
        ]},
    ],
}
schema_out2, stats2 = promote_tables([nt_p34], llm_schema_with_wrong)
table_qs2 = [q for sec in schema_out2["sections"]
             for q in (sec.get("questions") or [])
             if q.get("fill_mode") == "table_input"]
assert_eq("table question 1개 유지 (추가 안 됨)", len(table_qs2), 1)
assert_eq("LLM question_id 유지", table_qs2[0]["question_id"], "Q_BUDGET")
assert_eq("LLM title 유지", table_qs2[0]["title"], "사업비 총괄")
# table_schema가 보정됨
assert_eq("보정된 col_count", table_qs2[0]["table_schema"]["col_count"], 11)
assert_eq("보정된 row_count", table_qs2[0]["table_schema"]["row_count"], 8)
assert_eq("source_type 보정 표시",
          table_qs2[0]["source_type"], SOURCE_TYPE_CORRECTED)
assert_eq("metadata.corrected_by",
          table_qs2[0]["metadata"]["corrected_by"], "table_promoter")
assert_eq("llm_schema_corrected_count = 1", stats2["llm_schema_corrected_count"], 1)
assert_eq("promoted_table_count = 0", stats2["promoted_table_count"], 0)


# ─────────────────────────────────────────────────────────────────────
# 9. promote_tables — fragment는 승격 안 함
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 9: fragment 승격 제외 ===")
frag_nt = NormalizedTable(
    table_id="frag", source_page=6, bbox=[10, 10, 100, 50],
    rows=3, columns=1, header_paths=[["a"]],
    title_candidate="frag", empty_field_count=0,
    is_fragment=True, confidence=0.5, is_promotable=False,
    header_row_count=1, cells_raw=[],
)
schema9 = {"sections": []}
out9, stats9 = promote_tables([frag_nt], schema9)
all_qs9 = [q for sec in out9["sections"] for q in (sec.get("questions") or [])]
assert_eq("fragment 승격 0개", stats9["promoted_table_count"], 0)
assert_eq("skipped_fragment 1개", stats9["skipped_fragment_table_count"], 1)
assert_eq("question 추가 안 됨", len(all_qs9), 0)


# ─────────────────────────────────────────────────────────────────────
# 10. Integration — AX 40p fixture
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 10: Integration — AX 40p (LLM schema 비어있음) ===")
data = json.loads(FIXTURE.read_text(encoding="utf-8"))
pages = data["pages"]
normalized = normalize_layout_tables(pages)

# 빈 LLM schema (form_parser 결과를 시뮬레이션)
empty_schema = {"form_id": "AX_form1", "form_name": "AX form1", "sections": []}
result_schema, ax_stats = promote_tables(normalized, empty_schema)

print(f"  layout_table_count      = {ax_stats['layout_table_count']}")
print(f"  normalized_table_count  = {ax_stats['normalized_table_count']}")
print(f"  llm_table_input_count   = {ax_stats['llm_table_input_count']}")
print(f"  promoted_table_count    = {ax_stats['promoted_table_count']}")
print(f"  skipped_fragment        = {ax_stats['skipped_fragment_table_count']}")
print(f"  llm_schema_corrected    = {ax_stats['llm_schema_corrected_count']}")
print(f"  auto_section_used       = {ax_stats['auto_section_used_count']}")
print(f"  table_promotion_rate    = {ax_stats['table_promotion_rate']:.2f}")

assert_eq("normalized_table_count = 46", ax_stats["normalized_table_count"], 46)
assert_true("promoted >= 35", ax_stats["promoted_table_count"] >= 35)
assert_eq("llm_schema_corrected = 0 (빈 LLM schema)",
          ax_stats["llm_schema_corrected_count"], 0)
assert_true("skipped_fragment >= 5",
            ax_stats["skipped_fragment_table_count"] >= 5)

# 핵심 표 5종 모두 question으로 생성됨
key_pages_targets = [4, 7, 34, 35, 36]
all_qs_ax = [q for sec in result_schema["sections"]
             for q in (sec.get("questions") or [])]
table_qs_ax = [q for q in all_qs_ax if q.get("fill_mode") == "table_input"]
print(f"\n  total promoted questions = {len(table_qs_ax)}")

for pg in key_pages_targets:
    pg_qs = [q for q in table_qs_ax if q.get("source_page") == pg]
    print(f"  p.{pg:>2} promoted questions = {len(pg_qs)}")
    assert_true(f"p.{pg} ≥ 1 promoted", len(pg_qs) >= 1)

# 자동 section은 페이지 매칭 실패 시만 사용 (모든 page에 question 있으면 0이어야 함)
print(f"\n  auto_section_used_count = {ax_stats['auto_section_used_count']}")

# question_id deterministic 검증 — 재실행 후 같은 ID
empty_schema_2 = {"form_id": "AX_form1", "form_name": "AX form1", "sections": []}
result_schema_2, _ = promote_tables(normalized, empty_schema_2)
ids_1 = sorted([
    q["question_id"]
    for sec in result_schema["sections"]
    for q in (sec.get("questions") or [])
    if q.get("source_type") == SOURCE_TYPE_PROMOTED
])
ids_2 = sorted([
    q["question_id"]
    for sec in result_schema_2["sections"]
    for q in (sec.get("questions") or [])
    if q.get("source_type") == SOURCE_TYPE_PROMOTED
])
assert_eq("question_id 재실행 시 동일 (deterministic)", ids_1, ids_2)


# ─────────────────────────────────────────────────────────────────────
# 11. 핵심 표 p.34 보정 시나리오 (LLM columns=3 → layout 11 보정)
# ─────────────────────────────────────────────────────────────────────
print("\n=== Test 11: LLM 잘못 추출한 p.34 사업비 → layout 보정 ===")
# p.34 normalized table 추출
p34_nts = [n for n in normalized if n.source_page == 34 and n.is_promotable]
assert_true("p.34 promotable table 존재", len(p34_nts) >= 1)
if p34_nts:
    p34_first = p34_nts[0]
    # LLM이 columns=3으로 잘못 추출한 schema 생성
    llm_wrong = {
        "form_id": "AX_form1",
        "sections": [
            {"section_id": "S_BUDGET_REAL", "title": "사업비",
             "questions": [
                 {
                     "question_id": "Q_BUDGET_WRONG",
                     "source_page": 34,
                     "fill_mode": "table_input",
                     "title": "사업비 총괄",
                     "bbox": list(p34_first.bbox),  # 동일 bbox로 매칭 보장
                     "table_schema": {
                         "row_count": 4, "col_count": 3,
                         "columns": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
                     },
                 },
             ]},
        ],
    }
    result_corrected, stats_corrected = promote_tables(p34_nts, llm_wrong)
    table_qs_c = [q for sec in result_corrected["sections"]
                  for q in (sec.get("questions") or [])
                  if q.get("fill_mode") == "table_input"]
    # 같은 page에서 p34 첫 번째 표는 LLM과 매칭 → 보정
    matched = [q for q in table_qs_c if q.get("question_id") == "Q_BUDGET_WRONG"]
    assert_eq("Q_BUDGET_WRONG 유지됨", len(matched), 1)
    if matched:
        m = matched[0]
        assert_true("col_count 11로 보정",
                    m["table_schema"]["col_count"] == p34_first.columns,
                    f"got {m['table_schema']['col_count']}, expected {p34_first.columns}")
        assert_eq("source_type 보정 표시",
                  m["source_type"], SOURCE_TYPE_CORRECTED)


print(f"\n=== A-4-3 단위 + 통합 테스트 완료 ===")
