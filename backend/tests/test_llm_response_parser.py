"""
NOAPI-P1 Phase 3 — LLM Response Parser unit tests.

API key 무관, pure function 검증.
실제 LLM 호출 없음.
"""
import pytest
from pydantic import BaseModel, Field

from services.llm_response_parser import (
    parse_llm_json,
    parse_llm_json_to_dict,
    parse_llm_json_to_list,
    LLMResponseParseError,
    LLMResponseSchemaError,
)


# ─── Pydantic schema fixtures ─────────────────────────────────────

class SampleNotice(BaseModel):
    target: str
    benefit: str
    evaluation_criteria: list[str] = Field(default_factory=list)


class SampleMissing(BaseModel):
    missing_id: str
    question_id: str
    name: str


# ─── 1. Fenced JSON response ───────────────────────────────────────

def test_json_fenced_with_lang_tag():
    """```json ... ``` 펜스 정상 처리."""
    raw = '```json\n{"target": "중소기업", "benefit": "최대 2억"}\n```'
    out = parse_llm_json(raw)
    assert out == {"target": "중소기업", "benefit": "최대 2억"}


def test_json_fenced_without_lang_tag():
    """``` ... ``` (lang 없음) 펜스도 처리."""
    raw = '```\n{"a": 1}\n```'
    out = parse_llm_json(raw)
    assert out == {"a": 1}


# ─── 2. Plain JSON response ────────────────────────────────────────

def test_plain_json_object():
    """펜스 없는 plain JSON."""
    out = parse_llm_json('{"name": "test", "value": 42}')
    assert out == {"name": "test", "value": 42}


def test_plain_json_array():
    """JSON array도 처리."""
    out = parse_llm_json('[1, 2, 3]')
    assert out == [1, 2, 3]


# ─── 3. JSON 앞뒤 설명문 포함 ──────────────────────────────────────

def test_json_with_leading_explanation():
    """LLM이 앞에 설명을 붙인 경우 — 첫 JSON object 추출."""
    raw = '분석 결과는 다음과 같습니다:\n{"target": "중소기업"}\n이상입니다.'
    out = parse_llm_json(raw)
    assert out == {"target": "중소기업"}


def test_json_with_nested_objects():
    """중첩된 JSON object 정확히 추출."""
    raw = 'Result:\n{"outer": {"inner": [1, 2]}, "tail": "x"}\nDone.'
    out = parse_llm_json(raw)
    assert out == {"outer": {"inner": [1, 2]}, "tail": "x"}


def test_json_with_string_containing_braces():
    """string 안의 `}` 가 종료로 잘못 감지되지 않음."""
    raw = '{"text": "has } inside", "ok": true}'
    out = parse_llm_json(raw)
    assert out == {"text": "has } inside", "ok": True}


# ─── 4. Empty / null response ─────────────────────────────────────

def test_empty_string_raises_parse_error():
    with pytest.raises(LLMResponseParseError, match="빈 문자열"):
        parse_llm_json("")


def test_whitespace_only_raises_parse_error():
    with pytest.raises(LLMResponseParseError, match="빈 문자열"):
        parse_llm_json("   \n  \t  ")


def test_null_response_raises_parse_error():
    with pytest.raises(LLMResponseParseError, match='"null"'):
        parse_llm_json("null")


def test_none_response_raises_parse_error():
    with pytest.raises(LLMResponseParseError):
        parse_llm_json(None)


# ─── 5. Trailing comma repair ─────────────────────────────────────

def test_trailing_comma_in_object_repaired():
    """`,}` 패턴 제한적 repair."""
    out = parse_llm_json('{"a": 1, "b": 2,}')
    assert out == {"a": 1, "b": 2}


def test_trailing_comma_in_array_repaired():
    """`,]` 패턴 제한적 repair."""
    out = parse_llm_json('[1, 2, 3,]')
    assert out == [1, 2, 3]


def test_trailing_comma_disabled_raises():
    """allow_trailing_comma=False 시 raise."""
    with pytest.raises(LLMResponseParseError):
        parse_llm_json('{"a": 1,}', allow_trailing_comma=False)


