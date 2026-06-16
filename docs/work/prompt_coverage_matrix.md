# Prompt Coverage Matrix — v0.2 / draft-v2

> NOAPI-P1 산출물. v0.2 8 AI module 별 prompt / output schema / 현재 상태 매트릭스.
> 운영 상태(미사용 / Phase 5 후 활성화 등)는 본 문서에서만 관리한다.
> `backend/prompts/*.md` 본문에는 운영 상태 문구 넣지 않는다 (system prompt 오염 방지).

작성일: 2026-05-11 (NOAPI-P1)
범위: v0.2 / draft-v2 8 AI module + Anthropic / OpenAI / Local / Mock provider
관련 문서: PRD-13 §18~§19, test_02_plan.md

---

## 카테고리 정의

| 카테고리 | 의미 |
|----------|------|
| **v0.2 실제 사용** | `/draft-v2` 화면 + `/api/analysis/*` 흐름에서 실제 호출 |
| **prompt_exists_but_unused** | prompt 파일은 작성됐으나 provider 본체가 미연결 |
| **legacy_only** | `/api/ai/*` (V1 DraftPage) 또는 폐기된 `/lab` 에만 존재 |
| **mock_only** | MockProvider 응답만 동작, 실제 LLM 호출 없음 |
| **not_implemented** | provider 본체가 `NotImplementedError` |
| **missing_prompt** | prompt 파일 자체가 없음 |
| **ready** | prompt + schema + provider 본체 모두 연결 — 실제 LLM 호출 가능 |
| **portable** | legacy 또는 다른 영역에 패턴이 있어 v0.2로 이식 가능 |

---

## 8 module × prompt × schema × status 매트릭스

| module | prompt file | exists | used in v0.2 | output schema | status | note |
|--------|-------------|:--:|:--:|---------------|--------|------|
| `notice_analyst` | `prompts/notice_analyst.md` (v1.0) | ✓ | mock | `NoticeSchema` | `prompt_exists_but_unused` + `mock_only` + `not_implemented`(anthropic) | analysis.py:248. Anthropic 본체 line 130 `NotImplementedError` |
| `form_parser` | `prompts/form_parser.md` (v1.0) | ✓ | mock | `FormSchema` | 동일 | analysis.py:259. Anthropic 본체 line 134 |
| `evidence_extractor` | `prompts/evidence_extractor.md` (v1.0) | ✓ | mock | `EvidenceSchema` | 동일 | analysis.py:273. Anthropic 본체 line 138. **embedding은 placeholder 0.0×1024** |
| `company_analyzer` | `prompts/company_analyzer.md` (v1.0) | ✓ **NEW** | mock | `CompanySchema` + `FitAnalysis` | `mock_only` + `not_implemented` | analysis.py:288. Anthropic 본체 line 142. **prompt 신규 작성 (NOAPI-P1)** |
| `evidence_mapper` | `prompts/evidence_mapper.md` (v1.0) | ✓ | mock | `MappingResult` (QuestionMapping list 포함) | 동일 | analysis.py:303. Anthropic 본체 line 146. **RAG 없음 — LLM-only 매핑** |
| `missing_material` | `prompts/missing_material.md` (v1.0) | ✓ **NEW** | mock | `MissingMaterial[]` | `mock_only` + `not_implemented` | analysis.py:319. Anthropic 본체 line 150. **prompt 신규 작성 (NOAPI-P1)** |
| `draft_writer` | `prompts/draft_writer.md` (v1.0) | ✓ | mock | `DraftItem` | 동일 | analysis.py:906. Anthropic 본체 line 154 |
| `draft_rewriter` | `prompts/draft_rewriter.md` (v1.0) | ✓ **NEW** | mock | `DraftItem` (rewrite suggestion) | `mock_only` + `not_implemented` | analysis.py:938. Anthropic 본체 line 158. **prompt 신규 작성 (NOAPI-P1)** |

**요약**:
- 8 module 모두 status = **`mock_only` + `not_implemented`(Anthropic) + `_mock_fallback`(OpenAI/Local)**
- 8 prompt 모두 작성 완료 (5 기존 + 3 신규 — NOAPI-P1)
- `ready` 상태 module: **0건**

---

## Provider 매트릭스 (각 module × 각 provider)

| module | MockProvider | AnthropicProvider | OpenAIProvider | LocalProvider |
|--------|:--:|:--:|:--:|:--:|
| notice_analyst | ✅ mock 응답 | ❌ NotImplementedError | ❌ `_mock_fallback` 위임 | ❌ `_mock_fallback` 위임 |
| form_parser | ✅ | ❌ | ❌ | ❌ |
| evidence_extractor | ✅ | ❌ | ❌ | ❌ |
| company_analyzer | ✅ | ❌ | ❌ | ❌ |
| evidence_mapper | ✅ | ❌ | ❌ | ❌ |
| missing_material | ✅ | ❌ | ❌ | ❌ |
| draft_writer | ✅ | ❌ | ❌ | ❌ |
| draft_rewriter | ✅ | ❌ | ❌ | ❌ |

→ 현재 `AI_PROVIDER=anthropic` 설정 시 8 module 모두 500 (NotImplementedError raise).
→ `AI_PROVIDER=openai/local` 설정 시 표면상 다르지만 내부적으로 MockProvider 응답 (위장).
→ 실제 v0.2 분석 흐름은 default `mock` provider로만 동작.

