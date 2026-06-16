"""
NOAPI-P1 — LLM Response Parser

LLM 응답 텍스트 → 구조화된 JSON / Pydantic 모델 변환 helper.

용도:
  - AnthropicProvider / OpenAIProvider / LocalProvider 의 v0.2 8 모듈 본체에서 재사용
  - API key 없이도 unit test 가능 (raw text 입력 → 결과 확인)

분리 원칙:
  - JSON parse error (LLMResponseParseError) ↔ schema validation error (LLMResponseSchemaError) 구분
  - mojibake 자동 수정 X
  - 필드 임의 생성 X
  - 의미 추정 보정 X
  - silent pass X (실패는 명시적 raise)
  - trailing comma repair는 제한적 (`,]` `,}` 패턴만) + warning
"""
import json
import logging
import re
from typing import Any, Optional, Type, Union

try:
    from pydantic import BaseModel, ValidationError
except ImportError:
    BaseModel = None         # type: ignore
    ValidationError = None   # type: ignore

logger = logging.getLogger(__name__)


# ─── 예외 ─────────────────────────────────────────────────────────

class LLMResponseError(Exception):
    """LLM 응답 처리 공통 예외 base."""


class LLMResponseParseError(LLMResponseError):
    """JSON 파싱 실패 (구문 오류, 빈 응답, JSON 없음)."""


class LLMResponseSchemaError(LLMResponseError):
    """JSON은 유효하지만 Pydantic schema validation 실패."""


# ─── 내부 helper ──────────────────────────────────────────────────

_FENCE_PATTERN = re.compile(r"^```(?:json|JSON)?\s*\n?|\n?\s*```\s*$", re.MULTILINE)

# JSON object 또는 array의 시작 (첫 매칭만 사용)
_JSON_START_PATTERN = re.compile(r"[\{\[]")

# 제한적 trailing comma repair: 닫는 괄호 직전의 , 만 제거
_TRAILING_COMMA_PATTERN = re.compile(r",(\s*[\]}])")


