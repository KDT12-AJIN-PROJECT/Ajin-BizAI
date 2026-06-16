"""
Azure OpenAI Provider — Azure OpenAI 연동
AI_PROVIDER=azure 로 활성화

OpenAIProvider를 상속 → _get_client / _chat만 override.
모든 8 AI 모듈 + V1 호환 5 메서드가 Azure OpenAI로 자동 라우팅.
"""
import os
from typing import Optional

from services.openai_provider import OpenAIProvider
from services.audit_logger import audit_log

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


class AzureOpenAIProvider(OpenAIProvider):
    provider_name = "azure"
    model_name = AZURE_OPENAI_DEPLOYMENT

    def _get_client(self):
        try:
            from openai import AsyncAzureOpenAI
            return AsyncAzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_version=AZURE_OPENAI_API_VERSION,
            )
        except ImportError:
            raise RuntimeError("openai 패키지가 설치되지 않았습니다. pip install openai")

    # o1/o3/o4 reasoning 모델은 max_tokens 대신 max_completion_tokens,
    # temperature/top_p 미지원
    _IS_REASONING_MODEL = AZURE_OPENAI_DEPLOYMENT.startswith(("o1", "o3", "o4"))

    async def _chat(
        self,
        system: str,
        user: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        top_p: Optional[float] = None,
    ) -> str:
        """Azure OpenAI chat 호출.

        model 파라미터 무시 — Azure는 deployment name(AZURE_OPENAI_DEPLOYMENT)으로 고정.
        o1/o3/o4 reasoning 모델:
          - max_completion_tokens = max(max_tokens * 4, 16000) — reasoning 토큰 여분 확보
          - temperature/top_p 미지원 → 제외
          - system → developer role 변환
        """
        client = self._get_client()
        if self._IS_REASONING_MODEL:
            # reasoning 토큰이 output 토큰보다 훨씬 많이 소비됨 → 여유 있게 설정
            reasoning_budget = max(max_tokens * 4, 16000)
            kwargs = {
                "model": AZURE_OPENAI_DEPLOYMENT,
                "messages": [
                    {"role": "developer", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_completion_tokens": reasoning_budget,
            }
        else:
            kwargs = {
                "model": AZURE_OPENAI_DEPLOYMENT,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if top_p is not None:
                kwargs["top_p"] = top_p
        res = await client.chat.completions.create(**kwargs)
        if res.usage:
            self._last_token_usage = {
                "prompt_tokens": res.usage.prompt_tokens,
                "completion_tokens": res.usage.completion_tokens,
                "total_tokens": res.usage.total_tokens,
            }
        return res.choices[0].message.content

    async def _chat_stream(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ):
        """Azure OpenAI 스트리밍 호출 — async generator of text chunks."""
        client = self._get_client()
        kwargs = {
            "model": AZURE_OPENAI_DEPLOYMENT,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    @audit_log(task_type="generate_draft")
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        """V1 섹션별 초안 — max_tokens 최소화로 속도 개선."""
        import json
        profile_str = json.dumps(profile, ensure_ascii=False)[:800] if isinstance(profile, dict) else str(profile)[:800]
        system = "정부 지원사업 사업계획서 전문가. 요청 섹션만 간결하게 작성."
        user = (
            f"공고문:\n{notice_text[:1500]}\n\n"
            f"기업 프로필:\n{profile_str}\n\n"
            f"[{section}] 섹션을 500자 이내로 작성하세요."
        )
        return await self._chat(system, user, max_tokens=800, temperature=0.4)

    @audit_log(task_type="draft_rewriter")
    async def draft_rewriter(
        self,
        question_id: str,
        current_draft: str,
        user_message: str,
        evidence_list: list,
        *,
        request_id: str = "",
        session_id: str = "",
    ) -> dict:
        """초안 재작성 — Azure OpenAI 실제 호출 (OpenAIProvider mock 위임 override)."""
        evidence_summary = ""
        if evidence_list:
            snippets = [
                f"- {e.get('content', '')[:300]}"
                for e in evidence_list[:5]
                if e.get("content")
            ]
            if snippets:
                evidence_summary = "\n\n[참고 자료]\n" + "\n".join(snippets)

        system = (
            "당신은 정부지원사업 사업계획서 전문 컨설턴트입니다. "
            "사용자의 수정 요청을 반영하여 기존 초안을 개선하세요. "
            "JSON으로만 응답하세요: {\"suggestion\": \"...\", \"diff_summary\": \"...\"}"
        )
        user = (
            f"[문항 ID] {question_id}\n\n"
            f"[기존 초안]\n{current_draft[:2000]}\n\n"
            f"[수정 요청]\n{user_message}"
            f"{evidence_summary}"
        )
        import json, re
        raw = await self._chat(system, user, max_tokens=2048)
        try:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                return {
                    "suggestion": parsed.get("suggestion", raw),
                    "diff_summary": parsed.get("diff_summary", user_message),
                    "used_evidence_ids": [e.get("evidence_id", "") for e in evidence_list[:5]],
                }
        except Exception:
            pass
        return {
            "suggestion": raw,
            "diff_summary": user_message,
            "used_evidence_ids": [e.get("evidence_id", "") for e in evidence_list[:5]],
        }
