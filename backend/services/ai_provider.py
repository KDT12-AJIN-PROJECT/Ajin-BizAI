"""
AI Provider 인터페이스 (PRD §14.1 8 모듈 + V1 호환 5 메서드)

AI_PROVIDER 환경변수에 따라 mock / local / openai / anthropic / hybrid 중 선택.

v0.2 8 모듈 (PRD §14.1):
  1. notice_analyst       - 공고문 분석
  2. form_parser          - 제출양식 분석
  3. evidence_extractor   - 참고자료 evidence 추출
  4. company_analyzer     - 기업정보 분석 + FitAnalysis
  5. evidence_mapper      - 문항 ↔ evidence 매칭 (RAG)
  6. missing_material     - 부족자료 진단
  7. draft_writer         - 문항별 초안 작성
  8. draft_rewriter       - 대화형 보완

V1 호환 5 메서드 (기존):
  - generate_draft / evaluate_draft / improve_draft
  - check_completeness / chat_review

Failure Protocol (test_03 §3.7.2):
  - exponential backoff with jitter
  - 5회 retry (429/500/502/503/504/timeout)
  - no-retry: 400/401/403/context overflow
"""
import asyncio
import os
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


# ─── Failure Protocol Retry Helper (test_03 §3.7.2) ──────────────────


class RetryableError(Exception):
    """Retry 가능한 일시 오류 (429 / 5xx / timeout / network)"""


class NonRetryableError(Exception):
    """Retry 불가 (400 / 401 / 403 / context overflow / schema 오류 등)"""


async def call_with_retry(
    fn: Callable,
    *args,
    max_retries: int = 5,
    base_delay: float = 1.0,
    **kwargs,
) -> Any:
    """exponential backoff + jitter retry pattern.

    재시도 대상: RetryableError (429 / 500 / 502 / 503 / 504 / timeout)
    재시도 안 함: NonRetryableError (400 / 401 / 403 / context overflow)

    delay = base * (2 ** attempt) + jitter(±20%)
    예: base=1 → 1s, 2s, 4s, 8s, 16s (총 ~31s)
    """
    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except NonRetryableError:
            raise
        except RetryableError as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            jitter = random.uniform(-0.2 * delay, 0.2 * delay)
            await asyncio.sleep(delay + jitter)
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("call_with_retry exhausted without error")


# ─── AIProvider 인터페이스 ────────────────────────────────────────────


