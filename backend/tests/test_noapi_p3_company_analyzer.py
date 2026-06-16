"""
NOAPI-P3 unit tests.

테스트 정책 (사용자 추가 제한):
  - 실 OpenAI API 호출 금지 — stub / fixture 기반만
  - 회귀 테스트 격리 — AI_PROVIDER=mock 경로 무영향 확인

검증:
  R1: ai_cost.estimate_ai_cost_krw — pricing 미입력 시 None, 입력 시 산출
  R2: company_context_resolver — 정상 / parsed_text 없음 / truncated / insufficient
  R3: OpenAIProvider.company_analyzer (stub _chat) — fixture v2 통과
  R4: OpenAIProvider.company_analyzer — invalid JSON / Pydantic 실패 시 NonRetryableError
  R5: D5 호환 — 단순 list 입력 (legacy /analyze-company endpoint 호환)은 mock 위임
  R6: mapping_pipeline _step_analyze_company — call_with_retry 격리
"""
import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# backend/ 디렉토리를 import path에 추가 (다른 test_*.py와 동일 패턴)
HERE = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(HERE)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


FIXTURE_DIR = os.path.join(HERE, "fixtures", "llm_responses")


def _load_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURE_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


# ────────────────────────────────────────────────────────────────────
# R1: ai_cost
# ────────────────────────────────────────────────────────────────────

def test_ai_cost_pricing_missing_returns_none():
    from services.ai_cost import estimate_ai_cost_krw, reset_pricing_cache
    reset_pricing_cache()
    res = estimate_ai_cost_krw("gpt-4o-mini", 1000, 500)
    assert res["cost_estimate_krw"] is None
    assert "unknown_pricing" in res["warnings"]
    assert res["currency"] == "KRW"


def test_ai_cost_unknown_model():
    from services.ai_cost import estimate_ai_cost_krw
    res = estimate_ai_cost_krw("gpt-9000", 1000, 500, pricing_table={})
    assert res["cost_estimate_krw"] is None
    assert "unknown_model" in res["warnings"]


def test_ai_cost_model_none():
    from services.ai_cost import estimate_ai_cost_krw
    res = estimate_ai_cost_krw(None, 1000, 500)
    assert res["cost_estimate_krw"] is None
    assert "model_missing" in res["warnings"]


def test_ai_cost_pricing_filled_returns_krw():
    from services.ai_cost import estimate_ai_cost_krw
    table = {
        "gpt-4o-mini": {
            "input_per_1m_tokens_usd": 0.15,
            "output_per_1m_tokens_usd": 0.60,
            "usd_to_krw_rate": 1400.0,
        }
    }
    # input 1000 tokens × $0.15/1M + output 500 × $0.60/1M = $0.00015 + $0.0003 = $0.00045
    # × 1400 = 0.63 KRW
    res = estimate_ai_cost_krw("gpt-4o-mini", 1000, 500, pricing_table=table)
    assert res["cost_estimate_krw"] is not None
    assert res["cost_estimate_krw"] > 0
    assert abs(res["cost_estimate_krw"] - 0.63) < 0.01
    assert res["pricing_found"] is True
    assert res["warnings"] == []


def test_ai_cost_tokens_missing():
    from services.ai_cost import estimate_ai_cost_krw
    table = {
        "gpt-4o-mini": {
            "input_per_1m_tokens_usd": 0.15,
            "output_per_1m_tokens_usd": 0.60,
            "usd_to_krw_rate": 1400.0,
        }
    }
    res = estimate_ai_cost_krw("gpt-4o-mini", None, None, pricing_table=table)
    assert res["cost_estimate_krw"] is None
    assert "tokens_missing" in res["warnings"]


# ────────────────────────────────────────────────────────────────────
# R2: company_context_resolver
# ────────────────────────────────────────────────────────────────────

