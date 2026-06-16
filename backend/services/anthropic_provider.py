"""
Anthropic Provider — Claude API 연동 (v0.2 신규, PRD §14.2 + §1.7.1)

config 기반 모델 (Phase 0 검증 결과 적용):
  - ANTHROPIC_MODEL_HAIKU  → evidence_extractor / evidence_mapper / missing_material
  - ANTHROPIC_MODEL_SONNET → notice/form/company analyzer + draft_writer (Phase 7-A A/B 결과)
  - ANTHROPIC_MODEL_OPUS   → premium_final_writer 전용 (PRD §14.2.4, 기본 draft_writer 아님)

Failure Protocol (test_03 §3.7.2):
  - exponential backoff + jitter
  - retry: 429 / 500 / 502 / 503 / 504 / timeout
  - no-retry: 400 / 401 / 403 / context overflow

Phase 4-B 단계: 구조 + retry + 8 stub. 실제 Claude API 호출은 Phase 4-C~G에서 점진 구현.
"""
import json
import os
from typing import Any, Dict, List, Optional

from services.ai_provider import (
    AIProvider, NonRetryableError, RetryableError, call_with_retry,
)
from services.audit_logger import audit_log

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_HAIKU = os.getenv("ANTHROPIC_MODEL_HAIKU", "claude-haiku-4-5")
ANTHROPIC_MODEL_SONNET = os.getenv("ANTHROPIC_MODEL_SONNET", "claude-sonnet-4-6")
ANTHROPIC_MODEL_OPUS = os.getenv("ANTHROPIC_MODEL_OPUS", "claude-opus-4-7")


def _classify_http_error(status_code: int, error_str: str = "") -> Exception:
    """HTTP 상태 코드 → Retry 분류 (test_03 §3.7.2)"""
    if status_code in (400, 401, 403):
        return NonRetryableError(f"client error {status_code}: {error_str}")
    if "context window" in error_str.lower() or "context_length_exceeded" in error_str.lower():
        return NonRetryableError(f"context overflow: {error_str}")
    if status_code in (429, 500, 502, 503, 504):
        return RetryableError(f"transient error {status_code}: {error_str}")
    # 기본: 알 수 없는 5xx도 retry
    if 500 <= status_code < 600:
        return RetryableError(f"server error {status_code}: {error_str}")
    return NonRetryableError(f"unhandled {status_code}: {error_str}")


