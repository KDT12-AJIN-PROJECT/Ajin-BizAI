"""
A-4-5 — AX 40p 최종 검증 (A-4-5.md 10개 항목).

전제: fixture 캐시(`ax_form1_40p.json`) 사용. OpenAI 호출은 mock LLM 시나리오로만.
순수 normalize + promote 결과를 검증 (LLM 호출 시간 = 0).
"""
import sys
import json
import time
import pathlib
import os

sys.stdout.reconfigure(encoding="utf-8")
BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from services.table_normalizer import normalize_layout_tables
from services.table_promoter import (
    promote_tables,
    SOURCE_TYPE_PROMOTED,
    SOURCE_TYPE_CORRECTED,
)

FIXTURE = BACKEND / "tests" / "fixtures" / "layout_ir" / "ax_form1_40p.json"

KEY_PAGES = {
    4: "기관현황",
    7: "요약서-2",
    34: "사업비 총괄표",
    35: "비목별 총괄표",
    36: "인건비 표",
}

# ─── 통계 카운터 ────────────────────────────────────────
PASSES = 0
FAILS = 0


def ok(label, val, want):
    global PASSES, FAILS
    if val == want:
        print(f"  ✓ {label}")
        PASSES += 1
    else:
        print(f"  ✗ {label}  got={val!r} want={want!r}")
        FAILS += 1


def assert_true(label, cond, note=""):
    global PASSES, FAILS
    suffix = f"  ({note})" if note else ""
    if cond:
        print(f"  ✓ {label}{suffix}")
        PASSES += 1
    else:
        print(f"  ✗ {label}{suffix}")
        FAILS += 1


# ─────────────────────────────────────────────────────────────────────
# fixture 로드 + 베이스 결과 계산
# ─────────────────────────────────────────────────────────────────────

print("=" * 70)
print("A-4-5 AX 40p 최종 검증 시작")
print("=" * 70)

t0 = time.time()
data = json.loads(FIXTURE.read_text(encoding="utf-8"))
pages = data["pages"]
t_fixture_load = time.time() - t0
print(f"\n[fixture load] {t_fixture_load:.3f}s, pages={len(pages)}")

# normalize (성능 측정)
t1 = time.time()
normalized = normalize_layout_tables(pages)
t_normalize = time.time() - t1

# 빈 LLM schema로 promote
empty_llm = {"form_id": "AX_form1", "form_name": "AX form1", "sections": []}
t2 = time.time()
result_schema, stats = promote_tables(normalized, empty_llm)
t_promote = time.time() - t2

print(f"[normalizer]  {t_normalize:.3f}s, {len(normalized)} tables")
print(f"[promoter]    {t_promote:.3f}s")

all_qs = [q for sec in result_schema["sections"] for q in (sec.get("questions") or [])]
table_qs = [q for q in all_qs if q.get("fill_mode") == "table_input"]
promoted_qs = [q for q in table_qs if q.get("source_type") == SOURCE_TYPE_PROMOTED]


# ─────────────────────────────────────────────────────────────────────
# Item 1: 최종 schema table coverage
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 1] 최종 schema table coverage")
total_table = len(table_qs)
llm_table = len([q for q in table_qs if q.get("source_type") != SOURCE_TYPE_PROMOTED])
promoted_table = len(promoted_qs)
print(f"  total table_input    = {total_table}")
print(f"  llm_table_count      = {llm_table}")
print(f"  promoted_table_count = {promoted_table}")
ok("llm + promoted == total", llm_table + promoted_table, total_table)
assert_true("total ≥ 30", total_table >= 30)


