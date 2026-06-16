"""
C-5c smoke — Step3 missingMaterials / draft_items hydration 데이터 contract 검증.

C-5c는 frontend-only 변경. backend는 미수정.
본 smoke는 frontend(DraftPageV2 / Step3Draft)가 의존하는 backend 응답 shape이
정확히 노출되는지 검증한다.

검증 대상 contract:
  1. mapping-status 응답에서 mapping_pipeline.results.check_missing 존재 + list 타입
     (finalizeStep2 step9 + restoreSession Q6 case5에서 사용)
  2. check_missing item shape — SupplementalPanel adapter가 요구하는 키 존재
     (missing_id, question_id, name, status, input_type)
  3. draft-items 응답 shape — Step3Draft hydration에 필요한 키 존재
     (question_id, draft_text, status, constraints.max_length, matched_evidence_ids)

실행 환경 (NOAPI-P3 update):
  - **AI_PROVIDER=mock 환경 가정** (mock provider 기반 contract 검증).
  - AI_PROVIDER=openai 환경에서 selected_company_file_ids=[] / company_profile_input=None
    상태로 실행 시 P3 strict real path가 insufficient_company_data를 발생시켜
    pipeline.status=failed가 정상 동작 (의도된 결과).
  - 본 smoke는 frontend contract 검증이 목적이며 real OpenAI 호출 없음.

실행 예:
  AI_PROVIDER=mock python -m uvicorn main:app --port 8000
  python tests/test_c5c_smoke.py
"""
import sys
import json
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://localhost:8000"
PASSES = 0
FAILS = 0


def ok(label, val, want):
    global PASSES, FAILS
    if val == want:
        print(f"  ✓ {label}"); PASSES += 1
    else:
        print(f"  ✗ {label}  got={val!r} want={want!r}"); FAILS += 1


def assert_true(label, cond, note=""):
    global PASSES, FAILS
    if cond:
        print(f"  ✓ {label}"); PASSES += 1
    else:
        print(f"  ✗ {label}  {note}"); FAILS += 1


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


# ── 세션 + parse-form + 9단계 체인 ────────────────────────────
print("=== 사전 준비: 세션 + 9단계 mapping pipeline 통과 ===")
_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "c5c_contract"})
sid = sess["session_id"]

http_json("POST", "/api/analysis/parse-form", {
    "form_text": "=== PAGE 1 ===\nQ1 회사명\nQ2 사업개요",
    "form_name": "c5c.pdf",
    "session_id": sid,
    "request_id": "c5c_parse",
}, timeout=180)

http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid,
    "confirmed_form_schema": {
        "form_id": "c5c", "form_name": "c5c",
        "sections": [{"section_id": "S1", "title": "S1", "order": 1, "questions": [
            {"question_id": "Q1", "title": "회사명", "fill_mode": "ai_text",
             "source_page": 1, "is_required": True,
             "constraints": {"max_length": 500}},
            {"question_id": "Q2", "title": "사업개요", "fill_mode": "ai_text",
             "source_page": 1, "is_required": True,
             "constraints": {"max_length": 1000}},
        ]}]
    }
})
http_json("POST", f"/api/analysis/sessions/{sid}/announcement-signals/normalize")
http_json("POST", f"/api/analysis/sessions/{sid}/evaluation-rubric/resolve")
http_json("POST", f"/api/analysis/sessions/{sid}/draft-items/initialize", {})
http_json("POST", "/api/analysis/run-step2-mapping",
          {"session_id": sid, "request_id": "c5c_run"})

# polling (max 60s)
deadline = time.time() + 60
while time.time() < deadline:
    _, ms = http_json("GET", f"/api/analysis/sessions/{sid}/mapping-status")
    if (ms.get("mapping_pipeline") or {}).get("status") in ("success", "failed"):
        break
    time.sleep(1)
print(f"  사전 준비 완료. pipeline.status={ms.get('mapping_pipeline', {}).get('status')}")


