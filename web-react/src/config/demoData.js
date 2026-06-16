// src/config/demoData.js
export const DEMO_NOTICES = [
  {
    id: 'demo-1',
    title: '2026년 제조AI특화 스마트공장 구축지원사업',
    target: '국내 중소·중견 제조기업 (아진산업 적합)',
    benefit: 'AI 솔루션 및 연동 설비 구축 비용 최대 5억원 지원',
    content: '제조 데이터 기반 AI 다크팩토리 구축을 지원합니다...',
    date: new Date(Date.now() + 3 * 86400000), // D-3
    region: '전국',
    origin: '중소벤처기업부',
    ajin_similarity: 0.95
  },
  {
    id: 'demo-2',
    title: '미래차 전환 핵심부품 R&D 지원사업',
    target: '내연기관 자동차 부품 제조기업',
    benefit: '미래차 부품 설계 및 시제품 제작 최대 3억원',
    content: '탄소섬유강화플라스틱(CFRP) 등 경량화 소재 부품 개발...',
    date: new Date(Date.now() + 15 * 86400000), // D-15
    region: '경북',
    origin: '산업통상자원부',
    ajin_similarity: 0.88
  },
  {
    id: 'demo-3',
    title: '소재·부품·장비 으뜸기업 육성사업',
    target: '핵심전략기술 보유 소부장 기업',
    benefit: 'R&D, 사업화 패키지 최대 20억원 한도',
    content: '글로벌 공급망 재편에 대응하기 위한 소부장 자립화 지원...',
    date: new Date(Date.now() + 5 * 86400000), // D-5
    region: '전국',
    origin: '한국산업기술진흥원',
    ajin_similarity: 0.92
  }
];

export const DEMO_DRAFTS = [
  {
    notice: DEMO_NOTICES[0],
    currentStep: 4, // 전략 검토 단계 (80% 진행률)
    completedSteps: [1, 2, 3],
    drafts: {
      overview: '아진산업(주)는 40년 업력의 자동차 차체 부품 전문기업으로, 핫스탬핑 및 다중소재 접합 기술을 보유하고 있습니다.',
      purpose: '차체 부품 용접 공정의 AI 비전 검사 시스템을 구축하여 불량률을 0%대로 최소화하고자 합니다.',
      plan: '1단계: 데이터 수집 센서 부착\n2단계: AI 불량 판정 모델 학습\n3단계: MES 시스템 연동'
    },
    updatedAt: new Date().toISOString()
  }
];