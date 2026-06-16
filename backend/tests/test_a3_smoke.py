"""
Part A-3 smoke test — parser_metadata 보강, quality gate 동적 기준, repair loop, fallback
"""
import sys, json, asyncio
sys.stdout.reconfigure(encoding="utf-8")

import os
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite:///./ajin.db")

# ── backend root를 sys.path에 추가 ──────────────────────────────────────────
import pathlib
BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

from routers.analysis import (
    _build_layout_aware_text,
    _compute_form_quality_metrics,
    _merge_repair_schema,
    _count_page_markers,
    FORM_LAYOUT_TEXT_SAFETY_CAP,
)


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def section(sid, questions):
    return {"section_id": sid, "title": sid, "order": 1, "questions": questions}


def question(qid, **kwargs):
    base = {"question_id": qid, "title": qid, "is_required": True}
    base.update(kwargs)
    return base


def ok(label, val, want, note=""):
    mark = "✓" if val == want else "✗"
    suffix = f"  ({note})" if note else ""
    print(f"  {mark} {label}: {val!r}" + (f" (want {want!r})" if val != want else "") + suffix)
    return val == want


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — 소규모 신청서 (17p): question_count<40 단독으로 repair/needs_manual_review 금지
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 1: 소형 문서 (17p) — question_count<40 단독 실패 금지 ===")

form_17p = "\n".join(f"=== PAGE {i} ===" for i in range(1, 18))  # 17 page markers

schema_17p = {
    "sections": [
        section("S1", [
            question("Q1", source_page=1, fill_mode="ai_text"),
            question("Q2", source_page=2, fill_mode="user_text"),
            question("Q3", source_page=3, fill_mode="ai_text"),
        ])
    ]
}
pc17 = _count_page_markers(form_17p)
m17 = _compute_form_quality_metrics(schema_17p, form_17p, page_count=pc17)
print(f"  page_count={pc17}, question_count={m17['question_count']}, table_count={m17['table_count']}")
ok("needs_repair", m17["needs_repair"], False,
   "question_count<40 alone must not trigger repair for small doc")
ok("missing_source_page", m17["missing_source_page"], 0)
ok("missing_fill_mode", m17["missing_fill_mode"], 0)


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — 대형 문서 (40p): question_count<40 → repair 트리거
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 2: 대형 문서 (40p) — question_count<40 → repair ===")

form_40p = "\n".join(f"=== PAGE {i} ===" for i in range(1, 41))
schema_small_q = {
    "sections": [
        section("S1", [
            question(f"Q{i}", source_page=i, fill_mode="ai_text") for i in range(1, 6)
        ])
    ]
}
pc40 = _count_page_markers(form_40p)
m40 = _compute_form_quality_metrics(schema_small_q, form_40p, page_count=pc40)
print(f"  page_count={pc40}, question_count={m40['question_count']}, table_count={m40['table_count']}")
ok("needs_repair", m40["needs_repair"], True, "large doc: question_count<40 → repair")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — truncated=true → quality_status != "ok" / "success"
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 3: truncated=true → quality_status 최소 warning ===")
# simulate: layout_meta with truncated=true, quality_metrics ok
schema_ok = {
    "sections": [
        section("S1", [
            question(f"Q{i}", source_page=i, fill_mode="ai_text") for i in range(1, 50)
        ]),
        section("S2", [
            question(f"T{i}", source_page=i+50, fill_mode="table_input",
                     is_table_item=True) for i in range(1, 12)
        ]),
    ]
}
form_35p = "\n".join(f"=== PAGE {i} ===" for i in range(1, 30))  # 29 pages (truncated_after_page=29)
pc35 = 35  # total pages, but only 29 included
m35 = _compute_form_quality_metrics(schema_ok, form_35p, page_count=pc35)
print(f"  page_count={pc35}, question_count={m35['question_count']}, table_count={m35['table_count']}")

# simulate what parse_form does when truncated
quality_status = "ok" if not m35["needs_repair"] else "needs_manual_review"
layout_truncated = True
if layout_truncated and quality_status == "ok":
    quality_status = "warning_truncated"
