"""
HWP 파일 텍스트 추출기
사용법:
  python hwp_reader.py [파일명.hwp]          # 텍스트 추출
  python hwp_reader.py --debug [파일명.hwp]  # 첫 5개 PARA_TEXT 레코드 hex 덤프
"""

import sys
import olefile
import zlib
import struct

# 서로게이트·인코딩 오류 방지 (TextIOWrapper에만 reconfigure 존재)
try:
    sys.stdout.reconfigure(errors='replace')  # type: ignore[union-attr]
except AttributeError:
    pass

# HWP 레코드 태그 ID
HWPTAG_PARA_TEXT = 67  # 0x43

# ──────────────────────────────────────────────────────────
# HWP 인라인 컨트롤 블록 구조:
#   char_code (1 uint16) + 파라미터 (7 uint16) = 총 8 uint16
# → char_code를 읽은 뒤 뒤따르는 파라미터는 7개 건너뜀
# 예외: 0x06 줄나눔은 파라미터 없음 (0개)
# ──────────────────────────────────────────────────────────
CTRL_SKIP = {
    0x06: 0,   # 줄나눔(Line Break) – 파라미터 없음
    # 0x09 탭, 0x0A 줄바꿈, 0x0D 문단끝 → 아래에서 별도 처리
}


def parse_records(data):
    """바이너리 섹션 데이터에서 HWP 레코드를 파싱하는 제너레이터"""
    offset = 0
    while offset + 4 <= len(data):
        header = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        tag_id = header & 0x3FF
        size   = (header >> 20) & 0xFFF

        if size == 0xFFF:
            if offset + 4 > len(data):
                break
            size = struct.unpack_from('<I', data, offset)[0]
            offset += 4

        if offset + size > len(data):
            break

        yield tag_id, data[offset:offset + size]
        offset += size


def decode_para_text(data, debug_words=False):
    """
    HWPTAG_PARA_TEXT 레코드에서 순수 텍스트를 추출.

    각 uint16 값을 순서대로 읽으며:
      - 0x09          → 탭
      - 0x0A / 0x0D   → 줄바꿈
      - 0x0001~0x001F → 인라인 컨트롤 코드, CTRL_SKIP에 따라 뒤 파라미터 건너뜀
      - 0xD800~0xDFFF → UTF-16 서로게이트, 건너뜀
      - 그 외         → 일반 문자로 출력
    """
    n = len(data) // 2
    if n == 0:
        return ''

    words = struct.unpack_from(f'<{n}H', data)

    if debug_words:
        print(f"    words[0:24]: {' '.join(f'{w:04X}' for w in words[:24])}", file=sys.stderr)

    result = []
    i = 0
    while i < n:
        code = words[i]
        i += 1

        if code == 0x0009:
            result.append('\t')
        elif code in (0x000A, 0x000D):
            result.append('\n')
        elif 0x0000 <= code <= 0x001F:
            # 컨트롤 코드: char_code 포함 8 uint16 블록 → 파라미터 7개 건너뜀
            # 단, 0x06 줄나눔은 파라미터 없음
            skip = CTRL_SKIP.get(code, 7)
            i += skip
        elif 0xD800 <= code <= 0xDFFF:
            pass   # UTF-16 서로게이트 – 건너뜀
        else:
            result.append(chr(code))

    return ''.join(result)


def extract_text_from_section(data, debug=False):
    """섹션 데이터에서 텍스트 줄 목록을 반환"""
    texts = []
    para_count = 0
    for tag_id, record_data in parse_records(data):
        if tag_id == HWPTAG_PARA_TEXT:
            para_count += 1
            if debug and para_count <= 5:
                print(f"\n  [DEBUG] PARA_TEXT #{para_count} ({len(record_data)} bytes)", file=sys.stderr)
                # hex 덤프 (첫 48바이트)
                snippet = record_data[:48]
                hex_line = ' '.join(f'{b:02X}' for b in snippet)
                print(f"    hex : {hex_line}", file=sys.stderr)
                decode_para_text(record_data, debug_words=True)

            text = decode_para_text(record_data)
            for line in text.splitlines():
                line = line.strip()
                if line:
                    texts.append(line)
    return texts


def read_hwp(filepath, debug=False):
    """HWP 파일에서 텍스트를 추출하여 반환"""
    if not olefile.isOleFile(filepath):
        raise ValueError(f"'{filepath}' 은(는) 유효한 HWP/OLE 파일이 아닙니다.")

    ole = olefile.OleFileIO(filepath)
    try:
        return _extract_from_ole(ole, debug=debug)
    finally:
        ole.close()


def read_hwp_bytes(content: bytes, debug: bool = False):
    """HWP 파일 bytes에서 텍스트를 추출하여 반환 (multipart upload 통합용)."""
    import io
    if not olefile.isOleFile(io.BytesIO(content)):
        raise ValueError("유효한 HWP/OLE 파일이 아닙니다.")
    ole = olefile.OleFileIO(io.BytesIO(content))
    try:
        return _extract_from_ole(ole, debug=debug)
    finally:
        ole.close()


def _extract_from_ole(ole, debug=False):
    all_texts = []
    section_idx = 0
    while True:
        stream_path = f'BodyText/Section{section_idx}'
        if not ole.exists(stream_path):
            break
        raw = ole.openstream(stream_path).read()
        try:
            decompressed = zlib.decompress(raw, -15)
        except zlib.error:
            decompressed = raw
        texts = extract_text_from_section(decompressed, debug=debug)
        all_texts.extend(texts)
        section_idx += 1
    return all_texts


def main():
    args = sys.argv[1:]
    debug = '--debug' in args
    if debug:
        args = [a for a in args if a != '--debug']

    filepath = args[0] if args else '파일.hwp'

    if debug:
        print(f"[DEBUG 모드] 파일: {filepath}\n", file=sys.stderr)

    print(f"파일 읽는 중: {filepath}\n")
    print("=" * 60)

    try:
        texts = read_hwp(filepath, debug=debug)
        if not texts:
            print("(추출된 텍스트가 없습니다.)")
        else:
            for line in texts:
                print(line)
    except FileNotFoundError:
        print(f"오류: '{filepath}' 파일을 찾을 수 없습니다.")
        sys.exit(1)
    except ValueError as e:
        print(f"오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"오류 발생: {e}")
        sys.exit(1)

    print("=" * 60)
    print(f"\n총 {len(texts)}개 문단 추출 완료.")


if __name__ == '__main__':
    main()
