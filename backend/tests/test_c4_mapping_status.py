"""
Part C-4 — GET /sessions/{sid}/mapping-status 검증.

시나리오 (발주문 5개 + 보강):
  1. pipeline running → ready=false, reason=pipeline_status_running
  2. pipeline success + 모든 데이터 → ready=true, next=step3_draft_write
  3. pipeline failed → ready=false, reason=pipeline_status_failed
  4. evaluation_rubric 없음 → ready=false, reason=evaluation_rubric_missing
  5. draft_items 없음 → ready=false, reason=draft_items_missing
  + 추가: pipeline 없음 → pipeline_missing
  + 추가: success인데 evidence_exists=false → evidence_missing
  + 추가: missing_material_exists는 빈 list도 true
  + 추가: session 없음 → 404
  + 추가: gate 미적용 — status=created에서도 200
  + 추가: *_exists 5종 정확한 매핑
"""
import sys
import json
import urllib.request
import urllib.error
import os
import pathlib
from datetime import datetime

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


def get_status(sid):
    return http_json("GET", f"/api/analysis/sessions/{sid}/mapping-status")


def make_session(suffix):
    _, sess = http_json("POST", "/api/analysis/sessions", {"user_id": f"c4_{suffix}"})
    return sess["session_id"]


# DB 직접 조작 helpers
from database import get_db
from models import ApplicationSession
from sqlalchemy.orm.attributes import flag_modified


