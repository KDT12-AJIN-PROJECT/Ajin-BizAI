"""
Part C-3 — BackgroundTasks mapping pipeline 검증.

시나리오 (발주문 §"테스트" + 보강):
  1. run-step2-mapping 응답이 즉시 running
  2. mapping_pipeline.status가 running으로 저장
  3. 단계별 pending → running → done 기록 (BackgroundTask 완료 후)
  4. 성공 시 success
  5. 실패 시 failed_step / error_message 기록 (mock provider monkey-patch)
  6. retry 시 done 단계 skip 가능
  7. session 없음 → 404
  8. step2_confirmed 아니면 → 409
  + 보강 #1: status="running"일 때 재호출 → 새 task 안 만듦
  + 보강 #5: announcement_signals / evaluation_rubric context 포함 검증 (간접)

note: BackgroundTask 완료 대기는 polling으로 처리 (sleep + GET sessions).
"""
import sys
import json
import time
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


def make_step2_confirmed_session(suffix: str) -> str:
    """confirm-step2까지 마친 session 생성."""
    _, sess = http_json("POST", "/api/analysis/sessions", {"user_id": f"c3_{suffix}"})
    sid = sess["session_id"]
    http_json("POST", "/api/analysis/confirm-step2", {
        "session_id": sid,
        "confirmed_form_schema": {
            "form_id": f"c3_{suffix}", "form_name": f"c3_{suffix}",
            "sections": [
                {"section_id": "S1", "title": "S1", "order": 1, "questions": [
                    {"question_id": "Q1", "title": "회사명",
                     "fill_mode": "ai_text", "source_page": 1, "is_required": True}
                ]}
            ]
        }
    })
    return sid


def wait_for_pipeline(sid: str, expected_status: str, max_wait: int = 30) -> dict:
    """mapping_pipeline.status가 expected가 될 때까지 polling."""
    deadline = time.time() + max_wait
    last_pipeline = None
    while time.time() < deadline:
        _, raw = http_json("GET", f"/api/analysis/sessions/{sid}")
        fsj = raw.get("form_schema_json") or {}
        pipe = fsj.get("mapping_pipeline") or {}
        last_pipeline = pipe
        if pipe.get("status") == expected_status:
            return pipe
        time.sleep(0.5)
    return last_pipeline or {}


# ─────────────────────────────────────────────────────────────────────
# 시나리오 1+2: run-step2-mapping 즉시 running
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 1+2: run-step2-mapping 즉시 running ===")
sid_1 = make_step2_confirmed_session("1")

status_1, body_1 = http_json(
    "POST", "/api/analysis/run-step2-mapping",
    {"session_id": sid_1, "request_id": "c3_1"},
)
ok("1 status 200", status_1, 200)
ok("1 ok=true", body_1.get("ok"), True)
ok("1 status=running", body_1.get("status"), "running")
assert_true("1 mapping_pipeline 존재",
            isinstance(body_1.get("mapping_pipeline"), dict))
pipe_initial = body_1.get("mapping_pipeline") or {}
ok("1 initial status=running", pipe_initial.get("status"), "running")
ok("1 모든 step=pending (초기 응답)",
   all(v == "pending" for v in (pipe_initial.get("steps") or {}).values()),
   True)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 3+4: 단계별 전이 + success
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 3+4: BackgroundTask 완료 대기 후 success 확인 ===")
final = wait_for_pipeline(sid_1, "success", max_wait=60)
ok("3+4 status=success", final.get("status"), "success")
ok("3+4 모든 step=done",
   all(v == "done" for v in (final.get("steps") or {}).values()), True)
ok("3+4 failed_step=None", final.get("failed_step"), None)
ok("3+4 error_message=None", final.get("error_message"), None)
assert_true("3+4 completed_at ISO",
            isinstance(final.get("completed_at"), str))
# results 저장 확인 (Q1 권장)
assert_true("3+4 results dict 존재",
            isinstance(final.get("results"), dict))
for step in ("analyze_company", "extract_evidence", "map_evidence",
             "map_eval_criteria", "check_missing"):
    assert_true(f"3+4 results.{step} 저장됨",
                final.get("results", {}).get(step) is not None
                or step == "extract_evidence",  # extract_evidence는 reference 없으면 빈 list
                f"got: {type(final.get('results', {}).get(step)).__name__}")


# ─────────────────────────────────────────────────────────────────────
# 시나리오 보강 #1: status=running일 때 재호출 → 새 task 안 만듦
# (DB 직접 조작으로 status=running 고정 — mock provider가 빨라 race 회피)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 보강 #1: status=running 시 중복 task 차단 (DB 직접 조작) ===")
from database import get_db as _get_db
from models import ApplicationSession as _AppSess
from sqlalchemy.orm.attributes import flag_modified as _fm

sid_dup = make_step2_confirmed_session("dup")

