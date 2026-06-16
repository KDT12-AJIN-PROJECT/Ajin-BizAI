"""
기업 프로필 API
단일 행(id=1)으로 관리 — GET으로 불러오고, PUT으로 저장합니다.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Profile
from schemas import ProfileUpsert, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _get_or_create(db: Session) -> Profile:
    profile = db.query(Profile).filter(Profile.id == 1).first()
    if not profile:
        profile = Profile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    """저장된 프로필 조회. 없으면 기본값으로 생성."""
    return _get_or_create(db)


@router.put("", response_model=ProfileOut)
def save_profile(body: ProfileUpsert, db: Session = Depends(get_db)):
    """프로필 저장 (없으면 생성, 있으면 업데이트)."""
    profile = _get_or_create(db)
    for key, val in body.model_dump().items():
        setattr(profile, key, val)
    db.commit()
    db.refresh(profile)
    return profile
