"""
Part C-1.6 — evaluation_rubric resolver 검증.

시나리오 (발주문 §"테스트"):
  1. announcement criteria 있음 → source=announcement
  2. criteria weight 합계 normalize (rescale to 100)
  3. criteria weight 없음 → 균등 분배 (equal_distribution)
  4. criteria 없음 + startup 키워드 → default_template/startup
  5. criteria 없음 + 유형 불명확 → general
  6. axes weight 합계 100
  7. user_confirmed=false 저장
  8. 기존 form_schema_json key 보존
"""
import sys
import json
import urllib.request
import urllib.error
import os
import pathlib

sys.stdout.reconfigure(encoding="utf-8")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BASE = "http://localhost:8000"
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


def http_json(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# 단위 테스트용 직접 import
from services.rubric_resolver import (
    resolve_evaluation_rubric,
    detect_business_type,
    _normalize_announcement_axes,
    _template_axes,
    _DEFAULT_TEMPLATES,
)


# ─────────────────────────────────────────────────────────────────────
# Unit: detect_business_type
# ─────────────────────────────────────────────────────────────────────
print("=== Unit: detect_business_type ===")

# startup 키워드 매칭
det_su = detect_business_type(
    {"target": "초기창업 기업", "important_keywords": ["스타트업"]},
    None, None,
)
ok("startup detection", det_su["selected_type"], "startup")
ok("startup method", det_su["method"], "keyword_match")
assert_true("startup scores positive", det_su["scores"]["startup"] >= 1)

# R&D 키워드 매칭
det_rd = detect_business_type(
    {"target": "R&D 사업", "important_keywords": ["연구개발", "기술개발"]},
    None, None,
)
ok("R&D detection", det_rd["selected_type"], "R&D")

# 유형 불명확 → general
det_none = detect_business_type({"target": "어떤 일반 사업"}, None, None)
ok("불명확 → general", det_none["selected_type"], "general")
ok("불명확 method=default_general", det_none["method"], "default_general")

# 3개 소스 통합 (announcement_signals 포함)
det_combined = detect_business_type(
    {"target": "사업화 지원"},
    {"form_name": "양산 계획서"},
    {"criteria": [{"name": "제품 실증"}]},
)
ok("3 source combined → commercialization", det_combined["selected_type"], "commercialization")


# ─────────────────────────────────────────────────────────────────────
# Unit: _normalize_announcement_axes (Q6 사용자 확정안)
# ─────────────────────────────────────────────────────────────────────
print("\n=== Unit: _normalize_announcement_axes (3-case) ===")

# case 1: 모두 positive (rescale)
case1 = [
    {"name": "기술성", "weight": 40},
    {"name": "사업성", "weight": 30},
    {"name": "수행역량", "weight": 30},
]
axes1 = _normalize_announcement_axes(case1)
ok("case1 axes 3", len(axes1), 3)
ok("case1 weight sum=100", round(sum(a["weight"] for a in axes1), 6), 100.0)
ok("case1 모두 announcement_explicit",
   all(a["weight_source"] == "announcement_explicit" for a in axes1), True)
ok("case1 모두 is_scored=true",
   all(a["is_scored"] for a in axes1), True)

# case 1 rescale (합계 80 → 100)
case1b = [
    {"name": "A", "weight": 40},
    {"name": "B", "weight": 40},
]
axes1b = _normalize_announcement_axes(case1b)
ok("case1b rescale sum=100", round(sum(a["weight"] for a in axes1b), 6), 100.0)
assert_true("case1b weight 50.0", abs(axes1b[0]["weight"] - 50.0) < 1e-6)

# case 2: 모두 weight 없음 → 균등 분배
case2 = [
    {"name": "A"},
    {"name": "B"},
    {"name": "C"},
    {"name": "D"},
]
axes2 = _normalize_announcement_axes(case2)
ok("case2 sum=100", round(sum(a["weight"] for a in axes2), 6), 100.0)
ok("case2 모두 equal_distribution",
   all(a["weight_source"] == "announcement_equal_distribution" for a in axes2), True)
ok("case2 모두 is_scored=true",
   all(a["is_scored"] for a in axes2), True)
# 4개 각 25
assert_true("case2 weight 25.0",
            all(abs(a["weight"] - 25.0) < 1e-6 for a in axes2))

# case 3: mixed (10/0/20)
case3 = [
    {"name": "A", "weight": 10},
    {"name": "B"},  # weight 없음
    {"name": "C", "weight": 20},
]
axes3 = _normalize_announcement_axes(case3)
scored = [a for a in axes3 if a["is_scored"]]
non_scored = [a for a in axes3 if not a["is_scored"]]
ok("case3 scored 2", len(scored), 2)
ok("case3 non_scored 1", len(non_scored), 1)
ok("case3 scored sum=100", round(sum(a["weight"] for a in scored), 6), 100.0)
ok("case3 missing axis weight=0", non_scored[0]["weight"], 0.0)
ok("case3 missing weight_source",
   non_scored[0]["weight_source"], "missing_in_announcement")
ok("case3 scored A explicit",
   axes3[0]["weight_source"], "announcement_explicit")
ok("case3 scored C explicit",
   axes3[2]["weight_source"], "announcement_explicit")
# A: 10/30 × 100 = 33.33..., C: 20/30 × 100 = 66.67 (잔차 보정)
assert_true("case3 A weight ~33.33",
            abs(axes3[0]["weight"] - 33.333333333) < 1e-3)
assert_true("case3 C weight ~66.67",
            abs(axes3[2]["weight"] - 66.666666667) < 1e-3)


# ─────────────────────────────────────────────────────────────────────
# Unit: _template_axes
# ─────────────────────────────────────────────────────────────────────
print("\n=== Unit: _template_axes (5종) ===")
for tt in ("R&D", "startup", "commercialization", "marketing", "general"):
    axes = _template_axes(tt)
    ok(f"{tt} 5축", len(axes), 5)
    ok(f"{tt} sum=100", sum(a["weight"] for a in axes), 100.0)
    ok(f"{tt} 모두 weight_source=default_template",
       all(a["weight_source"] == "default_template" for a in axes), True)


# ─────────────────────────────────────────────────────────────────────
# Unit: resolve_evaluation_rubric (Source of Truth)
# ─────────────────────────────────────────────────────────────────────
print("\n=== Unit: resolve_evaluation_rubric Source of Truth ===")

# 시나리오 1: announcement criteria 있음
r1 = resolve_evaluation_rubric(
    notice_schema={"target": "어떤 사업"},
    confirmed_schema=None,
    announcement_signals={"criteria": [
        {"name": "기술성", "weight": 40},
        {"name": "사업성", "weight": 60},
    ]},
)
ok("시나리오1 source=announcement", r1["source"], "announcement")
ok("시나리오1 axes count=2", len(r1["axes"]), 2)
ok("시나리오1 sum=100", sum(a["weight"] for a in r1["axes"]), 100.0)

# 시나리오 4: criteria 없음 + startup 키워드 → default_template/startup
r4 = resolve_evaluation_rubric(
    notice_schema={"target": "예비창업자 지원", "important_keywords": ["스타트업"]},
    confirmed_schema=None,
    announcement_signals=None,
)
ok("시나리오4 source=default_template", r4["source"], "default_template")
ok("시나리오4 template_type=startup", r4["template_type"], "startup")
ok("시나리오4 axes=5", len(r4["axes"]), 5)

# 시나리오 5: criteria 없음 + 유형 불명확 → general
r5 = resolve_evaluation_rubric(
    notice_schema={"target": "어떤 사업"},
    confirmed_schema=None,
    announcement_signals=None,
)
ok("시나리오5 source=general", r5["source"], "general")
ok("시나리오5 template_type=general", r5["template_type"], "general")

# 시나리오 7: user_confirmed=false / user_modified=false
ok("시나리오7 user_confirmed=false", r1["user_confirmed"], False)
ok("시나리오7 user_modified=false", r1["user_modified"], False)

# announcement criteria 빈 배열 → default_template 분기
r_empty = resolve_evaluation_rubric(
    notice_schema={"target": "R&D 사업"},
    confirmed_schema=None,
    announcement_signals={"criteria": []},
)
ok("announcement criteria 빈 → default_template", r_empty["source"], "default_template")
ok("R&D template", r_empty["template_type"], "R&D")


# ─────────────────────────────────────────────────────────────────────
# Integration: API endpoint
# ─────────────────────────────────────────────────────────────────────
print("\n=== Integration: API endpoint ===")

_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "c16_int"})
sid = sess["session_id"]

