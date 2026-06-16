"""
북마크 CRUD API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Bookmark
from schemas import BookmarkCreate, BookmarkOut

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


@router.get("", response_model=List[BookmarkOut])
def get_bookmarks(db: Session = Depends(get_db)):
    """전체 북마크 목록"""
    return db.query(Bookmark).order_by(Bookmark.created_at.desc()).all()


@router.post("", response_model=BookmarkOut)
def add_bookmark(body: BookmarkCreate, db: Session = Depends(get_db)):
    """북마크 추가"""
    existing = db.query(Bookmark).filter(Bookmark.notice_id == body.notice_id).first()
    if existing:
        return existing  # 이미 있으면 그대로 반환
    bm = Bookmark(notice_id=body.notice_id, notice_snapshot=body.notice_snapshot)
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return bm


@router.delete("", response_model=dict)
def clear_bookmarks(db: Session = Depends(get_db)):
    """북마크 전체 삭제"""
    count = db.query(Bookmark).delete()
    db.commit()
    return {"deleted_count": count}


@router.delete("/{notice_id}", response_model=dict)
def remove_bookmark(notice_id: str, db: Session = Depends(get_db)):
    """북마크 제거"""
    bm = db.query(Bookmark).filter(Bookmark.notice_id == notice_id).first()
    if not bm:
        raise HTTPException(status_code=404, detail="북마크가 없습니다.")
    db.delete(bm)
    db.commit()
    return {"deleted": notice_id}
