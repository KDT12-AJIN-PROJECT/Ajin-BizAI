# AI-1 — Provider 연결 계획 (3 module 우선)

> NOAPI-P1 산출물. **계획 문서만, 코드 X**. API key 발급 후 AI-1 작업으로 구현.
> 본 문서의 패턴이 검증되면 나머지 5 module (evidence_extractor / company_analyzer /
> evidence_mapper / missing_material / draft_rewriter)에 동일 패턴 적용 (AI-1.x 후속).

작성일: 2026-05-11 (NOAPI-P1)
대상 module: `notice_analyst` / `form_parser` / `draft_writer`
대상 provider: `AnthropicProvider` (Sonnet 4.6 default)

---

## 공통 패턴

### 코드 골격 (3 module 공통)

```python
from prompts import load_prompt
from services.llm_response_parser import parse_llm_json, LLMResponseError
from ontology.schemas import NoticeSchema  # 또는 해당 schema
from services.ai_provider import call_with_retry, NonRetryableError

@audit_log(task_type="notice_analyst")
async def notice_analyst(self, notice_text: str, *, request_id="", session_id="") -> dict:
    # 1. prompt 로드
    system, version = load_prompt("notice_analyst")

    # 2. user prompt 외부 concat (placeholder 사용 X)
    user = f"공고문 텍스트:\n{notice_text}"

    # 3. _chat 호출 (이미 call_with_retry 래핑됨, 5회 backoff + jitter)
    raw = await self._chat(system, user)

    # 4. JSON 파싱 + Pydantic validation
    try:
        parsed = parse_llm_json(raw, schema=NoticeSchema)
    except LLMResponseError as e:
        # mock fallback 금지 — explicit raise
        raise NonRetryableError(f"notice_analyst LLM 응답 처리 실패: {e}") from e

    # 5. dict 반환 (router의 응답 shape)
    return parsed.model_dump()
```

### 핵심 정책

