"""
C-5a smoke — backendApi.js가 호출할 backend endpoint들이 정상 응답하는지 확인.

이번 단계는 frontend 변경만 (Step1Common.jsx + DraftPageV2.jsx).
backend는 미수정 — C-5a는 기존 endpoint를 사용하는 wrapper만 추가.

검증:
  1. uploadFile(kind=reference) — C-1 정책 유지 (raw_b64 미저장 등)
  2. patchSession(selectedCompanyFileIds) — C-1 PATCH endpoint 정상
  3. listFiles(kind=reference) — 명시 호출 시만 reference 반환
"""
import sys
import json
import io
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


def upload_multipart(sid, kind, name, content, ct="text/plain"):
    boundary = "----C5aBoundary"
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="session_id"\r\n\r\n{sid}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="kind"\r\n\r\n{kind}\r\n'.encode()
    body += f"--{boundary}\r\n".encode()
    body += (f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
             f"Content-Type: {ct}\r\n\r\n").encode()
    body += content
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{BASE}/api/analysis/files/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# 1. uploadFile(kind=reference)
print("=== uploadFile(kind=reference) ===")
_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "c5a_ref"})
sid = sess["session_id"]
status, body = upload_multipart(sid, "reference", "ref.txt", b"reference content")
ok("upload 200", status, 200)
ok("kind=reference", body.get("kind"), "reference")
ok("ok=true", body.get("ok"), True)

# 2. patchSession
print("\n=== patchSession(selectedCompanyFileIds) ===")
status_p, body_p = http_json("PATCH", f"/api/analysis/sessions/{sid}",
                              {"selected_company_file_ids": ["cf_a", "cf_b", "cf_a"]})
ok("PATCH 200", status_p, 200)
ok("dedupe", body_p.get("selected_company_file_ids"), ["cf_a", "cf_b"])

# 3. listFiles(kind=reference)
print("\n=== listFiles(kind=reference) ===")
status_l, body_l = http_json("GET", f"/api/analysis/files?session_id={sid}&kind=reference")
ok("status 200", status_l, 200)
items = body_l.get("items") or {}
ok("reference만 반환", set(items.keys()), {"reference"})

# 무필터 → reference 미포함 (C-1 정책)
status_n, body_n = http_json("GET", f"/api/analysis/files?session_id={sid}")
items_n = body_n.get("items") or {}
ok("무필터 → reference 미포함", "reference" in items_n, False)

print(f"\n=== C-5a smoke: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
