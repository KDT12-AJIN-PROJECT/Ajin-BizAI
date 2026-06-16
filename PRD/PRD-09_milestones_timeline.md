# PRD-09: 구현 우선순위 및 마일스톤 (일별 타임라인)

> **문서 버전** 1.0 | **선행 문서** PRD-08 | **후행 문서** PRD-10  
> **총 개발 기간** 56일 (8주) | **팀 구성** 2~4인 (Claude Code 에이전트 포함)

---

## 전체 일정 개요

| Phase | 기간 | 핵심 목표 | 완료 기준 |
|-------|------|---------|---------|
| Phase 1 | Day 1~14 | 기반 인프라 + 공고 검색 고도화 | 공고 수집·필터링·상세 정상 동작 |
| Phase 2 | Day 15~28 | 신청 준비 워크플로우 (핵심 차별점) | 파일 업로드 → AI 진단 → 인터뷰 완성 |
| Phase 3 | Day 29~42 | 초안 생성 + 평가 시뮬레이션 + 히스토리 | 초안 생성 + 점수 시뮬레이션 동작 |
| Phase 4 | Day 43~56 | 품질 완성 + 배포 | Lighthouse 90+, E2E 통과, Docker 배포 |

---

## Phase 1 (Day 1~14): 기반 인프라 + 공고 검색

### Day 1~3: 프로젝트 초기 설정
- [ ] 기존 `web-react/` 코드 분석 및 리팩터링 계획 수립
- [ ] `src/constants/pages.js` 생성 (PRD-03 §2 코드 그대로 적용)
- [ ] `src/constants/storageKeys.js` 생성 (PRD-07 §1 코드)
- [ ] `src/config/env.js` 업데이트 (PRD-05 §3.2 코드)
- [ ] `src/contexts/AppContext.jsx` 생성 (PRD-07 §1 전체 코드)
- [ ] `App.jsx` 라우팅 재구성 (PRD-03 §3 코드)
- [ ] `backend/` 폴더 생성, FastAPI 초기 설정 (PRD-05 §7)

**Day 3 DoD (Definition of Done)**:
- `npm run dev` 실행 → 빈 대시보드 표시
- `uvicorn main:app` 실행 → `/api/health` 응답 OK

### Day 4~6: 공고 수집 엔진 고도화
- [ ] `normalizeNotice()` PRD-04 §4.1.3 코드로 교체
- [ ] `fetchAllNotices()` PRD-04 §4.1.2 코드로 교체 (타임아웃, 캐시 포함)
- [ ] `dedupeNotices()` 구현
- [ ] `useNotices.js` PRD-07 §2 코드로 교체
- [ ] 단위 테스트: `normalize.test.js` (PRD-10 §2.1)

**Day 6 DoD**: 공고 목록 화면에서 실제 공고 > 0건 표시

### Day 7~9: AI 적합도 매칭 + 필터링
- [ ] `match.js` PRD-04 §4.2.1 코드로 교체
- [ ] `filtering.js` PRD-04 §4.3.1 코드로 교체
- [ ] `extractFilterOptions()` 구현
- [ ] 기업 프로필 설정 페이지 연동 (프로필 저장 → 적합도 재계산)
- [ ] 단위 테스트: `match.test.js` (PRD-10 §2.1)

**Day 9 DoD**: 기업 프로필 입력 후 공고 적합도 % 표시, 필터 전환 정상 동작

### Day 10~12: 공고 상세 고도화
- [ ] `evaluationParser.js` PRD-04 §4.4.1 코드 구현
- [ ] `EvaluationCriteriaCard` 컴포넌트 구현 (PRD-06 §Page 3)
- [ ] `DocChecklist` 컴포넌트 구현 (PRD-06 §Page 3)
- [ ] 지원 규모·조건·기간 카드 UI 추가
- [ ] 공고문 다운로드 링크 추가
- [ ] "신청 준비 시작" 버튼 추가 → ApplyPrepPage 진입

**Day 12 DoD**: 공고 상세에서 평가기준 뱃지, 서류 체크리스트, 신청 준비 버튼 표시

