# PRD-11: 용어 정의 (Glossary)

> **문서 버전** 1.0 | **선행 문서** PRD-10 | **후행 문서** PRD-12  
> **목적** 코드·문서 전체에서 동일한 용어를 일관되게 사용하기 위한 기준

---

## 도메인 용어

| 용어 | 영문 키 | 정의 | 코드 내 사용처 |
|------|--------|------|-------------|
| **공고** | Notice | 정부·공공기관의 지원사업 모집 공고 | `Notice` 타입, `noticeId` |
| **적합도** | Matching Score | 기업 프로필과 공고 내용의 텍스트 유사도 (0~1) | `ajin_similarity` 필드 |
| **임계값** | Threshold | 적합도 필터링 최솟값 (기본 0.02 = 2%) | `simThreshold`, `threshold` |
| **초안** | Draft | AI가 생성한 사업계획서 초안 텍스트 | `draftSession`, `fullText` |
| **작성 가능률** | Readiness Score | 업로드 자료로 채울 수 있는 초안 항목 비율 (0~100%) | `readinessScore` |
| **부족정보** | Missing Info | 초안 생성에 필요하나 업로드 자료에 없는 정보 | `diagnosisResult.missing_required` |
| **평가 시뮬레이션** | Score Simulation | 완성된 초안을 공고 평가기준으로 채점하는 기능 | `runScoreSimulation()` |
| **동시수행 제한** | Concurrent Limit | 동일 기업이 동시에 수행할 수 있는 사업 수 제한 | `isOngoing`, `checkConcurrentLimit()` |
| **D-Day** | D-Day | 공고 마감까지 남은 일수 (`Math.ceil((date - now) / 86400000)`) | `getDdayText()` |
| **STEP** | Step | 신청 준비 워크플로우의 단계 (1~5) | `currentStep`, `STEPS` |
| **히스토리** | History | 과거 신청 이력 및 수행 중 사업 기록 | `ApplicationRecord[]` |
| **북마크** | Bookmark | 관심 공고를 저장하는 기능 | `bookmarks: string[]` |
| **세션** | Session | 현재 진행 중인 신청 준비 또는 초안 작성 상태 | `applySession`, `draftSession` |

---

## 기술 용어

| 용어 | 정의 |
|------|------|
| **Jaccard 유사도** | `교집합 토큰 수 / 합집합 토큰 수` — MVP v1.0 적합도 계산 알고리즘 |
| **Sentence Transformer** | 문장을 고차원 벡터로 임베딩하는 딥러닝 모델. v1.1에서 Jaccard 대체 예정 |
| **LM Studio** | 로컬 PC에서 LLM을 실행하는 도구. OpenAI API와 호환 인터페이스 제공 |
| **pdfplumber** | Python PDF 텍스트 추출 라이브러리 |
| **SPA** | Single Page Application — 페이지 리로드 없이 React 조건부 렌더링으로 화면 전환 |
| **localStorage** | 브라우저 영구 저장소 (탭 닫아도 유지). MVP 데이터 영속성 계층 |
| **sessionStorage** | 브라우저 세션 저장소 (탭 닫으면 소멸). 공고 캐시에 사용 |
| **Context API** | React 전역 상태 관리 패턴 (Redux 미사용) |
| **shadcn/ui** | TailwindCSS 기반 React UI 컴포넌트 라이브러리 |
| **FastAPI** | Python 비동기 웹 프레임워크. 백엔드 파일 파싱 API 서버 |
| **CORS** | Cross-Origin Resource Sharing — 브라우저 보안 정책. Express 프록시로 우회 |

---

## API 필드명 매핑 (공공 API → 내부 필드)

| 내부 필드 | 기업마당 원본 필드 | 설명 |
|---------|----------------|------|
| `title` | `pblancNm` | 공고명 |
| `content` | `bsnsSumryCn` | 사업 개요 |
| `target` | `trgetNm` | 지원 대상 |
| `benefit` | `suptCn` | 지원 혜택 |
| `region` | `areaNm` | 지역 |
| `period` | `reqstBeginEndDe` | 신청 기간 문자열 |
| `date` | (`reqstBeginEndDe` 파싱) | 마감일 Date 객체 |
| `url` | `pblancUrl` | 공고 원문 URL |
| `jrsdInsttNm` | `jrsdInsttNm` | 소관기관 |
| `excInsttNm` | `excInsttNm` | 수행기관 |
| `ajin_similarity` | (계산값) | AI 적합도 점수 |

---

## 상태값 목록

### ApplicationRecord.status
| 값 | 표시 레이블 | 색상 클래스 |
|----|----------|-----------|
| `'drafting'` | 작성 중 | `bg-blue-100 text-blue-700` |
| `'submitted'` | 제출 완료 | `bg-slate-100 text-slate-700` |
| `'selected'` | 선정 | `bg-green-100 text-green-700` |
| `'rejected'` | 미선정 | `bg-red-100 text-red-700` |
| `'cancelled'` | 취소 | `bg-gray-100 text-gray-500` |

### DraftSection.status
| 값 | 의미 | 색상 |
|----|------|------|
| `'pending'` | 대기 중 (opacity 30%) | 회색 |
| `'generating'` | AI 작성 중 (애니메이션) | 파란색 점등 |
| `'draft'` | 검토 필요 | 주황색 |
| `'revising'` | 수정 중 (애니메이션) | 보라색 점등 |
| `'confirmed'` | 완료 | 녹색 |

### CompanyProfile.size
| 값 | 의미 |
|----|------|
| `'SME'` | 중소기업 (직원 300인 미만) |
| `'Mid'` | 중견기업 (직원 300~2,000인) |
| `'Large'` | 대기업 |