# normalize 호출
status, body = http_json(
    "POST", f"/api/analysis/sessions/{sid}/evaluation-rubric/resolve",
)
ok("INT status 200", status, 200)
ok("INT ok=true", body.get("ok"), True)
assert_true("INT axes_count > 0", body.get("axes_count", 0) > 0)
ok("INT scored_axes_count==axes_count (default 모두 scored)",
   body.get("scored_axes_count"), body.get("axes_count"))
ok("INT total_weight=100", body.get("total_weight"), 100.0)
# resolved_at ISO
assert_true("INT resolved_at",
            isinstance(body.get("evaluation_rubric", {}).get("resolved_at"), str))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 8: 기존 form_schema_json key 보존
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 8: 기존 key 보존 ===")
_, sess_8 = http_json("POST", "/api/analysis/sessions", {"user_id": "c16_8"})
sid_8 = sess_8["session_id"]

# B-1까지 진행
http_json("POST", "/api/analysis/parse-form", {
    "form_text": "=== PAGE 1 ===\nQ1", "form_name": "8.pdf",
    "session_id": sid_8, "request_id": "8_p",
}, timeout=180)
http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_8,
    "confirmed_form_schema": {
        "form_id": "8", "form_name": "8",
        "sections": [{"section_id": "S1", "questions": [
            {"question_id": "Q1", "title": "Q1", "fill_mode": "ai_text", "source_page": 1},
        ]}],
    },
})
# initialize draft_items
http_json("POST", f"/api/analysis/sessions/{sid_8}/draft-items/initialize", {})
# C-1.5 정규화
http_json(
    "POST", f"/api/analysis/sessions/{sid_8}/announcement-signals/normalize",
)
# C-1.6 resolve
status_8, body_8 = http_json(
    "POST", f"/api/analysis/sessions/{sid_8}/evaluation-rubric/resolve",
)
ok("시나리오8 status 200", status_8, 200)

