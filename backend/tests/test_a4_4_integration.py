"""
A-4-4 통합 테스트 — parse_form 내 normalize + promote 동작 확인.

전제: backend 서버가 localhost:8000에 실행 중. AI_PROVIDER=openai (실제 API 호출).
fixture AX 40p PDF를 raw_b64로 업로드 → parse-form 결과의 parser_metadata 검증.
"""
import sys
import json
import base64
import urllib.request
import urllib.error
import pathlib

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"
PDF = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples"
    r"\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문"
    r"\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)


def http_json(method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def ok(label, val, want):
    mark = "✓" if val == want else "✗"
    suffix = f"  got={val!r}, want={want!r}" if val != want else ""
    print(f"  {mark} {label}{suffix}")


def assert_true(label, cond, note=""):
    mark = "✓" if cond else "✗"
    suffix = f"  ({note})" if note else ""
    print(f"  {mark} {label}{suffix}")


# 1. session 생성
print("\n=== A-4-4 통합 — parse_form normalize + promote ===")
sess = http_json("POST", "/api/analysis/sessions", {"user_id": "test_a44"})
sid = sess["session_id"]
print(f"  session_id={sid}")

# 2. AX form PDF 업로드 (kind=form)
print(f"\n  Uploading AX 40p PDF...")
import urllib.parse
boundary = "----TestBoundary12345"
pdf_bytes = PDF.read_bytes()

multipart_body = b""
multipart_body += f"--{boundary}\r\n".encode()
multipart_body += f'Content-Disposition: form-data; name="session_id"\r\n\r\n{sid}\r\n'.encode()
multipart_body += f"--{boundary}\r\n".encode()
multipart_body += f'Content-Disposition: form-data; name="kind"\r\n\r\nform\r\n'.encode()
multipart_body += f"--{boundary}\r\n".encode()
multipart_body += (
    f'Content-Disposition: form-data; name="file"; filename="{PDF.name}"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode()
multipart_body += pdf_bytes
multipart_body += f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{BASE}/api/analysis/files/upload",
    data=multipart_body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=60) as resp:
    upload_result = json.loads(resp.read())
print(f"  upload result: file_id={upload_result.get('file_id')}, size={upload_result.get('size_bytes')}")

# 3. parse-form (form_text 비워두면 attachment에서 추출)
print(f"\n  parse-form 호출 중 (OpenAI form_parser + normalize + promote, ~120s 예상)...")
import time
t0 = time.time()
parse_result = http_json("POST", "/api/analysis/parse-form", {
    "form_text": "",
    "form_name": PDF.name,
    "session_id": sid,
    "request_id": "a44_test",
}, timeout=300)
elapsed = time.time() - t0
print(f"  parse-form 완료 ({elapsed:.1f}s)")

# 4. session에서 parser_metadata 조회
sess_data = http_json("GET", f"/api/analysis/sessions/{sid}", timeout=15)
pm = sess_data.get("form_schema_json", {}).get("parser_metadata", {})

print(f"\n[parser_metadata 핵심 필드 검증]")
ok("parser_mode", pm.get("parser_mode"), "layout_aware")
ok("fallback_used", pm.get("fallback_used"), False)
ok("normalize_table_enabled", pm.get("normalize_table_enabled"), True)
ok("auto_promote_table_enabled", pm.get("auto_promote_table_enabled"), True)

# 5. A-4-4 신규 필드 확인
print(f"\n[A-4-4 신규 stats 필드]")
print(f"  layout_table_count       = {pm.get('layout_table_count')}")
print(f"  normalized_table_count   = {pm.get('normalized_table_count')}")
print(f"  llm_table_input_count    = {pm.get('llm_table_input_count')}")
print(f"  promoted_table_count     = {pm.get('promoted_table_count')}")
print(f"  skipped_fragment_table   = {pm.get('skipped_fragment_table_count')}")
print(f"  llm_schema_corrected     = {pm.get('llm_schema_corrected_count')}")
print(f"  auto_section_used        = {pm.get('auto_section_used_count')}")
print(f"  table_promotion_rate     = {pm.get('table_promotion_rate')}")

assert_true("layout_table_count >= 40", pm.get("layout_table_count", 0) >= 40)
assert_true("normalized_table_count >= 40", pm.get("normalized_table_count", 0) >= 40)
assert_true("promoted_table_count >= 30", pm.get("promoted_table_count", 0) >= 30)
assert_true("skipped_fragment >= 5", pm.get("skipped_fragment_table_count", 0) >= 5)

# 6. quality_metrics 분리 확인
qm = pm.get("quality_metrics", {})
print(f"\n[quality_metrics 분리 (§3.9)]")
print(f"  table_count              = {qm.get('table_count')}")
print(f"  llm_table_count          = {qm.get('llm_table_count')}")
print(f"  promoted_table_count     = {qm.get('promoted_table_count')}")
assert_true("llm_table_count + promoted == table_count",
            qm.get('llm_table_count', 0) + qm.get('promoted_table_count', 0)
            == qm.get('table_count', 0))

# 7. schema에 promoted question 존재 확인
schema = sess_data.get("form_schema_json", {}).get("schema", {})
all_qs = [q for sec in (schema.get("sections") or [])
          for q in (sec.get("questions") or [])]
table_qs = [q for q in all_qs if q.get("fill_mode") == "table_input"]
promoted_qs = [q for q in table_qs if q.get("source_type") == "layout_table_promoted"]
corrected_qs = [q for q in table_qs if q.get("source_type") == "llm_table_schema_corrected_by_layout"]

print(f"\n[schema 검증]")
print(f"  total questions          = {len(all_qs)}")
print(f"  total table_input qs     = {len(table_qs)}")
print(f"  promoted qs              = {len(promoted_qs)}")
print(f"  corrected qs             = {len(corrected_qs)}")

# 핵심 표 5종 (p.4, p.7, p.34, p.35, p.36) 포함 확인
key_pages = [4, 7, 34, 35, 36]
for pg in key_pages:
    pg_table_qs = [q for q in table_qs if q.get("source_page") == pg]
    assert_true(f"p.{pg} ≥ 1 table_input question", len(pg_table_qs) >= 1)

print(f"\n=== A-4-4 통합 테스트 완료 ({elapsed:.1f}s) ===")
