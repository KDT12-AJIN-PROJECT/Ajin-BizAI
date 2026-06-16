"""
A-3 API-level smoke test — HTTP calls against running backend (localhost:8000)
Tests: parser_metadata fields, fallback detection, quality gate
"""
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")


BASE = "http://localhost:8000"


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def ok(label, val, want):
    mark = "✓" if val == want else "✗"
    print(f"  {mark} {label}: {val!r}" + (f" (want {want!r})" if val != want else ""))
    return val == want


# ─────────────────────────────────────────────────────────────────────────────
# 1. Create session
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== API Test A: direct_input parse-form ===")
sess = post("/api/analysis/sessions", {"user_id": "test_a3"})
sid = sess["session_id"]
print(f"  session_id={sid}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. parse-form with direct form_text (parser_mode=direct_input)
# ─────────────────────────────────────────────────────────────────────────────
form_text_17p = "\n".join(
    f"=== PAGE {i} ===\n항목{i}: <EMPTY_FIELD id='q{i}'/>" for i in range(1, 18)
)
result = post("/api/analysis/parse-form", {
    "form_text": form_text_17p,
    "form_name": "test_17p.pdf",
    "session_id": sid,
    "request_id": "test_a3_r1",
})

print(f"  quality_status={result.get('quality_status')!r}")
pm = result.get("quality_metrics", {})
print(f"  quality_metrics.page_count_used={pm.get('page_count_used')}")
print(f"  quality_metrics.question_count={pm.get('question_count')}")
print(f"  quality_metrics.needs_repair={pm.get('needs_repair')}")

# parser_metadata stored in DB — retrieve session to check
sess_data = None
try:
    req2 = urllib.request.Request(f"{BASE}/api/analysis/sessions/{sid}", method="GET")
    with urllib.request.urlopen(req2, timeout=10) as r:
        sess_data = json.loads(r.read())
except Exception as e:
    print(f"  [warn] session get failed: {e}")

if sess_data:
    pm2 = sess_data.get("form_schema_json", {}).get("parser_metadata", {})
    print(f"\n  [parser_metadata from DB]")
    ok("parser_mode", pm2.get("parser_mode"), "direct_input")
    ok("fallback_used", pm2.get("fallback_used"), False)
    ok("fallback_reason", pm2.get("fallback_reason"), None)
    ok("layout_text_truncated", pm2.get("layout_text_truncated"), False)
    ok("layout_text_safety_cap", pm2.get("layout_text_safety_cap"), 200000)
    ok("quality_status present", "quality_status" in pm2, True)
    ok("quality_metrics present", "quality_metrics" in pm2, True)
    # page_count_used: direct_input means no layout_meta, page markers counted from text
    pc = pm2.get("quality_metrics", {}).get("page_count_used", -1)
    ok("page_count_used=17", pc, 17)


# ─────────────────────────────────────────────────────────────────────────────
# 3. parse-form with session that has no attachments → 422 (expected behavior)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== API Test B: placeholder form_text → no attachments → 422 ===")
sess2 = post("/api/analysis/sessions", {"user_id": "test_a3_b"})
sid2 = sess2["session_id"]
try:
    result2 = post("/api/analysis/parse-form", {
        "form_text": "[제출양식 파일]",
        "form_name": "test.pdf",
        "session_id": sid2,
        "request_id": "test_a3_r2",
    })
    print(f"  [unexpected success]: {result2}")
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    ok("status 422", e.code, 422)
    print(f"  detail: {body.get('detail')!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== A-3 API 테스트 완료 ===")
