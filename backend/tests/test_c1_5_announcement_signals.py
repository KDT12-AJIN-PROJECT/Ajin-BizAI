"""
Part C-1.5 — announcement_signals 정규화 검증.

시나리오 (발주문 §"테스트" + 추가):
  A: 평가기준 있음 (mock provider 호출) → criteria 변환
  B: 가점조건만 있음 → bonuses 변환, criteria 빈 배열
  C: exclusion_conditions/target 있음 → eligibility 변환
  D: 평가 관련 신호 없음 → status=no_signals_found
  E: 공고문 없음 (notice_schema_json["schema"] 없음) → status=empty
  F: 기존 confirmed_schema / draft_items / reference_attachments 보존
  G: strength 계산 검증 (criteria 3-case + bonus regex + importance fallback)
  H: 재호출 시 created_at 보존, updated_at 갱신
  I: session 없음 → 404
"""
import sys
import json
import urllib.request
import urllib.error
import os
import pathlib
from datetime import datetime
import time

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


def normalize(sid: str):
    return http_json(
        "POST", f"/api/analysis/sessions/{sid}/announcement-signals/normalize",
    )


# 직접 _extract_announcement_signals helper 검증
from routers.analysis import (
    _extract_announcement_signals,
    _criteria_strength,
    _bonus_strength,
    _preference_strength,
    _emphasis_keyword_strength,
    _extract_bonus_points,
    _clamp_strength,
)


# ─────────────────────────────────────────────────────────────────────
# 단위 테스트: strength helpers
# ─────────────────────────────────────────────────────────────────────
print("=== Unit: strength helpers ===")

# clamp
ok("clamp(-0.5) = 0.0", _clamp_strength(-0.5), 0.0)
ok("clamp(1.5) = 1.0", _clamp_strength(1.5), 1.0)
ok("clamp(0.7) = 0.7", _clamp_strength(0.7), 0.7)

# _extract_bonus_points
ok("'가점 2점' → 2.0", _extract_bonus_points({"value": "가점 2점"}), 2.0)
ok("'1.5점' → 1.5", _extract_bonus_points({"value": "1.5점 우대"}), 1.5)
ok("'없음' → None", _extract_bonus_points({"value": "특이사항 없음"}), None)
ok("label 매칭 '3점 가점'", _extract_bonus_points({"label": "3점 가점", "value": ""}), 3.0)

# criteria strength (3-case)
crit_full = [{"name": "기술성", "weight": 40}, {"name": "사업성", "weight": 30}, {"name": "수행역량", "weight": 30}]
ok("기술성 40/100 = 0.4", round(_criteria_strength(crit_full[0], crit_full), 2), 0.4)
ok("사업성 30/100 = 0.3", round(_criteria_strength(crit_full[1], crit_full), 2), 0.3)

# case 1: 모두 weight 0/없음 → 0.6
crit_none = [{"name": "A"}, {"name": "B", "weight": 0}]
ok("전체 weight 없음 → 0.6", _criteria_strength(crit_none[0], crit_none), 0.6)
ok("전체 weight 없음 (B) → 0.6", _criteria_strength(crit_none[1], crit_none), 0.6)

# case 3: 일부만 누락 → 0.2 (사용자 확정안)
crit_partial = [{"name": "A", "weight": 10}, {"name": "B"}, {"name": "C", "weight": 20}]
ok("partial: A 10/30", round(_criteria_strength(crit_partial[0], crit_partial), 3), 0.333)
ok("partial: B (누락) → 0.2", _criteria_strength(crit_partial[1], crit_partial), 0.2)
ok("partial: C 20/30", round(_criteria_strength(crit_partial[2], crit_partial), 3), 0.667)

# bonus strength
ok("bonus 2점 → max(0.5, 2/5)=0.5", _bonus_strength({"value": "2점"}), 0.5)
ok("bonus 5점 → max(0.5, 1.0)=1.0", _bonus_strength({"value": "5점"}), 1.0)
ok("bonus 10점 → clamp 1.0", _bonus_strength({"value": "10점"}), 1.0)
ok("bonus 점수없음 importance=high → 0.9",
   _bonus_strength({"value": "없음", "importance": "high"}), 0.9)
ok("bonus 점수없음 importance=medium → 0.7",
   _bonus_strength({"value": "없음", "importance": "medium"}), 0.7)