class AnthropicProvider(AIProvider):
    """Claude API provider (Phase 4-B 구조, 실제 호출은 Phase 4-C~G)."""

    provider_name = "anthropic"

    def __init__(self, model_role: str = "sonnet"):
        """model_role: "haiku" | "sonnet" | "opus" (premium_final_writer 전용)"""
        self.model_role = model_role
        self.model_name = self._select_model(model_role)

    @staticmethod
    def _select_model(role: str) -> str:
        if role == "haiku":
            return ANTHROPIC_MODEL_HAIKU
        if role == "opus":
            return ANTHROPIC_MODEL_OPUS
        return ANTHROPIC_MODEL_SONNET  # default

    def _get_client(self):
        try:
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        except ImportError:
            raise RuntimeError("anthropic 패키지 미설치. pip install anthropic")

    async def _chat_raw(
        self,
        system: str,
        user: str,
        model: Optional[str] = None,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        top_p: Optional[float] = None,
    ) -> str:
        """단일 chat 호출 (retry 없음, call_with_retry 안에서 사용).

        NOAPI-P2 R2: temperature=0 default (repeatability + test/A-B 정합).
        top_p는 None일 때 미전달 (Anthropic SDK default 사용).
        max_tokens 초과 응답은 잘림 (caller가 검증).
        """
        client = self._get_client()
        kwargs = {
            "model": model or self.model_name,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
        }
        if top_p is not None:
            kwargs["top_p"] = top_p
        try:
            res = await client.messages.create(**kwargs)
            # token usage 캐싱 (audit_log 용)
            if hasattr(res, "usage") and res.usage:
                self._last_token_usage = {
                    "input_tokens": getattr(res.usage, "input_tokens", 0),
                    "output_tokens": getattr(res.usage, "output_tokens", 0),
                    "cache_read_input_tokens": getattr(res.usage, "cache_read_input_tokens", 0),
                    "cache_creation_input_tokens": getattr(res.usage, "cache_creation_input_tokens", 0),
                }
            # content 추출
            if res.content and len(res.content) > 0:
                return res.content[0].text
            return ""
        except Exception as e:
            # HTTP 오류 분류 (anthropic 패키지 예외 형식 따라 보강)
            status = getattr(e, "status_code", None)
            if status is not None:
                raise _classify_http_error(status, str(e))
            # network / timeout
            err_str = str(e).lower()
            if "timeout" in err_str or "network" in err_str or "connection" in err_str:
                raise RetryableError(f"network/timeout: {e}")
            raise NonRetryableError(f"unknown: {e}")

    async def _chat(
        self,
        system: str,
        user: str,
        model: Optional[str] = None,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        top_p: Optional[float] = None,
    ) -> str:
        """retry wrapped chat (default 5 attempts).

        NOAPI-P2 R2: temperature/max_tokens/top_p 옵션 노출.
        repeatability를 위해 temperature=0 default.
        """
        return await call_with_retry(
            self._chat_raw, system, user, model,
            temperature=temperature, max_tokens=max_tokens, top_p=top_p,
        )

    def _parse_json(self, text: str) -> Any:
        """LLM 출력 → JSON 파싱. 마크다운 코드블록 제거."""
        text = text.strip()
        if text.startswith("```"):
            # ```json ... ``` 또는 ``` ... ```
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            if text.endswith("```"):
                text = text[:-3].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise NonRetryableError(f"JSON parse error: {e}\n원본:\n{text[:500]}")

    # ──────────────────────────────────────────────
    # v0.2 8 AI 모듈 (Phase 4-B = stub + 구조)
    # ──────────────────────────────────────────────

    @audit_log(task_type="notice_analyst")
    async def notice_analyst(self, notice_text: str, *, request_id: str = "", session_id: str = "") -> dict:
        # TODO Phase 4-C: prompts/notice_analyst.md 로드 + system prompt + JSON output 강제
        raise NotImplementedError("anthropic notice_analyst — Phase 4-C에서 구현")

    @audit_log(task_type="form_parser")
    async def form_parser(self, form_text: str, form_name: str = "", *, request_id: str = "", session_id: str = "") -> dict:
        raise NotImplementedError("anthropic form_parser — Phase 4-C")

    @audit_log(task_type="evidence_extractor")
    async def evidence_extractor(self, ref_text: str, source_file: str = "", source_page: int = 0, *, request_id: str = "", session_id: str = "") -> dict:
        raise NotImplementedError("anthropic evidence_extractor — Phase 4-C")

    @audit_log(task_type="company_analyzer")
    async def company_analyzer(self, company_files: list, notice_schema: dict, *, request_id: str = "", session_id: str = "") -> dict:
        raise NotImplementedError("anthropic company_analyzer — Phase 4-C")

    @audit_log(task_type="evidence_mapper")
    async def evidence_mapper(self, form_schema: dict, evidence_list: list, notice_schema: dict, matching_threshold: float = 0.70, *, request_id: str = "", session_id: str = "") -> dict:
        raise NotImplementedError("anthropic evidence_mapper — Phase 4-C")

    @audit_log(task_type="missing_material")
    async def missing_material(self, mapping_result: dict, *, request_id: str = "", session_id: str = "") -> list:
        raise NotImplementedError("anthropic missing_material — Phase 4-C")

    @audit_log(task_type="draft_writer")
    async def draft_writer(self, question: dict, matched_evidence: list, company_schema: dict, notice_schema: dict, writing_guidelines: list = None, constraints: dict = None, *, request_id: str = "", session_id: str = "") -> dict:
        raise NotImplementedError("anthropic draft_writer — Phase 4-E")

    @audit_log(task_type="draft_rewriter")
    async def draft_rewriter(self, question_id: str, current_draft: str, user_message: str, evidence_list: list, *, request_id: str = "", session_id: str = "") -> dict:
        raise NotImplementedError("anthropic draft_rewriter — Phase 4-E")

    # ──────────────────────────────────────────────
    # V1 호환 5 메서드 (V1 코드 호환성, 단순 동작만)
    # ──────────────────────────────────────────────

    @audit_log(task_type="generate_draft")
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        system = "당신은 정부 지원사업 사업계획서 작성 전문가입니다."
        user = f"공고문:\n{notice_text[:3000]}\n\n기업 프로필:\n{profile}\n\n{section} 섹션을 작성해 주세요."
        return await self._chat(system, user)

    @audit_log(task_type="evaluate_draft")
    async def evaluate_draft(self, draft_text: str, notice_text: str) -> dict:
        system = "사업계획서 심사 전문가입니다."
        user = f"초안:\n{draft_text[:2000]}\n\n100점 만점 점수, 등급(A/B/C/D), 핵심 피드백을 작성하세요."
        result = await self._chat(system, user)
        return {"score": 0, "grade": "?", "feedback": result, "by_section": {}}

    @audit_log(task_type="improve_draft")
    async def improve_draft(self, draft_text: str, instruction: str) -> str:
        system = "사업계획서 개선 전문가입니다."
        user = f"기존 내용:\n{draft_text}\n\n지시:\n{instruction}\n\n개선된 내용:"
        return await self._chat(system, user)

    @audit_log(task_type="check_completeness")
    async def check_completeness(self, uploaded_docs: dict, notice_text: str) -> dict:
        from services.diagnosis import calculate_completeness
        return calculate_completeness(notice_text, uploaded_docs, {})

    @audit_log(task_type="chat_review")
    async def chat_review(self, message: str, draft_content: str, notice_title: str, history: list) -> str:
        history_text = "\n".join(
            f"{'사용자' if h['role'] == 'user' else 'AI'}: {h['content']}"
            for h in history[-6:]
        )
        system = "당신은 정부지원사업 사업계획서 전문 컨설턴트입니다."
        user = f"[공고명] {notice_title}\n\n[현재 초안]\n{draft_content[:1500]}\n\n[이전 대화]\n{history_text}\n\n[사용자 메시지]\n{message}"
        return await self._chat(system, user)
