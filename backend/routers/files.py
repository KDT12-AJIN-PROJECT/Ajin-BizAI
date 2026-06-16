"""
파일 파싱 API
PDF, DOCX, HWP, XLSX, CSV 파일에서 텍스트를 추출합니다.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
import pdfplumber
import docx
import io

router = APIRouter(prefix="/api", tags=["files"])

# 허용하는 파일 형식
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.hwp', '.xlsx', '.csv', '.txt'}

# 최대 파일 크기: 200MB
MAX_FILE_SIZE = 200 * 1024 * 1024

# Phase 4-H A1: 영속화용 parsed_text safety cap (한국어 ~100p 커버)
#   PDF 50page cap과 직교 — 두 cap이 안전망 이중화.
PARSED_TEXT_SAFETY_CAP = 200_000

# 기존 /api/parse-file 응답 preview cap (역호환, 변경 X)
TEXT_PREVIEW_CAP = 10_000


def parse_upload_bytes(filename: str, content: bytes) -> dict:
    """Phase 4-H A1: 파일명 + bytes → 텍스트 추출 결과 dict.

    /api/parse-file endpoint와 /api/analysis/files/upload 두 곳에서 재사용.
    예외는 HTTPException으로 던짐 (호출자 endpoint가 그대로 전파).

    응답 필드:
      - text             : ≤10K (preview, 역호환)
      - parsed_text      : ≤200K (영속화/Step 2 분석용)
      - char_count       : 원본 전체 char 수 (truncation 전)
      - parsed_text_stored_char_count: 실제 저장된 parsed_text 길이 (truncation 후)
      - parsed_text_truncated        : 200K 초과 시 true
    """
    filename_lower = filename.lower() if filename else ""

    ext = ""
    if "." in filename_lower:
        ext = "." + filename_lower.split(".")[-1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"지원하지 않는 파일 형식입니다: {ext}. PDF, DOCX, HWP, XLSX, CSV만 가능합니다."
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"파일 크기가 200MB를 초과합니다. ({len(content) // 1024 // 1024}MB)"
        )

    text = ""
    parse_success = True
    warning = None

    try:
        if ext == ".pdf":
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = pdf.pages[:50]
                # 페이지 마커 삽입 — LLM이 source_page를 정확히 추출하도록.
                # 형식: "=== PAGE 1 ===\n[1페이지 텍스트]\n\n=== PAGE 2 ===\n..."
                text = "\n\n".join(
                    f"=== PAGE {i + 1} ===\n{(page.extract_text() or '').strip()}"
                    for i, page in enumerate(pages)
                )
            if not text.strip() or all(
                line.startswith("=== PAGE") or not line.strip()
                for line in text.splitlines()
            ):
                parse_success = False
                warning = "PDF에서 텍스트를 추출하지 못했습니다. 스캔된 이미지 PDF일 수 있습니다."

        elif ext == ".docx":
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

        elif ext in (".xlsx", ".csv"):
            import pandas as pd
            if ext == ".xlsx":
                df = pd.read_excel(io.BytesIO(content))
            else:
                df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            text = df.to_string()

        elif ext == ".hwp":
            try:
                from hwpx.hwp_reader import read_hwp_bytes
                lines = read_hwp_bytes(content)
                text = "\n".join(lines).strip()
                if not text:
                    parse_success = False
                    warning = "HWP에서 추출된 텍스트가 비어있습니다."
            except Exception as e:
                parse_success = False
                warning = f"HWP 추출 실패: {e}"

        elif ext == ".txt":
            text = content.decode("utf-8-sig", errors="ignore")

    except Exception as e:
        parse_success = False
        warning = f"파일 내용을 읽는 중 오류가 발생했습니다: {str(e)}"

    char_count = len(text)
    parsed_text = text[:PARSED_TEXT_SAFETY_CAP]
    return {
        "filename": filename,
        "ext": ext,
        "size_kb": round(len(content) / 1024, 1),
        "size_bytes": len(content),
        "text": text[:TEXT_PREVIEW_CAP],          # preview (역호환)
        "parsed_text": parsed_text,                # 영속화용 (≤200K)
        "char_count": char_count,                  # 원본 전체 (truncation 전)
        "parsed_text_stored_char_count": len(parsed_text),
        "parsed_text_truncated": char_count > PARSED_TEXT_SAFETY_CAP,
        "parse_success": parse_success,
        "warning": warning,
    }


@router.post("/files/prefetch-url")
async def prefetch_url(payload: dict):
    """
    외부 URL의 파일을 backend가 다운로드 → 파싱 → text 반환.
    DetailPage 첨부파일이 HWP/PDF일 때 frontend가 직접 미리보기 못하는 경우 사용.

    payload: { "url": "https://...", "filename": "선택.hwp" }
    """
    import httpx
    url = (payload.get("url") or "").strip()
    filename = (payload.get("filename") or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")

    # protocol 누락 가드 (frontend가 originalUrl 대신 proxy 경로를 보낸 경우 등)
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/proxy/") or url.startswith("/"):
        raise HTTPException(
            status_code=422,
            detail=f"외부 절대 URL이 필요합니다 (받은 값: {url[:80]}). frontend에서 originalUrl을 전달하세요.",
        )
    elif not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    # filename이 비어있으면 URL 끝부분에서 추출 시도
    if not filename:
        from urllib.parse import urlparse, unquote
        path = urlparse(url).path
        filename = unquote(path.rsplit("/", 1)[-1] or "downloaded")

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"다운로드 실패: {e}")

    return parse_upload_bytes(filename, content)


@router.post("/files/export-hwpx")
async def export_hwpx(payload: dict):
    """텍스트(또는 lines)를 HWPX 파일로 변환해 다운로드.

    payload:
      { "text": "...", "filename": "사업계획서.hwpx" }
      또는
      { "lines": ["문단1", "문단2", ...], "filename": "..." }
    """
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote
    import io as _io

    raw_lines = payload.get("lines")
    if raw_lines is None:
        text = (payload.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="text 또는 lines 가 필요합니다.")
        raw_lines = text.split("\n")
    elif not isinstance(raw_lines, list):
        raise HTTPException(status_code=422, detail="lines는 배열이어야 합니다.")

    filename = (payload.get("filename") or "사업계획서.hwpx").strip()
    if not filename.lower().endswith(".hwpx"):
        filename += ".hwpx"

    try:
        from hwpx.hwpx_writer import save_hwpx_bytes
        hwpx_bytes = save_hwpx_bytes(raw_lines)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HWPX 생성 실패: {e}")

    # 한글 파일명은 RFC 5987 형식 (filename*=UTF-8'')
    quoted = quote(filename)
    return StreamingResponse(
        _io.BytesIO(hwpx_bytes),
        media_type="application/haansofthwpx",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


@router.post("/parse-file")
async def parse_file(file: UploadFile = File(...)):
    """
    파일 1개를 받아서 텍스트를 추출합니다.

    - PDF → pdfplumber로 텍스트 추출
    - DOCX → python-docx로 텍스트 추출
    - HWP → 자동 파싱 실패 시 사용자에게 직접 입력 안내
    - XLSX/CSV → pandas로 표 형태 텍스트 변환
    """
    content = await file.read()
    return parse_upload_bytes(file.filename or "", content)


@router.post("/parse-files")
async def parse_files(files: list[UploadFile] = File(...)):
    """
    여러 파일을 한번에 받아서 모두 파싱합니다.
    """
    results = {}
    for f in files:
        try:
            result = await parse_file(f)
            results[f.filename] = result
        except HTTPException as e:
            results[f.filename] = {
                "filename": f.filename,
                "parse_success": False,
                "warning": e.detail,
                "text": "",
            }
    return results
