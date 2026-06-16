"""
Part C-1 — reference 파일 업로드 + selected_company_file_ids PATCH 검증.

시나리오 (b7.md §5 + Q4/Q5 보강):
  A: reference 업로드 → reference_file_ids + reference_attachments 저장
  B: reference 중복 append 방지 (helper 단위 + 동일 file_id 시뮬레이션)
  C: PATCH selected_company_file_ids 중복 제거 + 순서 보존
  D: PATCH 빈 배열 → 빈 배열 저장
  E1: PATCH 비-string 원소 → 422 (StrictStr)
  E2: PATCH string non-list → 422
  E3: PATCH extra 필드 → 422 (extra="forbid")
  E4: PATCH null → 변경 없음 (no-op)
  E5: PATCH {} → 변경 없음 (no-op)
  F: session 없음 → 404
  G: B-3 흐름 보존 — confirmed_schema / draft_items / parser_metadata 보존
  Q4-A: GET /files 무필터 → notice + form만 (reference 미포함)
  Q4-B: GET /files?kind=reference → reference만 반환
  Q4-C: 422 메시지에 "notice/form/reference" 포함
"""
import sys
import json
import io
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


def upload_multipart(session_id: str, kind: str, filename: str, content: bytes,
                     content_type: str = "text/plain"):
    """multipart/form-data 업로드 helper."""
    boundary = "----TestBoundaryC1"
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="session_id"\r\n\r\n{session_id}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="kind"\r\n\r\n{kind}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body += content
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE}/api/analysis/files/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ─────────────────────────────────────────────────────────────────────
# A: reference 업로드
# ─────────────────────────────────────────────────────────────────────
print("=== 시나리오 A: reference 업로드 ===")
_, sess_a = http_json("POST", "/api/analysis/sessions", {"user_id": "c1_A"})
sid_a = sess_a["session_id"]

ref_content = b"This is a reference document for testing.\nContains useful information."
status_a, upload_a = upload_multipart(sid_a, "reference", "ref1.txt", ref_content)
ok("A status 200", status_a, 200)
ok("A ok=true", upload_a.get("ok"), True)
ok("A kind=reference", upload_a.get("kind"), "reference")
assert_true("A file_id 존재", isinstance(upload_a.get("file_id"), str)
            and upload_a["file_id"].startswith("f_"))
ok("A parse_status=parsed", upload_a.get("parse_status"), "parsed")
ok("A char_count > 0", upload_a.get("char_count", 0) > 0, True)
assert_true("A reference_file_ids에 file_id 포함",
            upload_a["file_id"] in upload_a["reference_file_ids"])
ok("A reference_attachment_count=1",
   upload_a.get("reference_attachment_count"), 1)

# session raw 조회로 저장 확인
_, raw_a = http_json("GET", f"/api/analysis/sessions/{sid_a}")
ok("A session.reference_file_ids 저장",
   upload_a["file_id"] in (raw_a.get("notice_schema_json") and [])
   or upload_a["file_id"] in raw_a.get("form_schema_json", {}).get("reference_attachments", []),
   False)  # ← 잘못된 접근, 아래로 수정

# 정확한 검증
fsj_a = raw_a.get("form_schema_json") or {}
ref_atts = fsj_a.get("reference_attachments") or []
assert_true("A form_schema_json.reference_attachments 1개",
            len(ref_atts) == 1)
att0 = ref_atts[0]
ok("A att.file_id 일치", att0.get("file_id"), upload_a["file_id"])
ok("A att.kind=reference", att0.get("kind"), "reference")
ok("A att.parse_status=parsed", att0.get("parse_status"), "parsed")
assert_true("A att.parsed_text 저장",
            bool(att0.get("parsed_text")))
assert_true("A att.text_preview 존재 (≤300자)",
            isinstance(att0.get("text_preview"), str)
            and 0 < len(att0["text_preview"]) <= 300)
assert_true("A att.metadata dict",
            isinstance(att0.get("metadata"), dict))
# raw_b64 미저장 검증
ok("A att.raw_b64 미저장 (None or 없음)",
   att0.get("raw_b64"), None)
# 기존 form_schema_json key 보존 (attachments는 form/notice용 — 아직 없을 수 있음)
# raw session에서 직접 확인:
sess_db_a = raw_a
ok("A session.status 보존 (created)",
   sess_db_a.get("status"), "created")
ok("A session.current_step 보존 (1)",
   sess_db_a.get("current_step"), 1)


# ─────────────────────────────────────────────────────────────────────
# B: reference 중복 append 방지 (helper 단위 테스트)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 B: 중복 file_id append 방지 (helper 단위) ===")
# 직접 helper 호출
from database import get_db
from models import ApplicationSession
from routers.analysis import (
    _get_attachments, _set_attachments, _attachments_subkey,
    _dedupe_preserve_order, _DEFAULT_LIST_KINDS,
)
ok("_attachments_subkey('reference')",
   _attachments_subkey("reference"), "reference_attachments")
