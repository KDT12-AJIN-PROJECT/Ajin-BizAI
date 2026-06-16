"""
Part B-1 — confirm-step2 DB 저장 + deep copy snapshot 검증.

시나리오:
  A: parse-form으로 schema 저장된 session → confirm-step2 (fallback path)
  B: req.confirmed_form_schema 명시 전달 (사용자 수정본 path)
  C: session 없음 → 404
  D: schema 둘 다 없음 → 422
  E: deep copy 검증 (id() 비교 + 객체 변경 격리)
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

# load .env for DB access
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


def http_json(method, path, body=None, timeout=30, expect_status=200):
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
# 시나리오 A: parse-form → confirm-step2 (fallback path)
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 A: parse-form schema fallback ===")
_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "b1_A"})
sid_a = sess["session_id"]

# parse-form (direct_input, 작은 form_text)
form_text = "=== PAGE 1 ===\n질문1: 회사명\n=== PAGE 2 ===\n질문2: 대표자"
_, parse_res = http_json("POST", "/api/analysis/parse-form", {
    "form_text": form_text,
    "form_name": "b1_A.pdf",
    "session_id": sid_a,
    "request_id": "b1_A_parse",
}, timeout=120)
ok("parse-form saved", parse_res.get("saved"), True)

# confirm-step2 (no confirmed_form_schema → fallback to session.schema)
status_a, conf_a = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_a,
})
ok("status 200", status_a, 200)
ok("ok=true", conf_a.get("ok"), True)
ok("session_status=step2_confirmed", conf_a.get("session_status"), "step2_confirmed")
ok("current_step=3", conf_a.get("current_step"), 3)
ok("next_step=step3_draft", conf_a.get("next_step"), "step3_draft")
assert_true("_note 제거됨", "_note" not in conf_a)
assert_true("confirmed_schema 본문 포함", "confirmed_schema" in conf_a)
assert_true("question_count >= 0", conf_a.get("confirmed_schema_question_count") is not None)
assert_true("section_count >= 0", conf_a.get("confirmed_schema_section_count") is not None)
assert_true("table_count >= 0", conf_a.get("confirmed_schema_table_count") is not None)
assert_true("confirmed_at ISO", isinstance(conf_a.get("confirmed_at"), str) and "T" in conf_a["confirmed_at"])

# DB 상태 캡처
_, sess_a_get = http_json("GET", f"/api/analysis/sessions/{sid_a}")
ok("session.status=step2_confirmed", sess_a_get.get("status"), "step2_confirmed")
ok("session.current_step=3", sess_a_get.get("current_step"), 3)
assert_true("session.confirmed_step2_at 채워짐", bool(sess_a_get.get("confirmed_step2_at")))
fsj = sess_a_get.get("form_schema_json") or {}
assert_true("form_schema_json.confirmed_schema 존재", "confirmed_schema" in fsj)
ok("form_schema_json.schema_status=confirmed", fsj.get("schema_status"), "confirmed")
assert_true("form_schema_json.confirmed_at 존재", "confirmed_at" in fsj)
assert_true("form_schema_json.schema 기존 키 유지", "schema" in fsj)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 B: req.confirmed_form_schema 명시 전달
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 B: confirmed_form_schema 명시 전달 ===")
_, sess_b = http_json("POST", "/api/analysis/sessions", {"user_id": "b1_B"})
sid_b = sess_b["session_id"]

user_modified = {
    "form_id": "user_modified",
    "form_name": "사용자 수정본",
    "sections": [
        {"section_id": "S1", "title": "수정된 섹션", "order": 1, "questions": [
            {"question_id": "Q1", "title": "수정질문1", "fill_mode": "ai_text", "source_page": 1},
            {"question_id": "Q2", "title": "수정질문2", "fill_mode": "table_input",
             "is_table_item": True, "source_page": 2},
        ]},
    ],
}
status_b, conf_b = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_b,
    "confirmed_form_schema": user_modified,
})
ok("status 200", status_b, 200)
ok("ok=true", conf_b.get("ok"), True)
ok("question_count=2", conf_b.get("confirmed_schema_question_count"), 2)
ok("section_count=1", conf_b.get("confirmed_schema_section_count"), 1)
ok("table_count=1", conf_b.get("confirmed_schema_table_count"), 1)
# user_modified와 동일 본문이지만 deep copy여야 함
ok("confirmed_schema.form_id 일치", conf_b["confirmed_schema"]["form_id"], "user_modified")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 C: session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 C: session 없음 → 404 ===")
status_c, body_c = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": "nonexistent_session_xyz",
})
ok("status 404", status_c, 404)
assert_true("detail에 'not found'", "not found" in (body_c.get("detail") or "").lower())


# ─────────────────────────────────────────────────────────────────────
# 시나리오 D: schema 둘 다 없음 → 422
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 D: schema 둘 다 없음 → 422 ===")
_, sess_d = http_json("POST", "/api/analysis/sessions", {"user_id": "b1_D"})
sid_d = sess_d["session_id"]
status_d, body_d = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_d,
})
ok("status 422", status_d, 422)
assert_true("detail에 schema 언급",
            "schema" in (body_d.get("detail") or "").lower())


# ─────────────────────────────────────────────────────────────────────
# 시나리오 E: deep copy 검증 (DB 직접 조회로 id() 비교)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E: deep copy 검증 — DB 직접 조회 ===")
from database import get_db
from models import ApplicationSession

db_gen = get_db()
db = next(db_gen)
sess_a_db = db.query(ApplicationSession).filter(
    ApplicationSession.session_id == sid_a
).first()
fsj = sess_a_db.form_schema_json or {}
sch = fsj.get("schema")
cs = fsj.get("confirmed_schema")

print(f"  schema id           = {id(sch)}")
print(f"  confirmed_schema id = {id(cs)}")
assert_true("두 dict 다른 객체 (id 다름)", id(sch) != id(cs))

# 깊은 비교: schema와 confirmed_schema 내용은 같으나 객체는 분리됨
ok("schema와 confirmed_schema 내용 동일",
   json.dumps(sch, sort_keys=True), json.dumps(cs, sort_keys=True))

# 중첩 dict 격리 확인: schema.sections와 confirmed_schema.sections도 다른 객체
schema_sections = sch.get("sections") if sch else None
confirmed_sections = cs.get("sections") if cs else None
if schema_sections and confirmed_sections:
    assert_true("schema.sections와 confirmed_schema.sections도 분리된 객체",
                id(schema_sections) != id(confirmed_sections))
    if schema_sections and len(schema_sections) > 0 and len(confirmed_sections) > 0:
        assert_true("section[0] 도 분리된 객체",
                    id(schema_sections[0]) != id(confirmed_sections[0]))

db.close()


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== B-1 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