### Day 13~14: 대시보드 + 북마크
- [ ] `DashboardPage.jsx` 신규 생성 (PRD-06 §Page 1)
- [ ] `BookmarksPage.jsx` 신규 생성
- [ ] `TopNav.jsx` 업데이트 (PRD-03 §4)
- [ ] 북마크 토글 기능 (`toggleBookmark`)

**Day 14 DoD (Phase 1 완료)**:
- 대시보드 → 공고 검색 → 공고 상세 → 북마크 전체 흐름 동작
- Lighthouse 성능 점수 70+

---

## Phase 2 (Day 15~28): 신청 준비 워크플로우

### Day 15~17: Python 백엔드 파일 파싱
- [ ] `backend/routers/files.py` PRD-04 §4.5.2 코드 구현
- [ ] `backend/services/file_parser.py` 구현 (PDF, DOCX)
- [ ] HWP 파싱 실패 처리 (텍스트 직접 입력 폴백)
- [ ] `src/api/fileProcessApi.js` PRD-07 §4 코드 구현
- [ ] 통합 테스트: PDF 업로드 → 텍스트 추출 성공 확인

**Day 17 DoD**: PDF 업로드 시 10,000자 이내 텍스트 추출 성공

### Day 18~20: STEP 1~2 (파일 업로드 + AI 분석)
- [ ] `ApplyPrepPage.jsx` PRD-06 §Page 4 코드 구현
- [ ] `StepUpload.jsx` 구현 (드래그앤드롭 + 파일 항목별 슬롯)
- [ ] `StepAnalysis.jsx` 구현 (분석 중 로딩 + 작성 가능률 표시)
- [ ] `backend/services/diagnosis.py` PRD-04 §4.5.3 `calculate_completeness()` 구현
- [ ] `backend/routers/diagnosis.py` `/api/diagnosis` 엔드포인트

**Day 20 DoD**: 파일 업로드 → AI 분석 → 작성 가능률 % 표시

### Day 21~24: STEP 3~4 (부족 진단 + AI 인터뷰)
- [ ] `StepDiagnosis.jsx` 구현 (필수/선택 부족 항목 카드)
- [ ] `StepInterview.jsx` 구현 (질문 시퀀스, 체크박스/텍스트/구조화 입력)
- [ ] `interviewQuestions.js` PRD-04 §4.5.4 전체 목록 구현
- [ ] 답변 → `applySession.interviewAnswers` 저장
- [ ] 답변 후 작성 가능률 재계산 표시

**Day 24 DoD**: 5개 인터뷰 질문 답변 가능, 완료 후 가능률 90%+ 표시

### Day 25~28: STEP 5 + 세션 영속성
- [ ] `StepReadiness.jsx` 구현 (항목별 준비도 진행바 + "초안 생성하기" CTA)
- [ ] `updateApplySession()` localStorage 연동
- [ ] 페이지 새로고침 후 세션 복원 확인
- [ ] 통합 테스트: 5단계 전체 흐름 E2E (PRD-10 §3)

**Day 28 DoD (Phase 2 완료)**:
- 파일 업로드 → AI 진단 → 인터뷰 → 작성 가능률 92% 확인 전체 흐름

---

## Phase 3 (Day 29~42): 초안 + 시뮬레이션 + 히스토리

### Day 29~32: ChatDraftPage 개선
- [ ] `lmStudioApi.js` PRD-04 §4.6.1 전체 코드로 교체
- [ ] 평가기준 체크리스트 패널 추가 (PRD-06 §Page 5)
- [ ] 섹션 상태 머신 (pending→generating→draft→revising→confirmed)
- [ ] `useAutoSave()` 훅 연동 (PRD-07 §3)
- [ ] Word(.txt) 다운로드 기능 개선

**Day 32 DoD**: ChatDraft에서 5섹션 초안 생성·수정·다운로드 동작

### Day 33~36: SimulationPage
- [ ] `SimulationPage.jsx` PRD-06 §Page 6 코드 구현
- [ ] `runScoreSimulation()` PRD-04 §4.7.1 프롬프트 구현
- [ ] 항목별 진행바 UI (점수 색상 조건 포함)
- [ ] "예상 점수이며 실제 심사 결과와 다를 수 있습니다" 면책 문구 표시 (필수)

