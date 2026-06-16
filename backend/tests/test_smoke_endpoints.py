"""
Phase 4-H B1-β — backend endpoint smoke tests (pytest).

사용자 명세 8 smoke:
  1. session 생성 (POST /sessions + GET 복원)
  2. parse-notice
  3. parse-form
  4. mapping (map-evidence + check-missing + map-eval-criteria)
  5. missing (text + upload + bulk-upload + confirm)
  6. confirm-step2
  7. write-draft-item (+ rewrite + approve)
  8. export-docx (no LLM 게이트 확인)

목표: Phase 4-G 완료 상태를 깨지 않게 잠근다 (lock-in).
거창한 coverage가 아니라 회귀 방지 net.

실행:
  cd backend
  pytest tests/test_smoke_endpoints.py -v
"""


# 1. session 생성
def test_smoke_1_session_lifecycle(client, session_id):
    """POST /sessions → GET /sessions/{id} 복원 + GET /sessions 목록."""
    # GET 복원
    r = client.get(f"/api/analysis/sessions/{session_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == session_id
    assert data["status"] == "created"
    assert data["current_step"] == 1

    # GET 목록 (필터 X)
    r = client.get("/api/analysis/sessions", params={"limit": 5})
    assert r.status_code == 200
    assert "items" in r.json()
    assert "total" in r.json()


# 2. parse-notice
def test_smoke_2_parse_notice(client, session_id):
    """notice 분석 — NoticeSchema 응답 (target / benefit / evaluation_criteria)."""
    r = client.post("/api/analysis/parse-notice",
                    json={"session_id": session_id, "notice_text": "sample"})
    assert r.status_code == 200
    data = r.json()
    assert "target" in data
    assert "benefit" in data
    assert "evaluation_criteria" in data
    assert isinstance(data["evaluation_criteria"], list)
    assert len(data["evaluation_criteria"]) > 0


# 3. parse-form
def test_smoke_3_parse_form(client, session_id):
    """form 분석 — FormSchema 응답 (sections + questions)."""
    r = client.post("/api/analysis/parse-form",
                    json={"session_id": session_id, "form_text": "sample", "form_name": "test.pdf"})
    assert r.status_code == 200
    data = r.json()
    assert "form_id" in data
    assert "sections" in data
    assert isinstance(data["sections"], list)


# 4. mapping pipeline (map-evidence + check-missing + map-eval-criteria)
def test_smoke_4_mapping_pipeline(client, session_id):
    """map-evidence → check-missing → map-eval-criteria 3 endpoint."""
    # map-evidence
    r = client.post("/api/analysis/map-evidence",
                    json={"session_id": session_id, "form_schema": {}, "evidence_list": []})
    assert r.status_code == 200
    map_data = r.json()
    assert "question_mappings" in map_data
    assert "coverage_rate" in map_data

    # check-missing (mapping_result 입력)
    r = client.post("/api/analysis/check-missing",
                    json={"session_id": session_id, "mapping_result": map_data})
    assert r.status_code == 200
    # check-missing 응답은 list 또는 {items: [...]}
    miss_data = r.json()
    assert isinstance(miss_data, (list, dict))

    # map-eval-criteria
    r = client.post("/api/analysis/map-eval-criteria",
                    json={"session_id": session_id, "notice_schema": {}, "form_schema": {}})
    assert r.status_code == 200
    ec_data = r.json()
    assert "mappings" in ec_data
    assert "total" in ec_data


# 5. missing (text + upload + bulk-upload + confirm)
def test_smoke_5_missing_lifecycle(client, session_id):
    """missing 4 action — text / upload / bulk-upload / confirm."""
    # text
    r = client.post("/api/analysis/missing/text",
                    json={"session_id": session_id, "question_id": "I-1", "content": "test"})
    assert r.status_code == 200
    text_data = r.json()
    assert "supplemental_id" in text_data
    assert text_data["status"] == "uploaded"

    # upload (단일 파일)
    r = client.post("/api/analysis/missing/upload",
                    json={"session_id": session_id, "question_id": "I-1",
                          "file_name": "test.pdf", "file_size_bytes": 100})
    assert r.status_code == 200
    upload_data = r.json()
    assert "file_id" in upload_data
    assert "supplemental_id" in upload_data

    # bulk-upload
    r = client.post("/api/analysis/missing/bulk-upload",
                    json={"session_id": session_id,
                          "files": [{"file_name": "a.pdf", "file_size_bytes": 1}],
                          "target_question_id": "I-1"})
    assert r.status_code == 200
    bulk_data = r.json()
    assert bulk_data["total_files"] == 1
    assert bulk_data["auto_matched"] >= 0  # confidence 0.85 (target 지정 시) → auto_match
    assert "results" in bulk_data

    # confirm correct
    sup_id = text_data["supplemental_id"]
    r = client.post("/api/analysis/missing/confirm",
                    json={"session_id": session_id, "supplemental_id": sup_id, "action": "correct"})
    assert r.status_code == 200
    confirm_data = r.json()
    assert confirm_data["supplemental_status"] == "converted"
    assert confirm_data["missing_status"] == "resolved"


# 6. confirm-step2
def test_smoke_6_confirm_step2(client, session_id):
    """Step 2 분석 확정 — session_status: confirmed."""
    r = client.post("/api/analysis/confirm-step2",
                    json={"session_id": session_id})
    assert r.status_code == 200
    data = r.json()
    assert data["session_status"] == "confirmed"
    assert data["next_step"] == "step3_draft"


# 7. write-draft-item (+ rewrite + approve)
def test_smoke_7_draft_lifecycle(client, session_id):
    """draft 3 action — write / rewrite / approve."""
    # write
    r = client.post("/api/analysis/write-draft-item",
                    json={"session_id": session_id,
                          "question": {"question_id": "I-1", "title": "test"},
                          "matched_evidence": [], "company_schema": {}, "notice_schema": {}})
    assert r.status_code == 200
    write_data = r.json()
    assert "draft_item_id" in write_data
    assert write_data["status"] in ("draft", "generated")

    # rewrite
    r = client.post("/api/analysis/rewrite-draft-item",
                    json={"session_id": session_id, "question_id": "I-1",
                          "current_draft": "test", "user_message": "shorter"})
    assert r.status_code == 200
    rewrite_data = r.json()
    assert "draft_item_id" in rewrite_data
    assert rewrite_data["version"] >= 1

    # approve
    r = client.post("/api/analysis/approve-draft-item",
                    json={"session_id": session_id, "question_id": "I-1"})
    assert r.status_code == 200
    approve_data = r.json()
    assert approve_data["status"] == "approved"
    assert approve_data["lock_on_reanalyze"] is True


# 9. files upload + list + delete (A1 multipart 영속화)
def test_smoke_9_files_upload_list_delete(client, session_id):
    """Phase 4-H A1 — multipart upload + JSON-piggyback 영속화 + restore + delete."""
    # upload notice
    files = {"file": ("notice.txt", b"sample notice text content", "text/plain")}
    data = {"session_id": session_id, "kind": "notice"}
    r = client.post("/api/analysis/files/upload", data=data, files=files)
    assert r.status_code == 200, f"upload 실패: {r.status_code} {r.text}"
    up = r.json()
    assert up["session_id"] == session_id
    assert up["kind"] == "notice"
    assert up["file_id"].startswith("f_")
    assert up["parse_success"] is True
    assert up["char_count"] > 0

    # upload form
    files2 = {"file": ("form.txt", b"submission form text", "text/plain")}
    data2 = {"session_id": session_id, "kind": "form"}
    r = client.post("/api/analysis/files/upload", data=data2, files=files2)
    assert r.status_code == 200
    form_file_id = r.json()["file_id"]

    # list — restore (영속화 검증)
    r = client.get("/api/analysis/files", params={"session_id": session_id})
    assert r.status_code == 200
    lst = r.json()
    assert lst["total"] == 2
    assert len(lst["items"]["notice"]) == 1
    assert len(lst["items"]["form"]) == 1
    # parsed_text 포함 검증
    assert lst["items"]["notice"][0]["parsed_text"] == "sample notice text content"

    # list kind 필터
    r = client.get("/api/analysis/files", params={"session_id": session_id, "kind": "notice"})
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # delete
    r = client.delete(f"/api/analysis/files/{form_file_id}",
                      params={"session_id": session_id})
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert r.json()["kind"] == "form"

    # 422 — kind 검증
    r = client.post("/api/analysis/files/upload",
                    data={"session_id": session_id, "kind": "reference"},
                    files={"file": ("x.txt", b"x", "text/plain")})
    assert r.status_code == 422


# 9b. parsed_text truncation (200K safety cap)
def test_smoke_9b_parsed_text_truncation(client, session_id):
    """A1 — 200K char safety cap 동작 검증.

    240K char txt 업로드 → parsed_text_truncated=true, stored=200_000.
    """
    big_text = ("가" * 240_000).encode("utf-8")  # 240K char (chr수 기준)
    files = {"file": ("big.txt", big_text, "text/plain")}
    data = {"session_id": session_id, "kind": "notice"}
    r = client.post("/api/analysis/files/upload", data=data, files=files)
    assert r.status_code == 200
    up = r.json()
    assert up["parse_success"] is True
    assert up["char_count"] == 240_000
    assert up["parsed_text_stored_char_count"] == 200_000
    assert up["parsed_text_truncated"] is True

    # list 응답에도 truncation 메타 + 잘린 parsed_text 보존
    r = client.get("/api/analysis/files",
                   params={"session_id": session_id, "kind": "notice"})
    assert r.status_code == 200
    items = r.json()["items"]["notice"]
    assert len(items) == 1
    att = items[0]
    assert att["parsed_text_truncated"] is True
    assert att["parsed_text_stored_char_count"] == 200_000
    assert att["char_count"] == 240_000
    assert len(att["parsed_text"]) == 200_000


# 10. drafts_preservation_policy (A2)
def test_smoke_10_drafts_policy(client, session_id):
    """A2 — PATCH drafts-policy + reanalyze 전달 → ApplicationSession 컬럼 갱신."""
    # PATCH drafts-policy 직접 호출
    r = client.patch(f"/api/analysis/sessions/{session_id}/drafts-policy",
                     json={"drafts_policy": "preserve"})
    assert r.status_code == 200
    assert r.json()["drafts_preservation_policy"] == "preserve"

    # GET session으로 영속화 확인
    r = client.get(f"/api/analysis/sessions/{session_id}")
    assert r.status_code == 200
    assert r.json()["drafts_preservation_policy"] == "preserve"

    # reanalyze에 drafts_policy 전달 시도 (discard로 변경)
    r = client.post("/api/analysis/reanalyze",
                    json={"session_id": session_id, "target": "missing",
                          "drafts_policy": "discard"})
    assert r.status_code == 200
    assert r.json()["drafts_preservation_policy"] == "discard"

    # GET session으로 reanalyze가 갱신했는지 재확인
    r = client.get(f"/api/analysis/sessions/{session_id}")
    assert r.json()["drafts_preservation_policy"] == "discard"

    # drafts_policy 미전달 시 기존 값 유지
    r = client.post("/api/analysis/reanalyze",
                    json={"session_id": session_id, "target": "missing"})
    assert r.status_code == 200
    assert r.json()["drafts_preservation_policy"] == "discard"

    # enum validation (422)
    r = client.patch(f"/api/analysis/sessions/{session_id}/drafts-policy",
                     json={"drafts_policy": "invalid_value"})
    assert r.status_code == 422


# 11. CompanyFile (A3) — upload + list + get + delete
def test_smoke_11_company_files(client):
    """A3 — CompanyFile multipart 업로드 + 디스크 BLOB + parsed_text 영속화."""
    # upload
    files = {"file": ("company_intro.txt", "회사 소개 텍스트".encode("utf-8"), "text/plain")}
    data = {"file_type": "회사소개서", "company_profile_id": "pytest_company"}
    r = client.post("/api/company/files", data=data, files=files)
    assert r.status_code == 200, f"upload 실패: {r.status_code} {r.text}"
    up = r.json()
    assert up["file_id"].startswith("cf_")
    assert up["file_type"] == "회사소개서"
    assert up["parse_success"] is True
    file_id = up["file_id"]

    # list
    r = client.get("/api/company/files", params={"company_profile_id": "pytest_company"})
    assert r.status_code == 200
    lst = r.json()
    assert lst["total"] >= 1
    found = [it for it in lst["items"] if it["file_id"] == file_id]
    assert len(found) == 1

    # list filter by file_type
    r = client.get("/api/company/files",
                   params={"company_profile_id": "pytest_company", "file_type": "특허"})
    assert r.status_code == 200
    assert all(it["file_type"] == "특허" for it in r.json()["items"])

    # get (parsed_text 포함)
    r = client.get(f"/api/company/files/{file_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["parsed_text"] == "회사 소개 텍스트"

    # delete
    r = client.delete(f"/api/company/files/{file_id}")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # delete 후 404
    r = client.get(f"/api/company/files/{file_id}")
    assert r.status_code == 404

    # invalid file_type → 422
    r = client.post("/api/company/files",
                    data={"file_type": "invalid", "company_profile_id": "pytest_company"},
                    files={"file": ("x.txt", b"x", "text/plain")})
    assert r.status_code == 422


# 12. PATCH /eval-criteria-mappings (v0.2.1 V1 — 평가기준 매핑 사용자 편집)
def test_smoke_12_eval_criteria_user_edit(client, session_id):
    """v0.2.1 V1 — upsert (생성/갱신) + mapped_by=user + history + list 검증."""
    import uuid as _uuid
    cid = f"crit_test_{_uuid.uuid4().hex[:8]}"

    # 1) PATCH 신규 생성 — criteria_name 필수
    r = client.patch(f"/api/analysis/eval-criteria-mappings/{cid}",
                     json={
                         "session_id": session_id,
                         "criteria_name": "시장성",
                         "weight": 30,
                         "scope": "section",
                         "mapped_questions": ["I-1", "I-2"],
                         "confidence": 0.85,
                         "reason": "사용자 직접 매핑",
                     })
    assert r.status_code == 200, f"신규 생성 실패: {r.status_code} {r.text}"
    data = r.json()
    assert data["created"] is True
    assert data["mapped_by"] == "user"
    assert data["scope"] == "section"
    assert data["mapped_questions"] == ["I-1", "I-2"]
    assert data["confidence"] == 0.85
    # V2: 신규 생성 시 history 1건 (action=create)
    assert data["history_count"] == 1
    assert data["history"][0]["action"] == "create"
    assert data["history"][0]["by"] == "user"

    # 2) PATCH 부분 갱신 — scope만 변경
    r = client.patch(f"/api/analysis/eval-criteria-mappings/{cid}",
                     json={"session_id": session_id, "scope": "question"})
    assert r.status_code == 200
    data = r.json()
    assert data["created"] is False
    assert data["scope"] == "question"
    # 다른 필드 보존
    assert data["criteria_name"] == "시장성"
    assert data["mapped_questions"] == ["I-1", "I-2"]
    assert data["mapped_by"] == "user"
    # V2: history 2건 (create + update with scope diff)
    assert data["history_count"] == 2
    assert data["history"][1]["action"] == "update"
    assert "scope" in data["history"][1]["changes"]
    assert data["history"][1]["changes"]["scope"] == ["section", "question"]

    # 2b) 동일 값 PATCH → history 추가 안 됨 (no-op detection)
    r = client.patch(f"/api/analysis/eval-criteria-mappings/{cid}",
                     json={"session_id": session_id, "scope": "question"})
    assert r.status_code == 200
    assert r.json()["history_count"] == 2  # 변경 없으면 append X

    # 3) GET list — 1개 반환
    r = client.get("/api/analysis/eval-criteria-mappings",
                   params={"session_id": session_id})
    assert r.status_code == 200
    lst = r.json()
    assert lst["total"] == 1
    assert lst["items"][0]["criteria_id"] == cid
    assert lst["items"][0]["scope"] == "question"
    assert lst["items"][0]["history_count"] == 2

    # 4) confidence 범위 422
    r = client.patch(f"/api/analysis/eval-criteria-mappings/{cid}",
                     json={"session_id": session_id, "confidence": 1.5})
    assert r.status_code == 422

    # 5) 신규 생성 시 criteria_name 없으면 422
    r = client.patch("/api/analysis/eval-criteria-mappings/crit_no_name",
                     json={"session_id": session_id, "scope": "document"})
    assert r.status_code == 422

    # 6) scope enum 422
    r = client.patch(f"/api/analysis/eval-criteria-mappings/{cid}",
                     json={"session_id": session_id, "scope": "invalid"})
    assert r.status_code == 422

    # 7) session not found 404
    r = client.patch(f"/api/analysis/eval-criteria-mappings/{cid}",
                     json={"session_id": "no_such_session", "scope": "document"})
    assert r.status_code == 404


# 10b. read/write 분리 — PATCH로 저장된 값을 reanalyze(미전달)가 읽는지
def test_smoke_10b_drafts_policy_read_from_patch(client, session_id):
    """A2 — PATCH로만 저장된 값을 reanalyze가 정확히 read 하는지 검증.

    test_smoke_10은 reanalyze 자기일관성만 검증. 본 테스트는 PATCH와 reanalyze의
    read/write 분리 자체를 보장 (모달 시점 PATCH + 사용자 재분석 시점 read).
    """
    # PATCH만 호출 (reanalyze 사이드이펙트 X)
    r = client.patch(f"/api/analysis/sessions/{session_id}/drafts-policy",
                     json={"drafts_policy": "preserve"})
    assert r.status_code == 200

    # reanalyze drafts_policy 미전달 → 응답이 PATCH로 저장된 값과 일치해야
    r = client.post("/api/analysis/reanalyze",
                    json={"session_id": session_id, "target": "missing"})
    assert r.status_code == 200
    assert r.json()["drafts_preservation_policy"] == "preserve"


# 8. export-docx (no LLM 게이트)
def test_smoke_8_export_docx(client, session_id):
    """Step 5 export — no LLM (test_03 §3.11.5 게이트).

    응답에 LLM 비용 필드가 없어야 함 (정책 부합).
    """
    r = client.post("/api/analysis/export-docx",
                    json={"session_id": session_id, "include_table_data": True})
    assert r.status_code == 200
    data = r.json()
    assert "export_id" in data
    assert data["status"] == "ready"
    assert "file_url" in data
    assert "file_name" in data
    # no LLM 게이트 — LLM 비용 / token usage 필드가 없어야 함
    assert "input_tokens" not in data
    assert "output_tokens" not in data
    assert "cost_estimate_krw" not in data