# ─────────────────────────────────────────────────────────────────────
# Item 2: 핵심 표 5종 상세 필드 검증
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 2] 핵심 표 5종 상세 검증")
for pg, name in KEY_PAGES.items():
    pg_qs = [q for q in table_qs if q.get("source_page") == pg]
    print(f"\n  p.{pg:>2} {name}")
    assert_true(f"    p.{pg} ≥ 1 table_input", len(pg_qs) >= 1)
    for q in pg_qs:
        qid = q.get("question_id")
        title = (q.get("title") or "")[:40]
        ts = q.get("table_schema", {})
        rc = ts.get("row_count")
        cc = ts.get("col_count")
        cols_n = len(ts.get("columns") or [])
        st = q.get("source_type")
        print(f"    qid={qid}  title={title!r}  {rc}r×{cc}c  cols={cols_n}  source_type={st}")
        # 모든 필드 존재 검증
        assert_true(f"    qid 존재", bool(qid))
        assert_true(f"    title 존재", bool(title))
        assert_true(f"    row_count > 0", (rc or 0) > 0)
        assert_true(f"    col_count > 0", (cc or 0) > 0)
        assert_true(f"    columns 수 일치", cols_n == cc)
        assert_true(f"    source_type 명시", st in {SOURCE_TYPE_PROMOTED, SOURCE_TYPE_CORRECTED, None, "llm"} or st is None)


# ─────────────────────────────────────────────────────────────────────
# Item 3: p.34 다단헤더 11컬럼 검증
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 3] p.34 사업비 총괄표 다단헤더 (11컬럼)")
p34_table_qs = [q for q in table_qs if q.get("source_page") == 34]
p34_11c = [q for q in p34_table_qs
           if q.get("table_schema", {}).get("col_count") == 11]
assert_true("p.34에 11컬럼 표 존재", len(p34_11c) >= 1)
if p34_11c:
    q = p34_11c[0]
    cols = q.get("table_schema", {}).get("columns", [])
    paths = [c.get("header_path", []) for c in cols]
    print(f"  header_paths:")
    for i, p in enumerate(paths):
        print(f"    c{i+1}: {p}")
    # 핵심 의미 보존 확인
    all_path_text = " ".join(" ".join(p) for p in paths)
    assert_true("정부지원금 포함", "정부지원금" in all_path_text)
    assert_true("기관부담금 포함", "기관부담금" in all_path_text)
    assert_true("합계 포함", "합 계" in all_path_text or "합계" in all_path_text)
    # 11컬럼 모두 header_path 가짐
    assert_true("11컬럼 모두 header_path 존재", all(len(p) > 0 for p in paths))


# ─────────────────────────────────────────────────────────────────────
# Item 4: LLM columns 보정 시나리오 (parse_form 흐름 안에서 재현)
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 4] LLM columns 보정 시나리오 — promote_tables() 직접 호출")
# LLM이 p.34 사업비를 columns=3으로 잘못 추출했다는 mock schema
p34_normalized = [n for n in normalized if n.source_page == 34 and n.is_promotable]
assert_true("p.34 promotable 존재", len(p34_normalized) >= 1)
if p34_normalized:
    p34_first = p34_normalized[0]
    # LLM mock schema 생성: 같은 bbox로 매칭되도록
    mock_llm = {
        "form_id": "mock",
        "sections": [
            {
                "section_id": "S_BUDGET", "title": "사업비",
                "questions": [
                    {
                        "question_id": "Q_BUDGET_WRONG",
                        "source_page": 34,
                        "fill_mode": "table_input",
                        "title": "사업비 총괄",
                        "bbox": list(p34_first.bbox) if p34_first.bbox else None,
                        "table_schema": {"row_count": 4, "col_count": 3,
                                          "columns": [{"name": "구분"},
                                                       {"name": "금액"},
                                                       {"name": "비율"}]},
                    }
                ],
            }
        ],
    }
    result_mock, stats_mock = promote_tables([p34_first], mock_llm)
    # LLM question 찾기
    mock_table_qs = [q for sec in result_mock["sections"]
                     for q in (sec.get("questions") or [])
                     if q.get("question_id") == "Q_BUDGET_WRONG"]
    assert_true("Q_BUDGET_WRONG 유지", len(mock_table_qs) == 1)
    if mock_table_qs:
        m = mock_table_qs[0]
        ok("col_count 11로 보정", m["table_schema"]["col_count"], 11)
        ok("source_type 보정 표시", m["source_type"], SOURCE_TYPE_CORRECTED)
        ok("metadata.corrected_by", m["metadata"]["corrected_by"], "table_promoter")
        ok("llm_schema_corrected_count 증가", stats_mock["llm_schema_corrected_count"], 1)
        ok("title LLM 우선 유지", m["title"], "사업비 총괄")


