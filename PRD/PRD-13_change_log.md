# PRD-13 구현 변경 이력 (Change Log)

**문서 성격:** PRD-01~12 원본 사양 vs 현재 구현 차이 추적
**문서 버전:** v1.0
**작성일:** 2026-05-09
**갱신 주기:** 새 변경 발생 시 본 문서에 추가 (PRD-01~12 본문은 직접 수정하지 않고 이 문서에 누적)

---

## 0. 이 문서를 처음 보는 사람을 위한 안내

### 0.1 무엇을 읽고 있는가

이 프로젝트의 **공식 사양**은 `PRD/PRD-01_*.md` ~ `PRD-12_*.md` 12개다.
구현이 진행되면서 그중 일부 사양이 **사용자 요구·기술 제약·UX 검증**을 거쳐 변경되었다.
본 문서(PRD-13)는 그 변경을 **변경 전 / 변경 후 / 사유** 형식으로 누적한다.

```
현재 구현 = PRD-01 ~ PRD-12 (원본 사양) + PRD-13 (본 문서, 변경 이력)
```

### 0.2 왜 PRD-01~12를 직접 수정하지 않는가

원본 사양을 보존해야 다음을 알 수 있다:
- "왜 이렇게 만들었지?" — 1년 후 회고 시 사고 흐름 추적
- "이 결정은 언제, 누가, 왜?" — 변경 시점과 이유 분리 보존
- "PRD-04와 다르게 구현됐는데 의도인가?" — 변경 이력으로 즉시 확인

### 0.3 어떻게 읽으면 되는가

1. **§1 (v1→v2 큰 전환)** 부터 읽기 — 2026-05-06에 한 큰 결정. 이후 모든 변경의 배경.
2. **§15 변경 이력 표** — 시간순 한눈에 보기.
3. **§14 미해결 사항** — 결정 안 된 부채 7개.
4. 관심 있는 변경(§2~§12)은 개별로 펼쳐 읽기.

### 0.4 자주 등장하는 내부 용어

| 용어 | 의미 |
|------|------|
| **DraftPage** | "신청 준비" 화면. 사용자가 제출 서류 초안을 작성하는 메인 5단계 워크플로우 페이지 |
| **/lab** | AI 품질 검증 페이지. 사용자용이 아닌 **개발자/검증자 전용** 내부 화면. URL 직접 입력으로만 접근 |
| **공고** | 정부지원사업/공모/R&D 과제 등의 공고문 (= notice) |
| **양식** | 제출양식 (사업계획서 등). 공고마다 다른 구조 (= form) |
| **참고자료** | 회사소개서/실적/특허 등 작성 근거 자료 (= reference) |
| **AIProvider** | mock/local/openai 추상화 인터페이스. 환경변수 `AI_PROVIDER`로 선택 |
| **audit_log** | AI 호출마다 `ai_call_logs` 테이블에 기록하는 데코레이터 |
| **request_id** | 한 사용자 요청에 묶이는 여러 LLM 호출을 그룹화하는 UUID |

---

## 1. v1 → v2 큰 전환 (2026-05-06)

PRD-01~12는 v1 사양이다. v2로 전환하면서 다음 큰 결정이 있었다.

### 1.1 폐기된 항목

| 폐기 대상 | 관련 PRD | 사유 |
|---------|---------|------|
| ApplyPrepPage 5단계 (공고분석→프로필매칭→부족정보파악→AI인터뷰→준비완료) | PRD-04 §F-05 | DraftPage 5단계로 통합. 별도 페이지 불필요 |
| DRAFT_SECTIONS 5개 고정 (신청기업개요/사업참여목적/세부추진계획/기대효과/예산계획) | PRD-04, PRD-06 | 실제 제출양식이 공고마다 다름. 고정 항목은 양식 무시 결과 초래 |
| INTERVIEW_QUESTIONS 카테고리 enum (company_basic/financial/business_content/project_plan) | PRD-04 | 사전 정의된 카테고리는 양식별 차이 반영 못 함 |
| CRITERIA_EXTRACTION 카테고리 enum (industry/age/revenue/certification/region) | PRD-04 | LLM 자유 추출이 더 정확 |
| 참고자료 6개 분류 enum | PRD-04 | 자료 종류는 사용자/공고마다 다름 |
| analyzeNoticeStructure 폴백 5~7개 고정 섹션 | PRD-04, PRD-06 | LLM 실패 시 의미 없는 가짜 섹션 생성 방지 |

### 1.2 유지된 항목

- PRD-06 DraftPage **5단계** (자료업로드 → 자료검사 → 초안작성 → 전략검토 → 완료)
- PRD-06 Step3 **3패널 구조** (좌: 섹션 / 중: 에디터 / 우: 챗봇 인터뷰)
- **PRD-12 절대원칙** (기존 코드/함수명/파일명 유지)
- PRD-08 파일 검증 (확장자/크기)
- 기업 프로필 LLM 호출 시 포함

### 1.3 신규 추가

- **Step2.5 자료 매칭** (양식 필드 ↔ 자료 청크 사전 인덱스)
- **Step4 자동 검증 + 자기 수정 루프** (최대 3회)
- **AI Provider 라우팅** (mock / local / openai / claude)
- **디버그 패널** (정식 앱 안, 토글)
- **/dev 페이지** (개발자 전용 테스트 도구) → 이후 **/lab**으로 진화 (변경 5 참조)
- 골든 케이스 + 매트릭스 테스트
- **출처 인용 강제 + 환각 검증**
- 프롬프트 DB 저장 (코드 하드코딩 X)
- **AI 호출 로그** → 변경 6 참조 (ai_call_logs 테이블)
- 사용자 검수 게이트 (Step2 / Step2.5 / Step4)
- 공고 자료 자동 인계 (DetailPage → DraftPage)
- **다중 파일 업로드** (제출양식·참고자료 모두)