ok("bonus 점수없음 importance=low → 0.5",
   _bonus_strength({"value": "없음", "importance": "low"}), 0.5)
ok("bonus 점수없음 unknown → 0.5",
   _bonus_strength({"value": "없음"}), 0.5)

# preference strength
ok("pref high → 0.5", _preference_strength({"importance": "high"}), 0.5)
ok("pref medium → 0.4", _preference_strength({"importance": "medium"}), 0.4)
ok("pref low → 0.3", _preference_strength({"importance": "low"}), 0.3)
ok("pref unknown → 0.3", _preference_strength({}), 0.3)

# emphasis_keyword strength
ok("kw high → 0.3", _emphasis_keyword_strength({"importance": "high"}), 0.3)
ok("kw medium → 0.2", _emphasis_keyword_strength({"importance": "medium"}), 0.2)
ok("kw unknown → 0.1", _emphasis_keyword_strength({}), 0.1)


# ─────────────────────────────────────────────────────────────────────
# 단위 테스트: _extract_announcement_signals — 5 시나리오
# ─────────────────────────────────────────────────────────────────────
print("\n=== Unit: _extract_announcement_signals ===")

# A: 평가기준 있음
schema_a = {
    "evaluation_criteria": [
        {"name": "기술성", "weight": 40, "scope": "section"},
        {"name": "사업성", "weight": 30, "scope": "section"},
    ],
    "extras": [],
}
sig_a = _extract_announcement_signals(schema_a)
ok("A status=normalized", sig_a["status"], "normalized")
ok("A criteria=2", len(sig_a["criteria"]), 2)
ok("A criteria[0].strength=0.571",
   round(sig_a["criteria"][0]["strength"], 3), 0.571)
ok("A bonuses 빈", len(sig_a["bonuses"]), 0)

# B: 가점만
schema_b = {
    "extras": [
        {"category": "가점", "label": "비수도권", "value": "2점", "source_page": 2,
         "source_quote": "비수도권 2점", "confidence": 0.95, "importance": "high"},
    ],
}
sig_b = _extract_announcement_signals(schema_b)
ok("B criteria 빈", len(sig_b["criteria"]), 0)
ok("B bonuses=1", len(sig_b["bonuses"]), 1)
ok("B bonus name", sig_b["bonuses"][0]["name"], "비수도권")
ok("B bonus strength (2점 → 0.5)", sig_b["bonuses"][0]["strength"], 0.5)

# C: exclusion + target → eligibility
schema_c = {
    "target": "중소기업",
    "exclusion_conditions": ["최근 3년 내 수혜 기업 제외"],
    "extras": [],
}
sig_c = _extract_announcement_signals(schema_c)
ok("C eligibility=2", len(sig_c["eligibility"]), 2)
ok("C eligibility[0].kind=target", sig_c["eligibility"][0]["kind"], "target")
ok("C eligibility[1].kind=exclusion", sig_c["eligibility"][1]["kind"], "exclusion")
ok("C eligibility[0].strength=1.0", sig_c["eligibility"][0]["strength"], 1.0)
ok("C criteria 빈", len(sig_c["criteria"]), 0)

# D: schema 있으나 모두 빈 → no_signals_found
schema_d = {
    "evaluation_criteria": [],
    "extras": [],
    "important_keywords": [],
    "exclusion_conditions": [],
    "required_documents": [],
}
sig_d = _extract_announcement_signals(schema_d)
ok("D status=no_signals_found", sig_d["status"], "no_signals_found")

# E: schema None → empty
sig_e = _extract_announcement_signals(None)
ok("E status=empty (None)", sig_e["status"], "empty")
sig_e2 = _extract_announcement_signals({})
ok("E2 status=no_signals_found (빈 dict)", sig_e2["status"], "no_signals_found")


# ─────────────────────────────────────────────────────────────────────
# Integration: API endpoint
# ─────────────────────────────────────────────────────────────────────
print("\n=== Integration: API endpoint ===")

# session 생성 + parse-notice로 mock NoticeSchema 저장
_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "c15_int"})
sid_int = sess["session_id"]

# parse-notice (mock provider 호출 — mock_provider.notice_analyst 결과 저장)
# AI_PROVIDER가 openai이면 실제 호출 시간 길지만, notice_text 있으면 가능
_, parse_res = http_json("POST", "/api/analysis/parse-notice", {
    "notice_text": "테스트 공고문\n중소기업 대상\n기술성 40점 사업성 30점",
    "session_id": sid_int,
    "request_id": "c15_int_parse",
}, timeout=180)

