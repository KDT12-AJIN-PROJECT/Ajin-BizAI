"""
AJIN BizAI — FastAPI 백엔드
파일 파싱 + AI 진단 + DB 연동 API 서버
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import files, diagnosis
from routers import notices, drafts, bookmarks, ai, profile
from routers import analysis  # v0.2 분석 API (PRD §16.1)
from routers import chat  # v0.2 AI 보완 대화 API (PRD §16.5)
from routers import company  # v0.2 기업프로필 자료 API (PRD §13.10) — Phase 4-H A3
from routers import library  # 자료실 통합 API (m-2, 2026-05-25)

# DB 테이블 자동 생성 (없으면 만들고, 있으면 그대로)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AJIN BizAI Backend",
    version="1.1.0",
    docs_url="/api/docs",
)

# ─── CORS (dev / prod 분리) ───────────────────────────
# APP_ENV: development (default) | production
#   - development: localhost / 127.0.0.1 모든 dev 포트 허용 (Vite fallback 5173→5175→… 대응)
#   - production : CORS_ALLOWED_ORIGINS 환경변수에 명시된 origin만 허용 (비어 있으면 startup error)
# 모바일/QR/LAN(192.168.*.*) 미고려 — 필요 시 별도 정책.
import os as _os
_app_env = _os.getenv("APP_ENV", "development").strip().lower()

if _app_env == "production":
    _origins_str = _os.getenv("CORS_ALLOWED_ORIGINS", "")
    _allowed_origins = [o.strip() for o in _origins_str.split(",") if o.strip()]
    if not _allowed_origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS is required in production")
    _cors_kwargs = {"allow_origins": _allowed_origins}
else:
    _cors_kwargs = {
        "allow_origin_regex": r"^https?://(localhost|127\.0\.0\.1):\d+$",
    }

app.add_middleware(
    CORSMiddleware,
    **_cors_kwargs,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(files.router)
app.include_router(diagnosis.router)
app.include_router(notices.router)
app.include_router(drafts.router)
app.include_router(bookmarks.router)
app.include_router(ai.router)
app.include_router(profile.router)
app.include_router(analysis.router)  # v0.2 /api/analysis/*
app.include_router(chat.router)  # v0.2 /api/chat/*
app.include_router(company.router)  # v0.2 /api/company/* (A3)
app.include_router(library.router)  # /api/library/* (자료실 통합)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "1.1.0"}