# 모든 key 보존
_, raw_8 = http_json("GET", f"/api/analysis/sessions/{sid_8}")
fsj = raw_8.get("form_schema_json") or {}
expected_keys = {
    "schema", "confirmed_schema", "schema_status", "confirmed_at",
    "draft_items", "draft_items_status",
    "announcement_signals", "evaluation_rubric",
}
assert_true("시나리오8 모든 key 보존",
            expected_keys.issubset(set(fsj.keys())),
            f"missing: {expected_keys - set(fsj.keys())}")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 6: axes weight 합계 100 (모든 케이스)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 6: 모든 경우 sum=100 ===")
for label, axes in [
    ("case1 (40/30/30)", axes1),
    ("case1b rescale (50/50)", axes1b),
    ("case2 균등 (25×4)", axes2),
    ("case3 mixed scored", [a for a in axes3 if a["is_scored"]]),
    ("template R&D", _template_axes("R&D")),
    ("template general", _template_axes("general")),
]:
    s = round(sum(a["weight"] for a in axes), 6)
    ok(f"  {label} sum=100", s, 100.0)


# ─────────────────────────────────────────────────────────────────────
# session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== session 없음 → 404 ===")
status_404, _ = http_json(
    "POST", "/api/analysis/sessions/nonexistent_c16/evaluation-rubric/resolve",
)
ok("404", status_404, 404)


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== C-1.6 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
