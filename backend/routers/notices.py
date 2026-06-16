"""
공고 캐시 API
외부 공공 API에서 공고를 수집하고 DB에 저장·조회합니다.
"""
import os
import re
import asyncio
from datetime import datetime
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Notice
from schemas import NoticeCreate, NoticeOut

router = APIRouter(prefix="/api/notices", tags=["notices"])

GONGGONG_API_KEY = os.getenv("GONGGONG_API_KEY", "")
BIZINFO_API_KEY = os.getenv("BIZINFO_API_KEY", "")

# ── 정규화 헬퍼 ─────────────────────────────────────────────────────────────

def _strip_html(value) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", text).strip()


def _normalize_period(raw) -> str:
    text = _strip_html(raw or "")
    return text or "상세공고 참조"


def _parse_date(text: str):
    if not text:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except (ValueError, AttributeError):
            pass
    return None


def _extract_date(period: str):
    if "~" in period:
        date_part = period.split("~")[-1].strip()
    else:
        dates = re.findall(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", period)
        date_part = dates[-1] if dates else ""
    return _parse_date(date_part)


def _extract_first_file(item: dict) -> tuple[str, str]:
    """과기부 등 nested files 구조에서 첫 번째 파일명/URL 추출."""
    files = item.get("files") or []
    if isinstance(files, list) and files:
        f = files[0]
        if isinstance(f, dict):
            inner = f.get("file") or f
            return (inner.get("fileName") or ""), (inner.get("fileUrl") or "")
    return "", ""


def _normalize_notice(item: dict, origin: str) -> dict:
    raw_title = (
        item.get("pblancNm") or item.get("title") or item.get("subject") or
        item.get("supt_biz_titl_nm") or item.get("btl") or item.get("announcementTitle") or ""
    )
    title = _strip_html(re.sub(r"\[.*?\]", "", str(raw_title)).strip()) or "제목 없음"

    # 기간: 각 API별 필드명 통합
    _start = item.get("applicationStartDate") or ""
    _end = item.get("applicationEndDate") or ""
    _app_period = (f"{_start}~{_end}" if _start or _end else "")
    period_raw = (
        item.get("reqstBeginEndDe") or item.get("reqstDt") or
        _app_period or item.get("pressDt") or ""
    )
    period = _normalize_period(period_raw)

    # URL
    url = (
        item.get("pblancUrl") or item.get("viewUrl") or item.get("link") or
        item.get("detailUrl") or item.get("detl_pg_url") or ""
    )
    if url and not url.startswith("http"):
        url = "https://" + url

    return {
        "id": f"{origin}-{title}-{period}",
        "origin": origin,
        "title": title,
        "full_title": str(raw_title),
        "target": _strip_html(
            item.get("trgetNm") or item.get("biz_supt_trgt_info") or "공고 참조"
        ),
        "benefit": _strip_html(
            item.get("suptCn") or item.get("biz_supt_ctnt") or
            item.get("biz_supt_bdgt_info") or "공고 요약 본문을 확인해 주세요."
        ),
        "limit": _strip_html(
            item.get("restr_cn") or item.get("biz_supt_trgt_excl_info") or "신청 제외 대상은 원본 공고를 참조하세요."
        ),
        "documents": _strip_html(item.get("subm_doc_nm") or "공고 본문을 확인해주세요"),
        "region": _strip_html(item.get("areaNm") or item.get("supt_regin") or "전국"),
        "url": url,
        "period": period,
        "date": _extract_date(period),
        "content": _strip_html(
            item.get("bsnsSumryCn") or item.get("supt_biz_intrd_info") or
            item.get("dataContents") or item.get("hashtags") or "상세 공고 페이지를 참조해 주세요."
        ),
        "jrsdInsttNm": _strip_html(item.get("jrsdInsttNm") or item.get("deptName") or ""),
        "excInsttNm": _strip_html(item.get("excInsttNm") or ""),
        "hashTags": _strip_html(item.get("hashTags") or ""),
        "printFileNm": _strip_html(item.get("printFileNm") or item.get("fileName") or _extract_first_file(item)[0] or ""),
        "printFlpthNm": item.get("printFlpthNm") or item.get("fileUrl") or _extract_first_file(item)[1] or "",
        "fileNm": item.get("fileNm") or "",
        "flpthNm": item.get("flpthNm") or "",
        "reqstMthPapersCn": _strip_html(item.get("reqstMthPapersCn") or ""),
        "refrncNm": _strip_html(item.get("refrncNm") or item.get("writerName") or ""),
        "rceptEngnHmpgUrl": item.get("rceptEngnHmpgUrl") or "",
        "category": _strip_html(
            item.get("pldirSportRealmLclasCodeNm") or item.get("biz_category_cd") or ""
        ),
        "ajin_similarity": 0.0,
    }


def _parse_items(agency: str, data: dict) -> list:
    if agency == "기업마당":
        return data.get("jsonArray") or data.get("items") or []

    if agency == "과기부":
        # response는 list: [{header}, {body}]
        response = data.get("response") or []
        body = {}
        if isinstance(response, list):
            for entry in response:
                if isinstance(entry, dict) and "body" in entry:
                    body = entry["body"]
                    break
        elif isinstance(response, dict):
            body = response.get("body") or {}
        items_raw = body.get("items") or []
        # 각 항목이 {"item": {...}} 래퍼
        return [
            i["item"] if isinstance(i, dict) and "item" in i else i
            for i in items_raw
        ]

    # 중기부(XML parsed) / 창진원 공통
    return data.get("pblancList") or data.get("items") or data.get("data") or []


def _notice_orm_to_dict(n: Notice) -> dict:
    return {
        "id": n.id,
        "origin": n.origin,
        "title": n.title,
        "full_title": n.full_title or "",
        "target": n.target or "",
        "benefit": n.benefit or "",
        "limit": n.limit or "",
        "documents": n.documents or "",
        "region": n.region or "전국",
        "url": n.url or "",
        "period": n.period or "",
        "date": n.date,
        "content": n.content or "",
        "jrsdInsttNm": n.jrsd_instt_nm or "",
        "excInsttNm": n.exc_instt_nm or "",
        "hashTags": n.hash_tags or "",
        "printFileNm": n.print_file_nm or "",
        "printFlpthNm": n.print_flpth_nm or "",
        "fileNm": n.file_nm or "",
        "flpthNm": n.flpth_nm or "",
        "reqstMthPapersCn": n.reqst_mth_papers_cn or "",
        "refrncNm": n.refrnc_nm or "",
        "rceptEngnHmpgUrl": n.rcept_engn_hmpg_url or "",
        "category": n.category or "",
        "ajin_similarity": n.ajin_similarity or 0.0,
        "fetched_at": n.fetched_at,
    }


# ── 외부 API 수집 ────────────────────────────────────────────────────────────

async def _fetch_external(q: str) -> tuple[list, list]:
    configs = [
        {
            "agency": "기업마당",
            "url": "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do",
            "params": {"crtfcKey": BIZINFO_API_KEY, "dataType": "json", "searchNm": q, "sortId": "L"},
        },
        {
            "agency": "과기부",
            "url": "https://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList",
            "params": {"ServiceKey": GONGGONG_API_KEY, "pageNo": 1, "numOfRows": 50, "returnType": "json"},
        },
        {
            "agency": "중기부",
            "url": "https://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2",
            "params": {"serviceKey": GONGGONG_API_KEY, "pageNo": 1, "numOfRows": 50},
        },
        {
            "agency": "창진원(통합)",
            "url": "https://apis.data.go.kr/B552735/kisedKstartupService01/getBusinessInformation01",
            "params": {"serviceKey": GONGGONG_API_KEY, "page": 1, "perPage": 50, "returnType": "json"},
        },
    ]

    notices: list = []
    errors: list = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        responses = await asyncio.gather(
            *[client.get(c["url"], params=c["params"]) for c in configs],
            return_exceptions=True,
        )

    for cfg, resp in zip(configs, responses):
        agency = cfg["agency"]
        if isinstance(resp, Exception):
            errors.append(f"{agency}: {resp}")
            continue
        try:
            try:
                data = resp.json()
            except Exception:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                data = {"items": [{c.tag: c.text for c in item} for item in root.findall(".//item")]}
            items = _parse_items(agency, data)
            for item in items:
                notices.append(_normalize_notice(item, agency))
        except Exception as e:
            errors.append(f"{agency}: {e}")

    # 중복 제거 (제목 기준)
    seen: set = set()
    deduped = []
    for n in notices:
        key = re.sub(r"\s+", "", n["title"])
        if key and key not in seen:
            seen.add(key)
            deduped.append(n)

    return deduped, errors


def _upsert_notices(db: Session, notices: list) -> None:
    for n in notices:
        row = {
            "id": n["id"], "origin": n["origin"], "title": n["title"],
            "full_title": n.get("full_title", ""), "target": n.get("target", ""),
            "benefit": n.get("benefit", ""), "limit": n.get("limit", ""),
            "documents": n.get("documents", ""), "region": n.get("region", "전국"),
            "url": n.get("url", ""), "period": n.get("period", ""),
            "date": n.get("date"), "content": n.get("content", ""),
            "jrsd_instt_nm": n.get("jrsdInsttNm", ""),
            "exc_instt_nm": n.get("excInsttNm", ""),
            "hash_tags": n.get("hashTags", ""),
            "print_file_nm": n.get("printFileNm", ""),
            "print_flpth_nm": n.get("printFlpthNm", ""),
            "file_nm": n.get("fileNm", ""),
            "flpth_nm": n.get("flpthNm", ""),
            "reqst_mth_papers_cn": n.get("reqstMthPapersCn", ""),
            "refrnc_nm": n.get("refrncNm", ""),
            "rcept_engn_hmpg_url": n.get("rceptEngnHmpgUrl", ""),
            "category": n.get("category", ""),
            "ajin_similarity": n.get("ajin_similarity", 0.0),
        }
        existing = db.query(Notice).filter(Notice.id == row["id"]).first()
        if existing:
            for k, v in row.items():
                if k != "id":
                    setattr(existing, k, v)
        else:
            db.add(Notice(**row))
    db.commit()


# ── 엔드포인트 ───────────────────────────────────────────────────────────────

@router.get("/search")
async def search_notices(
    q: str = Query(default="자동차", description="검색 키워드"),
    refresh: bool = Query(default=False, description="외부 API 재조회 강제"),
    limit: int = Query(default=500, le=1000, description="반환 최대 건수"),
    db: Session = Depends(get_db),
):
    """
    공고 검색.
    - refresh=false(기본): DB 캐시 우선 반환
    - refresh=true 또는 DB 비어있음: 4개 공공 API 실시간 수집 → DB 저장 → 반환
    """
    if not refresh:
        cached = db.query(Notice).order_by(Notice.fetched_at.desc()).limit(limit).all()
        if cached:
            return {"notices": [_notice_orm_to_dict(n) for n in cached], "errors": []}

    notices, errors = await _fetch_external(q)
    if notices:
        _upsert_notices(db, notices)

    return {"notices": notices, "errors": errors}


@router.get("", response_model=List[NoticeOut])
def get_notices(
    limit: int = Query(default=500, le=1000, description="반환 최대 건수"),
    db: Session = Depends(get_db),
):
    """캐시된 공고 전체 조회 (최신 fetched_at 순)"""
    return db.query(Notice).order_by(Notice.fetched_at.desc()).limit(limit).all()


@router.get("/by-id")
def get_notice_by_id(id: str, db: Session = Depends(get_db)):
    """단건 공고 조회 (ID로). printFlpthNm 등 파일 URL 보강용."""
    n = db.query(Notice).filter(Notice.id == id).first()
    if not n:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    return _notice_orm_to_dict(n)


@router.post("/bulk", response_model=dict)
def upsert_notices(notices: List[NoticeCreate], db: Session = Depends(get_db)):
    """공고 목록 일괄 저장(upsert). 프론트에서 외부 API 호출 성공 시 캐싱."""
    count = 0
    for n in notices:
        existing = db.query(Notice).filter(Notice.id == n.id).first()
        data = n.model_dump()
        snake = {
            "jrsd_instt_nm": data.pop("jrsdInsttNm", ""),
            "exc_instt_nm": data.pop("excInsttNm", ""),
            "hash_tags": data.pop("hashTags", ""),
            "print_file_nm": data.pop("printFileNm", ""),
            "print_flpth_nm": data.pop("printFlpthNm", ""),
            "file_nm": data.pop("fileNm", ""),
            "flpth_nm": data.pop("flpthNm", ""),
            "reqst_mth_papers_cn": data.pop("reqstMthPapersCn", ""),
            "refrnc_nm": data.pop("refrncNm", ""),
            "rcept_engn_hmpg_url": data.pop("rceptEngnHmpgUrl", ""),
        }
        data.update(snake)
        if existing:
            for key, val in data.items():
                setattr(existing, key, val)
        else:
            db.add(Notice(**data))
        count += 1
    db.commit()
    return {"saved": count}


# ─── DetailPage AI 본문 분석 (2026-05-25 C 그룹) ───
EXTRACT_SYSTEM_PROMPT = """당신은 한국 정부지원사업 공고문 분석 전문가입니다.
주어진 공고문 본문을 분석해 아래 JSON 형식 그대로 출력하세요.
설명·마크다운 없이 순수 JSON 한 덩어리만 출력합니다.
모르는 값은 빈 문자열로 두세요.

{
  "title": "공고 제목",
  "target": "지원 대상 (한 단락)",
  "benefit": "지원 내용·규모 (한 단락)",
  "documents": "제출 서류 (한 단락, 콤마 구분 가능)",
  "period": "신청 기간 (YYYY-MM-DD ~ YYYY-MM-DD 또는 원문)",
  "deadline": "마감일 (YYYY-MM-DD, 모르면 빈 문자열)",
  "region": "지역 (전국/지역명)",
  "limit": "제한 사항·신청 제외 (있으면)",
  "content": "사업 개요 요약 (3~5문장)",
  "contact": "문의처 (전화/이메일/담당부서)"
}"""


@router.post("/extract-structured")
async def extract_structured(payload: dict):
    """공고문 본문 텍스트 → LLM 분류 → DetailPage 카드용 구조화 JSON.

    payload: { "text": "공고 본문...", "title": "(선택) 공고 제목" }
    """
    text = (payload.get("text") or "").strip()
    title_hint = (payload.get("title") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text가 비어있습니다.")

    # 입력 길이 안전망 (LM Studio context window 보호)
    if len(text) > 20000:
        text = text[:20000] + "\n\n[이하 생략 — 본문이 길어 일부만 분석]"

    from services.lm_studio_client import try_parse_json
    from services.ai_provider import get_provider

    user_prompt = (
        (f"[공고 제목 힌트]\n{title_hint}\n\n" if title_hint else "")
        + f"[공고 본문]\n{text}\n\n위 JSON 스키마 그대로 출력하세요."
    )

    try:
        provider = get_provider()
        raw = await provider._chat(
            EXTRACT_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=4096,
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 호출 실패: {e}")

    parsed = try_parse_json(raw)
    if not parsed:
        return {
            "ok": False,
            "raw": raw[:2000],
            "warning": "LLM 응답에서 JSON을 추출하지 못했습니다.",
        }
    return {"ok": True, "data": parsed, "raw_preview": raw[:300]}


@router.delete("/{notice_id}", response_model=dict)
def delete_notice(notice_id: str, db: Session = Depends(get_db)):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if not notice:
        raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")
    db.delete(notice)
    db.commit()
    return {"deleted": notice_id}