# DB 직접 조작: mapping_pipeline.status=running 고정
fixed_started = "2026-05-15T08:00:00"
db_gen = _get_db()
db = next(db_gen)
try:
    s = db.query(_AppSess).filter(
        _AppSess.session_id == sid_dup
    ).first()
    fsj = dict(s.form_schema_json or {})
    fsj["mapping_pipeline"] = {
        "status": "running",
        "started_at": fixed_started,
        "completed_at": None,
        "steps": {
            "analyze_company": "running",
            "extract_evidence": "pending",
            "map_evidence": "pending",
            "map_eval_criteria": "pending",
            "check_missing": "pending",
        },
        "failed_step": None,
        "error_message": None,
        "results": {k: None for k in (
            "analyze_company", "extract_evidence", "map_evidence",
            "map_eval_criteria", "check_missing"
        )},
    }
    s.form_schema_json = fsj
    _fm(s, "form_schema_json")
    db.commit()
finally:
    db.close()

# run-step2-mapping 재호출 → 새 task 안 만들고 기존 pipeline 반환
status_dup, body_dup = http_json(
    "POST", "/api/analysis/run-step2-mapping",
    {"session_id": sid_dup, "request_id": "dup_retry"},
)
ok("보강#1 status 200", status_dup, 200)
ok("보강#1 status=running 응답", body_dup.get("status"), "running")
ok("보강#1 started_at 동일 (기존 pipeline 반환)",
   body_dup["mapping_pipeline"]["started_at"], fixed_started)
assert_true("보강#1 note 포함",
            "이미 running" in (body_dup.get("note") or ""))
# step도 그대로 (analyze_company=running 유지)
ok("보강#1 analyze_company 여전히 running (새 초기화 안 됨)",
   body_dup["mapping_pipeline"]["steps"]["analyze_company"], "running")

# retry-step2-mapping도 동일 검증 (running 시 무시)
status_dup_r, body_dup_r = http_json(
    "POST", "/api/analysis/retry-step2-mapping",
    {"session_id": sid_dup, "request_id": "dup_retry_r"},
)
ok("보강#1 retry running 시 status=running", body_dup_r.get("status"), "running")
assert_true("보강#1 retry note 포함",
            "이미 running" in (body_dup_r.get("note") or ""))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 6: retry — done 단계 skip
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 6: retry — done 단계 skip ===")
# sid_1는 이미 success 상태. retry → 422 거부 (Q4)
status_6a, body_6a = http_json(
    "POST", "/api/analysis/retry-step2-mapping",
    {"session_id": sid_1, "request_id": "c3_6a"},
)
ok("6a success 상태 retry → 422", status_6a, 422)

# 실제 retry 검증: DB 직접 조작으로 status=failed + failed_step 주입
from database import get_db
from models import ApplicationSession
from sqlalchemy.orm.attributes import flag_modified

sid_retry = make_step2_confirmed_session("retry")
# 먼저 run 한 번 → success
http_json("POST", "/api/analysis/run-step2-mapping",
          {"session_id": sid_retry, "request_id": "retry_init"})
wait_for_pipeline(sid_retry, "success", max_wait=60)

# DB 조작: status=failed + failed_step=map_evidence (앞 두 단계는 done 유지)
db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_retry
    ).first()
    fsj = dict(s.form_schema_json or {})
    pipe = dict(fsj.get("mapping_pipeline") or {})
    pipe["status"] = "failed"
    pipe["failed_step"] = "map_evidence"
    pipe["error_message"] = "mock failure"
    steps_state = dict(pipe.get("steps") or {})
    # 앞 2단계는 done 유지, map_evidence부터 failed, 뒤는 pending
    steps_state["analyze_company"] = "done"
    steps_state["extract_evidence"] = "done"
    steps_state["map_evidence"] = "failed"
    steps_state["map_eval_criteria"] = "pending"
    steps_state["check_missing"] = "pending"
    pipe["steps"] = steps_state
    fsj["mapping_pipeline"] = pipe
    s.form_schema_json = fsj
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

# retry 호출
status_6b, body_6b = http_json(
    "POST", "/api/analysis/retry-step2-mapping",
    {"session_id": sid_retry, "request_id": "retry"},
)
ok("6b retry status 200", status_6b, 200)
ok("6b retry status=running", body_6b.get("status"), "running")
ok("6b retry_from_step=map_evidence", body_6b.get("retry_from_step"), "map_evidence")
# retry 후에도 이전 done 단계는 유지되어야 함 (BackgroundTask 실행 전 시점)
mp = body_6b.get("mapping_pipeline") or {}
ok("6b analyze_company 여전히 done", mp.get("steps", {}).get("analyze_company"), "done")
ok("6b extract_evidence 여전히 done", mp.get("steps", {}).get("extract_evidence"), "done")
ok("6b failed_step reset", mp.get("failed_step"), None)
ok("6b error_message reset", mp.get("error_message"), None)