def _make_company_file(file_id, parse_success=True, parsed_text="텍스트", truncated=False,
                       file_name="x.pdf", file_type="기타"):
    f = MagicMock()
    f.file_id = file_id
    f.file_name = file_name
    f.file_type = file_type
    f.parse_success = parse_success
    f.parsed_text = parsed_text
    f.parsed_text_truncated = truncated
    f.ext = ".pdf"
    f.tags = []
    f.warning = None
    f.uploaded_at = None
    return f


def _mock_db(files_by_id: dict):
    db = MagicMock()
    q = MagicMock()
    filt = MagicMock()
    filt.all = MagicMock(return_value=list(files_by_id.values()))
    q.filter = MagicMock(return_value=filt)
    db.query = MagicMock(return_value=q)
    return db


def test_resolver_normal_case():
    from services.company_context_resolver import resolve_company_context
    f1 = _make_company_file("f1", parsed_text="회사소개서 본문", file_name="회사소개서.pdf", file_type="회사소개서")
    db = _mock_db({"f1": f1})
    ctx = resolve_company_context(
        db=db, session_id="s1",
        company_profile_input={"company_name": "테스트㈜"},
        selected_company_file_ids=["f1"],
    )
    assert ctx["structured_company_profile"] == {"company_name": "테스트㈜"}
    assert len(ctx["company_files"]) == 1
    assert ctx["company_files"][0]["parsed_text"] == "회사소개서 본문"
    assert ctx["company_files"][0]["document_type"] == "company_profile"
    assert ctx["selected_company_file_ids"] == ["f1"]


def test_resolver_parsed_text_missing_warning():
    from services.company_context_resolver import resolve_company_context
    f1 = _make_company_file("f1", parse_success=False, parsed_text="", file_name="실패.pdf")
    db = _mock_db({"f1": f1})
    ctx = resolve_company_context(
        db=db, session_id="s1",
        company_profile_input={"company_name": "테스트"},
        selected_company_file_ids=["f1"],
    )
    assert len(ctx["company_files"]) == 0
    assert any(w["warning_code"] == "company_file_text_missing" for w in ctx["warnings"])


def test_resolver_truncated_file_warning():
    from services.company_context_resolver import resolve_company_context
    big_text = "가" * 20_000  # > 12_000 max_chars_per_file
    f1 = _make_company_file("f1", parsed_text=big_text, file_name="long.pdf")
    db = _mock_db({"f1": f1})
    ctx = resolve_company_context(
        db=db, session_id="s1",
        company_profile_input={"company_name": "테스트"},
        selected_company_file_ids=["f1"],
    )
    assert len(ctx["company_files"]) == 1
    assert ctx["company_files"][0]["truncated"] is True
    assert ctx["company_files"][0]["returned_chars"] <= 12_000
    assert any(w["warning_code"] == "company_file_truncated" for w in ctx["warnings"])


def test_resolver_insufficient_raises():
    from services.company_context_resolver import resolve_company_context
    from services.ai_provider import NonRetryableError
    db = _mock_db({})
    with pytest.raises(NonRetryableError, match="insufficient_company_data"):
        resolve_company_context(
            db=db, session_id="s1",
            company_profile_input=None,
            selected_company_file_ids=[],
        )


def test_resolver_insufficient_no_raise():
    from services.company_context_resolver import resolve_company_context
    db = _mock_db({})
    ctx = resolve_company_context(
        db=db, session_id="s1",
        company_profile_input=None,
        selected_company_file_ids=[],
        raise_on_insufficient=False,
    )
    assert any(w["warning_code"] == "insufficient_company_data" for w in ctx["warnings"])


def test_resolver_file_not_found_warning():
    from services.company_context_resolver import resolve_company_context
    db = _mock_db({})  # query 결과 비어있음
    ctx = resolve_company_context(
        db=db, session_id="s1",
        company_profile_input={"company_name": "테스트"},
        selected_company_file_ids=["missing_id"],
    )
    assert any(w["warning_code"] == "company_file_not_found" for w in ctx["warnings"])


