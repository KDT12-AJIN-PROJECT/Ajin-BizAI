"""
초안(Draft) CRUD + 버전 관리 API
라우트 등록 순서 (FastAPI 매칭 우선순위):
  1. 고정 경로: /list, /permanent/bulk
  2. notice_id 하위: /{notice_id}/versions
  3. draft_id 기반: /by-id/{draft_id}/status, /by-id/{draft_id}/result,
                    /by-id/{draft_id}/archive, /by-id/{draft_id}/restore,
                    /by-id/{draft_id}/permanent
  4. 기존 호환 경로 (마지막): /{notice_id}
"""

# 기술부채 메모 (v1.1 대상):
# - /api/drafts/{notice_id} 경로를 /api/drafts/by-id/{id} 중심으로 통합 예정
# - DraftListPage와 MyDraftsPage 공통 hook(useMyDrafts)으로 일원화 예정

# ─────────────────────────────────────────────────────────────────────
# LEGACY READ-ONLY (v3.2 M-0)
# ─────────────────────────────────────────────────────────────────────
# 이 라우터(/api/drafts/*)는 legacy V1 흐름 전용이다.
# 신규 작성 흐름의 단일 출처는 ApplicationSession이며,
# 신규 초안 작성·평가·export는 form_schema_json["draft_items"]만 사용한다.
#
# 정책:
#   - read-only 보존: 삭제하지 않고 그대로 유지
#   - 신규 작업은 본 라우터를 호출하지 않음 (코드 컨벤션)
#   - 런타임 차단 (410 Gone 등)은 M-1 범위에서 검토 — 이번 M-0에서는 미적용
# ─────────────────────────────────────────────────────────────────────

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Draft
from schemas import (
    DraftListItem,
    DraftOut,
    DraftResultUpdate,
    DraftStatusUpdate,
    DraftUpsert,
    DraftVersionCreate,
)

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


# ─── 1. 고정 경로 ──────────────────────────────────────────────────────────

@router.get("/list")
def list_drafts(
    status: Optional[str] = Query(None),
    archived: Optional[bool] = Query(None),
    sort: str = Query("updated_desc"),
    db: Session = Depends(get_db),
):
    """
    MyDraftsPage용 목록 API.
    notice_id 단위로 그룹핑하여 최신 버전을 대표로 반환.
    query params:
      - status: 작성중 | 작성완료 | 제출완료 | 채택 | 미채택 | 미제출
      - archived: true/false
      - sort: updated_desc (기본) | deadline_asc
    """
    q = db.query(Draft)
    if archived is not None:
        q = q.filter(Draft.is_archived == archived)
    if status:
        q = q.filter(Draft.status == status)

    all_drafts = q.order_by(Draft.notice_id, Draft.version).all()

    # notice_id 그룹핑: 최신 버전을 대표, 이전 버전을 all_versions에 포함
    groups: dict[str, list[Draft]] = {}
    for d in all_drafts:
        groups.setdefault(d.notice_id, []).append(d)

    result = []
    for nid, versions in groups.items():
        versions_sorted = sorted(versions, key=lambda x: x.version, reverse=True)
        latest = versions_sorted[0]
        older = versions_sorted[1:]
        item = DraftListItem(
            id=latest.id,
            notice_id=latest.notice_id,
            notice_snapshot=latest.notice_snapshot or {},
            current_step=latest.current_step,
            version=latest.version,
            status=latest.status or '작성중',
            submitted_at=latest.submitted_at,
            result=latest.result,
            result_date=latest.result_date,
            result_memo=latest.result_memo,
            is_archived=latest.is_archived or False,
            updated_at=latest.updated_at,
            all_versions=[
                {
                    "id": v.id,
                    "version": v.version,
                    "status": v.status,
                    "submitted_at": v.submitted_at.isoformat() if v.submitted_at else None,
                    "result": v.result,
                    "version_note": v.version_note,
                    "updated_at": v.updated_at.isoformat() if v.updated_at else None,
                }
                for v in versions_sorted
            ],
        )
        result.append(item)

    return result


@router.delete("/permanent/bulk")
def bulk_permanent_delete(body: dict, db: Session = Depends(get_db)):
    """보관함 일괄 영구 삭제. body: { ids: [1, 2, 3] }"""
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="ids가 비어있습니다.")
    deleted = db.query(Draft).filter(Draft.id.in_(ids), Draft.is_archived == True).all()
    if len(deleted) != len(ids):
        raise HTTPException(status_code=400, detail="일부 ID가 보관함에 없거나 존재하지 않습니다.")
    for d in deleted:
        db.delete(d)
    db.commit()
    return {"deleted_ids": ids}


# ─── 2. notice_id 하위 고정 경로 ──────────────────────────────────────────

@router.post("/{notice_id}/versions")
def create_version(notice_id: str, body: DraftVersionCreate, db: Session = Depends(get_db)):
    """
    새 버전 만들기. 최신 버전을 복제하여 max_version+1 생성.
    - v3 초과 시 409 + 기존 버전 목록 반환 (프론트에서 교체 버전 선택 후 재호출)
    - replace_version 지정 시 해당 버전 삭제 후 신규 생성 (v4 교체 처리)
    """
    existing = (
        db.query(Draft)
        .filter(Draft.notice_id == notice_id)
        .order_by(Draft.version.desc())
        .all()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="해당 notice_id의 초안이 없습니다.")

    max_version = existing[0].version

    if max_version >= 3 and body.replace_version is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "max_version_reached",
                "message": "버전이 3개입니다. 교체할 버전을 선택하세요.",
                "versions": [
                    {"id": v.id, "version": v.version, "version_note": v.version_note}
                    for v in existing
                ],
            },
        )

    if body.replace_version is not None:
        to_delete = next((v for v in existing if v.version == body.replace_version), None)
        if not to_delete:
            raise HTTPException(status_code=404, detail=f"v{body.replace_version}이 없습니다.")
        db.delete(to_delete)
        db.commit()
        new_version = body.replace_version
    else:
        new_version = max_version + 1

    source = existing[0]  # 최신 버전 복제
    new_draft = Draft(
        notice_id=notice_id,
        notice_snapshot=source.notice_snapshot,
        current_step=1,
        completed_steps=[],
        uploads={},
        drafts={},
        version=new_version,
        status='작성중',
        parent_draft_id=source.id,
        version_note=body.version_note,
    )
    db.add(new_draft)
    db.commit()
    db.refresh(new_draft)
    return new_draft


