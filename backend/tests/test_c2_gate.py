"""
Part C-2 — step2_confirmed gate 검증 (8개 API).

시나리오 (b8.md §4):
  A: status=analyzing → 8개 API 모두 409
  B: status=step2_confirmed → 8개 API gate 통과 (mock 200 응답)
  C: ALLOW_PRECONFIRM_PRECHECK=true + allow_preconfirm=true → 통과
  D: ALLOW_PRECONFIRM_PRECHECK=false (default) + allow_preconfirm=true → 409
  E: ALLOW_PRECONFIRM_PRECHECK=true + allow_preconfirm=false → 409 (명시 안 함)
  F: session_id 빈 문자열 → 422
  G: session not found → 404
  H: 409 응답 body 형식 검증 (ok=false / reason / session_status / detail)

note: 시나리오 C/D/E는 backend env 변수 변경 + 재시작이 필요.
       이 테스트는 default (ALLOW_PRECONFIRM_PRECHECK=false) 가정으로 작성.
       precheck mode 동작은 별도 backend 재시작 시나리오에서 수동 확인.
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


# 8개 endpoint와 최소 valid body
def endpoints_with_body(sid: str, allow_preconfirm: bool = False):
    common = {"session_id": sid, "allow_preconfirm": allow_preconfirm}
    return [
        ("/api/analysis/extract-evidence",
         {**common, "ref_text": "test"}),
        ("/api/analysis/analyze-company",
         {**common, "company_files": [], "notice_schema": {}}),
        ("/api/analysis/map-evidence",
         {**common, "form_schema": {}, "evidence_list": [], "notice_schema": {}}),
        ("/api/analysis/check-missing",
         {**common, "mapping_result": {}}),
        ("/api/analysis/map-eval-criteria",
         {**common, "notice_schema": {"evaluation_criteria": []},
          "form_schema": {"sections": []}}),
        ("/api/analysis/write-draft-item",
         {**common, "question": {"question_id": "Q1"},
          "matched_evidence": [], "company_schema": {}, "notice_schema": {}}),
        ("/api/analysis/rewrite-draft-item",
         {**common, "question_id": "Q1", "current_draft": "draft",
          "user_message": "msg", "evidence_list": []}),
        ("/api/analysis/approve-draft-item",
         {**common, "question_id": "Q1"}),
    ]


# ─────────────────────────────────────────────────────────────────────
# 시나리오 A: status=analyzing → 8개 모두 409
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 A: status=analyzing → 8개 API 모두 409 ===")
# session 생성 후 DB 직접 조작으로 status="analyzing"
_, sess_a = http_json("POST", "/api/analysis/sessions", {"user_id": "c2_A"})
sid_a = sess_a["session_id"]

from database import get_db
from models import ApplicationSession
db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_a
    ).first()
    s.status = "analyzing"
    db.commit()
finally:
    db.close()

for path, body in endpoints_with_body(sid_a):
    status, resp = http_json("POST", path, body, timeout=60)
    ok(f"A {path} → 409", status, 409)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 H: 409 응답 body 형식 검증
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 H: 409 응답 body 형식 ===")
status_h, body_h = http_json(
    "POST", "/api/analysis/map-evidence",
    {"session_id": sid_a, "form_schema": {}, "evidence_list": [], "notice_schema": {}},
)
detail = body_h.get("detail") or {}
ok("H 409 status", status_h, 409)
ok("H ok=false", detail.get("ok"), False)
ok("H reason=step2_not_confirmed", detail.get("reason"), "step2_not_confirmed")
ok("H session_status=analyzing", detail.get("session_status"), "analyzing")
ok("H session_id 포함", detail.get("session_id"), sid_a)
assert_true("H detail 메시지 존재",
            isinstance(detail.get("detail"), str) and len(detail["detail"]) > 0)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 B: status=step2_confirmed → 8개 API gate 통과 (mock 200)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 B: status=step2_confirmed → 8개 API gate 통과 ===")
# session 생성 후 confirm-step2로 status="step2_confirmed"
_, sess_b = http_json("POST", "/api/analysis/sessions", {"user_id": "c2_B"})
sid_b = sess_b["session_id"]
# confirm-step2로 step2_confirmed 상태로 만들기
user_schema = {
    "form_id": "b", "form_name": "b",
    "sections": [
        {"section_id": "S1", "title": "S1", "order": 1, "questions": [
            {"question_id": "Q1", "title": "회사명", "fill_mode": "ai_text",
             "source_page": 1, "is_required": True}
        ]}
    ]
}
status_conf, conf = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_b,
    "confirmed_form_schema": user_schema,
})
assert_true("B confirm-step2 ok", conf.get("ok") == True)

for path, body in endpoints_with_body(sid_b):
    status, resp = http_json("POST", path, body, timeout=60)
    # mock 응답이 200이거나, mock provider 호출 실패해도 409만 아니면 gate 통과
    # gate 통과 시 mock provider 호출 → 정상 응답 또는 다른 에러
    ok(f"B {path} → not 409 (gate pass)", status != 409, True)
    # 일반적으로 200 또는 mock 결과
    assert_true(f"B {path} → status in [200, 500]",
                status in (200, 500), f"got {status}")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 D: allow_preconfirm=true + env=false (default) → 409
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 D: allow_preconfirm=true + ALLOW_PRECONFIRM_PRECHECK=false → 409 ===")
# 현재 env는 default false (backend 재시작 시 ALLOW_PRECONFIRM_PRECHECK 미설정)
# sid_a는 status=analyzing 상태
for path, body in endpoints_with_body(sid_a, allow_preconfirm=True):
    status, resp = http_json("POST", path, body, timeout=60)
    ok(f"D {path} → 409 (env false이므로 allow_preconfirm 무시)", status, 409)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 F: session_id 빈 문자열 → 422
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 F: session_id 빈 문자열 → 422 ===")
for path, body in endpoints_with_body("", allow_preconfirm=False):
    status, resp = http_json("POST", path, body, timeout=10)
    ok(f"F {path} → 422", status, 422)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 G: session not found → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 G: session not found → 404 ===")
for path, body in endpoints_with_body("nonexistent_c2_session"):
    status, resp = http_json("POST", path, body, timeout=10)
    ok(f"G {path} → 404", status, 404)


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== C-2 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
print("note: 시나리오 C (precheck=true) / E (env=true + allow=false)는 별도 backend 재시작 시나리오에서 수동 확인.")
sys.exit(0 if FAILS == 0 else 1)
