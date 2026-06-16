"""
NOAPI-P2 unit tests.

R1: llm_token_budget — estimate_tokens / check_budget / truncate
R3: LLM response fixtures (8 module) Pydantic schema 통과 검증
R4: validate_used_evidence_ids 환각 안전망

API key 무관. 실제 LLM 호출 없음.
"""
import json
import os
import pytest

from services.llm_token_budget import (
    estimate_tokens,
    estimate_messages_tokens,
    check_budget,
    assert_budget,
    truncate_to_token_budget,
    truncate_items_to_budget,
    TokenBudgetExceeded,
    DEFAULT_CONTEXT_TOKENS,
)
from services.llm_response_parser import (
    parse_llm_json,
    validate_used_evidence_ids,
    LLMHallucinatedEvidenceError,
    LLMResponseError,
)


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "llm_responses")


def load_fixture(name: str) -> dict:
    path = os.path.join(FIXTURE_DIR, f"{name}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─── R1: estimate_tokens ──────────────────────────────────────────

def test_estimate_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_estimate_ascii():
    # "Hello World" 11 chars × 0.25 + margin → ~3~4
    t = estimate_tokens("Hello World")
    assert 1 <= t <= 10


def test_estimate_korean_larger_than_ascii():
    """같은 글자 수라도 한국어가 토큰 더 많이 추정 (보수적)."""
    korean = "안녕하세요" * 20         # 100 chars 한국어
    ascii_ = "abcdefghij" * 10          # 100 chars 영문
    assert estimate_tokens(korean) > estimate_tokens(ascii_)


def test_estimate_messages():
    sys = "system prompt"
    usr = "user input"
    total = estimate_messages_tokens(sys, usr)
    assert total == estimate_tokens(sys) + estimate_tokens(usr) + 50


# ─── R1: check_budget / assert_budget ─────────────────────────────

def test_check_budget_under():
    res = check_budget("small system", "small user", max_response_tokens=4096)
    assert res["over_budget"] is False
    assert res["over_by"] == 0
    assert res["available_after_response"] > 0


def test_check_budget_over():
    huge = "안녕하세요" * 100_000  # ~60K * 1.5 = ~90K, 응답 4096 + margin 8192 → over
    res = check_budget("system", huge, context_limit=10_000, max_response_tokens=2_000, safety_margin=500)
    assert res["over_budget"] is True
    assert res["over_by"] > 0


def test_assert_budget_raises():
    huge = "테스트" * 100_000
    with pytest.raises(TokenBudgetExceeded):
        assert_budget("system", huge, context_limit=5_000)


def test_assert_budget_under_does_not_raise():
    assert_budget("small", "small", context_limit=DEFAULT_CONTEXT_TOKENS)


# ─── R1: truncate ─────────────────────────────────────────────────

def test_truncate_under_budget_returns_original():
    text = "짧은 텍스트"
    out = truncate_to_token_budget(text, 1000)
    assert out == text


def test_truncate_over_budget_shortens():
    text = "긴 문장입니다. " * 1000
    out = truncate_to_token_budget(text, 100)
    assert len(out) < len(text)
    assert "이하 생략" in out


def test_truncate_items_stops_at_budget():
    items = [
        {"text": "짧은 항목 " * 10},      # ~80 chars 한국어
        {"text": "두번째 항목 " * 10},
        {"text": "세번째 항목 " * 100},  # 큼
    ]
    out = truncate_items_to_budget(items, "text", max_total_tokens=80)
    # 첫 1~2개만 포함
    assert len(out) < len(items)


# ─── R3: 8 fixture Pydantic schema 통과 ───────────────────────────

def test_fixture_notice_analyst_passes_NoticeSchema():
    from ontology.schemas import NoticeSchema
    data = load_fixture("notice_analyst_v1")
    NoticeSchema(**data)  # raise X → 통과


def test_fixture_form_parser_passes_FormSchema():
    from ontology.schemas import FormSchema
    data = load_fixture("form_parser_v1")
    FormSchema(**data)


def test_fixture_evidence_extractor_passes_EvidenceSchema():
    from ontology.schemas import EvidenceSchema
    data = load_fixture("evidence_extractor_v1")
    EvidenceSchema(**data)


def test_fixture_company_analyzer_has_required_keys():
    """company_analyzer는 CompanySchema + FitAnalysis 둘 다 포함."""
    from ontology.schemas import CompanySchema, FitAnalysis
    data = load_fixture("company_analyzer_v1")
    assert "company_schema" in data
    assert "fit_analysis" in data
    CompanySchema(**data["company_schema"])
    FitAnalysis(**data["fit_analysis"])


def test_fixture_evidence_mapper_passes_MappingResult():
    from ontology.schemas import MappingResult
    data = load_fixture("evidence_mapper_v1")
    MappingResult(**data)


def test_fixture_missing_material_array_items_pass_MissingMaterial():
    from ontology.schemas import MissingMaterial
    data = load_fixture("missing_material_v1")
    assert "missing_materials" in data
    for item in data["missing_materials"]:
        MissingMaterial(**item)


def test_fixture_draft_writer_basic_shape():
    """draft_writer 응답 핵심 필드."""
    data = load_fixture("draft_writer_v1")
    assert data["draft_item_id"]
    assert data["question_id"]
    assert data["content"]
    assert isinstance(data["used_evidence_ids"], list)
    assert data["char_count"] > 0


def test_fixture_draft_rewriter_basic_shape():
    data = load_fixture("draft_rewriter_v1")
    assert data["question_id"]
    assert data["suggestion"]
    assert "diff_summary" in data
    assert isinstance(data["used_evidence_ids"], list)


# ─── R4: validate_used_evidence_ids ──────────────────────────────

def test_used_evidence_validation_pass():
    response = {"used_evidence_ids": ["ev_tech_001"]}
    out = validate_used_evidence_ids(response, input_evidence_ids=["ev_tech_001", "ev_market_001"])
    assert out == ["ev_tech_001"]


def test_used_evidence_validation_empty_list():
    response = {"used_evidence_ids": []}
    out = validate_used_evidence_ids(response, input_evidence_ids=["ev_x"])
    assert out == []


def test_used_evidence_validation_field_missing():
    """field 자체가 없으면 빈 배열 처리."""
    response = {"draft": "..."}
    out = validate_used_evidence_ids(response, input_evidence_ids=["ev_x"])
    assert out == []


def test_used_evidence_validation_hallucinated_raises():
    """input에 없는 ID 발견 시 raise."""
    response = {"used_evidence_ids": ["ev_real", "ev_HALLUCINATED"]}
    with pytest.raises(LLMHallucinatedEvidenceError, match="ev_HALLUCINATED"):
        validate_used_evidence_ids(response, input_evidence_ids=["ev_real"])


def test_used_evidence_validation_non_list_raises():
    response = {"used_evidence_ids": "not_a_list"}
    with pytest.raises(LLMResponseError):
        validate_used_evidence_ids(response, input_evidence_ids=["ev_x"])


def test_used_evidence_real_fixture_draft_writer():
    """draft_writer fixture로 실제 검증 흐름."""
    data = load_fixture("draft_writer_v1")
    input_evidence_ids = ["ev_tech_001", "ev_market_001"]   # 호출자가 LLM에 넘긴 evidence
    out = validate_used_evidence_ids(data, input_evidence_ids=input_evidence_ids)
    assert out == ["ev_tech_001"]


def test_used_evidence_real_fixture_draft_rewriter_partial_hallucination():
    """draft_rewriter fixture는 ev_market_001 + ev_tech_001 사용. 둘 다 input에 없으면 raise."""
    data = load_fixture("draft_rewriter_v1")
    # input에 ev_market_001만 있으면 ev_tech_001은 환각
    with pytest.raises(LLMHallucinatedEvidenceError, match="ev_tech_001"):
        validate_used_evidence_ids(data, input_evidence_ids=["ev_market_001"])