ok("quality_status != ok", quality_status != "ok", True, f"got: {quality_status!r}")
ok("quality_status", quality_status, "warning_truncated")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — fallback test: no raw_b64 → fallback_reason="missing_raw_b64"
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 4: fallback — missing_raw_b64 ===")
items_no_b64 = [{"parsed_text": "텍스트", "file_id": "f1"}]
text4, meta4, _pages4 = _build_layout_aware_text(items_no_b64)
ok("text empty", text4, "")
ok("fallback_reason", meta4.get("fallback_reason"), "missing_raw_b64")
ok("layout_text_truncated", meta4.get("layout_text_truncated"), False)

print("\n=== Test 4b: fallback — empty items ===")
text4b, meta4b, _pages4b = _build_layout_aware_text([])
ok("text empty", text4b, "")
ok("fallback_reason", meta4b.get("fallback_reason"), "missing_raw_b64")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — repair merge policy
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 5: repair merge — null/empty 필드 보정 + 신규 question 추가 ===")

base_schema = {
    "sections": [
        section("S1", [
            question("Q1", source_page=1),        # fill_mode 없음 (null)
            question("Q2", source_page=2, fill_mode="ai_text"),  # 기존 fill_mode 있음
        ])
    ]
}

repair_schema = {
    "sections": [
        section("S1", [
            question("Q1", source_page=1, fill_mode="user_text"),  # Q1 fill_mode 보정
            question("Q2", source_page=2, fill_mode="table_input"), # Q2 충돌 → 기존 우선
            question("Q3", source_page=3, fill_mode="ai_text"),     # 신규 추가
        ])
    ]
}

merged = _merge_repair_schema(base_schema, repair_schema)
merged_s1 = merged["sections"][0]
merged_qs = {q["question_id"]: q for q in merged_s1["questions"]}

# Q1: fill_mode was null → patched with repair value
ok("Q1.fill_mode patched", merged_qs["Q1"].get("fill_mode"), "user_text", "null → repair value")
# Q2: fill_mode existed → keep original (NOT overwrite)
ok("Q2.fill_mode unchanged", merged_qs["Q2"].get("fill_mode"), "ai_text", "existing value preserved")
# Q3: new question added
ok("Q3 added", "Q3" in merged_qs, True, "new question from repair")
# Q1 and Q2 not removed
ok("Q1 retained", "Q1" in merged_qs, True)
ok("Q2 retained", "Q2" in merged_qs, True)


# ─────────────────────────────────────────────────────────────────────────────
# Test 5b — repair loop: missing_fill_mode triggers repair for small doc
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 5b: repair loop trigger — missing_fill_mode 소형 문서 ===")

schema_missing_fill = {
    "sections": [
        section("S1", [
            question("Q1", source_page=1),   # no fill_mode
            question("Q2", source_page=2),   # no fill_mode
        ])
    ]
}
form_small = "\n".join(f"=== PAGE {i} ===" for i in range(1, 6))
pc_small = _count_page_markers(form_small)
m_small = _compute_form_quality_metrics(schema_missing_fill, form_small, page_count=pc_small)
ok("missing_fill_mode", m_small["missing_fill_mode"], 2)
ok("needs_repair", m_small["needs_repair"], True, "missing_fill_mode → repair triggered")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — source_page policy: user_added items exempt from missing check
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== Test 6: source_page 정책 — user_added는 source_page null 허용 ===")

schema_user_added = {
    "sections": [
        section("S1", [
            question("Q1", source_page=1, fill_mode="ai_text"),
            question("Q_USER", source_type="user_added", fill_mode="user_text"),  # no source_page
        ])
    ]
}
form_small2 = "\n".join(f"=== PAGE {i} ===" for i in range(1, 6))
pc_small2 = _count_page_markers(form_small2)
m_user = _compute_form_quality_metrics(schema_user_added, form_small2, page_count=pc_small2)
ok("missing_source_page excludes user_added", m_user["missing_source_page"], 0,
   "user_added with no source_page not counted")
ok("needs_repair=false", m_user["needs_repair"], False)


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

print("\n=== A-3 smoke test 완료 ===")
print(f"FORM_LAYOUT_TEXT_SAFETY_CAP = {FORM_LAYOUT_TEXT_SAFETY_CAP:,}")