### 1.4 원칙 변화

| 변경 전 | → | 변경 후 |
|--------|---|--------|
| 고정 카테고리 / 사전 정의 스키마 | → | LLM 자유 분석 + 사후 클러스터링 |
| 정규식 + 규칙 기반 1순위 | → | LLM 1순위, 규칙은 보조 |
| 요약으로 정보 압축 | → | RAG + 구조화 추출 (정확한 인용) |
| 매번 검색 | → | 사전 매칭 인덱스 1회 |

### 1.5 정정 (인터뷰는 사라지지 않음)

이전 대화 중 혼동:
- ~~"v2에서 인터뷰 단계가 사라진다"~~ ← 잘못된 이해
- **정확:** PRD-04의 **별도 STEP4 인터뷰 단계는 폐기**, **챗봇 인터뷰는 PRD-06 Step3 우측 패널에 그대로 살아있음**
- 작성 중 사용자에게 추가 질문 → 답변 → 섹션 재작성 흐름 유지

---

## 2. DB 구조 옵션 A 전환 (2026-05-07, commit cb3e901)

### 변경 전 (PRD 원본)
- PRD-07: `drafts` 테이블 단일 레코드 — `(notice_id)` PK
- 사용자가 한 공고에 대해 1개 초안만 보관

### 변경 후 (현재 구현)
- `drafts` 테이블 버전 관리 — `(notice_id, version)` UNIQUE
- 동일 공고에 v1, v2, v3 ... 다수 버전 보관
- 신규 페이지: **MyDraftsPage** (버전 목록), **ArchivePage** (보관함)
- 신규 API: `/api/drafts/list`, `/api/drafts/{notice_id}/versions`, `/api/drafts/by-id/{draft_id}/{action}`

### 사유
- 사용자가 "이전 버전과 비교하고 싶다", "임시 저장 후 복귀" 같은 요구
- 옵션 A vs B 검토 후 옵션 A (버전관리) 채택

### 부채
- `notice_id`(string) + `draft_id`(int) **이중 식별자** 공존 (변경 4 참조)

---

## 3. AI 호출 감사 인프라 (2026-05-07, commit d1fc6c1, ed5b454)

### 변경 전 (PRD 원본)
- PRD-05/07: AI 호출 로그 추가 (큰 그림만 정의됨)
- 구체적인 스키마/구현 없음

### 변경 후 (현재 구현)

**신규 테이블:** `ai_call_logs`
| 컬럼 | 타입 | 용도 |
|------|------|------|
| run_id | str | 매 호출 고유 ID |
| request_id | str | 사용자 요청 묶음 ID (분석 1회 = 4~N개 호출) |
| task_type | str | notice_analyst / form_parser / generate_draft 등 |
| prompt_version | str | 프롬프트 파일 버전 |
| model_provider | str | mock / local / openai |
| model_name | str | 사용 모델 |
| input_hash | str | 입력 SHA256 (캐싱 활용) |
| input_preview | str | 입력 처음 500자 |
| output_json | str | 구조화 출력 |
| raw_output | str | LLM 원본 응답 |
| status | str | success / timeout / parse_error / api_error |
| duration_ms | int | 실행 시간 |
| token_usage_json | str | 토큰 사용량 (OpenAI 한정) |
| cost_estimate_krw | float | 비용 추정 (미구현) |

**신규 데코레이터:** `@audit_log(task_type="...")`
- `services/audit_logger.py`에 정의
- 모든 AIProvider 메서드에 적용 (Mock/Local/OpenAI 각 5개)
- `request_id`를 kwarg로 받아 DB 기록 시 사용

**Provider 클래스 속성 추가:**
- `provider_name` (mock / local / openai)
- `model_name`
- `_last_token_usage` (OpenAI만 채움)

### 사유
- AI 호출 추적성 확보 (PRD-05 §확장성, PRD-07 §추적성)
- "왜 이렇게 응답했지?" 디버깅
- 비용 추정 + 모델 교체 가능성

---

## 4. 이중 식별자 — 잠재 부채 (2026-05-07)

### 변경 전 (PRD 원본)
- PRD-07: `notice_id` (string, 외부 공고 ID) 단일 식별자

### 변경 후 (현재 구현)
- `notice_id` (string) — 공고 식별
- `draft_id` (int, AUTO_INCREMENT) — drafts 테이블 PK
- API 경로 두 종류 공존:
  - `/api/drafts/{notice_id}` (notice_id 기반, 기존)
  - `/api/drafts/by-id/{draft_id}` (draft_id 기반, 신규)

### 사유
- DB 옵션 A 전환 시 동일 notice_id에 다수 버전 → notice_id로는 단일 draft 지정 불가
- 단기 해결책으로 draft_id 추가
- `/api/drafts/by-id/` 경로로 명시 분리

### 부채 (TODO_polish §3)
- v1.1에서 단일화 검토 — `draft_id` 중심으로 정리
- API 경로 일관성 부재 → 사용처 혼선 가능

---

## 5. /lab v0.1 — AI 품질 검증 페이지 (2026-05-07 신규 → **2026-05-09 폐기**)