| 정책 | 내용 |
|------|------|
| **mock fallback 금지** | 실패 시 NonRetryableError raise. router에서 적절히 502/422 처리 |
| **silent pass 금지** | parse error / schema error 모두 명시적 raise |
| **prompt 본문 운영 문구 X** | prompts/*.md는 system prompt로 그대로 사용 |
| **user concat 방식** | placeholder `{notice_text}` X, 외부에서 f-string concat |
| **retry는 `_chat()` 안에서 자동** | call_with_retry로 5회 backoff. 8 module에서 추가 retry X |
| **token usage 캐싱** | `self._last_token_usage` (audit_log 데코레이터가 추출) |
| **schema validation** | Pydantic v2 `BaseModel(**parsed)`. extra field는 ignore (default) |

---

## 1. `notice_analyst` 연결 계획

### 입력 payload
| 필드 | 출처 | 비고 |
|------|------|------|
| `notice_text` | `ParseNoticeRequest.notice_text` (analysis.py:43) | 사용자 입력 또는 A1 upload parsed_text |
| `session_id` | request body | audit_log 메타 |
| `request_id` | request body | 추적 ID |

### 출력 schema
`NoticeSchema` (ontology/schemas.py:148)
- `target` (str, 지원대상)
- `benefit` (str, 지원내용)
- `deadline` (Optional[str], YYYY-MM-DD)
- `evaluation_criteria` (List[EvalCriterion])
- `required_documents` (List[str])
- `exclusion_conditions` (List[str])

### unit test 방식 (API key 없이)
```python
# tests/test_anthropic_notice_analyst.py
from unittest.mock import AsyncMock

async def test_notice_analyst_with_mocked_chat(monkeypatch):
    provider = AnthropicProvider()
    fake_response = '{"target": "중소기업", "benefit": "...", ...}'
    monkeypatch.setattr(provider, "_chat", AsyncMock(return_value=fake_response))
    result = await provider.notice_analyst("공고문 텍스트")
    assert result["target"] == "중소기업"
    NoticeSchema(**result)   # validation 통과 확인
```

### 실패 시 처리 정책
| 실패 종류 | 처리 |
|----------|------|
| `_chat()` 5회 retry 실패 (429/5xx) | `RetryableError` → router 502 |
| `_chat()` 401/403 | `NonRetryableError` → router 401/403 |
| JSON 파싱 실패 | `LLMResponseParseError` → router 502 + 원본 일부 로깅 |
| Pydantic schema 실패 | `LLMResponseSchemaError` → router 502 + Pydantic 에러 로깅 |
| **mock fallback** | **금지** |

---

## 2. `form_parser` 연결 계획

### 입력 payload
| 필드 | 출처 |
|------|------|
| `form_text` | `ParseFormRequest.form_text` (analysis.py:48) |
| `form_name` | request body |
| `session_id` / `request_id` | 동일 |

### 출력 schema
`FormSchema` (ontology/schemas.py:198)
- `form_id` (str)
- `form_name` (str)
- `sections` (List[FormSection])
  - 각 section: `id`, `title`, `questions: List[FormQuestion]`
  - 각 question: `id`, `title`, `max_length`, `min_length`, `table_structure`, ...

### unit test
notice_analyst와 동일 패턴, mock 응답을 form schema shape으로.

### 특이사항
- FormSchema는 nested (sections > questions). validation 시 nested validation 자동 동작.
- mock_provider의 form_parser는 sections 1개 + question 1개만 반환 → e2e 데이터 한계 (Phase 5에서 실제 응답 시 풍부)

---

## 3. `draft_writer` 연결 계획

### 입력 payload
| 필드 | 출처 |
|------|------|
| `question` | FormQuestion dict |
| `matched_evidence` | EvidenceItem 배열 (evidence_mapper 결과 활용) |
| `company_schema` | CompanySchema (company_analyzer 결과) |
| `notice_schema` | NoticeSchema (notice_analyst 결과) |
| `writing_guidelines` | Optional[List[str]] |
| `constraints` | Optional[Dict[str, int]] (max_length, min_length) |

### 출력 schema
`DraftItem` (위치 확인 필요 — ontology/schemas.py 또는 별도)
- `draft_item_id`
- `question_id`
- `content` (작성된 초안 본문)
- `used_evidence_ids` (List[str]) — **환각 방지 핵심**
- `criteria_addressed` (List[str])
- `char_count`, `status`

### unit test
- mock 응답에 `used_evidence_ids` 포함되는지 검증
- `matched_evidence` 외부 정량 수치 생성 안 됨 검증 (PRD §14.3 환각 방지)
- `char_count <= constraints.max_length` 검증

### 특이사항
- `draft_writer`는 **장문 응답** (보통 800~2000자) → max_tokens 4096 충분
- premium_final_writer 분기: AI_COST_MODE=quality_first 시 Opus 사용 — **AI-1.x에서 처리** (이번 AI-1은 Sonnet 단일)

---

## 작업 순서 (AI-1)

| Phase | 작업 | 시간 |
|:--:|------|:--:|
| AI-1 사전 | C1 pricing report (Anthropic 실제 단가 확인) | 20분 |
| AI-1 사전 | `.env`에 ANTHROPIC_API_KEY + spending limit 설정 (사용자 직접 — B4) | 사용자 |
| AI-1.1 | AnthropicProvider.notice_analyst 본체 (위 패턴) | 45분 |
| AI-1.2 | AnthropicProvider.form_parser 본체 (동일 패턴) | 30분 |
| AI-1.3 | AnthropicProvider.draft_writer 본체 (동일 패턴 + matched_evidence 검증) | 45분 |
| AI-1.4 | pytest unit test 3 (각 module monkeypatch + schema validation) | 45분 |
| AI-1.5 | **실제 API smoke test** (각 module 1회 호출, 비용 ~150원) | 30분 |
| AI-1.6 | router에서 `LLMResponseError` 처리 (502 응답) | 30분 |
| AI-1.7 | STATUS / TODO 갱신 + Coverage Matrix `ready` 표시 | 15분 |

**합계**: ~4시간 (B4 + C1 후).

### AI-1 완료 시 도달 상태
- 3 module: `status=ready` (실제 LLM 호출 가능)
- 나머지 5 module: 그대로 (`mock_only + not_implemented`)
- `AI_PROVIDER=anthropic` 설정 + Step 1~2 진입 시 **실제 Sonnet 응답으로 분석 가능**

### AI-1 후 후속 (AI-1.x)
- 나머지 5 module (evidence_extractor / company_analyzer / evidence_mapper / missing_material / draft_rewriter) — 같은 패턴 4시간
- HybridProvider H1~H4 (모듈별 모델 분기 + AI_COST_MODE)
- OpenAIProvider 8 module 본체 (A/B 후보)

---

## 변경 이력

| 일자 | 작업 | 변경 |
|------|------|------|
| 2026-05-11 | NOAPI-P1 | 신규 작성. 3 module 연결 계획 + 공통 패턴 + unit test 방식 + 실패 처리 정책. |
