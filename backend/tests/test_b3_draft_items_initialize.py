"""
Part B-3 — confirmed_schema → DraftItem skeleton 생성 검증.

시나리오 (b6_b3.md §8):
  A: 정상 confirmed_schema → draft_items 생성 + count 검증
  B: table_input — table_draft.columns 보존 (다단헤더 11컬럼 시나리오)
  C: Step 2 미확정 → reason=step2_not_confirmed
  D: confirmed_schema 없음 → reason=confirmed_schema_missing
  E: idempotency — 2회 호출 시 중복 없음
  F: 기존 draft_text 보존 — DB 직접 조작 후 재호출
  G: GET 조회 endpoint — 저장된 draft_items 반환
  H: metadata 보존 — confirmed_schema / parser_metadata / quality_metrics 손실 없음
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

# .env 로드
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


def make_confirmed_session(user_id_suffix: str) -> tuple[str, dict]:
    """B-1 confirm-step2까지 마친 session을 만들어 반환."""
    _, sess = http_json("POST", "/api/analysis/sessions", {"user_id": f"b3_{user_id_suffix}"})
    sid = sess["session_id"]
    user_schema = {
        "form_id": f"b3_{user_id_suffix}", "form_name": f"b3_{user_id_suffix}",
        "sections": [
            {"section_id": "S1", "title": "기본정보", "order": 1, "questions": [
                {"question_id": "Q1", "title": "회사명",
                 "requirement": "회사명을 입력하세요",
                 "fill_mode": "ai_text", "source_page": 1,
                 "is_required": True,
                 "required_evidence_types": ["company_basic"]},
                {"question_id": "Q2", "title": "대표자",
                 "fill_mode": "profile_mapping", "source_page": 2,
                 "is_required": True},
            ]},
            {"section_id": "S2", "title": "사업비", "order": 2, "questions": [
                {"question_id": "Q3", "title": "사업비 총괄표",
                 "requirement": "사업비를 입력하세요",
                 "fill_mode": "table_input", "source_page": 34,
                 "is_required": True, "is_table_item": True,
                 "table_schema": {
                     "table_id": "T1", "row_count": 8, "col_count": 11,
                     "columns": [
                         {"name": "구 분", "header_path": ["구 분"]},
                         {"name": "금 액", "header_path": ["정부지원금", "금 액"]},
                         {"name": "%", "header_path": ["정부지원금", "%"]},
                         {"name": "금 액", "header_path": ["기관부담금", "현금", "금 액"]},
                         {"name": "%", "header_path": ["기관부담금", "현금", "%"]},
                         {"name": "금 액", "header_path": ["기관부담금", "현물", "금 액"]},
                         {"name": "%", "header_path": ["기관부담금", "현물", "%"]},
                         {"name": "금 액", "header_path": ["기관부담금", "소계", "금 액"]},
                         {"name": "%", "header_path": ["기관부담금", "소계", "%"]},
                         {"name": "금 액", "header_path": ["합 계", "금 액"]},
                         {"name": "%", "header_path": ["합 계", "%"]},
                     ],
                     "bbox": [60, 220, 537, 395],
                     "header_row_count": 3,
                 }},
            ]},
        ],
    }
    _, conf = http_json("POST", "/api/analysis/confirm-step2", {
        "session_id": sid,
        "confirmed_form_schema": user_schema,
    })
    assert conf.get("ok") is True, f"confirm-step2 failed: {conf}"
    return sid, user_schema


# ─────────────────────────────────────────────────────────────────────
# A: 정상 confirmed_schema → draft_items 생성
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 A: 정상 confirmed_schema → 3개 draft_items 생성 ===")
sid_a, schema_a = make_confirmed_session("A")

status_a, init_a = http_json(
    "POST", f"/api/analysis/sessions/{sid_a}/draft-items/initialize",
    body={"request_id": "b3_A_init"},
)
ok("status 200", status_a, 200)
ok("ok=true", init_a.get("ok"), True)
ok("draft_items_status=initialized", init_a.get("draft_items_status"), "initialized")
ok("draft_item_count=3", init_a.get("draft_item_count"), 3)
ok("text_draft_item_count=2", init_a.get("text_draft_item_count"), 2)
ok("table_draft_item_count=1", init_a.get("table_draft_item_count"), 1)
ok("next_step=step3_draft_write", init_a.get("next_step"), "step3_draft_write")

items_a = init_a.get("draft_items") or []
qids = {i.get("question_id") for i in items_a}
ok("question_id 3개 모두 포함", qids, {"Q1", "Q2", "Q3"})

# 필수 필드 검증
q1 = next(i for i in items_a if i["question_id"] == "Q1")
ok("Q1.draft_item_id=DI_Q1", q1["draft_item_id"], "DI_Q1")
ok("Q1.section_id=S1", q1["section_id"], "S1")
ok("Q1.fill_mode=ai_text", q1["fill_mode"], "ai_text")
ok("Q1.status=empty", q1["status"], "empty")
ok("Q1.draft_text=''", q1["draft_text"], "")
ok("Q1.table_draft=None", q1["table_draft"], None)
ok("Q1.created_from=confirmed_schema", q1["created_from"], "confirmed_schema")
ok("Q1.source_page=1", q1["source_page"], 1)
ok("Q1.question_title=회사명", q1["question_title"], "회사명")
ok("Q1.required_evidence_type=['company_basic']",
   q1["required_evidence_type"], ["company_basic"])

q2 = next(i for i in items_a if i["question_id"] == "Q2")
ok("Q2.fill_mode=profile_mapping (실제 정보 삽입 안 됨)",
   q2["fill_mode"], "profile_mapping")
ok("Q2.draft_text=''", q2["draft_text"], "")
ok("Q2.matched_evidence_ids=[]", q2["matched_evidence_ids"], [])
ok("Q2.missing_material_ids=[]", q2["missing_material_ids"], [])


# ─────────────────────────────────────────────────────────────────────
# B: table_input — table_draft.columns 보존 (다단헤더 11컬럼)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 B: table_input table_draft 검증 ===")
q3 = next(i for i in items_a if i["question_id"] == "Q3")
td = q3.get("table_draft")
assert_true("Q3.table_draft is dict", isinstance(td, dict))
ok("Q3.table_draft.source=table_schema", td["source"], "table_schema")
ok("Q3.table_draft.rows=[]", td["rows"], [])
ok("Q3.table_draft.columns 11개 보존", len(td["columns"]), 11)
# header_path 다단헤더 보존
col4_path = td["columns"][3]["header_path"]
ok("Q3 col4 다단헤더 ['기관부담금','현금','금 액'] 보존",
   col4_path, ["기관부담금", "현금", "금 액"])
ok("Q3.fill_mode=table_input", q3["fill_mode"], "table_input")
ok("Q3.status=empty", q3["status"], "empty")


# ─────────────────────────────────────────────────────────────────────
# C: Step 2 미확정 → reason=step2_not_confirmed
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 C: Step 2 미확정 ===")
_, sess_c = http_json("POST", "/api/analysis/sessions", {"user_id": "b3_C"})
sid_c = sess_c["session_id"]
status_c, init_c = http_json(
    "POST", f"/api/analysis/sessions/{sid_c}/draft-items/initialize", body={},
)
ok("status 200", status_c, 200)
ok("ok=false", init_c.get("ok"), False)
ok("step3_ready=false", init_c.get("step3_ready"), False)
ok("reason=step2_not_confirmed", init_c.get("reason"), "step2_not_confirmed")


# ─────────────────────────────────────────────────────────────────────
# D: confirmed_schema 없음 (DB 직접 조작)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 D: confirmed_schema 없음 ===")
from database import get_db
from models import ApplicationSession
from sqlalchemy.orm.attributes import flag_modified

_, sess_d = http_json("POST", "/api/analysis/sessions", {"user_id": "b3_D"})
sid_d = sess_d["session_id"]
db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_d
    ).first()
    s.status = "step2_confirmed"
    s.current_step = 3
    s.confirmed_step2_at = datetime.utcnow()
    s.form_schema_json = {"schema_status": "confirmed"}  # confirmed_schema 없음
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

status_d, init_d = http_json(
    "POST", f"/api/analysis/sessions/{sid_d}/draft-items/initialize", body={},
)
ok("reason=confirmed_schema_missing",
   init_d.get("reason"), "confirmed_schema_missing")


# ─────────────────────────────────────────────────────────────────────
# E: idempotency — 2회 호출 시 중복 없음
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E: idempotency 2회 호출 ===")
sid_e, _ = make_confirmed_session("E")
_, init_e1 = http_json(
    "POST", f"/api/analysis/sessions/{sid_e}/draft-items/initialize", body={},
)
ok("E 1회차 draft_item_count=3", init_e1.get("draft_item_count"), 3)
_, init_e2 = http_json(
    "POST", f"/api/analysis/sessions/{sid_e}/draft-items/initialize", body={},
)
ok("E 2회차 draft_item_count=3 (중복 증가 없음)",
   init_e2.get("draft_item_count"), 3)
# 같은 question_id 중복 없음
qids_e2 = [i.get("question_id") for i in init_e2.get("draft_items", [])]
ok("E 2회차 unique qid 수=3", len(set(qids_e2)), 3)


# ─────────────────────────────────────────────────────────────────────
# F: 기존 draft_text 보존 (DB 직접 조작 후 재호출)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 F: 기존 draft_text 보존 ===")
sid_f, _ = make_confirmed_session("F")
# 1회차 initialize
_, init_f1 = http_json(
    "POST", f"/api/analysis/sessions/{sid_f}/draft-items/initialize", body={},
)
assert init_f1.get("draft_item_count") == 3

# DB 직접 조작: Q1의 draft_text에 사용자 작성 내용 주입
db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid_f
    ).first()
    fsj = dict(s.form_schema_json or {})
    items = fsj.get("draft_items") or []
    for it in items:
        if it["question_id"] == "Q1":
            it["draft_text"] = "사용자가 작성한 본문"
            it["status"] = "draft"
            it["updated_at"] = "2026-05-14T10:00:00"
            user_created_at = it.get("created_at")
            break
    fsj["draft_items"] = items
    s.form_schema_json = fsj
    flag_modified(s, "form_schema_json")
    db.commit()
finally:
    db.close()

# 2회차 initialize 호출
_, init_f2 = http_json(
    "POST", f"/api/analysis/sessions/{sid_f}/draft-items/initialize", body={},
)
items_f2 = init_f2.get("draft_items", [])
q1_f = next(i for i in items_f2 if i["question_id"] == "Q1")
ok("F Q1.draft_text 보존", q1_f.get("draft_text"), "사용자가 작성한 본문")
ok("F Q1.status 보존 (draft)", q1_f.get("status"), "draft")
ok("F Q1.updated_at 보존 (2026-05-14T10:00:00)",
   q1_f.get("updated_at"), "2026-05-14T10:00:00")


# ─────────────────────────────────────────────────────────────────────
# G: GET 조회 endpoint — 저장된 draft_items 반환
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 G: GET /draft-items/{sid} 조회 ===")
status_g, get_g = http_json("GET", f"/api/analysis/draft-items/{sid_a}")
ok("status 200", status_g, 200)
ok("ok=true", get_g.get("ok"), True)
ok("draft_items_status=initialized", get_g.get("draft_items_status"), "initialized")
ok("draft_item_count=3", get_g.get("draft_item_count"), 3)
assert_true("draft_items 본문 포함 (mock empty 아님)",
            len(get_g.get("draft_items") or []) == 3)
# 이전 mock의 _note 필드 제거 확인
assert_true("_note 제거됨", "_note" not in get_g)
# initialize 미수행 session 조회
status_g_uninit, get_g_uninit = http_json(
    "GET", f"/api/analysis/draft-items/{sid_c}",
)
ok("uninit session: draft_items_status=uninitialized",
   get_g_uninit.get("draft_items_status"), "uninitialized")
ok("uninit session: draft_item_count=0", get_g_uninit.get("draft_item_count"), 0)

# session 없음
status_g_404, body_g_404 = http_json(
    "GET", "/api/analysis/draft-items/nonexistent_b3_g",
)
ok("session 없음 → 404", status_g_404, 404)


# ─────────────────────────────────────────────────────────────────────
# H: metadata 보존
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 H: confirmed_schema / parser_metadata / quality_metrics 보존 ===")
# sid_a는 시나리오 A에서 initialize까지 완료된 session
_, step3_ready_a = http_json(
    "GET", f"/api/analysis/sessions/{sid_a}/step3-ready",
)
assert_true("step3_ready=true (initialize 후에도 유지)",
            step3_ready_a.get("step3_ready") is True)
ok("confirmed_schema 존재", "confirmed_schema" in step3_ready_a, True)
ok("parser_metadata 존재", "parser_metadata" in step3_ready_a, True)
ok("quality_metrics 존재", "quality_metrics" in step3_ready_a, True)

# session 직접 조회로 form_schema_json 전체 키 확인
_, raw_a = http_json("GET", f"/api/analysis/sessions/{sid_a}")
fsj_keys = set((raw_a.get("form_schema_json") or {}).keys())
expected_keys = {"confirmed_schema", "schema_status", "confirmed_at",
                 "draft_items", "draft_items_status", "draft_items_initialized_at"}
assert_true("기존 + B-3 신규 key 모두 보존",
            expected_keys.issubset(fsj_keys),
            f"missing: {expected_keys - fsj_keys}")
# 시나리오 A는 parse-form 미호출 → schema 키 부재 정상.
# 실제 parse-form 거친 session에서도 schema 보존되는지는 별도 시나리오 J로 검증.

# ─────────────────────────────────────────────────────────────────────
# J: parse-form 거친 session에서 schema 키 보존 확인
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 J: parse-form 거친 session schema 키 보존 ===")
_, sess_j = http_json("POST", "/api/analysis/sessions", {"user_id": "b3_J"})
sid_j = sess_j["session_id"]
# parse-form으로 schema 저장
_, parse_j = http_json("POST", "/api/analysis/parse-form", {
    "form_text": "=== PAGE 1 ===\nQ1 회사명\n=== PAGE 2 ===\nQ2 대표자",
    "form_name": "b3_J.pdf",
    "session_id": sid_j,
    "request_id": "b3_J_parse",
}, timeout=180)
# confirm-step2 (req.confirmed_form_schema 없음 → schema fallback)
_, conf_j = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid_j,
})
# initialize
_, init_j = http_json(
    "POST", f"/api/analysis/sessions/{sid_j}/draft-items/initialize", body={},
)
ok("J initialize ok", init_j.get("ok"), True)
# raw 조회 → schema 키 확인
_, raw_j = http_json("GET", f"/api/analysis/sessions/{sid_j}")
fsj_keys_j = set((raw_j.get("form_schema_json") or {}).keys())
assert_true("J: schema 키 보존 (parse-form 결과)",
            "schema" in fsj_keys_j)
assert_true("J: confirmed_schema 키 보존",
            "confirmed_schema" in fsj_keys_j)
assert_true("J: draft_items 키 추가",
            "draft_items" in fsj_keys_j)


# ─────────────────────────────────────────────────────────────────────
# 추가 시나리오 I: session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 I: initialize session 없음 → 404 ===")
status_i, body_i = http_json(
    "POST", "/api/analysis/sessions/nonexistent_b3/draft-items/initialize",
    body={},
)
ok("status 404", status_i, 404)
detail_i = body_i.get("detail") or {}
ok("reason=session_not_found", detail_i.get("reason"), "session_not_found")


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== B-3 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