# ────────────────────────────────────────────────────────────────────
# R3: OpenAIProvider.company_analyzer fixture 통과 (stub _chat)
# ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_company_analyzer_fixture_passes_schema():
    """fixture v2 → CompanySchema + FitAnalysis validation 통과."""
    from services.openai_provider import OpenAIProvider

    fixture = _load_fixture("company_analyzer_v2")
    fixture_json = json.dumps(fixture, ensure_ascii=False)

    provider = OpenAIProvider()
    company_context = {
        "structured_company_profile": {"company_name": "테스트㈜"},
        "company_files": [{
            "file_id": "f1",
            "filename": "회사소개서.pdf",
            "document_type": "company_profile",
            "parsed_text": "본문 텍스트",
            "text_preview": "본문",
            "metadata": {},
            "parse_success": True,
            "truncated": False,
            "original_chars": 10,
            "returned_chars": 10,
        }],
        "selected_company_file_ids": ["f1"],
        "warnings": [],
    }

    with patch.object(provider, "_chat", new=AsyncMock(return_value=fixture_json)):
        result = await provider.company_analyzer(
            company_context, {"target": "중소기업"},
            request_id="test_r3", session_id="s_test",
        )

    assert "company" in result
    assert "fit_analysis" in result
    assert "warnings" in result
    assert result["company"]["name"] == "테스트제조㈜"
    assert len(result["fit_analysis"]["axes"]) == 3
    # enum 통일 확인 (높음/중간/낮음)
    levels = {a["level"] for a in result["fit_analysis"]["axes"]}
    assert levels.issubset({"높음", "중간", "낮음"})


# ────────────────────────────────────────────────────────────────────
# R4: 에러 케이스 — NonRetryableError raise
# ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_company_analyzer_invalid_json_raises():
    from services.openai_provider import OpenAIProvider
    from services.ai_provider import NonRetryableError

    provider = OpenAIProvider()
    company_context = {
        "structured_company_profile": {"company_name": "T"},
        "company_files": [],
        "selected_company_file_ids": [],
        "warnings": [],
    }

    with patch.object(provider, "_chat", new=AsyncMock(return_value="<<not json>>")):
        with pytest.raises(NonRetryableError):
            await provider.company_analyzer(
                company_context, {}, request_id="t", session_id="s",
            )


@pytest.mark.asyncio
async def test_company_analyzer_missing_keys_raises():
    from services.openai_provider import OpenAIProvider
    from services.ai_provider import NonRetryableError

    provider = OpenAIProvider()
    company_context = {
        "structured_company_profile": {"company_name": "T"},
        "company_files": [],
        "selected_company_file_ids": [],
        "warnings": [],
    }
    bad_response = json.dumps({"company_schema": {}, "fit_analysis": {}})  # 'company' 누락

    with patch.object(provider, "_chat", new=AsyncMock(return_value=bad_response)):
        with pytest.raises(NonRetryableError):
            await provider.company_analyzer(
                company_context, {}, request_id="t", session_id="s",
            )


@pytest.mark.asyncio
async def test_company_analyzer_schema_validation_fails():
    from services.openai_provider import OpenAIProvider
    from services.ai_provider import NonRetryableError

    provider = OpenAIProvider()
    company_context = {
        "structured_company_profile": {"company_name": "T"},
        "company_files": [],
        "selected_company_file_ids": [],
        "warnings": [],
    }
    # CompanySchema required: company_profile_id, name
    bad_response = json.dumps({
        "company": {},  # 필수 필드 누락
        "fit_analysis": {"session_id": "s", "company_profile_id": "c", "axes": [], "overall_score": 0},
    })

    with patch.object(provider, "_chat", new=AsyncMock(return_value=bad_response)):
        with pytest.raises(NonRetryableError):
            await provider.company_analyzer(
                company_context, {}, request_id="t", session_id="s",
            )