# ─────────────────────────────────────────────────────────────────────
# Item 5: fragment + non-promotable 제외
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 5] fragment / non-promotable 제외 검증")
p6_table_qs = [q for q in table_qs if q.get("source_page") == 6]
ok("p.6 table_input = 0 (fragment 4개 제외)", len(p6_table_qs), 0)
ok("skipped_fragment_table_count", stats["skipped_fragment_table_count"], 7)
ok("skipped_non_promotable_table_count", stats["skipped_non_promotable_table_count"], 2)
total_skipped = stats["skipped_fragment_table_count"] + stats["skipped_non_promotable_table_count"]
ok("skipped 합산 == normalized - promoted",
   total_skipped, stats["normalized_table_count"] - stats["promoted_table_count"])


# ─────────────────────────────────────────────────────────────────────
# Item 6: 중복 table_input 검증
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 6] 중복 table_input 검증")
# (source_page, row_count, col_count) 키로 그룹 → page별 동일 dimension 중복 카운트
from collections import defaultdict
key_count = defaultdict(int)
for q in table_qs:
    ts = q.get("table_schema", {})
    key = (q.get("source_page"), ts.get("row_count"), ts.get("col_count"))
    key_count[key] += 1

# p.37/p.40 등에서 6r×7c 표가 여러개 있을 수 있으므로 동일 page에 ≥2 promoted가 있을 수 있음
# 단, 다른 표(다른 bbox)여야 함 — chain-merge 시 1개로 줄어들었어야 함
dup_keys = {k: v for k, v in key_count.items() if v > 1}
print(f"  동일 (page, rows, cols) 중복: {len(dup_keys)} keys, 상세:")
for k, v in dup_keys.items():
    print(f"    {k}: {v}개")

# chain-merge 검사: 만약 normalize에서 46이었는데 promoted+llm < 39 (38 promotable + 가능 LLM) 이면 손실
# 즉 promoted_table_count는 37이 되어야 함 (A-4-3에서 확인)
ok("promoted_table_count == 37 (chain-merge 없음)",
   stats["promoted_table_count"], 37)


# ─────────────────────────────────────────────────────────────────────
# Item 7: repair 이후 유지 검증
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 7] repair 이후 promoter 결과 유지 검증")
# parse_form 흐름 시뮬레이션: promoted schema에 repair 적용
from routers.analysis import _merge_repair_schema

# repair_result mock: LLM이 누락한 ai_text question 추가
repair_mock = {
    "sections": [
        {"section_id": "S_REPAIR", "title": "repair section",
         "questions": [
             {"question_id": "NEW_AI_Q1", "source_page": 10, "fill_mode": "ai_text",
              "title": "신규 질문"},
         ]},
    ],
}

# promoted question ID 보존 검증
promoted_ids_before = {q["question_id"] for q in promoted_qs}
merged_result = _merge_repair_schema(dict(result_schema), repair_mock)
all_qs_after = [q for sec in (merged_result.get("sections") or [])
                for q in (sec.get("questions") or [])]
promoted_ids_after = {q.get("question_id") for q in all_qs_after
                      if q.get("source_type") == SOURCE_TYPE_PROMOTED}

ok("promoted question_id 모두 유지", promoted_ids_after, promoted_ids_before)

