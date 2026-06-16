"""
Phase 4-H A.1 — backend endpoint smoke test (dependency-free).

stdlib + httpx (already installed in bizai env) 만으로 실행.
backend 서버가 port 8000에서 실행 중이어야 함.

실행:
  cd backend
  python tests/smoke.py
또는:
  python -m backend.tests.smoke

검증 endpoint 21개:
  - sessions: POST / GET /{id} / GET (list)
  - analysis: parse-notice / parse-form / extract-evidence / analyze-company
              / map-evidence / check-missing / map-eval-criteria
              / confirm-step2 / export-docx / reanalyze
  - missing:  text / upload / bulk-upload / confirm
  - draft:    write-draft-item / rewrite-draft-item / approve-draft-item
              / GET draft-items/{sid}
  - chat:     draft-assist

정책 #6 부합: backend / DB / migration 변경 0. read-only smoke (POST는 mock 응답).
"""
import sys
import json
import httpx

BASE = "http://localhost:8000"
results = {"pass": 0, "fail": 0, "errors": []}


def check(name: str, response: httpx.Response, *required_keys):
    """endpoint 응답 검증 + 출력."""
    if response.status_code != 200:
        results["fail"] += 1
        results["errors"].append(f"[FAIL] {name}: HTTP {response.status_code}")
        print(f"  FAIL {name:40s} HTTP {response.status_code}")
        return None
    try:
        data = response.json()
    except Exception as e:
        results["fail"] += 1
        results["errors"].append(f"[FAIL] {name}: JSON parse error {e}")
        print(f"  FAIL {name:40s} JSON parse error")
        return None
    missing = [k for k in required_keys if k not in data]
    if missing:
        results["fail"] += 1
        results["errors"].append(f"[FAIL] {name}: missing keys {missing}")
        print(f"  FAIL {name:40s} missing keys: {missing}")
        return data
    results["pass"] += 1
    print(f"  PASS {name:40s} HTTP 200 + keys ok")
    return data


def main():
    print("=" * 64)
    print(" Phase 4-G smoke test (A.1 -- backend 21 endpoint)")
    print("=" * 64)
    print()

    with httpx.Client(base_url=BASE, timeout=10) as client:
        # 1. sessions
        print("[sessions]")
        r = client.post("/api/analysis/sessions", json={"user_id": "smoke"})
        data = check("POST /sessions", r, "session_id", "status", "current_step")
        sid = data["session_id"] if data else "smoke_fallback"

        r = client.get(f"/api/analysis/sessions/{sid}")
        check(f"GET  /sessions/{{sid}}", r, "session_id", "status", "current_step")

        r = client.get("/api/analysis/sessions", params={"limit": 5})
        check("GET  /sessions (list)", r, "items", "total")

        # 2. analysis
        print("\n[analysis]")
        r = client.post("/api/analysis/parse-notice",
                        json={"session_id": sid, "notice_text": "test"})
        check("POST /parse-notice", r, "target", "benefit", "evaluation_criteria")

        r = client.post("/api/analysis/parse-form",
                        json={"session_id": sid, "form_text": "test", "form_name": "f.pdf"})
        check("POST /parse-form", r, "form_id", "sections")

        r = client.post("/api/analysis/extract-evidence",
                        json={"session_id": sid, "ref_text": "test"})
        check("POST /extract-evidence", r, "items")

        r = client.post("/api/analysis/analyze-company",
                        json={"session_id": sid, "company_files": [], "notice_schema": {}})
        check("POST /analyze-company", r, "company", "fit_analysis")

        r = client.post("/api/analysis/map-evidence",
                        json={"session_id": sid, "form_schema": {}, "evidence_list": []})
        check("POST /map-evidence", r, "question_mappings", "coverage_rate")

        r = client.post("/api/analysis/check-missing",
                        json={"session_id": sid, "mapping_result": {}})
        if r.status_code == 200:
            data = r.json()
            # check-missing은 list 또는 dict 반환 (mock에 따라)
            if isinstance(data, list) or (isinstance(data, dict) and "items" in data):
                results["pass"] += 1
                print(f"  PASS {'POST /check-missing':40s} HTTP 200")
            else:
                results["fail"] += 1
                print(f"  FAIL {'POST /check-missing':40s} unexpected shape")
        else:
            results["fail"] += 1
            print(f"  FAIL {'POST /check-missing':40s} HTTP {r.status_code}")

        r = client.post("/api/analysis/map-eval-criteria",
                        json={"session_id": sid, "notice_schema": {}, "form_schema": {}})
        check("POST /map-eval-criteria", r, "mappings", "total")

        r = client.post("/api/analysis/confirm-step2", json={"session_id": sid})
        check("POST /confirm-step2", r, "session_status", "next_step")

        r = client.post("/api/analysis/export-docx",
                        json={"session_id": sid, "include_table_data": True})
        check("POST /export-docx", r, "export_id", "status", "file_url", "file_name")

        r = client.post("/api/analysis/reanalyze",
                        json={"session_id": sid, "target": "missing"})
        check("POST /reanalyze (missing)", r, "status", "target")

        # 3. missing/*
        print("\n[missing/*]")
        r = client.post("/api/analysis/missing/text",
                        json={"session_id": sid, "question_id": "I-1", "content": "t"})
        check("POST /missing/text", r, "supplemental_id", "status")

        r = client.post("/api/analysis/missing/upload",
                        json={"session_id": sid, "question_id": "I-1",
                              "file_name": "t.pdf", "file_size_bytes": 100})
        check("POST /missing/upload", r, "file_id", "supplemental_id")

        r = client.post("/api/analysis/missing/bulk-upload",
                        json={"session_id": sid, "files": [{"file_name": "a.pdf", "file_size_bytes": 1}]})
        check("POST /missing/bulk-upload", r, "total_files", "auto_matched", "results")

        r = client.post("/api/analysis/missing/confirm",
                        json={"session_id": sid, "supplemental_id": "supp_t", "action": "correct"})
        check("POST /missing/confirm (correct)", r, "supplemental_status", "missing_status")

        # 4. draft
        print("\n[draft]")
        r = client.post("/api/analysis/write-draft-item",
                        json={"session_id": sid, "question": {"question_id": "I-1", "title": "t"},
                              "matched_evidence": [], "company_schema": {}, "notice_schema": {}})
        check("POST /write-draft-item", r, "draft_item_id", "status")

        r = client.post("/api/analysis/rewrite-draft-item",
                        json={"session_id": sid, "question_id": "I-1",
                              "current_draft": "t", "user_message": "shorter"})
        check("POST /rewrite-draft-item", r, "draft_item_id", "version")

        r = client.post("/api/analysis/approve-draft-item",
                        json={"session_id": sid, "question_id": "I-1"})
        check("POST /approve-draft-item", r, "status", "lock_on_reanalyze")

        r = client.get(f"/api/analysis/draft-items/{sid}")
        check("GET  /draft-items/{sid}", r, "items", "stats")

        # 5. chat
        print("\n[chat]")
        r = client.post("/api/chat/draft-assist",
                        json={"session_id": sid, "question_id": "I-1", "message": "t"})
        check("POST /chat/draft-assist", r, "response", "history_appended")

    # summary
    print()
    print("=" * 64)
    total = results["pass"] + results["fail"]
    print(f" RESULT: {results['pass']} / {total} passed ({results['fail']} failed)")
    print("=" * 64)
    if results["errors"]:
        print("\nFAILURES:")
        for err in results["errors"]:
            print(f"  {err}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