# ────────────────────────────────────────────────────────────────────
# R5: D5 호환 — legacy endpoint 단순 list 입력은 mock 위임
# ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_company_analyzer_legacy_input_falls_back_to_mock():
    """레거시 endpoint /analyze-company가 req.company_files 그대로 전달 시
    OpenAIProvider는 mock fallback 위임 (D5 확정)."""
    from services.openai_provider import OpenAIProvider

    provider = OpenAIProvider()
    # legacy 형식: 단순 dict 또는 list (resolver 구조 없음)
    legacy_company_files = [{"file_id": "f1"}, {"file_id": "f2"}]

    result = await provider.company_analyzer(
        legacy_company_files, {},
        request_id="legacy", session_id="s",
    )
    # mock provider 응답 (company key 사용 확인)
    assert "company" in result
    assert "fit_analysis" in result


# ────────────────────────────────────────────────────────────────────
# R6: mapping_pipeline _step_analyze_company — call_with_retry 격리
# ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_step_analyze_company_uses_call_with_retry():
    """_step_analyze_company가 RetryableError 발생 시 retry, NonRetryableError 즉시 raise."""
    from services.ai_provider import RetryableError, NonRetryableError
    from services.mapping_pipeline import _step_analyze_company

    # company_context_resolver를 stub
    with patch("services.company_context_resolver.resolve_company_context") as mock_resolve:
        mock_resolve.return_value = {
            "structured_company_profile": {"company_name": "T"},
            "company_files": [],
            "selected_company_file_ids": [],
            "warnings": [],
        }

        # provider stub — 첫 2회 RetryableError, 3번째에 성공
        provider = MagicMock()
        call_count = {"n": 0}

        async def fake_analyze(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RetryableError("transient")
            return {"company": {"company_profile_id": "x", "name": "T"},
                    "fit_analysis": {"session_id": "s", "company_profile_id": "x", "axes": [], "overall_score": 0},
                    "warnings": []}

        provider.company_analyzer = fake_analyze

        context = {
            "_session_id": "s",
            "company_profile_input": {"company_name": "T"},
            "selected_company_file_ids": [],
            "notice_schema": {},
        }
        # base_delay 짧게 — sleep 없이 통과하도록 monkey patch
        with patch("services.ai_provider.asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await _step_analyze_company(context, provider)

        assert call_count["n"] == 3
        assert "company" in result


@pytest.mark.asyncio
async def test_step_analyze_company_nonretryable_immediate_raise():
    from services.ai_provider import NonRetryableError
    from services.mapping_pipeline import _step_analyze_company

    with patch("services.company_context_resolver.resolve_company_context") as mock_resolve:
        mock_resolve.return_value = {
            "structured_company_profile": {"company_name": "T"},
            "company_files": [],
            "selected_company_file_ids": [],
            "warnings": [],
        }

        provider = MagicMock()
        call_count = {"n": 0}

        async def fake_analyze(*args, **kwargs):
            call_count["n"] += 1
            raise NonRetryableError("schema bad")

        provider.company_analyzer = fake_analyze

        context = {
            "_session_id": "s",
            "company_profile_input": {"company_name": "T"},
            "selected_company_file_ids": [],
            "notice_schema": {},
        }
        with pytest.raises(NonRetryableError):
            await _step_analyze_company(context, provider)
        # 1번만 호출 (retry 없음)
        assert call_count["n"] == 1


# ────────────────────────────────────────────────────────────────────
# Smoke: AI_PROVIDER=mock 경로 회귀 (Mock 정상 동작)
# ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_provider_company_analyzer_unchanged():
    """AI_PROVIDER=mock 회귀 — MockProvider.company_analyzer는 무변경."""
    from services.mock_provider import MockProvider
    mock = MockProvider()
    result = await mock.company_analyzer([], {}, request_id="t", session_id="s")
    # mock 응답 key 확인 (D1 b: company key)
    assert "company" in result
    assert "fit_analysis" in result