# normalize 호출
status_int, body_int = normalize(sid_int)
ok("INT status 200", status_int, 200)
ok("INT ok=true", body_int.get("ok"), True)
status_val = body_int.get("status")
assert_true("INT status in [normalized, no_signals_found]",
            status_val in ("normalized", "no_signals_found"),
            f"got {status_val}")
assert_true("INT announcement_signals dict",
            isinstance(body_int.get("announcement_signals"), dict))

# 시나리오 E (실측): notice 없는 session
_, sess_e = http_json("POST", "/api/analysis/sessions", {"user_id": "c15_e"})
sid_e_int = sess_e["session_id"]
status_e_int, body_e_int = normalize(sid_e_int)
ok("E (실측) status 200", status_e_int, 200)
ok("E (실측) signal.status=empty", body_e_int.get("status"), "empty")
ok("E (실측) criteria_count=0", body_e_int.get("criteria_count"), 0)


# ─────────────────────────────────────────────────────────────────────
# F: 기존 form_schema_json key 보존
# ─────────────────────────────────────────────────────────────────────
print("\n=== F: 기존 confirmed_schema / draft_items / reference_attachments 보존 ===")

# B-1까지 마친 session 생성
_, sess_f = http_json("POST", "/api/analysis/sessions", {"user_id": "c15_F"})
sid_f = sess_f["session_id"]

# parse-notice + parse-form
http_json("POST", "/api/analysis/parse-notice", {
    "notice_text": "test notice", "session_id": sid_f, "request_id": "F_n",
}, timeout=180)
http_json("POST", "/api/analysis/parse-form", {
    "form_text": "=== PAGE 1 ===\nQ1", "form_name": "F.pdf",
    "session_id": sid_f, "request_id": "F_f",
}, timeout=180)
# confirm-step2
http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_f,
    "confirmed_form_schema": {
        "form_id": "F", "form_name": "F",
        "sections": [{"section_id": "S1", "questions": [
            {"question_id": "Q1", "title": "Q1", "fill_mode": "ai_text", "source_page": 1},
        ]}],
    },
})
# initialize draft_items
http_json("POST", f"/api/analysis/sessions/{sid_f}/draft-items/initialize", {})

# normalize 호출 (C-1.5)
status_f, body_f = normalize(sid_f)
ok("F normalize 200", status_f, 200)

# 모든 key 보존 검증
_, raw_f = http_json("GET", f"/api/analysis/sessions/{sid_f}")
fsj_keys = set((raw_f.get("form_schema_json") or {}).keys())
expected = {"confirmed_schema", "schema_status", "confirmed_at",
            "draft_items", "draft_items_status",
            "announcement_signals"}
assert_true("F 모든 key 보존",
            expected.issubset(fsj_keys),
            f"missing: {expected - fsj_keys}")
# parser_metadata도
parser_md = (raw_f.get("form_schema_json") or {}).get("parser_metadata")
assert_true("F parser_metadata 보존", isinstance(parser_md, dict))


# ─────────────────────────────────────────────────────────────────────
# H: 재호출 시 created_at 보존, updated_at 갱신
# ─────────────────────────────────────────────────────────────────────
print("\n=== H: 재호출 시 created_at 보존 + updated_at 갱신 ===")
_, sess_h = http_json("POST", "/api/analysis/sessions", {"user_id": "c15_H"})
sid_h = sess_h["session_id"]

# 1회차
_, body_h1 = normalize(sid_h)
created_at_1 = body_h1["announcement_signals"].get("created_at")
updated_at_1 = body_h1["announcement_signals"].get("updated_at")
assert_true("H 1회차 created_at 존재", isinstance(created_at_1, str))

# 잠시 대기 후 2회차
time.sleep(0.1)
_, body_h2 = normalize(sid_h)
created_at_2 = body_h2["announcement_signals"].get("created_at")
updated_at_2 = body_h2["announcement_signals"].get("updated_at")
ok("H 재호출 created_at 보존", created_at_2, created_at_1)
assert_true("H 재호출 updated_at 갱신 (다름)",
            updated_at_2 != updated_at_1)


# ─────────────────────────────────────────────────────────────────────
# I: session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== I: session 없음 → 404 ===")
status_i, _ = normalize("nonexistent_c15")
ok("I status 404", status_i, 404)


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== C-1.5 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
