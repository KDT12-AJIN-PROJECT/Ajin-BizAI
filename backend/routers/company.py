"""
v0.2 기업프로필 자료 API (PRD §13.10 / §3.2) — Phase 4-H A3.

CompanyFile 라이프사이클:
  - POST   /api/company/files          업로드 (multipart, 디스크 BLOB + parsed_text 영속화)
  - GET    /api/company/files          사용자별 목록
  - GET    /api/company/files/{id}     단일 조회 (parsed_text 포함)
  - DELETE /api/company/files/{id}     삭제 (디스크 BLOB + DB row)

Storage:
  - 메타 + parsed_text → SQLite (company_files 테이블)
  - 원본 BLOB → 디스크 (data/uploads/company/{company_profile_id}/{file_id}.{ext})

v0.2 user 모델:
  - auth 미구현 → company_profile_id = "anonymous" 고정
  - 향후 middleware에서 인증 후 주입
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import CompanyFile
from routers.files import parse_upload_bytes

router = APIRouter(prefix="/api/company", tags=["company"])

# 디스크 BLOB storage root
STORAGE_ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "uploads", "company")

# v0.2 단일 사용자
DEFAULT_PROFILE_ID = "anonymous"

ALLOWED_FILE_TYPES = {"회사소개서", "재무제표", "사업자등록증", "특허", "기타"}


def _to_dict(cf: CompanyFile, include_text: bool = True) -> dict:
    data = {
        "file_id": cf.file_id,
        "company_profile_id": cf.company_profile_id,
        "file_name": cf.file_name,
        "file_type": cf.file_type,
        "ext": cf.ext or "",
        "file_size_bytes": cf.file_size_bytes or 0,
        "char_count": cf.char_count or 0,
        "parsed_text_stored_char_count": cf.parsed_text_stored_char_count or 0,
        "parsed_text_truncated": bool(cf.parsed_text_truncated),
        "parse_success": bool(cf.parse_success),
        "warning": cf.warning,
        "status": cf.status,
        "tags": cf.tags or [],
        "uploaded_at": cf.uploaded_at.isoformat() if cf.uploaded_at else None,
        "updated_at": cf.updated_at.isoformat() if cf.updated_at else None,
    }
    if include_text:
        data["parsed_text"] = cf.parsed_text or ""
    return data


@router.post("/files")
async def upload_company_file(
    file: UploadFile = File(...),
    file_type: str = Form("기타"),
    company_profile_id: str = Form(DEFAULT_PROFILE_ID),
    db: Session = Depends(get_db),
) -> dict:
    """CompanyFile 업로드 — multipart + 디스크 BLOB 영속화."""
    if file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"file_type은 {sorted(ALLOWED_FILE_TYPES)} 중 하나여야 합니다: {file_type}",
        )

    content = await file.read()
    parsed = parse_upload_bytes(file.filename or "", content)

    file_id = f"cf_{uuid.uuid4().hex[:12]}"

    # 디스크 BLOB 저장
    profile_dir = os.path.join(STORAGE_ROOT, company_profile_id)
    os.makedirs(profile_dir, exist_ok=True)
    ext = parsed["ext"] or ""
    storage_path = os.path.join("company", company_profile_id, f"{file_id}{ext}")
    abs_path = os.path.join(profile_dir, f"{file_id}{ext}")
    with open(abs_path, "wb") as f:
        f.write(content)

    cf = CompanyFile(
        file_id=file_id,
        company_profile_id=company_profile_id,
        file_name=parsed["filename"],
        file_size_bytes=parsed["size_bytes"],
        file_storage_path=storage_path,
        file_type=file_type,
        uploaded_by=company_profile_id,
        status="active",
        ext=parsed["ext"],
        parsed_text=parsed["parsed_text"],
        char_count=parsed["char_count"],
        parsed_text_stored_char_count=parsed["parsed_text_stored_char_count"],
        parsed_text_truncated=parsed["parsed_text_truncated"],
        parse_success=parsed["parse_success"],
        warning=parsed["warning"],
    )
    db.add(cf)
    db.commit()
    db.refresh(cf)

    return _to_dict(cf, include_text=False)


@router.get("/files")
def list_company_files(
    company_profile_id: str = DEFAULT_PROFILE_ID,
    file_type: Optional[str] = None,
    status: Optional[str] = "active",
    db: Session = Depends(get_db),
) -> dict:
    """CompanyFile 목록 — Step1Common 카드 4번에서 호출."""
    query = db.query(CompanyFile).filter(
        CompanyFile.company_profile_id == company_profile_id
    )
    if file_type:
        query = query.filter(CompanyFile.file_type == file_type)
    if status:
        query = query.filter(CompanyFile.status == status)

    items = query.order_by(CompanyFile.uploaded_at.desc()).all()
    return {
        "company_profile_id": company_profile_id,
        "total": len(items),
        "items": [_to_dict(cf, include_text=False) for cf in items],
    }


@router.get("/files/{file_id}")
def get_company_file(
    file_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """CompanyFile 단일 조회 — parsed_text 포함."""
    cf = db.query(CompanyFile).filter(CompanyFile.file_id == file_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail=f"company file not found: {file_id}")
    return _to_dict(cf, include_text=True)


@router.delete("/files/{file_id}")
def delete_company_file(
    file_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """CompanyFile 삭제 — 디스크 BLOB + DB row."""
    cf = db.query(CompanyFile).filter(CompanyFile.file_id == file_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail=f"company file not found: {file_id}")

    # 디스크 BLOB 삭제 (있으면)
    if cf.file_storage_path:
        # storage_path = "company/{profile}/{file_id}.{ext}" → STORAGE_ROOT 기준 상대
        # STORAGE_ROOT = .../backend/data/uploads/company → 첫 segment "company"는 제거
        rel = cf.file_storage_path.replace("\\", "/").split("/", 1)[1] if "/" in cf.file_storage_path else cf.file_storage_path
        abs_path = os.path.join(STORAGE_ROOT, rel)
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        except OSError as e:
            print(f"[COMPANY_FILE_DELETE_DISK_FAIL] {file_id}: {e}")

    db.delete(cf)
    db.commit()
    return {"file_id": file_id, "deleted": True}
