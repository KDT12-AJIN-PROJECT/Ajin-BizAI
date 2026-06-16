// AJIN BizAI v0.2 — Step 2 개발자 모드 (Tab 3~7)
// 출처: PRD §7 / §19.3 / mockup_final.html (1257~2026)
// 노출 조건: VITE_ENABLE_ANALYSIS_DEV_MODE=true (PRD §17.2)

import { useState } from 'react'
import Step2SummaryPanel from './components/Step2SummaryPanel'
import StepNavigationBar from './components/StepNavigationBar'

// ─── Mock Data ────────────────────────────────────────
const VALIDATION_MOCK = {
  summary: {
    원본_문항수: { value: 18, meta: 'PDF 직접 카운트' },
    추출_문항수: { value: 16, meta: 'FormSchema', warning: true },
    검증_상태: { value: '검토 필요', meta: '2개 항목 누락 의심', badge: 'warning' },
    분석_모델: { value: 'ANTHROPIC_MODEL_SONNET', meta: 'form_parser_v001 · 12.4s', mono: true },
  },
  rows: [
    { type: 'error', title: '누락 의심 — II-3. 사업화 전략', desc: '원본 p.7에 "II-3. 사업화 전략" 헤더가 존재하나 FormSchema에 추출되지 않음. 인접한 III-2와 혼동 가능성.', source: 'p.7 · L142' },
    { type: 'error', title: '누락 의심 — IV-2. 예산 산출 근거', desc: '원본 p.9에 작성칸이 있으나 추출 결과에서 첨부 안내문으로 분류됨. 재분류 필요.', source: 'p.9 · L201' },
    { type: 'warn', title: '표 내부 문항 누락 가능 — p.6 추진 일정표', desc: '표 셀 일부가 병합 셀로 인식되어 작성칸 후보가 4개 → 3개로 축소됨.', source: 'p.6 · table#3' },
    { type: 'warn', title: '가이드라인 오분류 가능', desc: 'p.4 "작성 시 유의사항" 문구가 writable_question으로 분류됨. writing_guideline 또는 warning으로 재분류 필요.', source: 'p.4 · L98' },
    { type: 'ok', title: '대제목·중제목·소제목 일치 — 5개 섹션 모두 정상', desc: 'I~V 섹션 헤더 및 하위 번호 체계가 원본과 일치함.', source: 'all sections' },
    { type: 'ok', title: '글자수 / 분량 제한 추출 — 14/14 정상', desc: '모든 문항의 max_length 또는 page_limit이 정상 추출됨.', source: 'constraints' },
  ],
}

const EVIDENCE_MOCK = {
  stats: { 파일수: 7, 총페이지: 284, Chunk: '1,432', Evidence: 218, 매칭됨: 163, 미사용: 55 },
  files: [
    { type: 'PDF', name: '회사소개서_2026.pdf', pages: 42, chunks: 218, evidence: 38, matched: 32, status: 'ok' },
    { type: 'XLS', name: '프로젝트실적_2023-2025.xlsx', pages: 8, chunks: 94, evidence: 27, matched: 24, status: 'ok' },
    { type: 'PDF', name: '기술백서_제조AI플랫폼.pdf', pages: 68, chunks: 312, evidence: 46, matched: 31, status: 'ok' },
    { type: 'PDF', name: '이전사업계획서_2024.pdf', pages: 52, chunks: 256, evidence: 41, matched: 28, status: 'ok' },
    { type: 'PDF', name: '인증서_특허_모음.pdf', pages: 24, chunks: 98, evidence: 31, matched: 27, status: 'ok' },
    { type: 'DOC', name: '시장조사_초안.docx', pages: 14, chunks: 62, evidence: 19, matched: 11, status: 'warn' },
    { type: 'PDF', name: '재무제표_2024.pdf', pages: 76, chunks: 392, evidence: 16, matched: 10, status: 'ok' },
  ],
  preview: {
    fileName: '회사소개서_2026.pdf',
    total: 38,
    showing: 4,
    items: [
      { type: '보유 기술', conf: 0.92, qids: 'II-1, III-1', text: '자체 개발한 공정 데이터 분석 플랫폼 PMS-AI는 2024년부터 4개 제조 라인에 적용되어 불량률을 평균 23% 감소시킴.', source: '회사소개서_2026.pdf · p.4 · §3.2' },
      { type: '정량 실적', conf: 0.88, qids: 'I-3, V-1', text: '2025년 기준 누적 매출 142억 원, 영업이익률 11.4%, 직전 3년 매출 CAGR 18.6% 달성.', source: '회사소개서_2026.pdf · p.7 · §5' },
      { type: '수행 역량', conf: 0.84, qids: 'I-3, III-2', text: '중기부 R&D 사업 2건(2022, 2024) 성공적 완료, 산업부 스마트공장 보급사업 1건 수행 이력 보유.', source: '회사소개서_2026.pdf · p.12 · §7.1' },
    ],
  },
}

