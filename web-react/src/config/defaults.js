export const DEFAULT_AJIN_PROFILE = `
아진산업은 자동차/모빌리티 부품 제조 기업으로,
프레스·금형·생산자동화·스마트공장·품질고도화·에너지효율·탄소저감·공정혁신,
공급망 안정화, 수출경쟁력 강화, 제조DX, 설비투자, 기술개발(R&D), 인력양성 관련
정부지원사업에 관심이 높다.
`

// ✅ 기존 내용 유지 + 아래 추가
export const DEFAULT_PROFILE_DATA = {
  // 기본 정보
  companyName: '아진산업(주)',
  representative: '',
  bizNumber: '',
  foundedDate: '',
  region: '경남',
  address: '',
  // 매칭 필수
  industry: '제조업',
  subIndustry: '자동차 부품',
  employees: '1200',
  revenueRange: '1천억~5천억',
  certifications: [],
  matchKeywords: '자동차, 스마트공장, DX, 프레스, 에너지',
  excludeKeywords: '',
  // 기존 호환
  sales: '약 5,000억 원',
  emp_count: '1,200명',
  field: '자동차 부품, DX',
  summary: '자동차 차체 부품 및 스마트 팩토리 선도',
  strategy: '미래 모빌리티 전환',
  // 사업계획서 품질
  achievements: '',
  coreTech: '',
  coreTeam: '',
}

export const KEYWORD_GROUPS = {
  아진특화: ['자동차', '부품', '제조', '프레스', '에너지', '혁신'],
  금융: ['자금', '대출', '보증', '투자', '융자'],
  기술: ['R&D', '기술개발', '인증', '특허', '기술이전'],
  인력: ['채용', '교육', '일자리', '고용지원'],
  수출내수: ['해외진출', '수출', '마케팅', '판로'],
  창업경영: ['스타트업', '컨설팅', '법률', '세제'],
}

export const REGION_OPTIONS = [
  '전국', '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
  '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
]

export const SIZE_OPTIONS = ['중견', '중소', '창업', '대기업', '소상공인']