---

## V1 / legacy 영역 (참고용)

| 항목 | 위치 | 동작 | v0.2 이식 가치 |
|------|------|------|----------------|
| `AnthropicProvider.generate_draft` | anthropic_provider.py:165 | **실제 Anthropic API 호출** + hardcoded inline system prompt | ⭐ `_chat()` 패턴 v0.2 8 모듈에 그대로 활용 |
| `AnthropicProvider.evaluate_draft / improve_draft / chat_review` | line 171~196 | 동일 (inline prompt + `_chat()`) | 동일 |
| `services/diagnosis.py.calculate_completeness` | V1 키워드 기반 작성 가능률 | 26 필드 `REQUIRED_FIELDS_MAP` + `FIELD_KEYWORDS` | △ `missing_material` LLM 미사용 fallback rule로 활용 가능 |
| 폐기된 `/lab` v0.1 | `local/prompt/v0.2/LAB_v0.1_snapshot.md` | snapshot 문서만 | `_chat() + JSON parsing fallback` 패턴 참고 |

---

## load_prompt() / TASK_TYPE_TO_PROMPT (NOAPI-P1 확장)

| 항목 | 위치 | 상태 |
|------|------|:--:|
| `load_prompt(name)` | `backend/prompts/__init__.py:11` | ✅ 동작 (파일 없으면 `FileNotFoundError` raise) |
| `PROMPT_NAMES` 리스트 | `prompts/__init__.py:33` | ✅ **5 → 8개 확장 (NOAPI-P1)** |
| `TASK_TYPE_TO_PROMPT` dict | `prompts/__init__.py` 신규 | ✅ **8 module 1:1 매핑 (NOAPI-P1)** |
| `get_prompt_version(task_type)` | 신규 | ✅ missing_prompt 시 명시 반환 (silent None X) |
| audit_logger 연결 | `services/audit_logger.py:70` | △ version만 추출, prompt 본문 미사용 |

---

## LLM JSON parser (NOAPI-P1 신규)

| 항목 | 위치 | 상태 |
|------|------|:--:|
| `parse_llm_json(raw, schema=None)` | `services/llm_response_parser.py` (신규) | ✅ |
| `LLMResponseParseError` ↔ `LLMResponseSchemaError` 구분 | 신규 | ✅ |
| 코드 펜스 strip (```json``` / ``` ```) | 신규 | ✅ |
| 첫 JSON object/array 추출 (앞뒤 설명문 허용) | 신규 | ✅ (string 안 `}` 안전 처리) |
| trailing comma repair (`,}` `,]`) + warning | 신규 | ✅ 제한적 |
| Pydantic v2 schema validation | 신규 | ✅ `BaseModel(**parsed)` |
| 빈 응답 / "null" 감지 | 신규 | ✅ raise |
| mojibake 자동 수정 | — | ❌ **의도적 미구현** (silent 보정 금지) |
| 필드 임의 생성 | — | ❌ |
| pytest case | `tests/test_llm_response_parser.py` | ✅ **26/26 PASS** |

---

## Pydantic schema 정합 (v2 + extra='ignore' default)

| module | schema 파일 | 클래스 | 확정 |
|--------|------|------|:--:|
| notice_analyst | ontology/schemas.py:148 | `NoticeSchema` | ✓ |
| form_parser | ontology/schemas.py:198 | `FormSchema` (FormSection + FormQuestion 포함) | ✓ |
| evidence_extractor | ontology/schemas.py:225 | `EvidenceSchema` (EvidenceItem list 포함) | ✓ |
| company_analyzer | ontology/schemas.py:127 + 330 | `CompanySchema` + `FitAnalysis` | ✓ (2 schema 결합) |
| evidence_mapper | ontology/schemas.py:242 | `MappingResult` (QuestionMapping list 포함) | ✓ |
| missing_material | ontology/schemas.py:252 | `MissingMaterial[]` | ✓ |
| draft_writer | (DraftItem schema 위치 확인 필요) | `DraftItem` | △ |
| draft_rewriter | 동일 | `DraftItem` rewrite | △ |

**Pydantic 버전**: v2 (pydantic-settings 2.x 의존). `ConfigDict` 미사용 → `extra='ignore'` default.

---

## 미커버 영역 (NOAPI-P1 범위 외)

| 항목 | 사유 | 다음 작업 |
|------|------|------|
| 실제 Anthropic API 호출 smoke | API key 필요 | AI-1 |
| AnthropicProvider 8 module 본체 구현 | API key 필요 | AI-1 |
| OpenAIProvider 8 module 본체 | A/B 후보 | AI-1 후 |
| HybridProvider (H1~H4) | API key 후 | Phase 5 |
| pricing.json 실제 값 | API key 후 | C1/C2 |
| RAG (chunking + embedding + retrieval) | v0.3 영역 | v0.3 |
| 온톨로지 추론 엔진 | v2.0 영구 동결 | — |

---

## 변경 이력

| 일자 | 작업 | 변경 |
|------|------|------|
| 2026-05-11 | NOAPI-P1 | 신규 작성. 8 module × prompt 매트릭스. company_analyzer / missing_material / draft_rewriter prompt 신규 작성. `llm_response_parser.py` + `TASK_TYPE_TO_PROMPT` dict 신규. |