const COMPANY_MOCK = {
  capabilities: [
    { title: '제조 데이터 분석 역량', conf: 0.86, desc: '공정 데이터 기반 불량 원인 분석 및 예측 모델 구축 경험 4건 보유.', source: '회사소개서.pdf p.4 · 프로젝트실적.xlsx Sheet1' },
    { title: '정부지원사업 수행 경험', conf: 0.78, desc: '중기부 R&D 2건, 산업부 스마트공장 1건 성공 종료. 평가지표 100% 달성.', source: '회사소개서.pdf p.12' },
    { title: '제조업 도메인 전문성', conf: 0.82, desc: '자동차 부품·전자 조립 도메인 5년 이상 컨설팅 및 시스템 구축 실적.', source: '프로젝트실적.xlsx Sheet1 row 7-14' },
  ],
  gaps: [
    { title: '시장 규모·고객 수요 외부 근거', desc: '시장 규모 자료, 고객 인터뷰, 경쟁사 비교자료 부재. **II-1, III-2** 작성 시 사업성 평가에서 감점 위험.', recommend: '권장: 시장조사 보고서 · 고객사 LOI · 경쟁사 비교표' },
    { title: '정량적 ROI 산출 근거', desc: '예산 대비 기대효과를 정량화할 외부 벤치마크 부족. **IV-2, V-1**에 영향.', recommend: '권장: 산업 평균 KPI 지표 · 동종 사례 ROI 자료' },
  ],
  fit_analysis: [
    { name: '기술성', weight: 40, level: '높음', percent: 78, levelColor: 'success', desc: '**AI 기반 제조 데이터 분석 경험**이 공고의 디지털 전환 지원 목적과 직접 연결됨. PMS-AI 플랫폼 실 적용 사례 4건 보유.', evidence: '근거: 기술백서.pdf p.8 · 회사소개서.pdf p.4' },
    { name: '수행역량', weight: 30, level: '중간', percent: 52, levelColor: 'warning', desc: '**유사 프로젝트 경험은 있으나** 정부지원사업 성과보고서 형식의 정량 실적 근거가 부족함. 4대보험가입자명부와 직전 2개년 재무제표는 확보됨.', evidence: '근거: 프로젝트실적.xlsx · 재무제표.pdf' },
    { name: '사업성', weight: 30, level: '낮음', percent: 28, levelColor: 'error', desc: '**시장 규모와 고객 수요를 입증하는 외부 자료 부족**. 사업화 전략의 정량적 ROI 근거 약함. 평가에서 가장 취약한 축이며 추가 자료 업로드 권장.', evidence: '권장: 시장조사 보고서 · LOI · 경쟁사 비교' },
  ],
}

const EVAL_REVIEW_MOCK = [
  { name: '기술성', weight: 40, scope: 'question', mtype: 'direct', qids: ['III-1', 'III-T1'], conf: 0.88, confLevel: 'high', reason: '기술 개발 계획과 추진 일정표에 직접 반영. 평가위원이 기술 차별성·완성도를 정량 지표 중심으로 검토함.' },
  { name: '사업성', weight: 30, scope: 'section', mtype: 'indirect', qids: ['II-1', 'III-2', 'V-1'], conf: 0.78, confLevel: 'mid', reason: '시장 인식·사업화·정량 효과 3측면에서 종합 평가. 단일 문항보다 섹션 단위 일관성이 중요.' },
  { name: '수행역량', weight: 30, scope: 'document', mtype: 'context', qids: ['I-3', 'IV-2'], conf: 0.62, confLevel: 'low', reason: '전체 사업계획서의 실행 가능성·조직 역량·과거 실적 일관성을 종합적으로 검토.', warnings: ['신뢰도 낮음 (0.70 미만) — 매핑 재검토 권장', 'document scope — 전체 문서 일관성 평가, 단일 문항 매핑은 참고용'] },
]

const MAPPING_MOCK = [
  {
    qid: 'II-1', name: '시장 문제', status: 'weak',
    matched: [
      { text: '국내 제조업 디지털 전환 시장 성장률 18.4%/y', source: '시장조사_초안.docx p.3' },
      { text: '자체 개발 PMS-AI 공정 적용 4건 (2024-2025)', source: '회사소개서.pdf p.4' },
      { text: '제조업 평균 불량률 2.4% · 국내 통계청 자료', source: '시장조사_초안.docx p.5' },
    ],
    missing: ['고객 수요 설문·인터뷰 1차 자료', '경쟁사 대비 기술 차별성 비교표', '최근 2년 시장 규모 정량 데이터 (KOSIS·산업연구원)'],
  },
  {
    qid: 'II-2', name: '지원 필요성', status: 'missing',
    matched: [],
    missing: ['자체 자금 조달 시도 이력 / 거절 사유', '정부 지원 없이는 진행 불가능한 정량 근거'],
    blocked: true,
  },
  {
    qid: 'III-2', name: '사업화 전략', status: 'weak',
    matched: [
      { text: '고객사 A사 양산라인 도입 검토 (2025-Q4)', source: '프로젝트실적.xlsx Sheet1' },
      { text: '신규 SaaS 모델 가격 정책 초안', source: '기술백서.pdf p.42' },
    ],
    missing: ['파트너사 LOI / MOU', '3년차 매출 목표 산출 근거'],
  },
  {
    qid: 'IV-2', name: '예산 산출 근거', status: 'weak',
    matched: [
      { text: '인건비 표준 단가 (직급별)', source: '이전사업계획서_2024.pdf p.28' },
      { text: '장비 견적서 (NVIDIA RTX 6000 외)', source: '이전사업계획서_2024.pdf p.31' },
    ],
    missing: ['2026년 기준 시장 단가 견적서 (3개 업체 이상)'],
  },
]