def set_fsj(sid, fsj_patch):
    """form_schema_json을 patch."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        s = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == sid
        ).first()
        if s is None:
            return
        cur = dict(s.form_schema_json or {})
        cur.update(fsj_patch)
        s.form_schema_json = cur
        flag_modified(s, "form_schema_json")
        db.commit()
    finally:
        db.close()


def set_session_status(sid, status, current_step=None, confirmed_step2_at=None):
    db_gen = get_db()
    db = next(db_gen)
    try:
        s = db.query(ApplicationSession).filter(
            ApplicationSession.session_id == sid
        ).first()
        if s is None:
            return
        s.status = status
        if current_step is not None:
            s.current_step = current_step
        if confirmed_step2_at is not None:
            s.confirmed_step2_at = confirmed_step2_at
        db.commit()
    finally:
        db.close()


# 완전한 ready 상태를 만드는 fixture
def make_ready_session(suffix):
    """pipeline=success + 모든 데이터 갖춘 ready=true session."""
    sid = make_session(suffix)
    set_session_status(sid, "step2_confirmed", current_step=3,
                       confirmed_step2_at=datetime.utcnow())
    full_fsj = {
        "schema": {"sections": []},
        "confirmed_schema": {
            "form_id": "f",
            "sections": [{"section_id": "S1", "questions": [
                {"question_id": "Q1", "title": "Q1", "fill_mode": "ai_text"}
            ]}],
        },
        "schema_status": "confirmed",
        "confirmed_at": datetime.utcnow().isoformat(),
        "draft_items": [{"draft_item_id": "DI_Q1", "question_id": "Q1"}],
        "draft_items_status": "initialized",
        "evaluation_rubric": {
            "source": "default_template",
            "template_type": "general",
            "axes": [
                {"axis_id": "a1", "name": "a1", "weight": 50, "is_scored": True},
                {"axis_id": "a2", "name": "a2", "weight": 50, "is_scored": True},
            ],
        },
        "mapping_pipeline": {
            "status": "success",
            "started_at": "2026-05-15T17:00:00",
            "completed_at": "2026-05-15T17:00:05",
            "steps": {
                "analyze_company": "done",
                "extract_evidence": "done",
                "map_evidence": "done",
                "map_eval_criteria": "done",
                "check_missing": "done",
            },
            "failed_step": None,
            "error_message": None,
            "results": {
                "analyze_company": {"company": {"name": "test"}},
                "extract_evidence": [{"evidence_id": "ev1"}],
                "map_evidence": {"question_mappings": []},
                "map_eval_criteria": {"mappings": []},
                "check_missing": [{"missing_id": "m1"}],
            },
        },
    }
    set_fsj(sid, full_fsj)
    return sid


# ─────────────────────────────────────────────────────────────────────
# 시나리오 2: 모든 데이터 → ready=true
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 2: success + 모든 데이터 → ready=true ===")
sid_2 = make_ready_session("2")
status_2, body_2 = get_status(sid_2)
ok("2 status 200", status_2, 200)
ok("2 ok=true", body_2.get("ok"), True)
ok("2 mapping_ready=true", body_2.get("mapping_ready"), True)
ok("2 next_step=step3_draft_write", body_2.get("next_step"), "step3_draft_write")
ok("2 company_analysis_exists", body_2.get("company_analysis_exists"), True)
ok("2 evidence_exists", body_2.get("evidence_exists"), True)
ok("2 mapping_result_exists", body_2.get("mapping_result_exists"), True)
ok("2 missing_material_exists", body_2.get("missing_material_exists"), True)
ok("2 evaluation_rubric_exists", body_2.get("evaluation_rubric_exists"), True)
ok("2 not_ready_reasons=[]", body_2.get("not_ready_reasons"), [])


# ─────────────────────────────────────────────────────────────────────
# 시나리오 1: pipeline running → ready=false
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 1: pipeline running → ready=false ===")
sid_1 = make_ready_session("1")
set_fsj(sid_1, {"mapping_pipeline": {
    "status": "running", "steps": {}, "results": {},
    "failed_step": None, "error_message": None,
}})
_, body_1 = get_status(sid_1)
ok("1 mapping_ready=false", body_1.get("mapping_ready"), False)
ok("1 next_step=wait_for_mapping", body_1.get("next_step"), "wait_for_mapping")
assert_true("1 reasons에 pipeline_status_running",
            "pipeline_status_running" in body_1.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 3: pipeline failed → ready=false
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 3: pipeline failed → ready=false ===")
sid_3 = make_ready_session("3")
set_fsj(sid_3, {"mapping_pipeline": {
    "status": "failed", "steps": {"analyze_company": "failed"},
    "failed_step": "analyze_company", "error_message": "test",
    "results": {},
}})
_, body_3 = get_status(sid_3)
ok("3 mapping_ready=false", body_3.get("mapping_ready"), False)
assert_true("3 reasons에 pipeline_status_failed",
            "pipeline_status_failed" in body_3.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 4: evaluation_rubric 없음 → ready=false
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 4: evaluation_rubric 없음 → ready=false ===")
sid_4 = make_ready_session("4")
# evaluation_rubric을 빈 dict로 (axes 없음)
set_fsj(sid_4, {"evaluation_rubric": {}})
_, body_4 = get_status(sid_4)
ok("4 mapping_ready=false", body_4.get("mapping_ready"), False)
ok("4 evaluation_rubric_exists=false", body_4.get("evaluation_rubric_exists"), False)
assert_true("4 reasons에 evaluation_rubric_missing",
            "evaluation_rubric_missing" in body_4.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 시나리오 5: draft_items 없음 → ready=false
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 5: draft_items 없음 → ready=false ===")
sid_5 = make_ready_session("5")
set_fsj(sid_5, {"draft_items": []})
_, body_5 = get_status(sid_5)
ok("5 mapping_ready=false", body_5.get("mapping_ready"), False)
assert_true("5 reasons에 draft_items_missing",
            "draft_items_missing" in body_5.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 6: pipeline 자체가 없음 → pipeline_missing
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가 6: pipeline 없음 → pipeline_missing ===")
sid_6 = make_session("6")
set_session_status(sid_6, "step2_confirmed", current_step=3,
                   confirmed_step2_at=datetime.utcnow())
_, body_6 = get_status(sid_6)
ok("6 mapping_ready=false", body_6.get("mapping_ready"), False)
assert_true("6 reasons에 pipeline_missing",
            "pipeline_missing" in body_6.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 7: success인데 evidence_exists=false → evidence_missing
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가 7: success + extract_evidence 결과 없음 → evidence_missing ===")
sid_7 = make_ready_session("7")
# results.extract_evidence를 빈 list로 (success인데 빈 결과)
fsj_7_patch = {
    "mapping_pipeline": {
        "status": "success",
        "steps": {s: "done" for s in (
            "analyze_company", "extract_evidence", "map_evidence",
            "map_eval_criteria", "check_missing"
        )},
        "failed_step": None,
        "error_message": None,
        "results": {
            "analyze_company": {"company": {"name": "x"}},
            "extract_evidence": [],  # 빈 list → exists=false (보강 #1 명시)
            "map_evidence": {"question_mappings": []},
            "map_eval_criteria": {"mappings": []},
            "check_missing": [],
        },
    }
}
set_fsj(sid_7, fsj_7_patch)
_, body_7 = get_status(sid_7)
ok("7 evidence_exists=false (빈 list)", body_7.get("evidence_exists"), False)
ok("7 missing_material_exists=true (빈 list, is not None)",
   body_7.get("missing_material_exists"), True)
assert_true("7 reasons에 evidence_missing",
            "evidence_missing" in body_7.get("not_ready_reasons", []))
assert_true("7 reasons에 check_missing_not_completed 없음 (빈 list = 유효)",
            "check_missing_not_completed" not in body_7.get("not_ready_reasons", []))
ok("7 mapping_ready=false", body_7.get("mapping_ready"), False)


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 8: missing_material None → check_missing_not_completed
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가 8: missing_material is None → check_missing_not_completed ===")
sid_8 = make_ready_session("8")
set_fsj(sid_8, {"mapping_pipeline": {
    "status": "success",
    "steps": {s: "done" for s in (
        "analyze_company", "extract_evidence", "map_evidence",
        "map_eval_criteria",
    )},
    "results": {
        "analyze_company": {"company": {"name": "x"}},
        "extract_evidence": [{"evidence_id": "ev1"}],
        "map_evidence": {"question_mappings": []},
        "map_eval_criteria": {"mappings": []},
        "check_missing": None,  # None → exists=false
    },
    "failed_step": None,
    "error_message": None,
}})
_, body_8 = get_status(sid_8)
ok("8 missing_material_exists=false (None)",
   body_8.get("missing_material_exists"), False)
assert_true("8 reasons에 check_missing_not_completed",
            "check_missing_not_completed" in body_8.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 9: session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가 9: session 없음 → 404 ===")
status_9, _ = get_status("nonexistent_c4")
ok("9 status 404", status_9, 404)


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 10: gate 미적용 — status=created에서도 200
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가 10: gate 미적용 — status=created → 200, ready=false ===")
sid_10 = make_session("10")
# status는 그대로 "created"
status_10, body_10 = get_status(sid_10)
ok("10 status 200 (gate 미적용)", status_10, 200)
ok("10 mapping_ready=false", body_10.get("mapping_ready"), False)
# pipeline 없으므로 pipeline_missing + 다른 reasons
assert_true("10 reasons에 pipeline_missing",
            "pipeline_missing" in body_10.get("not_ready_reasons", []))
assert_true("10 reasons에 confirmed_schema_missing",
            "confirmed_schema_missing" in body_10.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 11: confirmed_schema 없음 → confirmed_schema_missing
# ─────────────────────────────────────────────────────────────────────
print("\n=== 추가 11: confirmed_schema 없음 → confirmed_schema_missing ===")
sid_11 = make_ready_session("11")
set_fsj(sid_11, {"confirmed_schema": None})
_, body_11 = get_status(sid_11)
ok("11 mapping_ready=false", body_11.get("mapping_ready"), False)
assert_true("11 reasons에 confirmed_schema_missing",
            "confirmed_schema_missing" in body_11.get("not_ready_reasons", []))


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== C-4 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