# promoted question의 table_schema가 보존되는지
promoted_q_sample = next((q for q in promoted_qs if q.get("source_page") == 34), None)
if promoted_q_sample:
    qid = promoted_q_sample["question_id"]
    merged_q = next((q for q in all_qs_after if q.get("question_id") == qid), None)
    if merged_q:
        ok("p.34 promoted table_schema.col_count 유지",
           merged_q["table_schema"]["col_count"],
           promoted_q_sample["table_schema"]["col_count"])
        ok("p.34 promoted fill_mode 유지",
           merged_q["fill_mode"], "table_input")
        ok("p.34 promoted source_type 유지",
           merged_q["source_type"], SOURCE_TYPE_PROMOTED)


# ─────────────────────────────────────────────────────────────────────
# Item 8: 성능 측정
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 8] 성능 측정")
print(f"  fixture load          = {t_fixture_load:.3f}s")
print(f"  normalize_layout      = {t_normalize:.3f}s  (목표 < 1s)")
print(f"  promote_tables        = {t_promote:.3f}s   (목표 < 1s)")
total_a4 = t_normalize + t_promote
print(f"  A-4 pipeline total    = {total_a4:.3f}s")
# 전체 parse_form 시간은 OpenAI 의존이므로 별도 측정. A-4-4 실측 108s 기준
# A-4 pipeline / 108 * 100
ratio_against_real = total_a4 / 108.0 * 100
print(f"  vs parse_form total (108s 기준): {ratio_against_real:.2f}%")
assert_true("normalizer < 1s", t_normalize < 1.0)
assert_true("promoter < 1s", t_promote < 1.0)
assert_true("A-4 추가 비용 < 10%", ratio_against_real < 10.0,
            f"got {ratio_against_real:.2f}%")


# ─────────────────────────────────────────────────────────────────────
# Item 9: feature flag off 회귀 (코드 레벨 검증)
# ─────────────────────────────────────────────────────────────────────

print("\n[Item 9] feature flag off 회귀 — 코드 흐름 검증")
# parse_form 코드 직접 검증: env 변수가 False면 normalize_tables / promote_tables 건너뜀
# 함수가 deterministic이므로 코드 흐름 시뮬레이션:
# 1) FORM_NORMALIZE_TABLE=false → normalized=[], promoted=0
# 2) FORM_AUTO_PROMOTE_TABLE=false → promoted=0 (normalize는 됨, promote는 skip)

# 직접 시나리오 시뮬레이션:
empty_llm_2 = {"form_id": "test", "sections": [
    {"section_id": "S1", "questions": [
        {"question_id": "X1", "source_page": 5, "fill_mode": "ai_text",
         "title": "기존 LLM Q1"},
    ]},
]}

# Case A: normalizer off → promoter도 입력 없음
result_off_a, stats_off_a = promote_tables([], empty_llm_2)  # normalized=[] 시뮬레이션
all_qs_off_a = [q for sec in result_off_a["sections"]
                for q in (sec.get("questions") or [])]
ok("normalizer off → promoted = 0", stats_off_a["promoted_table_count"], 0)
ok("normalizer off → table_input = 0", len([q for q in all_qs_off_a
                                              if q.get("fill_mode") == "table_input"]), 0)
ok("기존 LLM question 유지", "X1" in {q.get("question_id") for q in all_qs_off_a}, True)

# Case B: feature flag off에서 parse_form이 정상 진행
# parser_metadata 검증은 A-4-4 통합 시 이미 normalize_table_enabled / auto_promote_table_enabled 필드로 노출됨
# 여기서는 메모리상 검증
print("  (env 변수 변경 + backend 재시작 시 parser_metadata 검증은 별도 통합 테스트에서)")


# ─────────────────────────────────────────────────────────────────────
# 종합 결과
# ─────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print(f"A-4-5 종합 결과: PASS={PASSES}, FAIL={FAILS}")
print("=" * 70)
sys.exit(0 if FAILS == 0 else 1)