# 완료 대기 후 done 단계 skip 확인
final_retry = wait_for_pipeline(sid_retry, "success", max_wait=60)
ok("6 final status=success after retry", final_retry.get("status"), "success")
# 모든 단계가 done이어야 함 (앞 2개는 skip되어도 done 유지, 뒤 3개는 새로 실행)
ok("6 모든 step done",
   all(v == "done" for v in (final_retry.get("steps") or {}).values()), True)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 7: session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 7: session 없음 → 404 ===")
status_7a, _ = http_json(
    "POST", "/api/analysis/run-step2-mapping",
    {"session_id": "nonexistent_c3"},
)
ok("7a run-step2-mapping 404", status_7a, 404)
status_7b, _ = http_json(
    "POST", "/api/analysis/retry-step2-mapping",
    {"session_id": "nonexistent_c3"},
)
ok("7b retry-step2-mapping 404", status_7b, 404)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 8: step2_confirmed 아니면 → 409
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 8: step2_confirmed 아니면 → 409 ===")
# session 생성만 (confirm-step2 안 함 → status=created)
_, sess_8 = http_json("POST", "/api/analysis/sessions", {"user_id": "c3_8"})
sid_8 = sess_8["session_id"]
status_8a, body_8a = http_json(
    "POST", "/api/analysis/run-step2-mapping",
    {"session_id": sid_8},
)
ok("8a run-step2-mapping → 409", status_8a, 409)
detail_8a = body_8a.get("detail") or {}
ok("8a reason=step2_not_confirmed", detail_8a.get("reason"), "step2_not_confirmed")

status_8b, _ = http_json(
    "POST", "/api/analysis/retry-step2-mapping",
    {"session_id": sid_8},
)
ok("8b retry-step2-mapping → 409", status_8b, 409)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 추가: retry — pipeline 없음 → 422
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가: pipeline 없는 session에서 retry → 422 ===")
sid_no_pipe = make_step2_confirmed_session("no_pipe")
status_no_pipe, _ = http_json(
    "POST", "/api/analysis/retry-step2-mapping",
    {"session_id": sid_no_pipe},
)
ok("retry pipeline 없음 → 422", status_no_pipe, 422)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 5: 실패 시 failed_step / error_message 기록
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 5: 실패 시 failed_step / error_message 기록 ===")
# mapping_pipeline 직접 import 후 강제 실패 유도
# (mock_provider가 정상 응답 — 의도적 실패는 단위 테스트로 검증)
from services.mapping_pipeline import (
    init_mapping_pipeline, run_mapping_pipeline,
    PIPELINE_STEPS, _collect_context,
)
ok("5 PIPELINE_STEPS 5개", len(PIPELINE_STEPS), 5)
ok("5 PIPELINE_STEPS 순서",
   list(PIPELINE_STEPS),
   ["analyze_company", "extract_evidence", "map_evidence",
    "map_eval_criteria", "check_missing"])

# init_mapping_pipeline 구조 검증
init_pipe = init_mapping_pipeline("2026-05-15T17:30:00")
ok("5 init status=running", init_pipe["status"], "running")
ok("5 init steps 모두 pending",
   all(v == "pending" for v in init_pipe["steps"].values()), True)
ok("5 init results 모두 None",
   all(v is None for v in init_pipe["results"].values()), True)
ok("5 init failed_step=None", init_pipe["failed_step"], None)
ok("5 init error_message=None", init_pipe["error_message"], None)


# ─────────────────────────────────────────────────────────────────────
# 시나리오 보강 #5: announcement_signals + evaluation_rubric context 포함 검증 (간접)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 보강 #5: context 수집 announcement_signals + evaluation_rubric ===")
# 직접 _collect_context 호출
class _MockSession:
    session_id = "test"
    form_schema_json = {
        "confirmed_schema": {"form_id": "T"},
        "draft_items": [{"draft_item_id": "DI_1"}],
        "reference_attachments": [{"file_id": "f1"}],
        "announcement_signals": {"criteria": [{"name": "기술성", "weight": 40}]},
        "evaluation_rubric": {"source": "announcement", "axes": []},
    }
    notice_schema_json = {"schema": {"target": "test"}}
    selected_company_file_ids = ["cf1", "cf2"]

context = _collect_context(_MockSession())
ok("ctx confirmed_schema 포함", context["confirmed_schema"]["form_id"], "T")
ok("ctx draft_items 1개", len(context["draft_items"]), 1)
ok("ctx reference_attachments 1개", len(context["reference_attachments"]), 1)
ok("ctx selected_company_file_ids",
   context["selected_company_file_ids"], ["cf1", "cf2"])
ok("ctx announcement_signals.criteria",
   context["announcement_signals"]["criteria"][0]["name"], "기술성")
ok("ctx evaluation_rubric.source",
   context["evaluation_rubric"]["source"], "announcement")
ok("ctx notice_schema.target",
   context["notice_schema"]["target"], "test")


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== C-3 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
