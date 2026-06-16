"""
OpenAI Provider — GPT API 연동
AI_PROVIDER=openai 로 활성화
TODO: OPENAI_API_KEY 환경변수 설정 필요

v0.2 8 모듈 단계별 활성화:
  - AI-1 (NOAPI-P1/P2 자산 활용): notice_analyst 본체 (실제 OpenAI 호출)
  - AI-1.x 후속: form_parser / draft_writer / 나머지 5 module
  - V1 호환 5 메서드: 실제 OpenAI API 호출 (기존)
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from services.ai_provider import AIProvider, NonRetryableError
from services.audit_logger import audit_log
from services.llm_response_parser import (
    parse_llm_json,
    validate_used_evidence_ids,
    LLMResponseError,
    LLMHallucinatedEvidenceError,
)
from services.llm_token_budget import assert_budget, TokenBudgetExceeded

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_ANALYSIS = os.getenv("OPENAI_MODEL_ANALYSIS", OPENAI_MODEL)
OPENAI_MODEL_DRAFT = os.getenv("OPENAI_MODEL_DRAFT", OPENAI_MODEL)
# 2026-05-18: form_parser 별도 분리 — notice보다 입력이 큼 (~37K tokens) → TPM 회피용
# 미설정 시 OPENAI_MODEL_ANALYSIS fallback (기존 동작 유지)
OPENAI_MODEL_FORM_PARSER = os.getenv("OPENAI_MODEL_FORM_PARSER", OPENAI_MODEL_ANALYSIS)

# gpt-4o-mini context window
OPENAI_CONTEXT_LIMIT = int(os.getenv("OPENAI_CONTEXT_LIMIT", "128000"))


# ─── NOAPI-P3: company_analyzer user prompt builder (3 섹션 분리) ──────────────

def _build_company_analyzer_user_prompt(
    company_context: dict, notice_schema: dict, session_id: str,
) -> str:
    """resolver 결과 + NoticeSchema → LLM user message (3 섹션 + Notice).

    섹션 (NOAPI-P3 보완 1):
      ## User Provided Company Profile
      ## Parsed Company Files
      ## Missing or Unverified Company Information
      ## NoticeSchema
    """
    import json

    parts: list[str] = []

    parts.append(f"세션 ID: {session_id or 'anonymous'}")
    parts.append("")
    parts.append("## User Provided Company Profile")
    profile = company_context.get("structured_company_profile")
    if profile:
        parts.append("(사용자 직접 입력 — 출처가 사용자 입력임을 capability.source에 명시)")
        parts.append(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        parts.append("(없음)")
    parts.append("")

    parts.append("## Parsed Company Files")
    files = company_context.get("company_files") or []
    if files:
        for i, f in enumerate(files, 1):
            parts.append(f"### [{i}] {f.get('filename', '?')} (document_type={f.get('document_type', 'other')})")
            if f.get("truncated"):
                parts.append(
                    f"⚠ truncated: original={f.get('original_chars')} chars → returned={f.get('returned_chars')} chars."
                    " 잘린 부분에 대해 추측 금지."
                )
            parts.append(f.get("parsed_text") or "")
            parts.append("")
    else:
        parts.append("(없음)")
    parts.append("")

    parts.append("## Missing or Unverified Company Information")
    warnings_in = company_context.get("warnings") or []
    if warnings_in:
        parts.append(json.dumps(warnings_in, ensure_ascii=False, indent=2))
    else:
        parts.append("(없음)")
    parts.append("")

    parts.append("## NoticeSchema")
    parts.append(json.dumps(notice_schema or {}, ensure_ascii=False, indent=2))
    parts.append("")

    parts.append("위 입력을 바탕으로 prompt 지침에 따라 JSON 하나를 반환하세요.")
    return "\n".join(parts)


# ─── E-3 sub-step 1: draft_writer user prompt builder ──────────────
# 2026-05-18: prompts/draft_writer.md (system) + 본 함수 (user) 조합.
# 정책 검증 (used_evidence_ids 강제 / evidence 없는 수치 차단 / table_draft / missing 생성)은
# sub-step 2에서 추가. 이번 단계는 LLM 호출 본체만 구현.

def _build_draft_writer_user_prompt(
    question: dict,
    matched_evidence: list,
    company_schema: dict,
    notice_schema: dict,
    writing_guidelines: Optional[list] = None,
    constraints: Optional[dict] = None,
    *,
    evaluation_rubric: Optional[dict] = None,
    announcement_signals: Optional[dict] = None,
) -> str:
    """단일 문항용 draft_writer user message.

    2026-05-18 E-3 정책 강화 (v3):
      - evidence 없을 때 "추정/창작 금지" 명시
      - table_input 문항일 때 table_columns 포함
      - used_evidence_ids는 evidence_items의 ID 집합 내에서만 사용
      - evaluation_rubric (C-1.6): axes/weight/checklist 전달 → LLM이 평가기준 충족하며 작성
      - announcement_signals (C-1.5): eligibility/emphasis_keywords/compliance 전달 → 공고 요구 의식
    """
    import json

    parts: list[str] = []

    is_table = bool(question.get("is_table_item") or question.get("fill_mode") == "table_input")
    has_evidence = bool(matched_evidence)

    parts.append("## form_question")
    parts.append(json.dumps(question or {}, ensure_ascii=False, indent=2))
    parts.append("")

    parts.append("## evidence_items")
    if has_evidence:
        parts.append("(반드시 아래 항목만 인용. 외부 사실/수치 작성 절대 금지.)")
        parts.append("(used_evidence_ids 배열에 실제 인용한 evidence_id만 명시 — 인용 안 한 ID 포함 금지)")
    else:
        parts.append("⚠️ evidence_items 0개. 다음을 엄격히 따르세요:")
        parts.append("  - 수치/연도/금액/매출/실적 등 정량 정보 작성 절대 금지")
        parts.append("  - 고유명사(고객사/제품명/기관명 등) 작성 절대 금지")
        parts.append("  - 일반 원칙/방향성만 서술 가능")
        parts.append("  - 또는 'evidence 부족으로 본 항목은 추가 자료가 필요합니다' 안내문 작성 권장")
        parts.append("  - used_evidence_ids는 반드시 빈 배열 []")
    parts.append(json.dumps(matched_evidence or [], ensure_ascii=False, indent=2))
    parts.append("")

    parts.append("## company_profile")
    parts.append(json.dumps(company_schema or {}, ensure_ascii=False, indent=2))
    parts.append("")

    parts.append("## notice (요약)")
    notice_summary = {
        "name": (notice_schema or {}).get("name") if isinstance(notice_schema, dict) else None,
        "target": (notice_schema or {}).get("target") if isinstance(notice_schema, dict) else None,
        "evaluation_criteria_count": len((notice_schema or {}).get("evaluation_criteria") or []) if isinstance(notice_schema, dict) else 0,
    }
    parts.append(json.dumps(notice_summary, ensure_ascii=False, indent=2))
    parts.append("")

    # ── E-3: evaluation_rubric — 작성 기준 = 평가 기준 (C-1.6 산출물) ─────────
    if evaluation_rubric and isinstance(evaluation_rubric, dict):
        axes = evaluation_rubric.get("axes") or []
        if axes:
            parts.append("## evaluation_rubric (이 항목이 평가될 기준 — 충족 의식하며 작성)")
            parts.append(f"(source={evaluation_rubric.get('source')}, template={evaluation_rubric.get('template_type')}, axes {len(axes)}개)")
            rubric_summary = []
            for ax in axes:
                if not isinstance(ax, dict):
                    continue
                ax_entry = {
                    "axis_id": ax.get("axis_id"),
                    "name": ax.get("name"),
                    "weight": ax.get("weight"),
                }
                desc = ax.get("description")
                if desc:
                    ax_entry["description"] = desc[:150]
                checklist = ax.get("checklist") or []
                if checklist:
                    ax_entry["checklist"] = checklist[:5]
                rubric_summary.append(ax_entry)
            parts.append(json.dumps(rubric_summary, ensure_ascii=False, indent=2))
            parts.append("")

    # ── E-3: announcement_signals — 공고 요구사항 (C-1.5 산출물) ─────────────
    if announcement_signals and isinstance(announcement_signals, dict):
        eligibility = announcement_signals.get("eligibility") or []
        emphasis = announcement_signals.get("emphasis_keywords") or []
        compliance = announcement_signals.get("compliance_constraints") or []
        bonuses = announcement_signals.get("bonuses") or []

        sig_section = []
        if eligibility:
            elig_list = [
                {"name": e.get("name"), "value": (e.get("value") or "")[:200], "kind": e.get("kind")}
                for e in eligibility[:10] if isinstance(e, dict)
            ]
            sig_section.append(("eligibility (자격요건 — 충족 여부 의식)", elig_list))
        if emphasis:
            kw_list = [e.get("keyword") for e in emphasis[:15] if isinstance(e, dict) and e.get("keyword")]
            sig_section.append(("emphasis_keywords (이 키워드 자연스럽게 활용)", kw_list))
        if bonuses:
            bonus_list = [{"name": b.get("name"), "points": b.get("points")} for b in bonuses[:5] if isinstance(b, dict)]
            sig_section.append(("bonuses (가점조건 — 해당되면 강조)", bonus_list))
        if compliance:
            comp_list = [
                {"kind": c.get("kind"), "value": (c.get("value") or "")[:120]}
                for c in compliance[:8] if isinstance(c, dict)
            ]
            sig_section.append(("compliance_constraints (제출 형식/마감/서류)", comp_list))

        if sig_section:
            parts.append("## announcement_signals (공고 요구사항 — 작성 시 참고)")
            for label, data in sig_section:
                parts.append(f"### {label}")
                parts.append(json.dumps(data, ensure_ascii=False, indent=2))
            parts.append("")

    if writing_guidelines:
        parts.append("## writing_guidelines")
        parts.append(json.dumps(writing_guidelines, ensure_ascii=False, indent=2))
        parts.append("")

    if constraints:
        parts.append("## constraints")
        parts.append(json.dumps(constraints, ensure_ascii=False))
        parts.append("")

    parts.append("## 출력 형식 (단일 문항용)")
    if is_table:
        # table_input 문항은 content 대신 table_data 필수
        # 2026-05-18: 신/구 스키마 모두 지원 (table_columns 비었으면 table_schema.columns에서)
        from services.item_query_builder import get_table_columns
        cols = get_table_columns(question)
        parts.append(f"이 문항은 **table_input** 입니다 (table 컬럼 {len(cols)}개).")
        parts.append("응답:")
        parts.append('  items[0] = {')
        parts.append('    "question_id": "...",')
        parts.append('    "content": "(표 설명/요약 — 1~2문장)",')
        parts.append('    "table_data": [ [col1_v, col2_v, ...], [...], ... ],   ← 필수, 각 row는 table 컬럼 순서/개수와 일치')
        parts.append('    "used_evidence_ids": [...]')
        parts.append('  }')
        if cols:
            parts.append(f"table 컬럼 (순서 준수): {json.dumps(cols, ensure_ascii=False)}")
    else:
        parts.append("응답:")
        parts.append('  items[0] = {')
        parts.append('    "question_id": "...",')
        parts.append('    "content": "...",  ← 한국어 자연어')
        parts.append('    "used_evidence_ids": [...],  ← 빈 배열도 OK (인용 안 했을 때)')
        parts.append('    "table_data": []   ← 비워두기')
        parts.append('  }')

    return "\n".join(parts)


class OpenAIProvider(AIProvider):
    provider_name = "openai"
    model_name = OPENAI_MODEL

    def _get_client(self):
        # openai 패키지 설치 필요: pip install openai
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=OPENAI_API_KEY)
        except ImportError:
            raise RuntimeError("openai 패키지가 설치되지 않았습니다. pip install openai")

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
        """단일 chat 호출.

        NOAPI-P2 R2: temperature=0 default (repeatability + test 정합).
        """
        client = self._get_client()
        kwargs = {
            "model": model or OPENAI_MODEL,
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

    # ──────────────────────────────────────────────
    # v0.2 8 AI 모듈 (Phase 4-C 단계: MockProvider 위임)
    # 향후 실제 OpenAI API 호출로 교체 (Phase 4-C/E)
    # ──────────────────────────────────────────────

    def _mock_fallback(self):
        from services.mock_provider import MockProvider
        return MockProvider()

    @audit_log(task_type="notice_analyst")
    async def notice_analyst(self, notice_text: str, *, request_id: str = "", session_id: str = "") -> dict:
        """공고문 → NoticeSchema (PRD §13.x).

        AI-1: 실제 OpenAI 호출. NOAPI-P1/P2 자산 활용.
          - prompts/notice_analyst.md 로드
          - assert_budget (context overflow 방지)
          - _chat (temperature=0)
          - parse_llm_json + Pydantic NoticeSchema validation
          - mock fallback X — 실패 시 NonRetryableError
        """
        # circular import 방지: 런타임 import
        from prompts import load_prompt
        from ontology.schemas import NoticeSchema

        system, _version = load_prompt("notice_analyst")
        user = f"공고문 텍스트:\n{notice_text}"

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=4096,
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"notice_analyst context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_ANALYSIS,
            temperature=0.0,
            max_tokens=4096,
        )

        try:
            parsed = parse_llm_json(raw, schema=NoticeSchema)
        except LLMResponseError as e:
            # mock fallback 금지 — explicit raise
            raise NonRetryableError(f"notice_analyst LLM 응답 처리 실패: {e}") from e

        return parsed.model_dump()

    @audit_log(task_type="form_parser")
    async def form_parser(self, form_text: str, form_name: str = "", *, request_id: str = "", session_id: str = "") -> dict:
        """제출양식 → FormSchema (PRD §13.2).

        AI-1.x: notice_analyst와 같은 패턴.
          - prompts/form_parser.md 로드
          - assert_budget (context overflow 방지)
          - _chat (temperature=0)
          - parse_llm_json + Pydantic FormSchema validation
          - mock fallback X — 실패 시 NonRetryableError
        """
        from prompts import load_prompt
        from ontology.schemas import FormSchema

        system, _version = load_prompt("form_parser")
        user_parts = []
        if form_name:
            user_parts.append(f"양식 파일명: {form_name}")
        user_parts.append("양식 텍스트:")
        user_parts.append(form_text or "")
        user = "\n".join(user_parts)

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=8192,
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"form_parser context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_FORM_PARSER,
            temperature=0.0,
            max_tokens=8192,
        )

        try:
            parsed = parse_llm_json(raw, schema=FormSchema)
        except LLMResponseError as e:
            raise NonRetryableError(f"form_parser LLM 응답 처리 실패: {e}") from e

        return parsed.model_dump()

    @audit_log(task_type="evidence_extractor")
    async def evidence_extractor(
        self, ref_text: str, source_file: str = "", source_page: int = 0,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        """참고자료 텍스트 → evidence_items 추출 (E-2-mini, 2026-05-18).

        mock fallback 제거 + 실제 OpenAI 호출.
        prompts/evidence_extractor.md 사용.

        반환: {items: [{evidence_id, source_file, source_page, type, content, raw_text, ...}]}
        - evidence_id는 provider 코드에서 uuid로 부여 (prompt는 안 줌)
        """
        from prompts import load_prompt

        # 빈 텍스트면 빈 결과
        if not ref_text or not ref_text.strip():
            return {"items": []}

        system, _version = load_prompt("evidence_extractor")
        user_parts = [
            f"## source_file\n{source_file or 'unknown'}",
            f"## source_page\n{source_page or 0}",
            "## 참고자료 텍스트",
            ref_text,
            "",
            "위 자료에서 사업계획서 작성에 활용할 evidence items를 prompt 지침에 따라 추출하세요.",
        ]
        user = "\n".join(user_parts)

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=4096,
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"evidence_extractor context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_ANALYSIS,
            temperature=0.0,
            max_tokens=4096,
        )

        try:
            parsed = parse_llm_json(raw, schema=None)
        except LLMResponseError as e:
            raise NonRetryableError(f"evidence_extractor LLM 응답 처리 실패: {e}") from e

        items_raw = []
        if isinstance(parsed, dict):
            items_raw = parsed.get("items") or []
        if not isinstance(items_raw, list):
            items_raw = []

        # 정규화 + evidence_id 부여
        items_out: list[dict] = []
        for i, item in enumerate(items_raw):
            if not isinstance(item, dict):
                continue
            content = item.get("content") or ""
            if not content:
                continue
            items_out.append({
                "evidence_id": f"ev_{uuid.uuid4().hex[:10]}",
                "source_file": item.get("source_file") or source_file or "unknown",
                "source_page": item.get("source_page") if isinstance(item.get("source_page"), int) else (source_page or 0),
                "section": item.get("section"),
                "type": item.get("type") or "etc",
                "content": content,
                "raw_text": item.get("raw_text") or content,
            })

        return {"items": items_out}

    @audit_log(task_type="company_analyzer")
    async def company_analyzer(self, company_context: dict, notice_schema: dict, *, request_id: str = "", session_id: str = "") -> dict:
        """기업 정보 → CompanySchema + FitAnalysis (PRD §13.x).

        NOAPI-P3 (v2.0): real OpenAI 호출. MockProvider fallback 제거.

        입력 (NOAPI-P3 §3 resolver 결과):
          company_context = {
            "structured_company_profile": dict | None,
            "company_files": [{"file_id", "filename", "document_type",
                                "parsed_text", "text_preview", "metadata",
                                "parse_success", "truncated",
                                "original_chars", "returned_chars"}],
            "selected_company_file_ids": [...],
            "warnings": [{"warning_code": ..., ...}],
          }
          notice_schema: NoticeSchema dict

        출력 (D1 (b) — frontend 호환성):
          {"company": <CompanySchema dump>, "fit_analysis": <FitAnalysis dump>, "warnings": [...]}

        호환성 fallback:
          - 발신자가 list/dict 단순 형식(`company_files=[{file_id}]`)로 호출하면
            mock fallback 위임 (변경 전 endpoint /analyze-company 보존, D5).
        """
        from prompts import load_prompt
        from ontology.schemas import CompanySchema, FitAnalysis

        # ── D5 호환: 단순 list 입력(레거시 endpoint)은 mock fallback 유지 ──
        if not isinstance(company_context, dict) or (
            "structured_company_profile" not in company_context
            and "company_files" not in company_context
        ):
            # 발신자가 새 resolver 구조를 안 전달했으면 mock 위임 (분석 endpoint 보존)
            return await self._mock_fallback().company_analyzer(
                company_context, notice_schema,
                request_id=request_id, session_id=session_id,
            )

        system, _version = load_prompt("company_analyzer")
        user = _build_company_analyzer_user_prompt(company_context, notice_schema, session_id)

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=4096,
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"company_analyzer context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_ANALYSIS,
            temperature=0.0,
            max_tokens=4096,
        )

        try:
            parsed = parse_llm_json(raw, schema=None)
            if not isinstance(parsed, dict):
                raise LLMResponseError(f"company_analyzer 응답이 dict 아님: {type(parsed).__name__}")
            # D1 (b): key는 `company` / `fit_analysis` / `warnings`
            company_dict = parsed.get("company")
            fit_dict = parsed.get("fit_analysis")
            if not isinstance(company_dict, dict) or not isinstance(fit_dict, dict):
                raise LLMResponseError(
                    f"company_analyzer 응답에 company / fit_analysis 누락. keys={list(parsed.keys())}"
                )
            # Pydantic validation
            company = CompanySchema(**company_dict)
            fit = FitAnalysis(**fit_dict)
        except LLMResponseError as e:
            raise NonRetryableError(f"company_analyzer LLM 응답 처리 실패: {e}") from e
        except Exception as e:  # Pydantic ValidationError 등
            raise NonRetryableError(f"company_analyzer schema 검증 실패: {e}") from e

        # warnings: resolver warnings + LLM warnings 병합
        resolver_warnings = list(company_context.get("warnings") or [])
        llm_warnings = parsed.get("warnings") or []
        if not isinstance(llm_warnings, list):
            llm_warnings = []

        return {
            "company": company.model_dump(),
            "fit_analysis": fit.model_dump(),
            "warnings": resolver_warnings + llm_warnings,
        }

    @audit_log(task_type="evidence_mapper")
    async def evidence_mapper(
        self, form_schema: dict, evidence_list: list, notice_schema: dict,
        matching_threshold: float = 0.70,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        """form × evidence 매칭 (E-2-mini, 2026-05-18).

        mock fallback 제거 + 실제 OpenAI 호출.
        prompts/evidence_mapper.md 사용.

        반환 형식 (mock과 호환):
          {
            "session_id": ...,
            "question_mappings": [
              {question_id, matched_evidence_ids, used_evidence_ids,
               confidence_score, missing_evidence_types, match_status}
            ],
            "overall_missing_count", "coverage_rate"
          }
        """
        from prompts import load_prompt
        import json

        sections = (form_schema or {}).get("sections") or []
        # form questions 요약 — id + title + 핵심 필드만 (token 절약)
        form_questions = []
        for sec in sections:
            for q in (sec.get("questions") or []):
                qid = q.get("question_id")
                if not qid:
                    continue
                form_questions.append({
                    "question_id": qid,
                    "section_id": sec.get("section_id"),
                    "title": q.get("title", ""),
                    "fill_mode": q.get("fill_mode"),
                    "required_evidence_types": q.get("required_evidence_types") or [],
                })

        if not form_questions:
            return {
                "session_id": session_id,
                "question_mappings": [],
                "overall_missing_count": 0,
                "coverage_rate": 0.0,
            }

        # evidence 요약 — id + content (head 200자) + type
        evidence_summary = []
        for ev in (evidence_list or []):
            if not isinstance(ev, dict):
                continue
            eid = ev.get("evidence_id")
            if not eid:
                continue
            content = (ev.get("content") or "")[:1000]  # 2026-05-18: 200→1000 (매칭 정확도 ↑)
            evidence_summary.append({
                "evidence_id": eid,
                "type": ev.get("type"),
                "source_file": ev.get("source_file"),
                "section": ev.get("section"),
                "content": content,
            })

        system, _version = load_prompt("evidence_mapper")
        user_parts = [
            f"## form_questions ({len(form_questions)}개)",
            json.dumps(form_questions, ensure_ascii=False, indent=2),
            "",
            f"## evidence_items ({len(evidence_summary)}개)",
            json.dumps(evidence_summary, ensure_ascii=False, indent=2),
            "",
            f"## matching_threshold: {matching_threshold}",
            "",
            "각 form_question에 매칭 가능한 evidence_id 배열을 결정하세요.",
            "응답 형식:",
            '{"question_mappings": [{"question_id": "...", "matched_evidence_ids": ["...", ...], "confidence_score": 0.0~1.0, "mapping_reason": "..."}]}',
            "matched 안 되는 question은 matched_evidence_ids: [] + confidence_score: 0.0",
        ]
        user = "\n".join(user_parts)

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=8192,
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"evidence_mapper context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_ANALYSIS,
            temperature=0.0,
            max_tokens=8192,
        )

        try:
            parsed = parse_llm_json(raw, schema=None)
        except LLMResponseError as e:
            raise NonRetryableError(f"evidence_mapper LLM 응답 처리 실패: {e}") from e

        # 정규화 — mock 형식과 호환
        mappings_raw = []
        if isinstance(parsed, dict):
            mappings_raw = parsed.get("question_mappings") or parsed.get("mappings") or []
        if not isinstance(mappings_raw, list):
            mappings_raw = []

        valid_evidence_ids = {ev["evidence_id"] for ev in evidence_summary}
        valid_qids = {q["question_id"] for q in form_questions}

        question_mappings: list[dict] = []
        covered_qids = set()
        for m in mappings_raw:
            if not isinstance(m, dict):
                continue
            qid = m.get("question_id")
            if not qid or qid not in valid_qids:
                continue
            raw_eids = m.get("matched_evidence_ids") or m.get("evidence_ids") or []
            if not isinstance(raw_eids, list):
                raw_eids = []
            # 환각 evidence_id 필터
            matched = [str(e) for e in raw_eids if str(e) in valid_evidence_ids]
            confidence = m.get("confidence_score")
            if not isinstance(confidence, (int, float)):
                confidence = 1.0 if matched else 0.0
            match_status = "auto_confirmed" if confidence >= matching_threshold and matched else (
                "awaiting_user_confirm" if matched else "no_match"
            )
            question_mappings.append({
                "question_id": qid,
                "matched_evidence_ids": matched,
                "used_evidence_ids": matched,
                "confidence_score": float(confidence),
                "missing_evidence_types": [],
                "match_status": match_status,
            })
            covered_qids.add(qid)

        # 빠진 question은 빈 매핑으로 추가 (frontend가 status 결정 가능하도록)
        for qid in valid_qids:
            if qid not in covered_qids:
                question_mappings.append({
                    "question_id": qid,
                    "matched_evidence_ids": [],
                    "used_evidence_ids": [],
                    "confidence_score": 0.0,
                    "missing_evidence_types": [],
                    "match_status": "no_match",
                })

        matched_count = sum(1 for m in question_mappings if m["matched_evidence_ids"])
        coverage = matched_count / max(1, len(question_mappings))

        return {
            "session_id": session_id,
            "question_mappings": question_mappings,
            "overall_missing_count": len(question_mappings) - matched_count,
            "coverage_rate": round(coverage, 4),
        }

    @audit_log(task_type="missing_material")
    async def missing_material(
        self, mapping_result: dict,
        *, request_id: str = "", session_id: str = "",
    ) -> list:
        """매핑 결과 → 부족자료 진단 (E-2-mini, 2026-05-18).

        mock fallback 제거 + 실제 OpenAI 호출.
        prompts/missing_material.md 사용.

        반환: list of MissingMaterial dicts (mock과 호환).
        """
        from prompts import load_prompt
        import json

        question_mappings = (mapping_result or {}).get("question_mappings") or []
        if not question_mappings:
            return []

        # matched_evidence가 빈 question만 LLM에게 전달 (token 절약)
        unmatched = [
            qm for qm in question_mappings
            if isinstance(qm, dict) and not (qm.get("matched_evidence_ids") or qm.get("used_evidence_ids"))
        ]
        if not unmatched:
            return []

        system, _version = load_prompt("missing_material")
        user_parts = [
            f"## unmatched questions ({len(unmatched)}개) — evidence 0개",
            json.dumps(
                [{"question_id": qm.get("question_id"), "missing_evidence_types": qm.get("missing_evidence_types") or []}
                 for qm in unmatched],
                ensure_ascii=False, indent=2,
            ),
            "",
            f"## session_id: {session_id}",
            "",
            "각 question별로 어떤 자료가 부족한지 진단해서 missing_materials 배열로 반환하세요.",
            "응답 형식:",
            '{"missing_materials": [{"missing_id": "miss_xxx", "session_id": "...", "question_id": "...", "missing_type": "...", "name": "...", "description": "...", "input_type": "text|file|both", "status": "open"}]}',
        ]
        user = "\n".join(user_parts)

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=8192,  # 2026-05-18: 4096→8192 (60+ missing items 응답 길이 대응)
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"missing_material context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_ANALYSIS,
            temperature=0.0,
            max_tokens=8192,
        )

        try:
            parsed = parse_llm_json(raw, schema=None)
        except LLMResponseError as e:
            raise NonRetryableError(f"missing_material LLM 응답 처리 실패: {e}") from e

        items_raw = []
        if isinstance(parsed, dict):
            items_raw = parsed.get("missing_materials") or parsed.get("items") or []
        elif isinstance(parsed, list):
            items_raw = parsed
        if not isinstance(items_raw, list):
            items_raw = []

        # 정규화 — missing_id 강제, session_id 강제, status='open'
        valid_qids = {qm.get("question_id") for qm in unmatched}
        out: list[dict] = []
        for i, item in enumerate(items_raw):
            if not isinstance(item, dict):
                continue
            qid = item.get("question_id")
            if not qid or qid not in valid_qids:
                continue
            out.append({
                "missing_id": item.get("missing_id") or f"miss_{uuid.uuid4().hex[:10]}",
                "session_id": session_id,
                "question_id": qid,
                "missing_type": item.get("missing_type") or "기타",
                "name": item.get("name") or "필요 자료",
                "description": item.get("description") or "",
                "input_type": item.get("input_type") if item.get("input_type") in ("text", "file", "both") else "both",
                "status": "open",
            })

        return out

    @audit_log(task_type="draft_writer")
    async def draft_writer(
        self,
        question: dict,
        matched_evidence: list,
        company_schema: dict,
        notice_schema: dict,
        writing_guidelines: list = None,
        constraints: dict = None,
        evaluation_rubric: dict = None,
        announcement_signals: dict = None,
        *,
        request_id: str = "",
        session_id: str = "",
    ) -> dict:
        """문항별 초안 작성 — 실제 OpenAI 호출 (E-3 sub-step 1).

        2026-05-18: mock fallback 제거 + 실제 LLM 호출 본체 작성.
        sub-step 2에서 E-3 정책 4개 (used_evidence_ids 강제 검증,
        evidence 없는 수치 차단, table_draft 정규화, missing_material 생성) 추가 예정.

        반환 shape는 DraftItem 호환 (mock_provider.draft_writer와 동일):
          { draft_id, session_id, question_id, content, table_data,
            used_evidence_ids, char_count, status, warnings, ai_metadata }
        """
        from prompts import load_prompt

        system, prompt_version = load_prompt("draft_writer")
        user = _build_draft_writer_user_prompt(
            question, matched_evidence, company_schema, notice_schema,
            writing_guidelines, constraints,
            evaluation_rubric=evaluation_rubric,
            announcement_signals=announcement_signals,
        )

        try:
            assert_budget(
                system, user,
                context_limit=OPENAI_CONTEXT_LIMIT,
                max_response_tokens=2048,
            )
        except TokenBudgetExceeded as e:
            raise NonRetryableError(f"draft_writer context overflow: {e}") from e

        raw = await self._chat(
            system, user,
            model=OPENAI_MODEL_DRAFT,
            temperature=0.3,  # notice/form (0.0)보다 약간 창의 허용
            max_tokens=2048,
        )

        try:
            parsed = parse_llm_json(raw, schema=None)
        except LLMResponseError as e:
            raise NonRetryableError(f"draft_writer LLM 응답 처리 실패: {e}") from e

        # prompts/draft_writer.md 출력 형식: {items: [...]}.
        # single-question API이므로 items[0] 추출. 일부 LLM이 단일 dict로 반환하는 경우도 허용.
        if isinstance(parsed, dict) and isinstance(parsed.get("items"), list) and parsed["items"]:
            item = parsed["items"][0] if isinstance(parsed["items"][0], dict) else {}
        elif isinstance(parsed, dict):
            item = parsed
        else:
            item = {}

        qid = (question or {}).get("question_id", "") or item.get("question_id", "")
        content = (item.get("content") or "") if isinstance(item.get("content"), str) else ""
        # prompts/draft_writer.md는 "evidence_used"로 명시 — used_evidence_ids 우선
        raw_evidence_ids = item.get("used_evidence_ids") or item.get("evidence_used") or []
        used_evidence_ids: list[str] = [
            str(eid) for eid in raw_evidence_ids if eid is not None
        ]

        # ── E-3 정책 1: used_evidence_ids 환각 검증 + 필터링 ──────────
        # 다른 analyzer는 raise하지만 draft_writer는 사용자 클릭 트리거라 raise 대신 filter + warning
        warnings_out: list[dict] = []
        input_evidence_ids = [
            str(e.get("evidence_id", ""))
            for e in (matched_evidence or [])
            if isinstance(e, dict) and e.get("evidence_id")
        ]
        input_set = set(input_evidence_ids)
        hallucinated_ids = [eid for eid in used_evidence_ids if eid not in input_set]
        if hallucinated_ids:
            # input에 없는 evidence_id 사용 — 환각 발생. 제거 + warning.
            used_evidence_ids = [eid for eid in used_evidence_ids if eid in input_set]
            warnings_out.append({
                "code": "hallucinated_evidence_ids_filtered",
                "removed": hallucinated_ids,
                "message": f"LLM이 입력에 없는 evidence_id {len(hallucinated_ids)}개 사용 — 자동 제거됨",
            })

        # ── E-3 정책 4: evidence 부족 시 status=needs_evidence + warning ─
        is_table = bool((question or {}).get("is_table_item") or (question or {}).get("fill_mode") == "table_input")
        evidence_count = len(matched_evidence or [])
        if evidence_count == 0:
            warnings_out.append({
                "code": "evidence_insufficient",
                "message": "evidence 0개 — 추가 자료 업로드 권장. 본 초안은 일반 원칙만 서술됨.",
            })
            status_out = "needs_evidence"
        elif not used_evidence_ids and not is_table:
            # evidence 있는데 LLM이 하나도 사용 안 함
            warnings_out.append({
                "code": "evidence_unused",
                "message": f"evidence {evidence_count}개 제공됐으나 LLM이 인용 안 함",
            })
            status_out = "generated"
        else:
            status_out = "generated"

        # ── E-3 정책 3: table_data 정규화 ──────────────────────────────
        table_data_raw = item.get("table_data") or []
        if not isinstance(table_data_raw, list):
            table_data_raw = []
        # table 문항인데 table_data 빈 경우 warning
        if is_table:
            if not table_data_raw:
                warnings_out.append({
                    "code": "table_data_missing",
                    "message": "table_input 문항인데 LLM이 table_data 비움",
                })
            else:
                # 각 row가 list여야 함 + 컬럼 길이와 일치 검증 (length mismatch는 warning만)
                # 2026-05-18: 신/구 스키마 모두 지원
                from services.item_query_builder import get_table_columns
                expected_cols = len(get_table_columns(question or {}))
                bad_rows = []
                for i, row in enumerate(table_data_raw):
                    if not isinstance(row, list):
                        bad_rows.append(i)
                    elif expected_cols > 0 and len(row) != expected_cols:
                        bad_rows.append(i)
                if bad_rows:
                    warnings_out.append({
                        "code": "table_row_shape_mismatch",
                        "bad_row_indices": bad_rows,
                        "expected_cols": expected_cols,
                        "message": f"table_data {len(bad_rows)}개 row가 column 수와 불일치 — frontend 검증 필요",
                    })

        # constraints.max_length 잘라내기
        max_length = (constraints or {}).get("max_length") if isinstance(constraints, dict) else None
        if isinstance(max_length, int) and max_length > 0 and len(content) > max_length:
            content = content[:max_length]
            warnings_out.append({
                "code": "content_truncated_by_max_length",
                "max_length": max_length,
                "message": f"content가 max_length({max_length}) 초과 — 잘라냄",
            })

        return {
            "draft_id": f"draft_{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "question_id": qid,
            "content": content,
            "table_data": table_data_raw,
            "used_evidence_ids": used_evidence_ids,
            "char_count": len(content),
            "status": status_out,
            "warnings": warnings_out,
            "ai_metadata": {
                "model": OPENAI_MODEL_DRAFT,
                "prompt_version": prompt_version,
                "generated_at": datetime.utcnow().isoformat(),
            },
        }

    async def draft_rewriter(self, question_id: str, current_draft: str, user_message: str, evidence_list: list, *, request_id: str = "", session_id: str = "") -> dict:
        return await self._mock_fallback().draft_rewriter(question_id, current_draft, user_message, evidence_list, request_id=request_id, session_id=session_id)

    # ──────────────────────────────────────────────
    # V1 호환 5 메서드 (실제 OpenAI API 호출)
    # ──────────────────────────────────────────────

    @audit_log(task_type="generate_draft")
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        system = "당신은 정부 지원사업 사업계획서 작성 전문가입니다."
        user = f"공고문:\n{notice_text[:3000]}\n\n기업 프로필:\n{profile}\n\n{section} 섹션을 작성해 주세요."
        return await self._chat(system, user)

    @audit_log(task_type="evaluate_draft")
    async def evaluate_draft(self, draft_text: str, notice_text: str) -> dict:
        # TODO: function calling으로 구조화된 응답 받도록 개선
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
        system = "당신은 정부지원사업 사업계획서 전문 컨설턴트입니다. 작성된 초안을 검토하고 사용자의 수정 요청에 답변하세요."
        user = f"[공고명] {notice_title}\n\n[현재 초안]\n{draft_content[:1500]}\n\n[이전 대화]\n{history_text}\n\n[사용자 메시지]\n{message}"
        return await self._chat(system, user)