const SETTINGS_MOCK = {
  models: [
    { label: '공고문 분석', value: 'OPENAI_MODEL_ANALYSIS / ANTHROPIC_MODEL_SONNET' },
    { label: '제출양식 분석', value: 'OPENAI_MODEL_ANALYSIS / ANTHROPIC_MODEL_SONNET' },
    { label: '참고자료 분석', value: 'ANTHROPIC_MODEL_HAIKU / OPENAI_MODEL_ANALYSIS' },
    { label: '기업정보 분석', value: 'OPENAI_MODEL_ANALYSIS / ANTHROPIC_MODEL_SONNET' },
    { label: '매칭', value: 'ANTHROPIC_MODEL_HAIKU / OPENAI_MODEL_ANALYSIS' },
    { label: '초안 작성 (default)', value: 'ANTHROPIC_MODEL_SONNET / OPENAI_MODEL_DRAFT' },
  ],
  premium: { label: '최종 고품질 작성', tag: 'premium_final_writer', value: 'ANTHROPIC_MODEL_OPUS' },
  prompts: {
    'Prompt set': 'v0.2.1-stable',
    'notice_analyst': 'notice_analyst_v001',
    'form_parser': 'form_parser_v001',
    'evidence_extractor': 'evidence_extractor_v001',
    'evidence_mapper': 'evidence_mapper_v001',
    'draft_writer': 'draft_writer_v001',
  },
  chunk: {
    'Chunk size': '1,200 tokens',
    'Chunk overlap': '200 tokens',
    'RAG top_k': '8',
    'Matching threshold': '0.70',
    'Embedding': 'bge-m3-ko · local',
    'Vector store': 'SQLite cache (session)',
  },
  evidence: {
    'Evidence strictness': 'strict (no fabrication)',
    'Max evidence / question': '5',
    'Length validation': 'on · 1 retry',
    'Auto compress': 'on (max_length 초과 시)',
    'Max rewrite attempts': '2',
  },
  reanalyze_targets: ['notice', 'form', 'evidence', 'company', 'mapping', 'missing', 'all'],
}

// ─── Helpers ──────────────────────────────────────────
function renderBold(text) {
  return text.split(/(\*\*[^*]+\*\*)/).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
    }
    return <span key={i}>{part}</span>
  })
}

const STATUS_BADGE = {
  ok: { label: '작성 가능', cls: 'bg-emerald-50 text-emerald-700' },
  weak: { label: '근거 부족', cls: 'bg-amber-50 text-amber-700' },
  missing: { label: '자료 없음', cls: 'bg-red-50 text-red-700' },
}

