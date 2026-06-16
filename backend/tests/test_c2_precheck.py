"""
C-2 precheck mode 검증 (ALLOW_PRECONFIRM_PRECHECK=true backend에서 실행).

시나리오:
  C: env=true + allow_preconfirm=true → 통과
  E: env=true + allow_preconfirm=false → 409 (allow_preconfirm 명시 안 함)
"""
import sys, json, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"
PASSES = 0; FAILS = 0


def ok(label, val, want):
    global PASSES, FAILS
    if val == want: print(f"  ✓ {label}"); PASSES += 1
    else: print(f"  ✗ {label}  got={val!r} want={want!r}"); FAILS += 1


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


# session 생성 후 status=analyzing
import os, pathlib
BACKEND = pathlib.Path(__file__).parent.parent
import sys as _s
_s.path.insert(0, str(BACKEND))
env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_, sess = http_json("POST", "/api/analysis/sessions", {"user_id": "c2_precheck"})
sid = sess["session_id"]

from database import get_db
from models import ApplicationSession
db_gen = get_db()
db = next(db_gen)
try:
    s = db.query(ApplicationSession).filter(
        ApplicationSession.session_id == sid
    ).first()
    s.status = "analyzing"
    db.commit()
finally:
    db.close()

# 대표 endpoint: map-evidence
def call_map_evidence(allow_preconfirm: bool):
    return http_json("POST", "/api/analysis/map-evidence", {
        "session_id": sid, "allow_preconfirm": allow_preconfirm,
        "form_schema": {}, "evidence_list": [], "notice_schema": {},
    })


print("=== 시나리오 C: env=true + allow_preconfirm=true → 통과 ===")
status_c, _ = call_map_evidence(True)
ok("C status not 409 (gate 우회 정상)", status_c != 409, True)
ok("C status 200", status_c, 200)


print("\n=== 시나리오 E: env=true + allow_preconfirm=false → 409 ===")
status_e, _ = call_map_evidence(False)
ok("E status 409", status_e, 409)

print(f"\n=== C-2 precheck 결과: PASS={PASSES}, FAIL={FAILS} ===")
sys.exit(0 if FAILS == 0 else 1)