### 변경 전 (PRD 원본)
- PRD에 `/lab` 페이지 없음
- v1 단계에서는 `/dev` 페이지 (개발자 전용 테스트 도구)로 정의됨 (변경 1.3)

### 변경 후 (현재 — 폐기됨)
- **/lab v0.1 신규 (2026-05-07)** — `/dev` 개념을 발전시킨 형태
  - 3-panel UI: 파일 업로드 / 양식 선택 + 분석 / 결과 5개 탭
  - 신규 라우트: `/lab` (App.jsx)
  - 5개 endpoint: `/api/lab/{parse,analyze-notice,analyze-form,extract-evidence,map-evidence}`
- **2026-05-09 폐기**:
  - 동작 미검증 (런타임 검증 0/8) → 사용자 결정으로 커밋 보류
  - PRD v0.2 FINAL 정리 시 endpoint/스키마/메서드명 모두 변경됨
  - v0.2의 `/api/analysis/*` (10개+) + 8 모듈로 진화 → /lab은 dev mode prototype 역할 종결
  - 미커밋 상태에서 `git checkout` + `rm`으로 폐기 (비용 0)

### 사유 (당시)
- DraftPage Step2의 분석 흐름이 블랙박스로 보임
- 파일 파싱 → 구조 추출 → 매칭 품질을 가시화 후 DraftPage에 반영하는 순서 필요

### 폐기 사유 (2026-05-09)
1. v0.2 PRD가 새 endpoint(`/api/analysis/*`) + 새 8 모듈 정의 → 어차피 새로 작성
2. 이름/시그니처 불일치: `analyze_notice` (lab) ≠ `notice_analyst_v001` (v0.2)
3. v0.2 Step 2 개발자 모드 Tab 3~7 + Raw JSON이 /lab 가시성 역할 대체
4. 이중 endpoint 운영 부담 회피
5. compatibility wrapper 생성 금지 — 신규는 `/api/analysis/*`로 통일

### 폐기 처리 (2026-05-09)
**삭제된 파일 (3개):**
- `backend/routers/lab.py`
- `web-react/src/api/labApi.js`
- `web-react/src/features/lab/LabPage.jsx` (폴더 통째)

**되돌린 파일 (7개, git checkout):**
- `backend/main.py` (lab router include 제거)
- `backend/ontology/schemas.py` (EvidenceMatch/QuestionMapping/MappingResult 제거)
- `backend/services/{ai_provider,local_provider,mock_provider,openai_provider}.py` (lab 4 메서드 제거)
- `web-react/src/App.jsx` (/lab route + LabPage import 제거)

### 관련 문서
- **Snapshot:** `local/prompt/v0.2/LAB_v0.1_snapshot.md` (폐기 직전 패턴 보존)
- `local/1_PRD/features/lab/lab_v01_prd.md` (사양 학습 자료, 보존)
- `local/1_PRD/features/lab/lab_v01_suggestions.md` (제안 메모, 보존)
- `local/2_work/reports/20250507_lab_v01_report.md` (당시 구현 보고서, 보존)
- `local/2_work/reports/2026-05-09_lab_v0.1_discard_report.md` (폐기 보고서)
- **git history**: 폐기 직전 코드 영구 보존 (`git log` 추적 가능)

---

## 6. /api/lab/* — 5개 엔드포인트 신규 (2026-05-07)

### 변경 전 (PRD 원본)
- PRD-05: `/api/ai/*` 6개 엔드포인트 (generate-draft, evaluate, improve, check-completeness, chat-review, provider-info)
- 단계별 분석 API 미정의

### 변경 후 (현재 구현)
신규 5개 엔드포인트:

| 엔드포인트 | 용도 |
|-----------|------|
| `POST /api/lab/parse` | 파일 multipart 업로드 + 카테고리별 파싱 |
| `POST /api/lab/analyze-notice` | 공고문 텍스트 → NoticeSchema |
| `POST /api/lab/analyze-form` | 제출양식 텍스트 → FormSchema |
| `POST /api/lab/extract-evidence` | 참고자료 텍스트 → EvidenceSchema (파일별 1회) |
| `POST /api/lab/map-evidence` | FormSchema + EvidenceSchema → MappingResult |

**파일:** `backend/routers/lab.py` (신규)

### 사유
- 변경 5 (/lab 페이지)의 백엔드 인프라
- 단계별 분석 결과를 가시화하기 위해 단일 호출이 아닌 5단계 분리

### 상태
- ⚠️ 변경 5와 함께 커밋 보류

---

## 7. AI Provider — lab 전용 메서드 4개 추가 (2026-05-07)

### 변경 전 (PRD 원본)
- PRD-05: `AIProvider` ABC에 5개 추상 메서드
  - `generate_draft`, `evaluate_draft`, `improve_draft`, `check_completeness`, `chat_review`

### 변경 후 (현재 구현)
신규 4개 추상 메서드:

```python
@abstractmethod
async def analyze_notice(self, notice_text: str) -> dict: ...
@abstractmethod
async def parse_form(self, form_text: str, form_name: str) -> dict: ...
@abstractmethod
async def extract_evidence(self, ref_text: str, source_file: str) -> dict: ...
@abstractmethod
async def map_evidence(self, form_schema: dict, evidence_list: list, notice_schema: dict) -> dict: ...
```

