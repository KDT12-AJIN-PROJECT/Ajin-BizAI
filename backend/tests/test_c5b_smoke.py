"""
C-5b smoke — Step 2 확정 9단계 backend 체인 정상 동작 확인.

frontend가 호출할 9단계 endpoint를 순차 호출하여 mock 환경에서 end-to-end 통과 검증.

순서:
  1. confirm-step2
  2. announcement-signals normalize
  3. evaluation-rubric resolve
  4. step3-ready
  5. draft-items/initialize
  6. run-step2-mapping
  7. mapping-status polling (success까지)
  8. GET /draft-items

실행 환경 (NOAPI-P3 update):
  - **AI_PROVIDER=mock 환경 가정** (mock provider 9단계 체인 contract 검증).
  - AI_PROVIDER=openai 환경에서 selected_company_file_ids=[] / company_profile_input=None
    상태로 실행 시 P3 strict real path가 insufficient_company_data를 발생시켜
    pipeline.status=failed가 정상 동작 (의도된 결과).
  - 본 smoke는 mock 기반 contract 검증이 목적이며 real OpenAI 호출 없음.
  - real path 검증은 별도 fixture 기반 unit test (test_noapi_p3_company_analyzer.py)로 분리.

실행 예:
  # 권장 — 명시적 mock override
  AI_PROVIDER=mock python -m uvicorn main:app --port 8000
  python tests/test_c5b_smoke.py
"""
import sys, json, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://localhost:8000"
PASSES = 0
FAILS = 0


def ok(label, val, want):
    global PASSES, FAILS
    if val == want: print(f"  ✓ {label}"); PASSES += 1
    else: print(f"  ✗ {label}  got={val!r} want={want!r}"); FAILS += 1


def assert_true(label, cond, note=""):
    global PASSES, FAILS
    if cond: print(f"  ✓ {label}"); PASSES += 1
    else: print(f"  ✗ {label}  {note}"); FAILS += 1


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


# session 생성 + parse-form (form_text로 빠르게)
print("=== Step 2 확정 9단계 체인 ===")
_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "c5b_chain"})
sid = sess["session_id"]
http_json("POST", "/api/analysis/parse-form", {
    "form_text": "=== PAGE 1 ===\nQ1 회사명", "form_name": "c5b.pdf",
    "session_id": sid, "request_id": "c5b_parse",
}, timeout=180)

# 1. confirm-step2
status1, body1 = http_json("POST", "/api/analysis/confirm-step2", {
    "session_id": sid,
    "confirmed_form_schema": {
        "form_id": "c5b", "form_name": "c5b",
        "sections": [{"section_id": "S1", "title": "S1", "order": 1, "questions": [
            {"question_id": "Q1", "title": "Q1", "fill_mode": "ai_text",
             "source_page": 1, "is_required": True}
        ]}]
    }
})
ok("1 confirm-step2 200", status1, 200)
ok("1 ok=true", body1.get("ok"), True)

# 2. normalize announcement-signals
status2, body2 = http_json("POST", f"/api/analysis/sessions/{sid}/announcement-signals/normalize")
ok("2 normalize 200", status2, 200)
ok("2 ok=true", body2.get("ok"), True)
assert_true("2 announcement_signals dict", isinstance(body2.get("announcement_signals"), dict))
# Q4 표시 항목 6개 모두 존재
for key in ("criteria_count", "bonuses_count", "preferences_count",
            "eligibility_count", "emphasis_keywords_count", "compliance_constraints_count"):
    assert_true(f"2 {key} 존재", key in body2)

# 3. resolve evaluation-rubric
status3, body3 = http_json("POST", f"/api/analysis/sessions/{sid}/evaluation-rubric/resolve")
ok("3 resolve 200", status3, 200)
ok("3 ok=true", body3.get("ok"), True)
# Q4 표시 항목 4개 (source, template_type, axes_count, scored_axes_count, total_weight)
for key in ("source", "template_type", "axes_count", "scored_axes_count", "total_weight"):
    assert_true(f"3 {key} 존재", key in body3)

# 4. step3-ready
status4, body4 = http_json("GET", f"/api/analysis/sessions/{sid}/step3-ready")
ok("4 step3-ready 200", status4, 200)
ok("4 step3_ready=true", body4.get("step3_ready"), True)

# 5. initialize draft_items
status5, body5 = http_json("POST", f"/api/analysis/sessions/{sid}/draft-items/initialize", {})
ok("5 initialize 200", status5, 200)
ok("5 ok=true", body5.get("ok"), True)
assert_true("5 draft_item_count > 0", body5.get("draft_item_count", 0) > 0)

# 6. run-step2-mapping
status6, body6 = http_json("POST", "/api/analysis/run-step2-mapping",
                            {"session_id": sid, "request_id": "c5b_run"})
ok("6 run 200", status6, 200)
ok("6 status=running", body6.get("status"), "running")

# 7. mapping-status polling (max 60s, 2s interval)
print("\n=== 7. mapping-status polling ===")
deadline = time.time() + 60
last_status = None
while time.time() < deadline:
    _, ms = http_json("GET", f"/api/analysis/sessions/{sid}/mapping-status")
    pipeline = ms.get("mapping_pipeline") or {}
    last_status = pipeline.get("status")
    if last_status == "success":
        ok("7 mapping success", last_status, "success")
        break
    if last_status == "failed":
        ok("7 mapping NOT failed", "failed", "success")
        break
    time.sleep(1)
else:
    ok("7 timeout (60s)", "timeout", "success")

# 8. GET /draft-items
status8, body8 = http_json("GET", f"/api/analysis/draft-items/{sid}")
ok("8 draft-items 200", status8, 200)
ok("8 ok=true", body8.get("ok"), True)

# mapping-status 최종 확인 (C-4)
# 본 smoke는 reference 업로드 안 했으므로 extract_evidence 빈 → evidence_missing
# C-4 정책상 정상 (reference 의존). pipeline.status=success는 확인 가능.
status_r, body_r = http_json("GET", f"/api/analysis/sessions/{sid}/mapping-status")
ok("최종 pipeline.status=success", body_r.get("mapping_pipeline", {}).get("status"), "success")
ok("최종 company_analysis_exists", body_r.get("company_analysis_exists"), True)
ok("최종 mapping_result_exists", body_r.get("mapping_result_exists"), True)
ok("최종 missing_material_exists", body_r.get("missing_material_exists"), True)
ok("최종 evaluation_rubric_exists", body_r.get("evaluation_rubric_exists"), True)
assert_true("최종 evidence_exists=false (reference 없음, 정상)",
            body_r.get("evidence_exists") is False)
assert_true("최종 not_ready_reasons에 evidence_missing (정상)",
            "evidence_missing" in (body_r.get("not_ready_reasons") or []))

print(f"\n=== C-5b smoke: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