# ─── 6. No JSON found ─────────────────────────────────────────────

def test_no_json_object_raises():
    raw = "이것은 그냥 텍스트입니다. JSON 없음."
    with pytest.raises(LLMResponseParseError, match="찾을 수 없음"):
        parse_llm_json(raw)


# ─── 7. Schema validation 성공 ─────────────────────────────────────

def test_schema_validation_success_returns_model():
    raw = '{"target": "중소기업", "benefit": "2억원", "evaluation_criteria": ["기술성", "사업성"]}'
    out = parse_llm_json(raw, schema=SampleNotice)
    assert isinstance(out, SampleNotice)
    assert out.target == "중소기업"
    assert out.evaluation_criteria == ["기술성", "사업성"]


def test_schema_with_default_field():
    """schema의 default 값 자동 적용."""
    raw = '{"target": "T", "benefit": "B"}'  # evaluation_criteria 누락
    out = parse_llm_json(raw, schema=SampleNotice)
    assert out.evaluation_criteria == []


def test_schema_extra_field_ignored():
    """Pydantic v2 default extra='ignore' — extra field 무시."""
    raw = '{"target": "T", "benefit": "B", "extra_unknown": "x"}'
    out = parse_llm_json(raw, schema=SampleNotice)
    assert out.target == "T"


# ─── 8. Schema validation 실패 ────────────────────────────────────

def test_schema_validation_failure_raises_schema_error():
    """필수 필드 누락 → LLMResponseSchemaError (LLMResponseParseError와 구분)."""
    raw = '{"target": "T"}'  # benefit 누락
    with pytest.raises(LLMResponseSchemaError, match="SampleNotice"):
        parse_llm_json(raw, schema=SampleNotice)


def test_schema_type_mismatch_raises_schema_error():
    """타입 불일치도 SchemaError."""
    raw = '{"target": "T", "benefit": "B", "evaluation_criteria": "not a list"}'
    with pytest.raises(LLMResponseSchemaError):
        parse_llm_json(raw, schema=SampleNotice)


# ─── 9. parse vs schema 에러 구분 ─────────────────────────────────

def test_parse_error_and_schema_error_are_distinct():
    """LLMResponseParseError와 LLMResponseSchemaError는 별개 (둘 다 LLMResponseError 상속)."""
    from services.llm_response_parser import LLMResponseError
    assert issubclass(LLMResponseParseError, LLMResponseError)
    assert issubclass(LLMResponseSchemaError, LLMResponseError)
    assert not issubclass(LLMResponseParseError, LLMResponseSchemaError)
    assert not issubclass(LLMResponseSchemaError, LLMResponseParseError)


# ─── 10. helper variants ──────────────────────────────────────────

def test_parse_to_dict_returns_dict():
    out = parse_llm_json_to_dict('{"a": 1}')
    assert isinstance(out, dict)


def test_parse_to_dict_rejects_array():
    with pytest.raises(LLMResponseParseError, match="dict가 아닌"):
        parse_llm_json_to_dict('[1, 2, 3]')


def test_parse_to_list_returns_list():
    out = parse_llm_json_to_list('[1, 2, 3]')
    assert out == [1, 2, 3]


def test_parse_to_list_rejects_dict():
    with pytest.raises(LLMResponseParseError, match="list가 아닌"):
        parse_llm_json_to_list('{"a": 1}')


# ─── 11. Real-world LLM 응답 시뮬레이션 ───────────────────────────

def test_realistic_anthropic_response_with_thought_process():
    """Anthropic이 종종 앞에 thinking을 붙이는 케이스."""
    raw = """공고문을 분석한 결과는 다음과 같습니다:

```json
{
  "target": "중소·중견 제조기업",
  "benefit": "총 사업비의 70% 이내, 최대 2억 원",
  "evaluation_criteria": ["기술성", "사업성", "수행역량"]
}
```

위와 같이 정리되었습니다."""
    out = parse_llm_json(raw, schema=SampleNotice)
    assert out.target == "중소·중견 제조기업"
    assert len(out.evaluation_criteria) == 3
