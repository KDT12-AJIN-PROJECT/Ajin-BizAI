export const env = {
  apiKey: import.meta.env.VITE_API_KEY ?? '',
  bizKey: import.meta.env.VITE_BIZ_KEY ?? '',
  // Vite 개발 프록시 경유 — CORS 우회
  bizInfoUrl:
    import.meta.env.VITE_BIZINFO_API_URL ??
    '/proxy/bizinfo/uss/rss/bizinfoApi.do',
  msitUrl:
    import.meta.env.VITE_MSIT_API_URL ??
    '/proxy/apis/1721000/msitannouncementinfo/businessAnnouncMentList',
  mssUrl:
    import.meta.env.VITE_MSS_API_URL ??
    '/proxy/apis/1421000/mssBizService_v2/getbizList_v2',
  kstartupUrl:
    import.meta.env.VITE_KSTARTUP_API_URL ??
    '/proxy/apis/B552735/kisedKstartupService01/getBusinessInformation01',
  noticeSearchNm: import.meta.env.VITE_NOTICE_SEARCH_NM ?? '자동차',
  useMockWhenFailed: (import.meta.env.VITE_USE_MOCK_WHEN_FAILED ?? 'true').toLowerCase() !== 'false',
  // LM Studio 로컬 LLM (기본 포트 1234)
  lmStudioUrl:   import.meta.env.VITE_LM_STUDIO_URL   ?? '/proxy/lmstudio',
  lmStudioToken: import.meta.env.VITE_LM_STUDIO_TOKEN ?? '',
  // 외부 LLM API 키 (있으면 LM Studio 대신 사용)
  openaiApiKey:    import.meta.env.VITE_OPENAI_API_KEY    ?? '',
  anthropicApiKey: import.meta.env.VITE_ANTHROPIC_API_KEY ?? '',
  // DEMO_NOTICES 표시 여부 (기본 false — 로딩 중/API 실패 시 샘플카드 숨김)
  enableDemoNotices: (import.meta.env.VITE_ENABLE_DEMO_NOTICES ?? 'false').toLowerCase() === 'true',
  // v3.2 C-5c (Q1 정책): DRAFT_MOCK / FORM_MOCK fallback 활성화 토글
  //   default false (production-safe). .env.development에도 기본 true 추가 금지.
  //   품질 테스트에서 mock이 섞이면 안 됨.
  useMock: (import.meta.env.VITE_USE_MOCK ?? 'false').toLowerCase() === 'true',
}

// v3.2 C-5c (Q1 정책): 단일 entry point — 모든 mock 분기는 이 상수 참조
// import { env } from '@/config/env' 후 env.useMock 사용 또는
// 아래 alias 직접 import
export const USE_MOCK = env.useMock
