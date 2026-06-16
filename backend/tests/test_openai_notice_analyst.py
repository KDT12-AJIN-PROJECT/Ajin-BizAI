"""
AI-1 — OpenAIProvider.notice_analyst unit tests.

monkeypatch로 _chat() 대체 → API key 없이 검증.
실제 OpenAI API 호출 없음 (별도 smoke test에서).
"""
import json
import os
from unittest.mock import AsyncMock

import pytest

from services.openai_provider import OpenAIProvider
from services.ai_provider import NonRetryableError
from services.llm_response_parser import LLMHallucinatedEvidenceError

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "llm_responses")


def load_fixture_text(name: str) -> str:
    """fixture JSON을 raw text로 반환 (LLM 응답 시뮬레이션)."""
    path = os.path.join(FIXTURE_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.mark.asyncio
async def test_notice_analyst_with_mocked_chat():
    """fixture 응답을 _chat이 반환 → notice_analyst가 NoticeSchema dict 반환."""
    provider = OpenAIProvider()
    fake_raw = load_fixture_text("notice_analyst_v1")
    provider._chat = AsyncMock(return_value=fake_raw)

    result = await provider.notice_analyst(notice_text="공고문 샘플 텍스트")

    assert isinstance(result, dict)
    assert result["target"] == "중소·중견 제조기업 (업력 3년 이상)"
    assert result["benefit"] == "총 사업비의 70% 이내, 최대 2억 원"
    assert result["deadline"] == "2026-06-15T18:00"
    assert len(result["evaluation_criteria"]) == 3
    assert len(result["required_documents"]) == 4


@pytest.mark.asyncio
async def test_notice_analyst_with_code_fence():
    """LLM이 응답에 ```json``` 펜스를 붙이는 경우도 처리."""
    provider = OpenAIProvider()
    fixture_raw = load_fixture_text("notice_analyst_v1")
    fenced = f"분석 결과:\n```json\n{fixture_raw}\n```\n끝."
    provider._chat = AsyncMock(return_value=fenced)

    result = await provider.notice_analyst(notice_text="공고문")
    assert result["target"]


@pytest.mark.asyncio
async def test_notice_analyst_invalid_json_raises():
    """JSON 파싱 실패 → NonRetryableError raise (mock fallback 안 됨)."""
    provider = OpenAIProvider()
    provider._chat = AsyncMock(return_value="유효하지 않은 응답입니다. JSON 없음.")

    with pytest.raises(NonRetryableError, match="notice_analyst"):
        await provider.notice_analyst(notice_text="공고문")


@pytest.mark.asyncio
async def test_notice_analyst_schema_violation_raises():
    """JSON은 유효하지만 NoticeSchema 위반 → NonRetryableError."""
    provider = OpenAIProvider()
    # benefit 누락 (필수 필드)
    bad_response = json.dumps({"target": "중소기업"})
    provider._chat = AsyncMock(return_value=bad_response)

    with pytest.raises(NonRetryableError, match="notice_analyst"):
        await provider.notice_analyst(notice_text="공고문")


@pytest.mark.asyncio
async def test_notice_analyst_context_overflow_raises():
    """입력이 context limit 초과 → NonRetryableError (LLM 호출 전 차단)."""
    provider = OpenAIProvider()
    provider._chat = AsyncMock(return_value="{}")
    # 매우 큰 한국어 입력 (context limit 초과)
    huge_notice = "공고문 내용 매우 긴 텍스트 " * 100_000

    with pytest.raises(NonRetryableError, match="context overflow"):
        await provider.notice_analyst(notice_text=huge_notice)


@pytest.mark.asyncio
async def test_notice_analyst_temperature_zero_default(monkeypatch):
    """_chat 호출 시 temperature=0 default 확인."""
    provider = OpenAIProvider()
    captured_kwargs = {}

    async def fake_chat(system, user, **kwargs):
        captured_kwargs.update(kwargs)
        return load_fixture_text("notice_analyst_v1")

    provider._chat = fake_chat
    await provider.notice_analyst(notice_text="공고문")

    assert captured_kwargs.get("temperature") == 0.0