# ─── 3. draft_id(정수 PK) 기반 경로 /by-id/{draft_id}/... ────────────────

@router.put("/by-id/{draft_id}/status")
def update_status(draft_id: int, body: DraftStatusUpdate, db: Session = Depends(get_db)):
    """상태 변경. status: 작성중 | 작성완료 | 제출완료 | 채택 | 미채택 | 미제출"""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    draft.status = body.status
    if body.result_memo:
        draft.result_memo = body.result_memo
    if body.status == '제출완료' and not draft.submitted_at:
        draft.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/by-id/{draft_id}/result")
def update_result(draft_id: int, body: DraftResultUpdate, db: Session = Depends(get_db)):
    """결과 입력. 미채택 시 is_archived=True 자동 처리."""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    draft.result = body.result
    draft.result_date = body.result_date or datetime.utcnow()
    if body.result_memo:
        draft.result_memo = body.result_memo
    draft.status = body.result  # '채택' or '미채택'
    if body.result == '미채택':
        draft.is_archived = True
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/by-id/{draft_id}/archive")
def archive_draft(draft_id: int, db: Session = Depends(get_db)):
    """보관함 이동. 작성중/작성완료 → is_archived=True, status='미제출'."""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    if draft.status in ('채택', '미채택'):
        raise HTTPException(status_code=400, detail="채택/미채택 상태는 보관함 이동을 사용하지 않습니다.")
    draft.is_archived = True
    if draft.status in ('작성중', '작성완료'):
        draft.status = '미제출'
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/by-id/{draft_id}/restore")
def restore_draft(draft_id: int, db: Session = Depends(get_db)):
    """보관함 복원. 미채택 상태는 복원 불가."""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    if draft.status == '미채택':
        raise HTTPException(status_code=400, detail="미채택 항목은 복원할 수 없습니다.")
    draft.is_archived = False
    if draft.status == '미제출':
        draft.status = '작성중'
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/by-id/{draft_id}/permanent")
def permanent_delete(draft_id: int, db: Session = Depends(get_db)):
    """영구 삭제 (보관함에서만 가능)."""
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    if not draft.is_archived:
        raise HTTPException(status_code=400, detail="보관함에 있는 초안만 영구 삭제할 수 있습니다.")
    db.delete(draft)
    db.commit()
    return {"deleted_id": draft_id}


# ─── 4. 기존 호환 경로 (DraftPage 사용 중 — 마지막에 등록) ────────────────

@router.get("", response_model=List[DraftOut])
def get_all_drafts(db: Session = Depends(get_db)):
    """전체 초안 목록 (최신 updated_at 순). DashboardPage / DraftListPage 용."""
    return db.query(Draft).order_by(Draft.updated_at.desc()).all()


@router.get("/{notice_id}", response_model=DraftOut)
def get_draft(notice_id: str, db: Session = Depends(get_db)):
    """특정 공고의 최신 버전 조회 (MAX version). 기존 DraftPage 호환."""
    draft = (
        db.query(Draft)
        .filter(Draft.notice_id == notice_id)
        .order_by(Draft.version.desc())
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    return draft


@router.put("/{notice_id}", response_model=DraftOut)
def upsert_draft(notice_id: str, body: DraftUpsert, db: Session = Depends(get_db)):
    """
    최신 버전 저장 또는 신규 생성 (upsert). 기존 DraftPage 호환.
    - 없으면 version=1 신규 생성
    - 있으면 MAX(version) 업데이트
    - body.status 포함 시 함께 업데이트 (Step5 완료 처리)
    """
    draft = (
        db.query(Draft)
        .filter(Draft.notice_id == notice_id)
        .order_by(Draft.version.desc())
        .first()
    )
    if draft:
        # Preserve the original notice snapshot once a draft exists.
        # If a legacy row has no snapshot, allow a one-time backfill.
        if not draft.notice_snapshot and body.notice_snapshot:
            draft.notice_snapshot = body.notice_snapshot
        draft.current_step = body.current_step
        draft.completed_steps = body.completed_steps
        draft.uploads = body.uploads
        draft.drafts = body.drafts
        if body.status:
            draft.status = body.status
    else:
        draft = Draft(
            notice_id=notice_id,
            notice_snapshot=body.notice_snapshot,
            current_step=body.current_step,
            completed_steps=body.completed_steps,
            uploads=body.uploads,
            drafts=body.drafts,
            version=1,
            status=body.status or '작성중',
        )
        db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{notice_id}", response_model=dict)
def delete_draft(notice_id: str, db: Session = Depends(get_db)):
    """최신 버전 삭제. 기존 DraftPage 호환."""
    draft = (
        db.query(Draft)
        .filter(Draft.notice_id == notice_id)
        .order_by(Draft.version.desc())
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="초안이 없습니다.")
    db.delete(draft)
    db.commit()
    return {"deleted": notice_id}