**Day 36 DoD**: 초안 입력 → 점수 시뮬레이션 → 항목별 개선 제안 표시

### Day 37~40: HistoryPage + 동시수행 추적
- [ ] `HistoryPage.jsx` PRD-06 §Page 7 코드 구현
- [ ] `addHistoryRecord()`, `updateHistoryRecord()` 액션 구현
- [ ] `checkConcurrentLimit()` 로직 구현
- [ ] 공고 상세 진입 시 동시수행 경고 배너 표시
- [ ] 상태 전환 버튼 (작성 중 → 제출 완료 → 선정/미선정)

**Day 40 DoD**: 이력 2건 "수행 중" 상태로 저장 후 공고 상세 접근 → 경고 배너 확인

### Day 41~42: 알림 시스템
- [ ] `checkDeadlineAlerts()` PRD-04 §F-10 코드 구현
- [ ] `NotificationPage.jsx` 업데이트 (읽음/안읽음, 전체 읽음)
- [ ] TopNav 알림 뱃지 업데이트 (읽지 않은 수)
- [ ] 앱 시작 시 D-7, D-3, D-1 알림 자동 체크

**Day 42 DoD (Phase 3 완료)**:
- 전체 사용자 여정 (공고 검색 → 초안 → 시뮬레이션 → 이력 저장) 완주 가능

---

## Phase 4 (Day 43~56): 품질 완성 + 배포

### Day 43~46: 성능 최적화
- [ ] Lighthouse LCP < 3초 달성 (코드 스플리팅, 이미지 최적화)
- [ ] 공고 목록 로딩 < 5초 달성 (캐시 확인, 병렬 API 최적화)
- [ ] AI 적합도 계산 < 2초 (1,000건 기준 벤치마크)
- [ ] `sessionStorage` 캐시 TTL 1시간 검증

### Day 47~49: 테스트 완성
- [ ] 단위 테스트 커버리지 80%+ 달성 (PRD-10 §2)
- [ ] 통합 테스트 체크리스트 전체 통과 (PRD-10 §3)
- [ ] 에러 시나리오 3가지 수동 확인 (PRD-02 §4)

### Day 50~52: 접근성 + 한국어 에러 메시지
- [ ] `aria-label` 전체 점검 (PRD-08 §4)
- [ ] 에러 메시지 한국어 상수 모두 적용 (PRD-08 §3)
- [ ] Lighthouse 접근성 점수 90+ 달성

### Day 53~56: Docker 배포
- [ ] `Dockerfile` (프론트엔드) 작성
- [ ] `Dockerfile` (백엔드) 작성
- [ ] `docker-compose.yml` (PRD-05 §9) 작성
- [ ] Nginx 리버스 프록시 설정
- [ ] `docker-compose up` → 전체 앱 정상 동작 확인
- [ ] README.md 업데이트 (설치·실행 가이드)

**Day 56 DoD (v1.0 완료)**:
- `docker-compose up` 실행 후 전체 기능 동작
- Lighthouse Performance 70+, Accessibility 90+
- 단위 테스트 커버리지 80%+

---

## 이미 구현된 기능 목록 (Day 1 기준 기존 코드)

```
✅ 공고 수집 API (4개 소스) — fetchAllNotices() 기본 구조
✅ 공고 정규화 기본 — normalizeNotice() 기본 구조
✅ Jaccard 유사도 기본 — similarityScore()
✅ 필터링·정렬·페이지네이션 기본
✅ 카드/리스트/일정 뷰
✅ 공고 상세 기본 — DetailPage 기본 구조
✅ 빠른 초안 (QuickDraft/DraftPage)
✅ AI 대화형 초안 (ChatDraftPage) 기본 구조
✅ 기업 설정 (SettingsPage)
✅ 알림 페이지 기본 (NotificationPage)
```

**Phase 1 Day 1~3의 우선 작업**: 기존 코드를 PRD 명세에 맞게 리팩터링
