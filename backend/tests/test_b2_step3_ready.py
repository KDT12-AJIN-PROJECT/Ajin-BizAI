"""
Part B-2 — GET /api/analysis/sessions/{sid}/step3-ready 검증.

시나리오 (b6.md §4):
  A: 정상 confirmed session → ready=true
  B: session 없음 → 404 + reason=session_not_found
  C: Step 2 미확정 → ready=false, reason=step2_not_confirmed
  D: confirmed_schema 없음 (status는 step2_confirmed지만 fsj 비어있음) → reason=confirmed_schema_missing
  E: confirmed_schema 빈 값 (sections 없음 또는 question 0개) → reason=confirmed_schema_empty
  F: parser_metadata / quality_metrics 보존 확인
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

# .env 로드 (DB 직접 조작용)
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
    """Returns (status, body_dict). 404/422도 정상 처리."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 A: 정상 confirmed session → ready=true
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 A: 정상 confirmed session ===")

_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "b2_A"})
sid_a = sess["session_id"]

# parse-form (작은 form_text)
form_text = (
    "=== PAGE 1 ===\n질문1: 회사명\n"
    "=== PAGE 2 ===\n질문2: 대표자\n"
    "=== PAGE 3 ===\n질문3: 사업비표 (table_input)"
)
_, parse_res = http_json("POST", "/api/analysis/parse-form", {
    "form_text": form_text, "form_name": "b2_A.pdf",
    "session_id": sid_a, "request_id": "b2_A_parse",
}, timeout=180)
assert_true("parse-form saved", parse_res.get("saved") == True)

# confirm-step2 (사용자 수정본 — table_input 1개 포함하도록 명시)
user_schema_a = {
    "form_id": "b2_A_form", "form_name": "b2_A",
    "sections": [
        {"section_id": "S1", "title": "기본정보", "order": 1, "questions": [
            {"question_id": "Q1", "title": "회사명", "fill_mode": "ai_text",
             "source_page": 1, "is_required": True},
            {"question_id": "Q2", "title": "대표자", "fill_mode": "profile_mapping",
             "source_page": 2, "is_required": True},
        ]},
        {"section_id": "S2", "title": "사업비", "order": 2, "questions": [
            {"question_id": "Q3", "title": "사업비표", "fill_mode": "table_input",
             "source_page": 3, "is_required": True,
             "table_schema": {"row_count": 5, "col_count": 5, "columns": []}},
        ]},
    ],
}
_, conf_res = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_a,
    "confirmed_form_schema": user_schema_a,
})
ok("confirm-step2 ok", conf_res.get("ok"), True)

# step3-ready 호출
status_a, ready_a = http_json("GET", f"/api/analysis/sessions/{sid_a}/step3-ready")
ok("status 200", status_a, 200)
ok("ok=true", ready_a.get("ok"), True)
ok("step3_ready=true", ready_a.get("step3_ready"), True)
ok("session_status", ready_a.get("session_status"), "step2_confirmed")
ok("current_step=3", ready_a.get("current_step"), 3)
ok("schema_status", ready_a.get("schema_status"), "confirmed")
ok("next_step", ready_a.get("next_step"), "step3_draft")
ok("question_count=3", ready_a.get("confirmed_schema_question_count"), 3)
ok("section_count=2", ready_a.get("confirmed_schema_section_count"), 2)
ok("table_count=1 (fill_mode=table_input 단독)",
   ready_a.get("confirmed_schema_table_count"), 1)
assert_true("confirmed_schema 본문 존재",
            isinstance(ready_a.get("confirmed_schema"), dict))
assert_true("confirmed_at ISO", isinstance(ready_a.get("confirmed_at"), str))
assert_true("confirmed_step2_at ISO",
            isinstance(ready_a.get("confirmed_step2_at"), str))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 B: session 없음 → 404 + reason=session_not_found
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 B: session 없음 → 404 ===")
status_b, body_b = http_json("GET", "/api/analysis/sessions/nonexistent_b2/step3-ready")
ok("status 404", status_b, 404)
# FastAPI HTTPException detail은 {"detail": {...}} 형태로 wrapping됨
detail_b = body_b.get("detail") or {}
ok("ok=false", detail_b.get("ok"), False)
ok("reason=session_not_found", detail_b.get("reason"), "session_not_found")
ok("step3_ready=false", detail_b.get("step3_ready"), False)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 C: Step 2 미확정 → reason=step2_not_confirmed
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 C: Step 2 미확정 ===")
_, sess_c = http_json("POST", "/api/analysis/sessions", {"user_id": "b2_C"})
sid_c = sess_c["session_id"]
# confirm-step2 호출 없이 바로 step3-ready
status_c, ready_c = http_json("GET", f"/api/analysis/sessions/{sid_c}/step3-ready")
ok("status 200", status_c, 200)
ok("ok=false", ready_c.get("ok"), False)
ok("step3_ready=false", ready_c.get("step3_ready"), False)
ok("reason=step2_not_confirmed", ready_c.get("reason"), "step2_not_confirmed")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 D: confirmed_schema 없음 (DB 직접 조작)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 D: status는 step2_confirmed지만 confirmed_schema 누락 ===")
from database import get_db
from models import ApplicationSession
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime

_, sess_d = http_json("POST", "/api/analysis/sessions", {"user_id": "b2_D"})
sid_d = sess_d["session_id"]

# DB 직접 조작: status만 step2_confirmed로 + form_schema_json 비워둠
db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_d
    ).first()
    s.status = "step2_confirmed"
    s.current_step = 3
    s.confirmed_step2_at = datetime.utcnow()
    # form_schema_json은 빈 dict
    s.form_schema_json = {}
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

