"""
hwpx_writer.py  –  텍스트를 HWPX 파일로 저장

사용법:
  python hwpx_writer.py output.hwpx input.txt   # txt → hwpx 변환
  python hwpx_writer.py output.hwpx             # 예시 텍스트로 생성

요구사항:
  - this_is_hwpx.hwpx 가 같은 폴더에 있어야 합니다 (템플릿)
"""

import os
import random
import re
import sys
import zipfile
from xml.sax.saxutils import escape

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "this_is_hwpx.hwpx")


# ── 핵심 로직 ──────────────────────────────────────────────────────────

def _extra_para(text: str) -> str:
    """두 번째 이후 문단 XML 조각 생성 (secPr 없음)"""
    pid = random.randint(1_000_000_000, 9_999_999_999)
    safe = escape(text)
    return (
        f'<hp:p id="{pid}" paraPrIDRef="0" styleIDRef="0" '
        f'pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0"><hp:t>{safe}</hp:t></hp:run>'
        f'<hp:linesegarray>'
        f'<hp:lineseg textpos="0" vertpos="0" vertsize="1000" '
        f'textheight="1000" baseline="850" spacing="600" '
        f'horzpos="0" horzsize="42520" flags="393216"/>'
        f'</hp:linesegarray></hp:p>'
    )


def _patch_section(template_bytes: bytes, lines: list) -> bytes:
    """
    템플릿 section0.xml 에서
      · 첫 번째 <hp:t>…</hp:t> → 첫 줄 텍스트로 교체
      · 나머지 줄 → </hs:sec> 앞에 새 문단으로 삽입
    """
    xml = template_bytes.decode("utf-8")
    xml = re.sub(r"<hp:t>[^<]*</hp:t>",
                 f"<hp:t>{escape(lines[0]) if lines else ''}</hp:t>",
                 xml, count=1)
    if len(lines) > 1:
        extra = "".join(_extra_para(ln) for ln in lines[1:])
        xml = xml.replace("</hs:sec>", extra + "</hs:sec>")
    return xml.encode("utf-8")


def save_hwpx(output_path: str, lines: list, template: str = TEMPLATE) -> None:
    """줄 목록을 HWPX 파일로 저장합니다."""
    if not os.path.exists(template):
        raise FileNotFoundError(
            f"템플릿 파일이 없습니다: {template}\n"
            "this_is_hwpx.hwpx 를 같은 폴더에 놓아주세요."
        )
    if not output_path.endswith(".hwpx"):
        output_path += ".hwpx"

    data_bytes = save_hwpx_bytes(lines, template=template)
    with open(output_path, "wb") as f:
        f.write(data_bytes)
    print(f"저장 완료: {output_path}  ({len(lines)}개 문단)")


def save_hwpx_bytes(lines: list, template: str = TEMPLATE) -> bytes:
    """줄 목록을 HWPX 파일 bytes로 반환 (FastAPI StreamingResponse 등에 사용)."""
    import io
    if not os.path.exists(template):
        raise FileNotFoundError(f"템플릿 파일이 없습니다: {template}")

    lines = lines or [""]
    buf = io.BytesIO()
    with zipfile.ZipFile(template, "r") as src:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = src.read(item.filename)
                if item.filename == "Contents/section0.xml":
                    data = _patch_section(data, lines)
                if item.filename == "mimetype":
                    item.compress_type = zipfile.ZIP_STORED
                dst.writestr(item, data)
    buf.seek(0)
    return buf.read()


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("사용법: python hwpx_writer.py output.hwpx [input.txt]")
        sys.exit(1)

    output_path = args[0]

    if len(args) >= 2:
        src_path = args[1]
        for enc in ("utf-8", "cp949"):
            try:
                with open(src_path, encoding=enc) as f:
                    lines = [ln.rstrip() for ln in f.readlines()]
                break
            except (UnicodeDecodeError, FileNotFoundError):
                continue
        else:
            print(f"오류: '{src_path}' 파일을 읽을 수 없습니다.")
            sys.exit(1)
    else:
        print("(입력 파일 없음 → 예시 텍스트로 생성)")
        lines = [
            "안녕하세요!",
            "이 파일은 Python으로 생성한 HWPX 문서입니다.",
            "",
            "한글(Hancom Office)에서 열 수 있습니다.",
        ]

    try:
        save_hwpx(output_path, lines)
    except FileNotFoundError as e:
        print(f"오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