// ─── Tab 3: VALIDATION ────────────────────────────────
function Tab3Validation() {
  const v = VALIDATION_MOCK
  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        {Object.entries(v.summary).map(([k, val]) => (
          <div key={k} className="bg-white border border-slate-200 rounded p-3">
            <div className="text-xs text-slate-500 mb-1">{k.replace(/_/g, ' ')}</div>
            <div className={`text-lg font-semibold ${val.warning ? 'text-amber-600' : 'text-slate-900'} ${val.mono ? 'font-mono text-xs' : ''}`}>
              {val.badge ? (
                <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded">{val.value}</span>
              ) : (
                val.value
              )}
            </div>
            <div className="text-[10px] text-slate-400 mt-1">{val.meta}</div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <span className="font-semibold text-slate-900">검증 결과 상세</span>
          <div className="flex gap-1.5">
            <button className="text-xs px-2.5 py-1 border border-slate-200 rounded hover:bg-slate-50">수동 수정</button>
            <button className="text-xs px-2.5 py-1 bg-slate-100 rounded hover:bg-slate-200">제출양식 다시 분석</button>
          </div>
        </div>
        <div className="divide-y divide-slate-100">
          {v.rows.map((r, i) => (
            <div key={i} className="px-4 py-3 flex gap-3">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 ${
                r.type === 'error' ? 'bg-red-100 text-red-700' :
                r.type === 'warn' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
              }`}>
                {r.type === 'error' ? '!' : r.type === 'warn' ? '⚠' : '✓'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-900">{r.title}</div>
                <div className="text-xs text-slate-600 mt-1 leading-relaxed">{r.desc}</div>
              </div>
              <div className="text-[11px] font-mono text-slate-400 shrink-0">{r.source}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Tab 4: EVIDENCE ──────────────────────────────────
// ─── adapter: evidenceData + mappingResult + uploads → Tab4 display shape ───
function adaptEvidence(evidenceData, mappingResult, uploads) {
  if (!evidenceData) return null
  const items = evidenceData.items || []

  // 1. matched evidence_ids 수집
  const matchedSet = new Set()
  for (const qm of (mappingResult?.question_mappings || [])) {
    for (const eid of (qm.used_evidence_ids || qm.matched_evidence_ids || [])) {
      matchedSet.add(eid)
    }
  }

  // 2. 파일별 그룹화
  const fileMap = {}
  for (const it of items) {
    const src = it.source_file || '(미지정)'
    if (!fileMap[src]) {
      const ext = (src.split('.').pop() || '').toUpperCase().slice(0, 4) || 'FILE'
      fileMap[src] = { name: src, type: ext, pages: new Set(), items: [], matchedCount: 0 }
    }
    fileMap[src].items.push(it)
    if (it.source_page) fileMap[src].pages.add(it.source_page)
    if (matchedSet.has(it.evidence_id)) fileMap[src].matchedCount++
  }

  const files = Object.values(fileMap).map(f => ({
    type: f.type,
    name: f.name,
    pages: f.pages.size || '—',
    chunks: '—',  // chunk 카운트는 backend 미지원
    evidence: f.items.length,
    matched: f.matchedCount,
    status: (f.matchedCount === 0 && f.items.length > 0) ? 'warn' : 'ok',
  }))

  // 3. stats
  const totalPagesNum = files.reduce((s, f) => s + (typeof f.pages === 'number' ? f.pages : 0), 0)
  const stats = {
    '파일수': files.length || (uploads?.length ?? 0),
    '총페이지': totalPagesNum || '—',
    'Chunk': '—',
    'Evidence': items.length,
    '매칭됨': matchedSet.size,
    '미사용': Math.max(0, items.length - matchedSet.size),
  }

  // 4. preview: 첫 파일의 최대 4개
  const firstFile = files[0]
  const firstFileItems = firstFile ? fileMap[firstFile.name].items : []
  const previewItems = firstFileItems.slice(0, 4).map(it => {
    const confidences = Object.values(it.confidence_per_question || {})
    const avgConf = confidences.length
      ? (confidences.reduce((a, b) => a + b, 0) / confidences.length).toFixed(2)
      : '—'
    return {
      type: it.type || '기타',
      conf: avgConf,
      qids: (it.matched_questions || []).join(', ') || '—',
      text: it.content || it.raw_text || '(내용 없음)',
      source: [it.source_file, it.source_page ? `p.${it.source_page}` : null, it.source_block]
        .filter(Boolean).join(' · ') || '—',
    }
  })

  const preview = firstFile
    ? { fileName: firstFile.name, total: firstFileItems.length, showing: previewItems.length, items: previewItems }
    : { fileName: '—', total: 0, showing: 0, items: [] }

  return { stats, files, preview }
}

function Tab4Evidence({ evidenceData, mappingResult, uploads }) {
  const adapted = adaptEvidence(evidenceData, mappingResult, uploads?.references)
  const e = adapted || EVIDENCE_MOCK
  const usingMock = !adapted
  return (
    <div>
      <SampleDataBadge visible={usingMock} />
      <div className="grid grid-cols-3 lg:grid-cols-6 gap-2 mb-4">
        {Object.entries(e.stats).map(([k, v]) => (
          <div key={k} className="bg-white border border-slate-200 rounded p-2.5 text-center">
            <div className="text-[10px] text-slate-500 mb-0.5">{k}</div>
            <div className={`text-lg font-semibold ${k === '매칭됨' ? 'text-emerald-700' : k === '미사용' ? 'text-slate-400' : 'text-slate-900'}`}>{v}</div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded mb-4">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <span className="font-semibold text-slate-900">파일별 Evidence 분석</span>
          <div className="flex gap-1.5">
            <button className="text-xs px-2.5 py-1 border border-slate-200 rounded hover:bg-slate-50">매칭만 다시 실행</button>
            <button className="text-xs px-2.5 py-1 bg-slate-100 rounded hover:bg-slate-200">전체 다시 분석</button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-2 text-left font-medium">파일명</th>
                <th className="px-3 py-2 text-right font-medium">페이지</th>
                <th className="px-3 py-2 text-right font-medium">Chunk</th>
                <th className="px-3 py-2 text-right font-medium">Evidence</th>
                <th className="px-3 py-2 text-right font-medium">매칭</th>
                <th className="px-3 py-2 text-left font-medium">상태</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {e.files.map((f, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-900">{f.type}</span>
                      <span className="text-slate-900">{f.name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right text-slate-600 font-mono">{f.pages}</td>
                  <td className="px-3 py-2.5 text-right text-slate-600 font-mono">{f.chunks}</td>
                  <td className="px-3 py-2.5 text-right text-slate-600 font-mono">{f.evidence}</td>
                  <td className={`px-3 py-2.5 text-right font-mono font-semibold ${f.status === 'warn' ? 'text-amber-600' : 'text-emerald-700'}`}>{f.matched}</td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${f.status === 'warn' ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>
                      {f.status === 'warn' ? '검토 필요' : '정상'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t border-slate-200 p-4 bg-slate-50/50">
          <div className="text-sm font-medium text-slate-700 mb-2">
            ▼ {e.preview.fileName} · Evidence 미리보기 ({e.preview.showing} / {e.preview.total})
          </div>
          <div className="space-y-2">
            {e.preview.items.map((item, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded p-2.5 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-900 rounded font-medium">{item.type}</span>
                  <span className="text-[10px] font-mono text-slate-500">관련도 {item.conf} · {item.qids}</span>
                </div>
                <div className="text-slate-700 leading-relaxed">{item.text}</div>
                <div className="text-[10px] font-mono text-slate-400 mt-1">↗ {item.source}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── adapter: companyData(api) → Tab5 display shape ───
// Backend: { company: { capabilities:[{name,confidence,description,source}] },
//           fit_analysis: { axes:[{name,weight,score,level,level_color,description,evidence,recommendation}], overall_score } }
// Display: { capabilities:[{title,conf,desc,source}], gaps:[{title,desc,recommend}], fit_analysis:[{name,weight,level,percent,levelColor,desc,evidence}] }
function adaptCompany(companyData) {
  if (!companyData) return null
  const capabilities = (companyData.company?.capabilities || []).map(c => ({
    title: c.name || '(이름 없음)',
    conf: typeof c.confidence === 'number' ? c.confidence : null,
    desc: c.description || '',
    source: c.source || '',
  }))
  const axes = companyData.fit_analysis?.axes || []
  // gaps: 우수(success)가 아닌 축의 recommendation
  const gaps = axes
    .filter(a => a.level_color !== 'success')
    .map(a => ({
      title: `${a.name}${a.level ? ` — ${a.level}` : ''}`,
      desc: a.description || '',
      recommend: a.recommendation ? `권장: ${a.recommendation}` : '',
    }))
  const fit_analysis = axes.map(a => ({
    name: a.name || '',
    weight: a.weight ?? 0,
    level: a.level || '',
    percent: a.score ?? 0,
    levelColor: a.level_color || 'warning',
    desc: a.description || '',
    evidence: Array.isArray(a.evidence) ? a.evidence.join(' · ') : (a.evidence || ''),
  }))
  return { capabilities, gaps, fit_analysis }
}

// ─── Tab 5: COMPANY FIT ───────────────────────────────
function Tab5CompanyFit({ companyData }) {
  const adapted = adaptCompany(companyData)
  const c = adapted || COMPANY_MOCK
  const usingMock = !adapted
  return (
    <div>
      <SampleDataBadge visible={usingMock} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-4">
        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="font-semibold text-slate-900">기업 역량</span>
            <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">{c.capabilities.length}</span>
          </div>
          <div className="divide-y divide-slate-100">
            {c.capabilities.map((cap, i) => (
              <div key={i} className="px-4 py-3">
                <div className="text-sm font-medium text-slate-900 mb-1 flex items-center gap-2">
                  {cap.title}
                  <span className="text-[10px] font-mono px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded">신뢰도 {cap.conf}</span>
                </div>
                <div className="text-xs text-slate-600 mb-1">{cap.desc}</div>
                <div className="text-[10px] font-mono text-slate-400">↗ {cap.source}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <div>
              <span className="font-semibold text-slate-900">보완 필요 항목</span>
              <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">{c.gaps.length}</span>
            </div>
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded font-medium">근거 부족</span>
          </div>
          <div className="divide-y divide-slate-100">
            {c.gaps.map((g, i) => (
              <div key={i} className="px-4 py-3">
                <div className="text-sm font-medium text-slate-900 mb-1">{g.title}</div>
                <div className="text-xs text-slate-600 mb-1">{renderBold(g.desc)}</div>
                <div className="text-[10px] text-slate-500">{g.recommend}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <span className="font-semibold text-slate-900">공고 적합성 (FitAnalysis)</span>
          <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded font-medium">평가기준 3축 분석</span>
        </div>
        <div className="p-4 space-y-4">
          {c.fit_analysis.map((axis, i) => {
            const colorMap = { success: 'emerald', warning: 'amber', error: 'red' }
            const color = colorMap[axis.levelColor]
            return (
              <div key={i}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="text-sm">
                    <span className="font-medium text-slate-900">{axis.name}</span>
                    <span className="ml-2 text-[11px] font-mono text-slate-400">{axis.weight}점</span>
                  </div>
                  <div className={`text-sm font-semibold text-${color}-700`}>{axis.level} · {axis.percent}%</div>
                </div>
                <div className="h-2 bg-slate-100 rounded overflow-hidden mb-2">
                  <div className={`h-full bg-${color}-500`} style={{ width: `${axis.percent}%` }} />
                </div>
                <div className="text-xs text-slate-700 leading-relaxed">
                  {renderBold(axis.desc)}
                  <span className="ml-2 text-[10px] font-mono text-slate-400">{axis.evidence}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ─── adapter: mappingResult + missingMaterials + evidenceData + formApiResp → Tab6 하단(문항별 매칭) display shape ───
function adaptMapping(mappingResult, missingMaterials, evidenceData, formApiResp) {
  if (!mappingResult || !formApiResp) return null

  // evidence_id → evidence 객체 인덱스
  const evidenceById = {}
  for (const e of (evidenceData?.items || [])) {
    const eid = e.evidence_id || e.id
    if (eid) evidenceById[eid] = e
  }

  // question_id → [missing] 인덱스
  const missingByQid = {}
  for (const m of (missingMaterials || [])) {
    if (!m.question_id) continue
    if (!missingByQid[m.question_id]) missingByQid[m.question_id] = []
    missingByQid[m.question_id].push(m)
  }

  // question_id → mapping 인덱스
  const mappingByQid = {}
  for (const qm of (mappingResult.question_mappings || [])) {
    if (qm.question_id) mappingByQid[qm.question_id] = qm
  }

  const result = []
  for (const sec of (formApiResp.sections || [])) {
    for (const q of (sec.questions || [])) {
      const qid = q.question_id || q.id
      if (!qid) continue
      const name = q.title || q.text || q.label || qid
      const mapping = mappingByQid[qid]
      const missing = missingByQid[qid] || []

      const usedIds = mapping?.used_evidence_ids || mapping?.matched_evidence_ids || []
      const matched = usedIds.map(eid => {
        const ev = evidenceById[eid]
        if (!ev) return { text: `[evidence_id ${eid} — 본문 미확인]`, source: '—' }
        const src = [
          ev.source_file,
          ev.source_page ? `p.${ev.source_page}` : null,
        ].filter(Boolean).join(' · ')
        return {
          text: ev.text || ev.summary || ev.content || '(텍스트 없음)',
          source: src || '—',
        }
      })

      let status = 'ok'
      if (missing.length > 0 && matched.length === 0) status = 'missing'
      else if (missing.length > 0 || (mapping?.confidence_score ?? 1) < 0.70) status = 'weak'

      const blocked = matched.length === 0 && missing.length > 0

      result.push({
        qid,
        name,
        status,
        matched,
        missing: missing.map(m => m.name || m.description || '(이름 없음)'),
        blocked,
      })
    }
  }

  return result
}

// ─── adapter: evalCriteriaMapping.mappings[] → Tab6 상단 평가기준 검토 display shape ───
function adaptEvalReview(evalCriteriaMapping) {
  const mappings = evalCriteriaMapping?.mappings
  if (!Array.isArray(mappings) || mappings.length === 0) return null
  return mappings.map(m => {
    const conf = typeof m.confidence === 'number' ? m.confidence : 0
    const confLevel = conf >= 0.80 ? 'high' : conf >= 0.60 ? 'mid' : 'low'
    const warnings = []
    if (conf < 0.70) warnings.push('신뢰도 낮음 (0.70 미만) — 매핑 재검토 권장')
    if (m.scope === 'document') warnings.push('document scope — 전체 문서 일관성 평가, 단일 문항 매핑은 참고용')
    return {
      name: m.criteria_name || '(이름 없음)',
      weight: m.weight ?? 0,
      scope: m.scope || 'section',
      mtype: m.mapping_type || 'direct',
      qids: Array.isArray(m.mapped_questions) ? m.mapped_questions : [],
      conf: Number(conf.toFixed(2)),
      confLevel,
      reason: m.reason || '',
      warnings,
      source_page: m.source_page,
      mapped_by: m.mapped_by || 'ai',
    }
  })
}

// ─── Tab 6: MAPPING ───────────────────────────────────
function Tab6Mapping({ mappingResult, missingMaterials, evidenceData, formApiResp, evalCriteriaMapping }) {
  const [evalOpen, setEvalOpen] = useState(false)
  const adaptedMapping = adaptMapping(mappingResult, missingMaterials, evidenceData, formApiResp)
  const mappingItems = adaptedMapping || MAPPING_MOCK
  const usingMappingMock = !adaptedMapping
  const adaptedEval = adaptEvalReview(evalCriteriaMapping)
  const evalItems = adaptedEval || EVAL_REVIEW_MOCK
  const usingEvalMock = !adaptedEval

  return (
    <div className="space-y-4">
      {/* 평가기준 검토 카드 (접기/펼치기, 기본 접힘 — PRD §19.3 #6) */}
      <div className="border border-slate-200 rounded bg-white">
        <button
          onClick={() => setEvalOpen(!evalOpen)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50"
        >
          <div className="flex items-center gap-2">
            <span>⚖</span>
            <span className="font-semibold text-slate-900">평가기준 ↔ 문항 매핑 검토</span>
            <span className="text-[10px] text-slate-500">{evalItems.length}개 평가기준 · 읽기 전용</span>
            {usingEvalMock && (
              <span className="text-[10px] px-1.5 py-0.5 bg-rose-50 border border-rose-200 text-rose-700 rounded font-medium">샘플</span>
            )}
          </div>
          <span className={`transition ${evalOpen ? 'rotate-180' : ''}`}>▾</span>
        </button>

        {evalOpen && (
          <div className="border-t border-slate-200 p-4 space-y-3">
            <div className="text-xs text-slate-700 bg-blue-50 border border-blue-200 rounded px-3 py-2 leading-relaxed">
              🔒 실제 편집은 <strong>Step 2 Tab1 평가기준 카드</strong>에서 수행합니다.
              이 화면은 개발자용 읽기 전용 상세 검토입니다.
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              {evalItems.map((c) => (
                <div key={c.name} className="border border-slate-200 rounded p-3 text-sm">
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-100">
                    <div>
                      <span className="font-semibold text-slate-900">{c.name}</span>
                      <span className="ml-1.5 text-[11px] font-mono text-slate-400">{c.weight}점</span>
                    </div>
                    <span className="text-[10px] text-slate-500">🔒 읽기 전용</span>
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">scope</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        c.scope === 'question' ? 'bg-indigo-50 text-indigo-900' :
                        c.scope === 'section' ? 'bg-blue-50 text-blue-900' : 'bg-slate-100 text-slate-700'
                      }`}>{c.scope}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">유형</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                        c.mtype === 'direct' ? 'bg-emerald-50 text-emerald-700' :
                        c.mtype === 'indirect' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'
                      }`}>{c.mtype}</span>
                    </div>
                    <div>
                      <div className="text-slate-500 mb-0.5">반영 위치</div>
                      <div className="flex flex-wrap gap-1">
                        {c.qids.map((q) => (
                          <span key={q} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded font-mono">{q}</span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500 mb-0.5">신뢰도</div>
                      <div className="flex items-center gap-1.5">
                        <div className="flex-1 h-1.5 bg-slate-100 rounded overflow-hidden">
                          <div className={`h-full ${
                            c.confLevel === 'high' ? 'bg-emerald-500' :
                            c.confLevel === 'mid' ? 'bg-amber-500' : 'bg-red-500'
                          }`} style={{ width: `${c.conf * 100}%` }} />
                        </div>
                        <span className="text-[10px] font-mono">{c.conf}</span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-slate-600 leading-relaxed">
                    {c.reason}
                  </div>
                  {c.warnings && (
                    <div className="mt-2 space-y-1">
                      {c.warnings.map((w, i) => (
                        <div key={i} className="flex gap-1 text-[10px] text-amber-700 bg-amber-50 rounded px-2 py-1">
                          <span>⚠</span><span>{w}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-2 pt-2 border-t border-slate-100 flex flex-wrap gap-2 text-[10px] text-slate-400">
                    <span>
                      <span className={`px-1 py-0.5 rounded font-mono ${
                        c.mapped_by === 'user' ? 'bg-blue-50 text-blue-900' : 'bg-indigo-50 text-indigo-900'
                      }`}>
                        {c.mapped_by === 'user' ? 'USER' : 'AI'}
                      </span>
                      {' '}{c.mapped_by === 'user' ? '사용자 편집' : 'notice_analyst'}
                    </span>
                    {c.source_page != null && <span>출처: p.{c.source_page}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 문항별 Evidence 매칭 / 부족자료 진단 */}
      <div>
        <SampleDataBadge visible={usingMappingMock} />
      </div>
      <div className="bg-white border border-slate-200 rounded">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <div>
            <span className="font-semibold text-slate-900">문항별 Evidence 매칭 / 부족자료 진단</span>
            <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">{mappingItems.length} 문항</span>
          </div>
          <div className="flex gap-1.5">
            <button className="text-xs px-2.5 py-1 border border-slate-200 rounded hover:bg-slate-50">매칭만 다시 실행</button>
            <button className="text-xs px-2.5 py-1 bg-slate-100 rounded hover:bg-slate-200">부족자료 추가 업로드</button>
          </div>
        </div>
        <div className="divide-y divide-slate-100">
          {mappingItems.map((m) => (
            <div key={m.qid} className="px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">{m.qid}</span>
                  <span className="text-sm font-medium text-slate-900">{m.name}</span>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_BADGE[m.status].cls}`}>
                  {STATUS_BADGE[m.status].label}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1">
                    매칭된 Evidence ({m.matched.length})
                  </div>
                  <div className="space-y-1">
                    {m.matched.length === 0 ? (
                      <div className="text-slate-400 text-center py-3 border border-dashed border-slate-200 rounded">매칭 결과 없음</div>
                    ) : (
                      m.matched.map((ev, i) => (
                        <div key={i} className="flex items-center justify-between gap-2 px-2 py-1.5 border border-slate-100 rounded text-slate-700">
                          <span className="flex-1">{ev.text}</span>
                          <span className="text-[10px] font-mono text-slate-400 shrink-0">{ev.source}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1">
                    부족자료 ({m.missing.length}){m.blocked && <span className="text-red-700 ml-1">· AI 자동 작성 차단됨</span>}
                  </div>
                  <div className="space-y-1">
                    {m.missing.map((mi, i) => (
                      <div key={i} className="px-2 py-1.5 bg-amber-50/50 border border-amber-200 rounded text-amber-900">
                        {mi}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Tab 7: SETTINGS ──────────────────────────────────
function Tab7Settings() {
  const s = SETTINGS_MOCK

  return (
    <div className="space-y-4">
      <div className="flex gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded text-sm text-amber-900">
        <span>!</span>
        <span>모델·프롬프트 선택 UI는 사용자에게 노출되지 않습니다. 운영 환경에서는 환경변수로 차단됩니다.</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* 모델 / Provider */}
        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="font-semibold text-slate-900">모델 / Provider (config slot)</span>
          </div>
          <div className="p-4 space-y-2 text-sm">
            {s.models.map((m, i) => (
              <div key={i} className="flex items-center justify-between gap-3">
                <span className="text-slate-600 shrink-0">{m.label}</span>
                <span className="text-[11px] font-mono px-2 py-1 bg-slate-50 border border-slate-200 rounded text-slate-700 truncate">
                  {m.value} ▾
                </span>
              </div>
            ))}
            <div className="pt-2 mt-2 border-t border-dashed border-slate-200">
              <div className="flex items-center justify-between gap-3 mb-1">
                <span className="text-slate-600 shrink-0">
                  {s.premium.label}
                  <span className="ml-1.5 text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded font-mono">{s.premium.tag}</span>
                </span>
                <span className="text-[11px] font-mono px-2 py-1 bg-slate-50 border border-slate-200 rounded text-slate-700 opacity-85">
                  {s.premium.value} ▾
                </span>
              </div>
            </div>
            <div className="text-[10px] text-slate-400 leading-relaxed pt-2">
              ※ 실제 모델 ID는 Phase 0에서 provider model list + pricing_config 기준으로 검증<br />
              ※ Opus는 기본 draft_writer가 아니라 premium_final_writer 전용
            </div>
          </div>
        </div>

        {/* Prompt Set / Parser */}
        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="font-semibold text-slate-900">Prompt Set / Parser</span>
          </div>
          <div className="p-4 space-y-2 text-sm">
            {Object.entries(s.prompts).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <span className="text-slate-600 shrink-0">{k}</span>
                <span className="text-[11px] font-mono text-slate-700">{v}{k === 'Prompt set' ? ' ▾' : ''}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Chunk / RAG */}
        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="font-semibold text-slate-900">Chunk / RAG</span>
          </div>
          <div className="p-4 space-y-2 text-sm">
            {Object.entries(s.chunk).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <span className="text-slate-600 shrink-0">{k}</span>
                <span className="text-[11px] font-mono text-slate-700">{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Evidence / Length */}
        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="font-semibold text-slate-900">Evidence / Length</span>
          </div>
          <div className="p-4 space-y-2 text-sm">
            {Object.entries(s.evidence).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3">
                <span className="text-slate-600 shrink-0">{k}</span>
                <span className="text-[11px] font-mono text-slate-700">{v}</span>
              </div>
            ))}
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate-600">Raw JSON 보기</span>
              <button className="text-[11px] px-2 py-1 bg-slate-100 rounded hover:bg-slate-200">
                JSON 열기 ↗
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 범위별 다시 분석하기 */}
      <div className="bg-white border border-slate-200 rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="font-semibold text-slate-900">범위별 다시 분석하기</span>
          <span className="text-[11px] font-mono text-slate-400">re-analysis target</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {s.reanalyze_targets.map((t) => (
            <button
              key={t}
              className={`text-xs px-3 py-1.5 rounded border transition ${
                t === 'all'
                  ? 'bg-slate-900 text-white border-slate-900 hover:bg-slate-800'
                  : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Step 2 DevMode wrapper ──────────────────────────
const DEV_TABS = [
  { id: 'validation', num: '03', label: '양식 검증' },
  { id: 'evidence', num: '04', label: '참고자료 분석' },
  { id: 'company', num: '05', label: '기업 분석' },
  { id: 'mapping', num: '06', label: '매핑 검토' },
  { id: 'settings', num: '07', label: '디버깅 도구' },
]

// Tab별 footer 요약 (Dev Mode: 검증 상태 / 모델 슬롯 / API target)
const DEV_FOOTER_BY_TAB = {
  validation: {
    stats: [
      { label: '원본 문항', value: '18' },
      { label: '추출', value: '16' },
      { label: '검증', chips: [{ label: '검토 필요', value: 2 }] },
      { label: '모델', chips: [{ label: 'form_parser_v001' }] },
    ],
    hint: '누락 의심 2건 — 수동 수정 또는 제출양식 다시 분석 권장',
  },
  evidence: {
    stats: [
      { label: '파일', value: '7' },
      { label: 'Evidence', value: '218' },
      { label: '매칭', value: '163' },
      { label: '미사용', value: '55' },
      { label: '모델', chips: [{ label: 'evidence_extractor_v001' }] },
    ],
    hint: '시장조사_초안.docx 매칭률 낮음 — 검토 권장',
  },
  company: {
    stats: [
      { label: '역량', value: '3' },
      { label: '보완 필요', value: '2', highlight: 'red' },
      { label: 'Fit', chips: [{ label: '기술 78%' }, { label: '수행 52%' }, { label: '사업 28%' }] },
      { label: '모델', chips: [{ label: 'company_analyzer_v001' }] },
    ],
    hint: '사업성 28% — 시장 규모·LOI·경쟁사 비교 자료 보강 권장',
  },
  mapping: {
    stats: [
      { label: '평가기준', value: '3' },
      { label: '매핑 문항', value: '18' },
      { label: '근거 부족', value: '4', highlight: 'red' },
      { label: '자료 없음', value: '2', highlight: 'red' },
      { label: '모델', chips: [{ label: 'evidence_mapper_v001' }] },
    ],
    hint: '평가기준 매핑 편집은 Step 2 Tab1 카드에서 수행 — 본 화면은 읽기 전용',
  },
  settings: {
    stats: [
      { label: 'Provider', chips: [{ label: 'OpenAI' }, { label: 'Anthropic' }] },
      { label: 'Prompt set', chips: [{ label: 'v0.2.1-stable' }] },
      { label: 'Threshold', value: '0.70' },
      { label: 'Vector', chips: [{ label: 'sqlite' }] },
      { label: 're-analyze targets', value: '7' },
    ],
    hint: '운영 환경에서는 환경변수로 차단 — 모델·프롬프트 변경 X',
  },
}

// 실데이터 없을 때 mock fallback을 시각적으로 알리는 배지
// 각 Tab 상단에 `<SampleDataBadge visible={!realDataAvailable} />` 형태로 사용
export function SampleDataBadge({ visible }) {
  if (!visible) return null
  return (
    <div className="mb-3 px-3 py-1.5 rounded-md bg-rose-50 border border-rose-200 text-[11px] text-rose-700 font-medium inline-flex items-center gap-1.5">
      <span>⚠</span>
      <span>샘플 데이터 — 분석 완료 후 실데이터로 교체됩니다</span>
    </div>
  )
}

export default function Step2DevMode({
  onPrev, onConfirmStep2, onToggleDevMode,
  sessionId = null,
  step2Data = null,        // {formApiResp, noticeApiResp, mappingResult, missingMaterials, evidenceData, companyData, evalCriteriaMapping, ...}
  uploads = null,          // {noticeFiles, formFiles, references}
  notice = null,
}) {
  const [activeTab, setActiveTab] = useState('validation')

  return (
    <div className="p-6">
      <div className="bg-yellow-100 border-2 border-yellow-400 rounded px-4 py-2 mb-4">
        <span className="text-sm font-semibold text-yellow-900">
          🛠 개발자 모드 (운영 환경에서는 비노출 — PRD §17.2 #5)
        </span>
      </div>

      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Step 2. 분석 (개발자 모드)</h2>
          <p className="text-sm text-slate-500 mt-1">검증 / Evidence / 기업 / 매핑 / 설정 (Tab 3~7)</p>
        </div>
        <button
          onClick={onToggleDevMode}
          className="px-3 py-1.5 text-sm border border-slate-200 rounded hover:bg-slate-50"
        >
          👁 사용자 모드로
        </button>
      </div>

      {/* 탭 */}
      <div className="flex gap-1 border-b border-slate-200 mb-4 overflow-x-auto">
        {DEV_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2.5 text-sm transition border-b-2 -mb-px whitespace-nowrap ${
              activeTab === t.id
                ? 'border-slate-900 text-slate-900 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            <span className="font-mono text-[11px] text-slate-400 mr-2">{t.num}</span>
            {t.label}
          </button>
        ))}
      </div>

      {/* 패널 */}
      {activeTab === 'validation' && <Tab3Validation />}
      {activeTab === 'evidence' && (
        <Tab4Evidence
          evidenceData={step2Data?.evidenceData}
          mappingResult={step2Data?.mappingResult}
          uploads={uploads}
        />
      )}
      {activeTab === 'company' && <Tab5CompanyFit companyData={step2Data?.companyData} />}
      {activeTab === 'mapping' && (
        <Tab6Mapping
          mappingResult={step2Data?.mappingResult}
          missingMaterials={step2Data?.missingMaterials}
          evidenceData={step2Data?.evidenceData}
          formApiResp={step2Data?.formApiResp}
          evalCriteriaMapping={step2Data?.evalCriteriaMapping}
        />
      )}
      {activeTab === 'settings' && <Tab7Settings />}

      {/* Step 2 요약 정보 (Dev Mode Tab별 stats + hint) */}
      <Step2SummaryPanel
        stats={DEV_FOOTER_BY_TAB[activeTab].stats}
        hint={DEV_FOOTER_BY_TAB[activeTab].hint}
      />

      {/* 네비게이션 바 (좌끝 이전 / 우끝 확정) */}
      <StepNavigationBar
        onPrev={onPrev}
        onNext={onConfirmStep2}
        prevLabel="← 이전 (Step 1)"
        nextLabel="Step 2 분석 결과 확정 →"
        nextVariant="confirm"
      />
    </div>
  )
}