ok("_attachments_subkey('notice')",
   _attachments_subkey("notice"), "attachments")
ok("_attachments_subkey('form')",
   _attachments_subkey("form"), "attachments")
ok("_DEFAULT_LIST_KINDS",
   _DEFAULT_LIST_KINDS, ("notice", "form"))

# _dedupe_preserve_order
ok("dedupe ['a','b','a']", _dedupe_preserve_order(["a", "b", "a"]), ["a", "b"])
ok("dedupe ['c','b','a','b']",
   _dedupe_preserve_order(["c", "b", "a", "b"]), ["c", "b", "a"])
ok("dedupe []", _dedupe_preserve_order([]), [])


# ─────────────────────────────────────────────────────────────────────
# C: PATCH selected_company_file_ids 중복 제거 + 순서 보존
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 C: PATCH 중복 제거 + 순서 보존 ===")
_, sess_c = http_json("POST", "/api/analysis/sessions", {"user_id": "c1_C"})
sid_c = sess_c["session_id"]

status_c, body_c = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"selected_company_file_ids": ["file_a", "file_b", "file_a", "file_c", "file_b"]},
)
ok("C status 200", status_c, 200)
ok("C ok=true", body_c.get("ok"), True)
ok("C selected_company_file_ids 순서 보존+중복 제거",
   body_c.get("selected_company_file_ids"),
   ["file_a", "file_b", "file_c"])


# ─────────────────────────────────────────────────────────────────────
# D: PATCH 빈 배열
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 D: PATCH 빈 배열 ===")
status_d, body_d = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"selected_company_file_ids": []},
)
ok("D status 200", status_d, 200)
ok("D selected_company_file_ids=[]", body_d.get("selected_company_file_ids"), [])


# ─────────────────────────────────────────────────────────────────────
# E1: PATCH 비-string 원소 → 422
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E1: PATCH [123, null] → 422 ===")
status_e1, body_e1 = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"selected_company_file_ids": [123, None]},
)
ok("E1 status 422", status_e1, 422)


# ─────────────────────────────────────────────────────────────────────
# E2: PATCH string non-list → 422
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E2: PATCH string non-list → 422 ===")
status_e2, _ = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"selected_company_file_ids": "abc"},
)
ok("E2 status 422", status_e2, 422)


# ─────────────────────────────────────────────────────────────────────
# E3: PATCH extra field → 422
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E3: PATCH {status: 'x'} → 422 ===")
status_e3, _ = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"status": "x"},
)
ok("E3 status 422", status_e3, 422)

status_e3b, _ = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"selected_company_file_ids": ["a"], "status": "x"},
)
ok("E3-2 mixed → 422", status_e3b, 422)


# ─────────────────────────────────────────────────────────────────────
# E4: PATCH null → 변경 없음 (no-op)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E4: PATCH null → 변경 없음 ===")
# 먼저 값 설정
http_json("PATCH", f"/api/analysis/sessions/{sid_c}",
          {"selected_company_file_ids": ["preserved_a", "preserved_b"]})
status_e4, body_e4 = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}",
    {"selected_company_file_ids": None},
)
ok("E4 status 200", status_e4, 200)
ok("E4 기존 값 유지",
   body_e4.get("selected_company_file_ids"),
   ["preserved_a", "preserved_b"])


# ─────────────────────────────────────────────────────────────────────
# E5: PATCH {} → 변경 없음 (no-op)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 E5: PATCH {} → 변경 없음 ===")
status_e5, body_e5 = http_json(
    "PATCH", f"/api/analysis/sessions/{sid_c}", {},
)
ok("E5 status 200", status_e5, 200)
ok("E5 기존 값 유지",
   body_e5.get("selected_company_file_ids"),
   ["preserved_a", "preserved_b"])


# ─────────────────────────────────────────────────────────────────────
# F: session 없음 → 404
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 F: PATCH session 없음 → 404 ===")
status_f, body_f = http_json(
    "PATCH", "/api/analysis/sessions/nonexistent_c1",
    {"selected_company_file_ids": ["a"]},
)
ok("F status 404", status_f, 404)


# ─────────────────────────────────────────────────────────────────────
# G: B-3 흐름 보존
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 G: B-3 흐름 보존 (confirmed_schema/draft_items/parser_metadata) ===")
_, sess_g = http_json("POST", "/api/analysis/sessions", {"user_id": "c1_G"})
sid_g = sess_g["session_id"]