status_d, ready_d = http_json("GET", f"/api/analysis/sessions/{sid_d}/step3-ready")
ok("status 200", status_d, 200)
ok("ok=false", ready_d.get("ok"), False)
ok("step3_ready=false", ready_d.get("step3_ready"), False)
ok("reason=schema_status_not_confirmed (또는 confirmed_schema_missing)",
   ready_d.get("reason") in {"schema_status_not_confirmed",
                              "confirmed_schema_missing"}, True)
# 정확히 schema_status_not_confirmed 여야 함 (form_schema_json이 빈 dict이므로
# schema_status 키가 없음)
ok("reason 정확히 schema_status_not_confirmed",
   ready_d.get("reason"), "schema_status_not_confirmed")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 D-2: confirmed_schema_missing 정확히 재현
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 D-2: schema_status='confirmed'지만 confirmed_schema 키 없음 ===")
_, sess_d2 = http_json("POST", "/api/analysis/sessions", {"user_id": "b2_D2"})
sid_d2 = sess_d2["session_id"]

db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_d2
    ).first()
    s.status = "step2_confirmed"
    s.current_step = 3
    s.confirmed_step2_at = datetime.utcnow()
    s.form_schema_json = {"schema_status": "confirmed"}  # confirmed_schema 없음
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

status_d2, ready_d2 = http_json("GET", f"/api/analysis/sessions/{sid_d2}/step3-ready")
ok("D-2 reason=confirmed_schema_missing",
   ready_d2.get("reason"), "confirmed_schema_missing")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 E: confirmed_schema 빈 값 (sections 없음)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E: confirmed_schema sections 없음 또는 question 0개 ===")
_, sess_e = http_json("POST", "/api/analysis/sessions", {"user_id": "b2_E"})
sid_e = sess_e["session_id"]

db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_e
    ).first()
    s.status = "step2_confirmed"
    s.current_step = 3
    s.confirmed_step2_at = datetime.utcnow()
    s.form_schema_json = {
        "schema_status": "confirmed",
        "confirmed_schema": {"form_id": "empty", "sections": []},  # sections 비어있음
        "confirmed_at": datetime.utcnow().isoformat(),
    }
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

status_e, ready_e = http_json("GET", f"/api/analysis/sessions/{sid_e}/step3-ready")
ok("E reason=confirmed_schema_empty",
   ready_e.get("reason"), "confirmed_schema_empty")

# 시나리오 E-2: sections는 있지만 questions 0개
print("\n=== 시나리오 E-2: sections 있지만 question 0개 ===")
_, sess_e2 = http_json("POST", "/api/analysis/sessions", {"user_id": "b2_E2"})
sid_e2 = sess_e2["session_id"]

db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_e2
    ).first()
    s.status = "step2_confirmed"
    s.current_step = 3
    s.confirmed_step2_at = datetime.utcnow()
    s.form_schema_json = {
        "schema_status": "confirmed",
        "confirmed_schema": {
            "form_id": "empty_q",
            "sections": [{"section_id": "S1", "title": "빈 섹션", "questions": []}],
        },
        "confirmed_at": datetime.utcnow().isoformat(),
    }
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

status_e2, ready_e2 = http_json("GET", f"/api/analysis/sessions/{sid_e2}/step3-ready")
ok("E-2 reason=confirmed_schema_empty",
   ready_e2.get("reason"), "confirmed_schema_empty")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 F: parser_metadata / quality_metrics 보존 (시나리오 A 재활용)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 F: parser_metadata / quality_metrics 보존 ===")
# 시나리오 A의 sid_a를 다시 조회
_, ready_a2 = http_json("GET", f"/api/analysis/sessions/{sid_a}/step3-ready")
pm_a = ready_a2.get("parser_metadata", {})
qm_a = ready_a2.get("quality_metrics", {})

# parser_metadata: A-4-4 신규 필드 일부 포함 확인
assert_true("parser_metadata dict 존재", isinstance(pm_a, dict))
assert_true("parser_metadata.provider 존재", "provider" in pm_a)
assert_true("parser_metadata.parser_mode 존재", "parser_mode" in pm_a)
# A-4-4 신규 필드
assert_true("parser_metadata.layout_table_count 존재", "layout_table_count" in pm_a)
assert_true("parser_metadata.promoted_table_count 존재", "promoted_table_count" in pm_a)
assert_true("parser_metadata.normalize_table_enabled 존재",
            "normalize_table_enabled" in pm_a)
# nested quality_metrics 보존 확인
assert_true("parser_metadata.quality_metrics nested 보존",
            "quality_metrics" in pm_a)

# top-level quality_metrics
assert_true("top-level quality_metrics dict", isinstance(qm_a, dict))
assert_true("quality_metrics.question_count 존재",
            "question_count" in qm_a)
assert_true("quality_metrics.table_count 존재",
            "table_count" in qm_a)

# 보존 검증: parser_metadata.quality_metrics와 top-level quality_metrics 동일
nested_qm = pm_a.get("quality_metrics", {})
ok("top-level == nested quality_metrics",
   json.dumps(nested_qm, sort_keys=True),
   json.dumps(qm_a, sort_keys=True))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 G: 기존 GET /sessions/{sid} 회귀 확인 (수정 안 됨)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 G: 기존 /sessions/{sid} 회귀 (raw 조회 영향 없음) ===")
status_g, raw_g = http_json("GET", f"/api/analysis/sessions/{sid_a}")
ok("기존 endpoint status 200", status_g, 200)
ok("기존 응답 status 필드", raw_g.get("status"), "step2_confirmed")
ok("기존 응답 form_schema_json 키 존재",
   isinstance(raw_g.get("form_schema_json"), dict), True)
assert_true("기존 응답에 step3_ready 키 없음 (확장 안 됨)",
            "step3_ready" not in raw_g)


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== B-2 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
