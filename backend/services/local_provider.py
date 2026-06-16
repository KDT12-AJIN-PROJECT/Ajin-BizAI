"""
Local LLM Provider — LM Studio / Ollama 등 로컬 OpenAI-호환 서버 연동
AI_PROVIDER=local 로 활성화
TODO: LOCAL_LLM_URL, LOCAL_LLM_MODEL 환경변수 설정 필요
"""
import os
import httpx
from services.ai_provider import AIProvider
from services.audit_logger import audit_log

LOCAL_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1")
LOCAL_MODEL = os.getenv("LOCAL_LLM_MODEL", "local-model")


class LocalProvider(AIProvider):
    provider_name = "local"
    model_name = LOCAL_MODEL

    async def _chat(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(
                f"{LOCAL_URL}/chat/completions",
                json={
                    "model": LOCAL_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                },
            )
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]

    # ──────────────────────────────────────────────
    # v0.2 8 AI 모듈 (Phase 4-C 단계: MockProvider 위임)
    # 향후 실제 Local LLM (LM Studio / Ollama) 호출로 교체
    # ──────────────────────────────────────────────

    def _mock_fallback(self):
        from services.mock_provider import MockProvider
        return MockProvider()

    async def notice_analyst(self, notice_text: str, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().notice_analyst(notice_text, request_id=request_id, session_id=session_id)

    async def form_parser(self, form_text: str, form_name: str = "", *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().form_parser(form_text, form_name, request_id=request_id, session_id=session_id)

    async def evidence_extractor(self, ref_text: str, source_file: str = "", source_page: int = 0, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().evidence_extractor(ref_text, source_file, source_page, request_id=request_id, session_id=session_id)

    async def company_analyzer(self, company_files: list, notice_schema: dict, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().company_analyzer(company_files, notice_schema, request_id=request_id, session_id=session_id)

    async def evidence_mapper(self, form_schema: dict, evidence_list: list, notice_schema: dict, matching_threshold: float = 0.70, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().evidence_mapper(form_schema, evidence_list, notice_schema, matching_threshold, request_id=request_id, session_id=session_id)

    async def missing_material(self, mapping_result: dict, *, request_id: str = "", session_id: str = "") -> list:
        return await self._mock_fallback().missing_material(mapping_result, request_id=request_id, session_id=session_id)

    async def draft_writer(self, question: dict, matched_evidence: list, company_schema: dict, notice_schema: dict, writing_guidelines: list = None, constraints: dict = None, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().draft_writer(question, matched_evidence, company_schema, notice_schema, writing_guidelines, constraints, request_id=request_id, session_id=session_id)

    async def draft_rewriter(self, question_id: str, current_draft: str, user_message: str, evidence_list: list, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().draft_rewriter(question_id, current_draft, user_message, evidence_list, request_id=request_id, session_id=session_id)

    # ──────────────────────────────────────────────
    # V1 호환 5 메서드 (실제 Local LLM 호출)
    # ──────────────────────────────────────────────

    @audit_log(task_type="generate_draft")
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        system = "당신은 정부 지원사업 사업계획서 작성 전문가입니다. 주어진 공고문과 기업 프로필을 바탕으로 지정 섹션을 작성하세요."
        user = f"공고문:\n{notice_text[:2000]}\n\n기업 프로필:\n{profile}\n\n섹션: {section}\n\n해당 섹션 내용을 작성해 주세요."
        return await self._chat(system, user)

    @audit_log(task_type="evaluate_draft")
    async def evaluate_draft(self, draft_text: str, notice_text: str) -> dict:
        import json, re
        system = '사업계획서 심사 전문가입니다. 반드시 JSON만 응답하세요: {"score": 0-100, "grade": "A/B/C/D", "feedback": "...", "by_section": {}}'
        user = f"공고문:\n{notice_text[:1000]}\n\n초안:\n{draft_text[:2000]}\n\n평가 결과를 JSON으로만 반환하세요."
        result = await self._chat(system, user)
        try:
            m = re.search(r'\{.*\}', result, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                return {
                    "score": int(parsed.get("score", 0)),
                    "grade": str(parsed.get("grade", "?")),
                    "feedback": str(parsed.get("feedback", result)),
                    "by_section": parsed.get("by_section", {}),
                }
        except Exception:
            pass
        return {"score": 0, "grade": "?", "feedback": result, "by_section": {}}

    @audit_log(task_type="improve_draft")
    async def improve_draft(self, draft_text: str, instruction: str) -> str:
        system = "사업계획서 개선 전문가입니다."
        user = f"기존 내용:\n{draft_text}\n\n개선 지시:\n{instruction}\n\n개선된 내용을 작성해 주세요."
        return await self._chat(system, user)

    @audit_log(task_type="check_completeness")
    async def check_completeness(self, uploaded_docs: dict, notice_text: str) -> dict:
        from services.diagnosis import calculate_completeness
        all_text = " ".join(str(v) for v in uploaded_docs.values() if v)
        return calculate_completeness(notice_text, uploaded_docs, {})

    @audit_log(task_type="chat_review")
    async def chat_review(self, message: str, draft_content: str, notice_title: str, history: list) -> str:
        history_text = "\n".join(
            f"{'사용자' if h['role'] == 'user' else 'AI'}: {h['content']}"
            for h in history[-6:]
        )
        system = "당신은 정부지원사업 사업계획서 전문 컨설턴트입니다. 작성된 초안을 검토하고 사용자의 수정 요청에 답변하세요."
        user = f"[공고명] {notice_title}\n\n[현재 초안]\n{draft_content[:1500]}\n\n[이전 대화]\n{history_text}\n\n[사용자 메시지]\n{message}"
        return await self._chat(system, user)