def _strip_code_fences(text: str) -> str:
    """```json ... ``` 또는 ``` ... ``` 코드 펜스 제거.

    펜스 안에 펜스가 없는 단일 블록만 처리. 그 외엔 원본 반환.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    # 첫 ``` 와 마지막 ``` 사이 추출
    inner = _FENCE_PATTERN.sub("", stripped)
    return inner.strip()


def _extract_first_json_block(text: str) -> Optional[str]:
    """텍스트에서 첫 JSON object 또는 array를 추출.

    `{` 또는 `[` 의 첫 등장 위치부터 매칭되는 닫는 괄호까지.
    중첩 추적 (string 안의 괄호는 무시).
    매칭 실패 시 None.
    """
    m = _JSON_START_PATTERN.search(text)
    if not m:
        return None
    start = m.start()
    open_char = text[start]
    close_char = "}" if open_char == "{" else "]"

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _try_repair_trailing_comma(text: str) -> tuple[str, bool]:
    """`,}` `,]` 단순 패턴만 제거. 반환: (repaired_text, was_repaired)."""
    new_text = _TRAILING_COMMA_PATTERN.sub(r"\1", text)
    return new_text, new_text != text


# ─── public API ───────────────────────────────────────────────────

def parse_llm_json(
    raw: str,
    *,
    schema: Optional[Type[BaseModel]] = None,
    allow_trailing_comma: bool = True,
) -> Union[dict, list, BaseModel]:
    """LLM 응답 텍스트 → dict / list / Pydantic model.

    절차:
      1. 빈 응답 / "null" 응답 감지 → LLMResponseParseError
      2. 코드 펜스 제거
      3. 첫 JSON object/array 추출 (앞뒤 설명문 허용)
      4. json.loads
      5. (선택) trailing comma repair + warning, json.loads 재시도
      6. (선택) Pydantic schema validation

    Args:
        raw: LLM 응답 원본 텍스트
        schema: Pydantic BaseModel 클래스 (선택). 주어지면 validation 후 model 반환.
        allow_trailing_comma: True 시 `,]` `,}` 패턴 제거 후 재파싱 1회 시도.

    Returns:
        schema=None → dict 또는 list
        schema 주어짐 → Pydantic BaseModel 인스턴스

    Raises:
        LLMResponseParseError: 빈 응답 / JSON 없음 / 파싱 실패
        LLMResponseSchemaError: schema validation 실패
    """
    if raw is None:
        raise LLMResponseParseError("LLM 응답이 None")

    text = str(raw).strip()
    if not text:
        raise LLMResponseParseError("LLM 응답이 빈 문자열")

    # "null" 단독 응답
    if text in ("null", "None"):
        raise LLMResponseParseError(f'LLM 응답이 "{text}"')

    # 1. 펜스 제거
    text_clean = _strip_code_fences(text)
    if not text_clean:
        raise LLMResponseParseError("코드 펜스 제거 후 빈 텍스트")

    # 2. 첫 JSON block 추출
    json_block = _extract_first_json_block(text_clean)
    if json_block is None:
        raise LLMResponseParseError(
            f"JSON object/array를 찾을 수 없음. 원본 처음 200자:\n{text_clean[:200]}"
        )

    # 3. json.loads
    parsed: Any
    try:
        parsed = json.loads(json_block)
    except json.JSONDecodeError as e:
        # 4. trailing comma repair 시도
        if allow_trailing_comma:
            repaired, was_repaired = _try_repair_trailing_comma(json_block)
            if was_repaired:
                try:
                    parsed = json.loads(repaired)
                    logger.warning(
                        "[LLM_PARSE_TRAILING_COMMA_REPAIRED] %s → repaired",
                        str(e)[:100],
                    )
                except json.JSONDecodeError as e2:
                    raise LLMResponseParseError(
                        f"JSON 파싱 실패 (trailing comma repair 후에도): {e2}\n원본:\n{json_block[:300]}"
                    ) from e2
            else:
                raise LLMResponseParseError(
                    f"JSON 파싱 실패: {e}\n원본:\n{json_block[:300]}"
                ) from e
        else:
            raise LLMResponseParseError(
                f"JSON 파싱 실패: {e}\n원본:\n{json_block[:300]}"
            ) from e

    # 5. schema validation (선택)
    if schema is not None:
        if BaseModel is None:
            raise LLMResponseError("pydantic 패키지 미설치")
        try:
            return schema(**parsed) if isinstance(parsed, dict) else schema.model_validate(parsed)
        except ValidationError as e:
            raise LLMResponseSchemaError(
                f"Pydantic schema {schema.__name__} validation 실패:\n{e}"
            ) from e

    return parsed


def parse_llm_json_to_dict(raw: str, **kwargs) -> dict:
    """schema 없이 dict만 반환. dict가 아니면 raise."""
    result = parse_llm_json(raw, schema=None, **kwargs)
    if not isinstance(result, dict):
        raise LLMResponseParseError(
            f"dict가 아닌 {type(result).__name__} 반환됨"
        )
    return result


def parse_llm_json_to_list(raw: str, **kwargs) -> list:
    """schema 없이 list만 반환. list가 아니면 raise."""
    result = parse_llm_json(raw, schema=None, **kwargs)
    if not isinstance(result, list):
        raise LLMResponseParseError(
            f"list가 아닌 {type(result).__name__} 반환됨"
        )
    return result


# ─── NOAPI-P2 R4: used_evidence_ids 환각 안전망 ───────────────────────

class LLMHallucinatedEvidenceError(LLMResponseError):
    """LLM 응답의 used_evidence_ids가 input evidence_list에 없는 ID 포함."""


def validate_used_evidence_ids(
    response: dict,
    *,
    input_evidence_ids: list,
    field_name: str = "used_evidence_ids",
) -> list:
    """PRD §14.3 환각 방지 — used_evidence_ids 검증.

    LLM 응답(dict)의 used_evidence_ids가 모두 input_evidence_ids에 있는지 확인.
    하나라도 없으면 LLMHallucinatedEvidenceError raise.

    Args:
        response: LLM 응답 dict (parse_llm_json 결과)
        input_evidence_ids: 호출자가 LLM에 전달한 evidence ID 배열
        field_name: 검증할 필드명 (draft_writer 등에서 "used_evidence_ids")

    Returns:
        검증 통과한 used_evidence_ids 배열

    Raises:
        LLMHallucinatedEvidenceError: 환각 ID 포함 시
    """
    if not isinstance(response, dict):
        raise LLMResponseError(f"dict가 아님: {type(response).__name__}")

    used = response.get(field_name)
    if used is None:
        # 필드 자체가 없으면 빈 배열 처리 (LLM이 evidence 미사용)
        return []
    if not isinstance(used, list):
        raise LLMResponseError(f"{field_name}이 list가 아님: {type(used).__name__}")

    input_set = set(input_evidence_ids or [])
    hallucinated = [eid for eid in used if eid not in input_set]
    if hallucinated:
        raise LLMHallucinatedEvidenceError(
            f"LLM이 input에 없는 evidence ID 사용: {hallucinated}. "
            f"input_evidence_ids({len(input_evidence_ids)}개)에 한정해야 합니다. "
            f"PRD §14.3 환각 방지 위반."
        )
    return used
