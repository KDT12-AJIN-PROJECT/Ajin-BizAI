"""
v0.2 자료실(Materials Library) 통합 API — 2026-05-25.

PRD m-2 (`local/1_PRD/v3.2/m-2_materials_library_submission_checklist.md`) 기반.
사용자 명시: PDF 업로드 → 자동 텍스트 추출 → DB 영속화 → 자료실 UI에서 리스트/preview.

설계 결정:
- 기존 `company_files` 테이블 재활용 (parsed_text 컬럼 이미 존재, migration 0004)
- `file_type` 컬럼을 카테고리 enum으로 확장 ("회사자료" | "첨부자료" | "필요자료")
  - 기존 세부 type (회사소개서/재무제표/...) 은 모두 "회사자료" 그룹으로 매핑
- 새 라우터로 분리해 company.py 기존 동작 보존

Endpoints:
  POST   /api/library/files               업로드 (multipart, category 지정)
  GET    /api/library/files?category=&sort=  리스트 (필터 + 정렬)
  GET    /api/library/files/{file_id}     상세 (parsed_text 포함)
  DELETE /api/library/files/{file_id}     soft delete (status='deleted')
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import CompanyFile
from routers.files import parse_upload_bytes

router = APIRouter(prefix="/api/library", tags=["library"])

STORAGE_ROOT = os.path.join(os.path.dirname(__file__), "..", "data", "uploads", "company")
DEFAULT_PROFILE_ID = "anonymous"

# 자료실 카테고리 (사용자 요청: 회사 자료 / 첨부 자료 / 필요 자료)
LIBRARY_CATEGORIES = {"회사자료", "첨부자료", "필요자료"}

# 기존 company.py 의 세부 type → "회사자료" 그룹 매핑
LEGACY_COMPANY_TYPES = {"회사소개서", "재무제표", "사업자등록증", "특허", "기타"}


def _classify(file_type: str) -> str:
    """저장된 file_type을 자료실 카테고리로 환산."""
    if file_type in LIBRARY_CATEGORIES:
        return file_type
    if file_type in LEGACY_COMPANY_TYPES:
        return "회사자료"
    return "회사자료"  # default


def _to_dict(cf: CompanyFile, include_text: bool = False) -> dict:
    text = cf.parsed_text or ""
    preview = text[:500] if text else ""
    data = {
        "file_id": cf.file_id,
        "file_name": cf.file_name,
        "category": _classify(cf.file_type or ""),
        "raw_file_type": cf.file_type or "",
        "ext": cf.ext or "",
        "file_size_bytes": cf.file_size_bytes or 0,
        "char_count": cf.char_count or 0,
        "parsed_text_truncated": bool(cf.parsed_text_truncated),
        "parse_success": bool(cf.parse_success),
        "warning": cf.warning,
        "status": cf.status,
        "uploaded_at": cf.uploaded_at.isoformat() if cf.uploaded_at else None,
        "updated_at": cf.updated_at.isoformat() if cf.updated_at else None,
        "preview": preview,
    }
    if include_text:
        data["parsed_text"] = text
    return data


@router.post("/files")
async def upload_library_file(
    file: UploadFile = File(...),
    category: str = Form("회사자료"),
    company_profile_id: str = Form(DEFAULT_PROFILE_ID),
    db: Session = Depends(get_db),
) -> dict:
    if category not in LIBRARY_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"category는 {sorted(LIBRARY_CATEGORIES)} 중 하나여야 합니다: {category}",
        )

    content = await file.read()
    parsed = parse_upload_bytes(file.filename or "", content)

    file_id = f"lf_{uuid.uuid4().hex[:12]}"

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
        file_type=category,
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
def list_library_files(
    category: Optional[str] = None,
    sort: str = "recent",  # recent | name
    company_profile_id: str = DEFAULT_PROFILE_ID,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(CompanyFile).filter(
        CompanyFile.company_profile_id == company_profile_id,
        CompanyFile.status == "active",
    )

    # 카테고리 필터 — "회사자료" 면 legacy type까지 포함, 그 외는 정확 매칭
    if category and category != "전체":
        if category not in LIBRARY_CATEGORIES:
            raise HTTPException(status_code=422, detail=f"unknown category: {category}")
        if category == "회사자료":
            query = query.filter(CompanyFile.file_type.in_(list(LEGACY_COMPANY_TYPES | {"회사자료"})))
        else:
            query = query.filter(CompanyFile.file_type == category)

    items = query.all()

    if sort == "name":
        items.sort(key=lambda c: (c.file_name or "").lower())
    else:  # recent
        items.sort(key=lambda c: c.uploaded_at or 0, reverse=True)

    return {
        "company_profile_id": company_profile_id,
        "category": category or "전체",
        "sort": sort,
        "total": len(items),
        "items": [_to_dict(c, include_text=False) for c in items],
    }


@router.get("/files/{file_id}")
def get_library_file(
    file_id: str,
    db: Session = Depends(get_db),
) -> dict:
    cf = db.query(CompanyFile).filter(CompanyFile.file_id == file_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail=f"library file not found: {file_id}")
    return _to_dict(cf, include_text=True)


@router.delete("/files/{file_id}")
def delete_library_file(
    file_id: str,
    db: Session = Depends(get_db),
) -> dict:
    cf = db.query(CompanyFile).filter(CompanyFile.file_id == file_id).first()
    if not cf:
        raise HTTPException(status_code=404, detail=f"library file not found: {file_id}")
    cf.status = "deleted"
    db.commit()
    return {"file_id": file_id, "deleted": True}