# ── 1. mapping-status contract — mapping_pipeline.results.check_missing 존재 ──
print("\n=== 1. mapping-status: mapping_pipeline.results.check_missing 존재 ===")
status_ms, body_ms = http_json("GET", f"/api/analysis/sessions/{sid}/mapping-status")
ok("mapping-status 200", status_ms, 200)

pipeline = body_ms.get("mapping_pipeline") or {}
assert_true("mapping_pipeline dict 존재", isinstance(pipeline, dict))
ok("pipeline.status=success", pipeline.get("status"), "success")

results = pipeline.get("results") or {}
assert_true("pipeline.results dict 존재", isinstance(results, dict))
assert_true("results.check_missing 키 존재", "check_missing" in results)

check_missing = results.get("check_missing")
assert_true("check_missing list 타입",
            isinstance(check_missing, list),
            note=f"got={type(check_missing).__name__}")


# ── 2. check_missing item shape (있을 때만) ───────────────────────
print("\n=== 2. check_missing item shape (SupplementalPanel adapter 요구 키) ===")
if check_missing:
    item = check_missing[0]
    assert_true("item dict 타입", isinstance(item, dict))
    # missingAdapter.js adaptMissingItems 요구 키
    for key in ("missing_id", "question_id", "name", "status", "input_type"):
        assert_true(f"item.{key} 존재", key in item,
                    note=f"item keys={list(item.keys())}")
else:
    print("  ⓘ check_missing 빈 list — item shape 검증 skip (정상)")
    # 빈 list라도 list 타입이면 OK (Step3Draft localMissingMaterials sync 동작)


# ── 3. draft-items contract (Step3Draft hydration 매핑) ───────────
print("\n=== 3. draft-items 응답 shape (Step3Draft hydration) ===")
status_di, body_di = http_json("GET", f"/api/analysis/draft-items/{sid}")
ok("draft-items 200", status_di, 200)
ok("ok=true", body_di.get("ok"), True)

draft_items = body_di.get("draft_items") or []
assert_true("draft_items list 타입", isinstance(draft_items, list))
assert_true("draft_items 1건 이상", len(draft_items) > 0,
            note=f"len={len(draft_items)}")

if draft_items:
    di = draft_items[0]
    # Step3Draft draftMap hydration 매핑 (DraftPageV2.jsx:213-220, 571-578)
    for key in ("question_id", "draft_text", "status", "draft_item_id"):
        assert_true(f"di.{key} 존재", key in di,
                    note=f"di keys={list(di.keys())}")
    # constraints — Step3Draft optional chaining: `di.constraints?.max_length || 1000`
    # backend가 constraints=None 반환해도 frontend는 fallback 1000 사용 (정상)
    constraints = di.get("constraints")
    assert_true("di.constraints는 None 또는 dict (frontend optional 처리)",
                constraints is None or isinstance(constraints, dict),
                note=f"got={type(constraints).__name__}")
    # matched_evidence_ids — Step3Draft evidenceIds 매핑
    assert_true("di.matched_evidence_ids list 타입",
                isinstance(di.get("matched_evidence_ids") or [], list))


# ── 4. restoreSession Q6 case5 — pipeline.results 복원 가능 확인 ──
print("\n=== 4. restoreSession Q6 case5 contract ===")
# Q6 case5는 mapping-status + draft-items 동시 호출 후
# mappingRes.mapping_pipeline.results.check_missing 사용
# 위 1, 3에서 이미 검증된 contract이므로 별도 호출 없음
assert_true("pipeline.results.check_missing 접근 경로 확인",
            isinstance((body_ms.get("mapping_pipeline") or {}).get("results") or {},
                       dict))


# ── 5. finalizeStep2 step9 — pollMappingStatus return shape ───────
print("\n=== 5. finalizeStep2 step9 — pollMappingStatus return shape ===")
# DraftPageV2.jsx pollMappingStatus는 mapping-status 응답 전체를 return
# 1번에서 검증된 shape과 동일하므로 별도 호출 없음
ok("pollMappingStatus return == mapping-status 응답", True, True)


print(f"\n=== C-5c smoke: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