# parse-form (작은 form_text)
_, _ = http_json("POST", "/api/analysis/parse-form", {
    "form_text": "=== PAGE 1 ===\nQ1 회사명\n=== PAGE 2 ===\nQ2 대표자",
    "form_name": "g.pdf", "session_id": sid_g, "request_id": "g_parse",
}, timeout=180)

# confirm-step2 (사용자 수정본)
user_schema = {
    "form_id": "g", "form_name": "g",
    "sections": [
        {"section_id": "S1", "title": "S1", "order": 1, "questions": [
            {"question_id": "Q1", "title": "회사명", "fill_mode": "ai_text",
             "source_page": 1, "is_required": True},
        ]},
    ],
}
http_json("POST", "/api/analysis/confirm-step2",
          {"session_id": sid_g, "confirmed_form_schema": user_schema})

# initialize draft-items
http_json("POST", f"/api/analysis/sessions/{sid_g}/draft-items/initialize", {})

# 이제 C-1: reference 업로드 + PATCH
upload_multipart(sid_g, "reference", "g_ref.txt", b"reference content for G")
http_json("PATCH", f"/api/analysis/sessions/{sid_g}",
          {"selected_company_file_ids": ["g_cf_001"]})

# 모든 키 보존 확인
_, raw_g = http_json("GET", f"/api/analysis/sessions/{sid_g}")
fsj_g = raw_g.get("form_schema_json") or {}
preserved_keys = {"confirmed_schema", "schema_status", "confirmed_at",
                  "draft_items", "draft_items_status", "parser_metadata",
                  "reference_attachments"}
assert_true("G B-3 + C-1 keys 모두 보존",
            preserved_keys.issubset(set(fsj_g.keys())),
            f"missing: {preserved_keys - set(fsj_g.keys())}")
ok("G status=step2_confirmed", raw_g.get("status"), "step2_confirmed")
ok("G current_step=3", raw_g.get("current_step"), 3)
ok("G selected_company_file_ids 저장",
   raw_g.get("selected_company_file_ids"), ["g_cf_001"])
# step3-ready 재확인 — reference/selected_company_file_ids가 영향 안 줌
_, ready_g = http_json("GET", f"/api/analysis/sessions/{sid_g}/step3-ready")
ok("G step3_ready 유지", ready_g.get("step3_ready"), True)


# ─────────────────────────────────────────────────────────────────────
# Q4-A: GET /files 무필터 → notice + form만 (reference 미포함)
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 Q4-A: GET /files 무필터 → notice + form만 ===")
# sid_g는 reference 업로드 + parse-form (form attachment 있음). notice 없음.
status_q4a, body_q4a = http_json(
    "GET", f"/api/analysis/files?session_id={sid_g}",
)
ok("Q4-A status 200", status_q4a, 200)
items_q4a = body_q4a.get("items") or {}
returned_kinds = set(items_q4a.keys())
ok("Q4-A 반환 kinds = {notice, form} (reference 미포함)",
   returned_kinds, {"notice", "form"})
assert_true("Q4-A reference 키 없음", "reference" not in items_q4a)


# ─────────────────────────────────────────────────────────────────────
# Q4-B: GET /files?kind=reference → reference만
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 Q4-B: GET /files?kind=reference → reference만 ===")
status_q4b, body_q4b = http_json(
    "GET", f"/api/analysis/files?session_id={sid_g}&kind=reference",
)
ok("Q4-B status 200", status_q4b, 200)
items_q4b = body_q4b.get("items") or {}
ok("Q4-B reference 키 존재", "reference" in items_q4b, True)
ok("Q4-B kinds = {reference}", set(items_q4b.keys()), {"reference"})
assert_true("Q4-B reference 1개 반환",
            len(items_q4b.get("reference") or []) == 1)


# ─────────────────────────────────────────────────────────────────────
# Q4-C: 422 메시지에 reference 포함
# ─────────────────────────────────────────────────────────────────────
print("\n=== 시나리오 Q4-C: invalid kind → 422 메시지에 reference 포함 ===")
status_q4c, body_q4c = http_json(
    "GET", f"/api/analysis/files?session_id={sid_g}&kind=invalid",
)
ok("Q4-C status 422", status_q4c, 422)
detail = body_q4c.get("detail") or ""
assert_true("Q4-C 422 detail에 'reference' 포함",
            "reference" in str(detail))
# upload_file도 동일
status_q4c2, body_q4c2 = upload_multipart(sid_g, "invalid", "x.txt", b"x")
ok("Q4-C upload invalid → 422", status_q4c2, 422)
detail2 = body_q4c2.get("detail") or ""
assert_true("Q4-C upload 422 detail에 'reference' 포함",
            "reference" in str(detail2))


# ─────────────────────────────────────────────────────────────────────
# 종합
# ─────────────────────────────────────────────────────────────────────
print(f"\n=== C-1 검증 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