3개 Provider 모두 구현:
- **MockProvider** — 의미 있는 한국어 mock 데이터
- **LocalProvider** — `_chat()` + JSON 파싱 + fallback (stub)
- **OpenAIProvider** — `_chat()` + JSON 파싱 + fallback (stub)

### 사유
- 변경 6 (/api/lab/* 엔드포인트)의 비즈니스 로직 위임
- ABC 패턴 유지: 모든 Provider 동일 시그니처 → import 깨짐 방지

### 상태
- ⚠️ 변경 5/6과 함께 커밋 보류

---

## 8. FormSchema 확장 (2026-05-07)

### 변경 전 (PRD 원본)
```python
class FormSchema(BaseModel):
    questions: List[FormQuestion]
```

### 변경 후 (현재 구현)
```python
class FormSchema(BaseModel):
    form_id: str = Field(default="", description="양식 식별자 (ex: form_0)")
    form_name: str = Field(default="", description="양식 파일명")
    form_file: str = Field(default="", description="원본 파일명")
    questions: List[FormQuestion] = Field(default_factory=list)
```

신규 스키마:
```python
class FormSetSchema(BaseModel):
    forms: List[FormSchema]

class EvidenceMatch(BaseModel):
    evidence_content: str
    source_file: str
    confidence: float
    relevance_reason: str

class QuestionMapping(BaseModel):
    question_id: str
    question_title: str
    matches: List[EvidenceMatch]
    missing: bool
    missing_reason: Optional[str]

class MappingResult(BaseModel):
    question_mappings: List[QuestionMapping]
    overall_missing_count: int
    coverage_rate: float
```

### 사유
- 다중 양식 처리 (변경 1.3 "다중 파일 업로드")
- /lab map-evidence 결과 구조화

### 보강 규칙 적용
- grep으로 web-react/, /api/ai/* 미사용 확인 → 별도 LabFormSchema 생성 없이 기존 FormSchema 직접 확장 (회귀 위험 0)

### 상태
- ⚠️ 변경 5/6/7과 함께 커밋 보류

---

## 9. DraftPage 5단계 — 신청 준비 직접 진입 허용 (2026-05-07, commit 5d26d9a, a4ed45b)

### 변경 전 (PRD 원본)
- PRD-06: DraftPage는 **DetailPage(공고 상세)에서만 진입** 가능
- 코드: `if (!notice) return <NoticeRequired />` (early return 가드)

### 변경 후 (현재 구현)
- TopNav '신청 준비' 메뉴에서 직접 진입 가능 (notice 없이)
- DraftPage early return 가드 **제거**
- 모든 `notice.X` 접근을 `notice?.X` 옵셔널 체이닝으로 변경
- 다운로드 파일명: `notice?.title || '제목없음'`

**Step1Upload 추가:**
- 공고문 카드 하단에 **수동 업로드** 영역
- accept: `.pdf,.docx,.hwp,.hwpx`
- noticeFiles state 추가

### 사유
- 사용자가 공고 없이도 사업계획서 작업 시작 원함
- TopNav '신청 준비'가 disabled 였던 것을 활성화

---

## 10. DraftPage Step5 신규 — 완료 & 제출 (2026-05-08, commit ed68416)

### 변경 전 (PRD 원본)
- PRD-06: DraftPage 4단계 (자료업로드 → 자료검사 → 초안작성 → 전략검토)
- 완료/제출은 별도 화면

### 변경 후 (현재 구현)
**5단계 추가:** `완료 & 제출`
- DOCX 다운로드 (`docx` + `file-saver` 라이브러리)
- TXT 다운로드
- 기관 제출 외부 링크 (`notice?.rceptEngnHmpgUrl`)
- 종합 평가 리포트 (90점/100점 + 카테고리별 평가)

### 사유
- "전략 검토" 직후 다운로드/제출하면 인지적 단절 발생
- 별도 게이트(완료)를 두어 사용자에게 "끝났다" 신호 명확화

### 부채
- 종합 점수 90점 **하드코딩** — evalResult 연동은 v0.2 예정 (`local/PRD/features/draft/draft_v01_suggestions.md` §4.1)

---

## 11. 자동 저장 — File 메타데이터만 저장 (2026-05-07~)

### 변경 전 (PRD 원본)
- PRD-07: `localStorage`에 drafts 저장 (개념적)
- 파일 객체 처리 미정의

### 변경 후 (현재 구현)
**500ms 디바운스 + File 객체는 메타데이터만 저장:**

```jsx
const uploadsMetadata = Object.fromEntries(
  Object.entries(uploads).map(([key, files]) => [
    key,
    (files || []).map(f => ({ name: f.name, size: f.size, type: f.type })),
  ])
)
```

재로드 시 `!(file instanceof File)` 검사로 **"⚠️ 재업로드 필요"** UI 표시.

### 사유
- File 객체는 `JSON.stringify` 직렬화 불가
- 파일 자체는 React 메모리에만 존재 (페이지 이동 시 소멸)
- 백엔드 파일 저장 API는 v1.1 부채 (TODO_polish §A)

### 부채
- 업로드 파일이 backend에 영속화되지 않음 → /lab 흐름과 통합 시 결정 필요

---

## 12. 기능별 단계 진화 (요약)

| 단계 | 변경 전 | 변경 후 |
|-----|--------|--------|
| Step1 자료 업로드 | DetailPage 진입 시 공고 자료 자동 인계 | + 사용자 수동 업로드 (notice 없이도 가능) |
| Step2 자료 검사 | 단일 검사 결과 표시 | 3컬럼 (양식 구조 / 자동작성 미리보기 / 충족도+부족자료) |
| Step3 초안 작성 | 좌(섹션) + 중(에디터) + 우(챗봇) | 동일 + 키워드 매칭 시 챗봇 응답을 drafts에 직접 반영 |
| Step4 전략 검토 | 자기 수정 루프 (PRD v2) | 메타 6-grid + 평가 항목 진단 + 우선순위 보완 카드 + 정합성 검사 |
| Step5 완료 & 제출 | 없음 (PRD v1) / 분리 (PRD v2) | 신규 단계, DOCX/TXT 다운로드 + 기관 제출 링크 |

---

## 13. 관련 문서 위치

본 문서가 추적하는 변경의 상세 사양은 다른 문서에 있다.

| 변경 # | 상세 문서 | 위치 |
|-------|---------|------|
| 5, 6, 7, 8 (폐기) | LAB_v0.1_snapshot.md | local/prompt/v0.2/ (폐기 직전 패턴 보존) |
| 5, 6, 7, 8 (참고) | lab_v01_prd.md, lab_v01_suggestions.md | local/1_PRD/features/lab/ (학습 자료) |
| 9, 10, 11, 12 | draft_v01_prd.md, draft_v01_suggestions.md | local/1_PRD/features/draft/ |
| v1→v2 큰 전환 | (PRD-13 §1에 통합됨) | (이전 0506_변경정리.md는 PRD-13에 흡수 후 삭제) |

---

## 14. 미해결 사항 (결정 필요)

| 항목 | 상태 | 결정 필요 |
|------|-----|---------|
| Jaccard 적합도 계산 | 미정 | 유지? 임베딩으로 대체? |
| 평가 시뮬레이션 (PRD-04 §F-07, PRD-06 §Page 6) | 미정 | 유지 / Step4 흡수 / 폐기? |
| LLM 미연결 시 동작 범위 | 미정 | PRD-12 원칙 3과 v2의 호환성 |
| 이중 식별자 (notice_id, draft_id) | 부채 | v1.1에서 단일화 검토 |
| 업로드 파일 backend 영속화 | 부채 | v0.2 Phase 1 결정 |
| ~~/lab v0.1 동작 검증 + 커밋~~ | ✅ 폐기 (2026-05-09) | v0.2 8 모듈로 진화. Snapshot 보존 |
| Step5 종합 점수 하드코딩 (90점) | 부채 | evalResult 연동 (v0.2) |

---

## 15. 변경 이력 (Changelog)

| 날짜 | 변경 # | 요약 | 커밋 |
|------|-------|------|------|
| 2026-05-06 | §1 (v1→v2 전환) | 폐기 6개 / 신규 12개 / 원칙 4개 | (이전 커밋들) |
| 2026-05-07 | §2 | DB 옵션 A 전환 (drafts 버전관리) | cb3e901 |
| 2026-05-07 | §3 | ai_call_logs + @audit_log | d1fc6c1, ed5b454 |
| 2026-05-07 | §4 | 이중 식별자 (notice_id + draft_id) | cb3e901 |
| 2026-05-07 | §5 | /lab v0.1 페이지 (코드 완성, **2026-05-09 폐기**) | (미커밋, 폐기) |
| 2026-05-07 | §6 | /api/lab/* 5개 엔드포인트 (**2026-05-09 폐기**) | (미커밋, 폐기) |
| 2026-05-07 | §7 | AI Provider lab 메서드 4개 (**2026-05-09 폐기**) | (미커밋, 폐기) |
| 2026-05-07 | §8 | FormSchema 확장 (**2026-05-09 되돌림, v0.2 spec으로 새로 정의 예정**) | (미커밋, 되돌림) |
| 2026-05-07 | §9 | DraftPage 신청 준비 직접 진입 | 5d26d9a, a4ed45b |
| 2026-05-08 | §10 | DraftPage Step5 신규 | ed68416 |
| 2026-05-09 | §0 | 폴더 정리 + local/ 분리 | f0f86bc |
| 2026-05-09 | §5~§8 | /lab v0.1 폐기 (Snapshot: local/prompt/v0.2/LAB_v0.1_snapshot.md) | (this commit) |

---

## 16. 사용 규칙

### 16.1 새 변경 발생 시
1. 본 문서 끝(§17 신규 변경 슬롯)에 변경 항목 추가
2. **변경 전 (PRD 원본)** + **변경 후 (현재 구현)** + **사유** 형식 유지
3. 관련 PRD 섹션 명시
4. §15 변경 이력에 1줄 추가

### 16.2 PRD-01~12 본문은 갱신하지 않음
원본 보존 → 변경 추적성 확보. 갱신이 필요한 정보는 본 문서에.

### 16.3 안정화된 기능 PRD가 있으면
`local/PRD/features/{기능}/` 또는 `PRD/{기능}_prd.md`로 별도 관리. 본 문서는 요약만.

---

## 17. 신규 변경 슬롯 (다음 변경 시 여기에 추가)

(추가 시 이 위치에 §19, §20 ... 형식으로)

---

## 18. v0.2 통합 정책 Addendum (2026-05-11)

**배경:** Phase 4-G 진행 중 V1↔V2 통합 시 발생할 architectural 결정사항을 PRD v0.2 FINAL 본문에 추가하지 않고, 본 changelog의 추가 정책으로 명시. PRD §13.9 ApplicationSession 원칙 + §16.8 wrapper 금지 + §20 Phase 7 흐름 정합.

### 18.1 ApplicationSession is the single source of truth for V2

- V2 analysis, mapping, evidence, missing materials, and draft items must be linked by `session_id`.
- V2 must not write draft-generation results into the legacy V1 `Draft` table.

### 18.2 Notice and ApplicationSession relationship — 1 : N

- One `Notice` can have multiple `ApplicationSession` records (1 공고 → N 세션).
- Do not assume `notice_id = one session`.
- **Frontend default behavior**: 매 진입마다 새 세션을 생성하지 않는다. 동일 `user_id` + `notice_id`에 active session이 있으면 기본은 reuse한다. 새 세션 생성은 사용자가 명시적으로 새로 시작을 선택한 경우에만 수행한다.
- Active status: `created` / `analyzing` / `analysis_ready` / `step2_confirmed` / `drafting`
- Inactive: `completed` / `abandoned` / `failed`
- 구현: `GET /api/analysis/sessions?user_id=&notice_id=&limit=` 로 기존 세션 조회 → frontend에서 active status 필터링 → reuse (Phase 4-G P0 완료, cd02dd8 + 작업 1·2).

**English (canonical):**

> One Notice can have multiple ApplicationSession records. However, the default frontend behavior must not create a new session every time. If an active ApplicationSession already exists for the same notice and user, the UI should reuse or offer to resume it. A new ApplicationSession should be created only when the user explicitly starts a new application flow.

### 18.3 Legacy Draft policy

- V1 `Draft` remains legacy.
- V2 must not read V1 `Draft` as a source for analysis or draft generation.
- 사용자 사후 제출/채택/미채택 관리는 별도 `SubmissionRecord` (또는 `ApplicationOutcome`) entity로 분리한다 (v0.3 신설 예정).
- V1 `Draft`의 작성 흐름 (V1 5섹션 고정 모델: overview/purpose/plan/effect/budget) 은 V2가 따르지 않는다.
- V2는 form_parser가 추출한 **동적 question 단위**(DraftItem)로 작성한다.

### 18.4 `/api/ai/*` policy

- `/api/ai/*` endpoints are legacy/deprecated.
- V2 must use `/api/analysis/*` and `/api/chat/draft-assist`.
- V2 must not call `/api/ai/*` as wrappers (PRD §16.8 정합).
- `/api/ai/evaluate` may remain temporarily until Step 4 evaluation is redesigned in v0.3.

### 18.5 ChatDraftPage policy

- `ChatDraftPage` is not part of V2 PRD.
- Its useful functions are absorbed into V2 Step 3 AI 보완 패널 (`/api/chat/draft-assist`).
- `ChatDraftPage.jsx` is to be renamed to `ChatDraftPage_legacy.jsx` and removed from V2 routing after V2 Step 3 is fully verified.

### 18.6 `drafts_preservation_policy`

- Default policy is `user_choice` (PRD §13.9 그대로).
- The preservation modal is required before enabling re-analysis from Step 3 or later.
- 구현 시점: Phase 4-G 후반 (4-G-7/8 이후 P3). G-0.5 / G-1~6 에 포함하지 않음.

### 18.7 `/draft-v2` route gate

- Keep `/draft-v2` behind dev gate (`VITE_ENABLE_ANALYSIS_DEV_MODE=true`) until V2 beta readiness.
- Do not redirect `/draft` to V2 until Phase 7 베타 전환.
- 베타 전환 시: `/draft` → V2, `/draft-v1` (legacy backup) 생성.
- 잠깐이라도 `/draft`와 `/draft-v2`가 둘 다 V2를 가리키는 구조는 피한다.

### 18.8 V1 flow vs V1 model 분리 — 운영 정의

| 항목 | 분류 | V2 처리 |
|------|------|---------|
| 5-step 화면 흐름 | V1 flow | 재사용 가능 |
| 대시보드 → 검색 → 상세 → 신청 준비 | V1 flow | 재사용 가능 |
| StepIndicator UI | V1 flow | 재사용 가능 |
| 이전/다음 버튼 흐름 | V1 flow | 재사용 가능 |
| 자동 저장 UX | V1 flow | 재사용 가능 |
| `drafts` 테이블 | V1 model | V2에서 사용 금지 |
| `overview/purpose/plan/effect/budget` 5섹션 | V1 model | 사용 금지 |
| `/api/ai/generate-draft` `section` enum 방식 | V1 model | 사용 금지 |
| `Draft.status` 제출/채택 enum | V1 model | V2 작성 흐름에서 사용 금지 |
| `completed_steps` 고정 배열 | V1 model | 사용 금지 |
| localStorage key schema | V1 model | V2 전용 key로 분리 (`ajin_v2_session_id`) |
| V1 `checkResult` 구조 | V1 model | V2는 FormSchema/DraftItem 기반 재정의 |

**핵심 문장:**

> V2는 V1의 UX journey를 재사용할 수 있으나, V1의 persistence schema, fixed draft sections, fixed API contract, localStorage schema는 재사용하지 않는다.

### 18.10 Step 4 v0.2 검토 화면 정책

**목적:** Step 3 작성 결과(DraftItem) + Step 2 분석 결과(MappingResult / MissingMaterial / EvalCriteriaMapping)를 요약 표시. 평가 엔진 미사용 (v0.3 분리, §11.2).

**화면 구성 (5 영역):**
- ① 작성 요약 통계 (6 카드, status 3 segments 통합)
- ② 문항별 검토 리스트 (테이블: 문항 ID / 문항명 / 작성상태 / Evidence / 부족자료, 클릭 시 Step 3 점프)
- ③ 사전 점검 체크리스트 (notice.required_documents 동적 + fallback 4개)
- ④ 평가기준 매핑 요약 (scope=question/section/document별 작성 완료 수 / 전체 매핑 수)
- ⑤ MissingMaterial / SupplementalMaterial status 요약

**컬럼 매핑 규칙:**
- 작성 상태 (2값): 작성 완료 ← generated/user_edited/needs_revision/approved | 미작성 ← draft/blocked
- Evidence (2값): 근거자료 있음 ← used_evidence_ids.length > 0 | 근거자료 없음
- 부족자료 (4값, 우선순위): open → deferred → resolved (rejected 포함) → 없음

**금지 사항 (V2 architectural integrity):**
- V1 `Step4Review` import 금지
- `/api/ai/evaluate` / `/api/ai/improve` 호출 금지
- V1 5섹션 구조 (`overview`/`purpose`/`plan`/`effect`/`budget`) 사용 금지
- V2는 FormSchema + DraftItem + question_id 기준 유지
- 어떤 scope에서도 V1 5섹션 enum으로 변환 X

**scope 처리 (PRD §13.8 EvalCriteriaMapping 정합):**
- `'question'`: 매핑된 question_id의 DraftItem 상태 직접 집계
- `'section'`: 매핑된 question_id가 속한 section 전체 question 집계
- `'document'`: 전체 DraftItem 상태 집계

**Step 5 이동 정책:**
- 차단 X
- 미작성/needs_revision/open missing 있으면 `Step4ProceedModal` 표시 (별도 컴포넌트, AnalysisConfirmModal과 분리)
- 사용자 확인 시 이동 허용

**Backend / DB 영향: 없음**
- ApplicationSession / DraftItem / MissingMaterial / SupplementalMaterial enum 모두 그대로
- SupplementalMaterial status enum 신규 추가 X
- migration 0건
- missing/* API 기존 schema 그대로 호출

**v0.3 분리 (§11.2 정합):** 심사위원 관점 평가 / 평가표 점수화 / 자동 보완 제안 엔진 / 사용자 커스텀 체크리스트.

### 18.9 anonymous user_id 임시 정책 (v0.2)

- v0.2는 단일 사용자 환경(`user_id = "anonymous"`) 으로 운영한다.
- `GET /api/analysis/sessions` 호출 시 `user_id` 미지정 = 모든 세션 노출. v0.2 단일 사용자 환경 기준이라 OK.
- v0.3 multi-user 전환 시 결정 사항 (별도 시점에 마이그레이션 계획):
  - 기존 anonymous 세션의 소유권 이관 (특정 신규 user_id로 일괄 매핑 vs 폐기)
  - `GET /sessions`에 user_id 인증 강제 (현재는 query 파라미터만)
  - `ApplicationSession.user_id` 인덱스 추가 검토
- v0.2/v0.2.1 동안은 본 정책 그대로 유지. 별도 코드 변경 없음.

### 변경 영향

- PRD-01~12 본문 갱신 없음 (§16.2 원칙).
- PRD v0.2 FINAL (`local/1_PRD/v0.2/PRD_v0.2_FINAL.md`) §13.9, §16.4~§16.8, §20 모두 본 Addendum과 정합.
- 코드 영향:
  - backend/routers/analysis.py P0 GET sessions 추가 (cd02dd8)
  - frontend P0 FE + active session reuse + runtime 가시성 (작업 1~3, 후속 commit)
  - 그 외 모두 Phase 4-G 진행 중 자연스럽게 정합.

### §15 변경 이력 추가
| 2026-05-11 | §18 | v0.2 통합 정책 Addendum 8개 (ApplicationSession SoT / Notice:Session N:1 / Legacy Draft / api/ai 폐기 / ChatDraftPage / preservation_policy / dev gate / V1 flow vs model 분리) | (this commit) |
| 2026-05-11 | §18 보강 | §18.2 정정 (N:1 → 1:N + active reuse default policy) / §18.8 V1 flow vs model 운영 정의 표 12행 / §18.9 anonymous user_id v0.2 임시 정책 신설 | (next commit) |
| 2026-05-11 | §18.10 | Step 4 v0.2 검토 화면 정책 신설 (5 영역 + V1 금지 + scope 처리 + Step 5 이동 모달 + backend/DB 미변경) | (this commit) |

---

## §19 — v0.2.1 평가기준 매핑 편집 정책 (2026-05-11 추가)

**Context:** PRD §2 정의 = "v0.2.1 = 평가기준 매핑 수정 기능 전용 마이너 릴리스". v0.2 구현 종료 후 진행.

### 19.1 범위

| # | 항목 | 비고 |
|----|------|------|
| 1 | EvalCriteriaMapping 편집 UI (scope/문항/유형/confidence 수정) | frontend |
| 2 | 사용자 편집 영속화 — `mapped_by="user"` 강제 | backend (V1 완료, 2026-05-11) |
| 3 | 변경 이력 추적 | backend (V2) |
| 4 | 매핑 변경 시 영향받는 데이터 갱신 흐름 | Step 4 검토 패널 |

### 19.2 backend endpoint (V1 완료)

| Method | Path | 책임 |
|--------|------|------|
| `PATCH /api/analysis/eval-criteria-mappings/{criteria_id}` | upsert — 없으면 생성, 있으면 갱신. mapped_by="user" 자동 |
| `GET /api/analysis/eval-criteria-mappings?session_id={id}` | 사용자 편집 row 목록 (AI 생성 mock 결과는 별도, frontend merge) |
| `POST /api/analysis/map-eval-criteria` (기존) | AI 자동 매핑 — 응답만 반환, DB 저장 X |

**정책:** map-eval-criteria의 mock 결과는 항상 frontend 메모리, PATCH 한 row만 DB. v0.2.1 화면은 두 source merge하되 user 편집 우선.

### 19.3 변경 이력 정책 (V2)

**선택지 (2026-05-11 결정 보류):**
- A. `eval_criteria_mappings.history` JSON 컬럼 — 단순, row 단위 보존
- B. 별도 `eval_criteria_mapping_history` 테이블 — 정규화, 시계열 조회 효율
- C. `ai_call_logs` 재활용 — 기존 audit 인프라 활용

**권장:** A (JSON 컬럼) — v0.2.1 범위에선 단일 row history 충분. v0.3 multi-user 전환 시 B로 마이그레이션 검토.

**저장 내용 (예시):**
```json
{
  "history": [
    {"at": "2026-05-11T18:00:00", "by": "user",
     "changes": {"scope": ["section", "question"], "mapped_questions": [["I-1"], ["I-1","I-2"]]}}
  ]
}
```

### 19.4 영향받는 데이터 갱신 (V4)

매핑 편집 시 Step 4 검토 패널 즉시 반영:
- scope 변경 → 작성 완료 수 / 전체 매핑 수 재계산
- mapped_questions 변경 → 영향받는 DraftItem 표시
- confidence 변경 → 검토 화면 정렬 영향

**backend 영향: 없음.** state lift + adapter 재계산만 (frontend).

### 19.5 v0.2.1 vs v0.2 vs v0.3 경계

| 항목 | v0.2 | v0.2.1 | v0.3 |
|------|:--:|:--:|:--:|
| AI 자동 매핑 (map-eval-criteria) | ✓ | ✓ | ✓ |
| 사용자 편집 UI | ✗ | **✓** | ✓ |
| 변경 이력 추적 | ✗ | **✓** | ✓ |
| 영향받는 데이터 즉시 갱신 | ✗ | **✓** | ✓ |
| 평가표 점수화 (평가 엔진) | ✗ | ✗ | ✓ |
| 자동 보완 제안 | ✗ | ✗ | ✓ |
| 심사위원 관점 평가 | ✗ | ✗ | ✓ |
| 다중 사용자 권한 | ✗ | ✗ | ✓ |

### 19.6 backend / DB 영향

- **신규 endpoint 2건** (PATCH / GET, V1 완료)
- **migration 0005** (V2 미진행 시 — eval_criteria_mappings.history JSON ADD COLUMN)
- 기존 테이블 보호 (CLAUDE.md §4): notices/drafts/bookmarks/profile/ai_call_logs row 보전 검증

### §15 변경 이력 추가
| 2026-05-11 | §19 | v0.2.1 평가기준 매핑 편집 정책 신설 (V1 backend PATCH/GET 완료 / V2~V4 부채 정의 / 변경 이력 옵션 A 권장) | (this commit) |

---

## §20 — 공고 수집 아키텍처 전환: 프론트 직접 호출 → FastAPI `/api/notices/search` (2026-05-12)

### 변경 전 (기존 구현)
- `noticesApi.js`(브라우저)가 4개 공공 API를 직접 호출
- API 키(`VITE_API_KEY`, `VITE_BIZ_KEY`)가 `VITE_*` 환경변수로 브라우저에 노출
- CORS 우회: Express `server.js` + `vite.config.js`의 `/proxy/bizinfo`, `/proxy/apis` 프록시 사용
- 키 보관 위치: `web-react/.env.server` (Node.js 전용)
- 캐싱 흐름: 프론트 외부 API 성공 시 → `POST /api/notices/bulk` 수동 저장

### 변경 후 (현재 구현)
- FastAPI가 4개 공공 API를 서버에서 직접 호출 (`GET /api/notices/search`)
- API 키 위치: `backend/.env` (`GONGGONG_API_KEY`, `BIZINFO_API_KEY`) — 브라우저 미노출
- `web-react/.env.server`에서 `API_KEY`, `BIZ_KEY` 제거 완료
- Express `/proxy/bizinfo`, `/proxy/apis` 블록 → 제거 대상 (추후 정리)
- 프론트는 `GET /api/notices/search?q={keyword}&refresh={bool}` 단일 호출

### 사유
1. API 키 브라우저 노출 방지 (보안)
2. CORS 문제 근본 해결 (서버↔서버 호출)
3. Express proxy + `VITE_*` URL 환경변수 복잡성 제거
4. `46dcc83` 원래 설계 의도(서버에 키 보관) 완성 — `0d981fd` UI 대수정에서 깨진 구조 복원

### 변경 파일
| 파일 | 변경 내용 |
|------|---------|
| `backend/.env` | `GONGGONG_API_KEY`, `BIZINFO_API_KEY` 추가 |
| `web-react/.env.server` | `API_KEY`, `BIZ_KEY` 제거 |
| `backend/routers/notices.py` | `GET /api/notices/search` 신규 (외부 fetch + upsert + 반환) |

### §15 변경 이력 추가
| 2026-05-12 | §20 | 공고 수집 아키텍처 전환 — FastAPI /api/notices/search 신규, API 키 backend .env 이동, .env.server 정리 | (this commit) |