class AIProvider(ABC):
    """모든 provider가 구현해야 하는 인터페이스. v0.2 8 모듈 + V1 호환 5 메서드."""

    provider_name: str = "abstract"
    model_name: str = "abstract"

    # ──────────────────────────────────────────────
    # v0.2 8 AI 모듈 (PRD §14.1)
    # ──────────────────────────────────────────────

    async def notice_analyst(self, notice_text: str, *, request_id: str = "", session_id: str = "") -> Dict[str, Any]:
        """공고문 → NoticeSchema (PRD §13.x). 기본 NotImplemented."""
        raise NotImplementedError("notice_analyst not implemented for this provider")

    async def form_parser(
        self, form_text: str, form_name: str = "", *, request_id: str = "", session_id: str = ""
    ) -> Dict[str, Any]:
        """제출양식 → FormSchema (PRD §13.2)."""
        raise NotImplementedError("form_parser not implemented for this provider")

    async def evidence_extractor(
        self, ref_text: str, source_file: str = "", source_page: int = 0,
        *, request_id: str = "", session_id: str = "",
    ) -> Dict[str, Any]:
        """참고자료 chunk → EvidenceSchema (PRD §13.3)."""
        raise NotImplementedError("evidence_extractor not implemented for this provider")

    async def company_analyzer(
        self, company_files: List[Dict[str, Any]], notice_schema: Dict[str, Any],
        *, request_id: str = "", session_id: str = "",
    ) -> Dict[str, Any]:
        """기업정보 → CompanySchema + FitAnalysis (PRD §13.x)."""
        raise NotImplementedError("company_analyzer not implemented for this provider")

    async def evidence_mapper(
        self, form_schema: Dict[str, Any], evidence_list: List[Dict[str, Any]],
        notice_schema: Dict[str, Any], matching_threshold: float = 0.70,
        *, request_id: str = "", session_id: str = "",
    ) -> Dict[str, Any]:
        """문항 × evidence RAG 매칭 → MappingResult (PRD §13.4)."""
        raise NotImplementedError("evidence_mapper not implemented for this provider")

    async def missing_material(
        self, mapping_result: Dict[str, Any],
        *, request_id: str = "", session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """근거 부족 문항 → MissingMaterial[] (PRD §13.5)."""
        raise NotImplementedError("missing_material not implemented for this provider")

    async def draft_writer(
        self, question: Dict[str, Any], matched_evidence: List[Dict[str, Any]],
        company_schema: Dict[str, Any], notice_schema: Dict[str, Any],
        writing_guidelines: Optional[List[str]] = None,
        constraints: Optional[Dict[str, int]] = None,
        *, request_id: str = "", session_id: str = "",
    ) -> Dict[str, Any]:
        """문항별 초안 → DraftItem (PRD §13.7).
        환각 방지 (PRD §14.3):
        - matched_evidence 외부 정량 수치 생성 금지
        - used_evidence_ids 기록 강제
        - 글자수 검증 (constraints.max_length / min_length)
        """
        raise NotImplementedError("draft_writer not implemented for this provider")

    async def draft_rewriter(
        self, question_id: str, current_draft: str, user_message: str,
        evidence_list: List[Dict[str, Any]],
        *, request_id: str = "", session_id: str = "",
    ) -> Dict[str, Any]:
        """대화형 보완 → suggestion (PRD §10.4 / §16.5)."""
        raise NotImplementedError("draft_rewriter not implemented for this provider")

    # ──────────────────────────────────────────────
    # V1 호환 5 메서드 (DraftPage v1 / 기존 코드)
    # ──────────────────────────────────────────────

    @abstractmethod
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        """V1: 섹션별 초안 생성"""

    @abstractmethod
    async def evaluate_draft(self, draft_text: str, notice_text: str) -> dict:
        """V1: 초안 평가"""

    @abstractmethod
    async def improve_draft(self, draft_text: str, instruction: str) -> str:
        """V1: 초안 개선"""

    @abstractmethod
    async def check_completeness(self, uploaded_docs: dict, notice_text: str) -> dict:
        """V1: 업로드 자료 완성도 검사"""

    @abstractmethod
    async def chat_review(self, message: str, draft_content: str, notice_title: str, history: list) -> str:
        """V1: 사업계획서 검토 챗봇"""


def get_provider() -> AIProvider:
    """환경변수 AI_PROVIDER 값에 따라 provider 인스턴스 반환.

    값:
      - mock      → MockProvider (default, V1·V2 mock 응답)
      - local     → LocalProvider (LM Studio / Ollama)
      - openai    → OpenAIProvider
      - anthropic → AnthropicProvider
      - azure     → AzureOpenAIProvider (Azure OpenAI Service)
      - hybrid    → 단계별 분기 (Phase 4-C 시점에 구현)
    """
    provider_name = os.getenv("AI_PROVIDER", "mock").lower()

    if provider_name == "openai":
        from services.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider_name == "anthropic":
        from services.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    elif provider_name == "azure":
        from services.azure_openai_provider import AzureOpenAIProvider
        return AzureOpenAIProvider()
    elif provider_name == "local":
        from services.local_provider import LocalProvider
        return LocalProvider()
    elif provider_name == "hybrid":
        # TODO Phase 4-C: hybrid routing (단계별 provider 분기)
        from services.mock_provider import MockProvider
        return MockProvider()
    else:
        from services.mock_provider import MockProvider
        return MockProvider()
