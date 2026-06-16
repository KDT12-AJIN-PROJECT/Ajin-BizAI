import { env } from '../config/env'

// ── 텍스트 길이 제한 헬퍼 ─────────────────────────────────────────
function trunc(text, maxChars = 800) {
  if (!text) return '-'
  const t = String(text).trim()
  return t.length <= maxChars ? t : t.slice(0, maxChars) + '...(이하 생략)'
}

// 공고 핵심 필드만 뽑아 토큰을 아끼는 요약 블록
function noticeContext(notice, { contentLen = 600, fieldLen = 400 } = {}) {
  return [
    `공고명: ${notice.title}`,
    `지원 대상: ${trunc(notice.target, fieldLen)}`,
    `지원 내용: ${trunc(notice.benefit, fieldLen)}`,
    `사업 내용: ${trunc(notice.content, contentLen)}`,
  ].join('\n')
}

// ── LLM 공통 호출 (OpenAI → Anthropic → LM Studio 순서로 자동 선택) ──
//
// 우선순위:
//   1. VITE_OPENAI_API_KEY 가 .env 에 있으면 → OpenAI (GPT-4o-mini)
//   2. VITE_ANTHROPIC_API_KEY 가 있으면      → Anthropic (Claude Haiku)
//   3. 둘 다 없으면                          → LM Studio (로컬)
//
async function callLM({ system, user, maxTokens = 1024, temperature = 0.4 }) {

  const messages = [
    { role: 'system', content: system },
    { role: 'user',   content: user },
  ]

  // ── 0순위: 백엔드 AI (Azure gpt-4.1 등 서버 설정 provider) ────
  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ system, user, max_tokens: maxTokens, temperature }),
    })
    if (res.ok) {
      const data = await res.json()
      if (data?.content) return data.content
    }
  } catch (_) { /* 백엔드 없으면 아래 순서로 fallback */ }

  // ── 1순위: OpenAI ──────────────────────────────────────────────
  if (env.openaiApiKey) {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${env.openaiApiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages,
        temperature,
        max_tokens: maxTokens,
      }),
    })
    if (!res.ok) throw new Error(`OpenAI 오류 (HTTP ${res.status})`)
    const data = await res.json()
    const content = data?.choices?.[0]?.message?.content
    if (!content) throw new Error('OpenAI 응답이 비어있습니다.')
    return content
  }

  // ── 2순위: Anthropic (Claude) ──────────────────────────────────
  if (env.anthropicApiKey) {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.anthropicApiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: maxTokens,
        system,
        messages: [{ role: 'user', content: user }],
      }),
    })
    if (!res.ok) throw new Error(`Anthropic 오류 (HTTP ${res.status})`)
    const data = await res.json()
    const content = data?.content?.[0]?.text
    if (!content) throw new Error('Anthropic 응답이 비어있습니다.')
    return content
  }

  // ── 3순위: LM Studio (로컬) ────────────────────────────────────
  const headers = { 'Content-Type': 'application/json' }
  if (env.lmStudioToken) headers['Authorization'] = `Bearer ${env.lmStudioToken}`
  const response = await fetch(`${env.lmStudioUrl}/v1/chat/completions`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model: 'google/gemma-4-e4b',
      messages,
      temperature,
      max_tokens: maxTokens,
      stream: false,
    }),
  })

  if (!response.ok) {
    const errText = await response.text().catch(() => '')
    throw new Error(`LM Studio 오류 (HTTP ${response.status})${errText ? ': ' + errText.slice(0, 200) : ''}`)
  }

  const data = await response.json()
  const content = data?.choices?.[0]?.message?.content

  if (content == null) {
    throw new Error('LM Studio 응답 구조가 예상과 다릅니다. LM Studio가 실행 중인지 확인하세요.')
  }

  if (content.trim() === '') {
    const reason = data?.choices?.[0]?.finish_reason ?? 'unknown'
    throw new Error(`LM Studio가 빈 응답을 반환했습니다 (finish_reason: ${reason}). Context Length 설정을 높이거나 모델을 확인하세요.`)
  }

  return content
}

// 외부에서 직접 쓸 수 있도록 callLLM 이름으로도 내보내기
export { callLM as callLLM }

// ── 공고 요약 (3~4문장) ───────────────────────────────────────────
export async function generateNoticeSummary(notice) {
  const raw = [notice.content, notice.benefit, notice.target]
    .filter((v) => v && !v.includes('참조') && !v.includes('확인해주세요'))
    .join(' ')

  if (!raw.trim()) throw new Error('요약할 본문 내용이 없습니다. API 키와 공고 원문을 확인하세요.')

  return callLM({
    system: `당신은 한국 정부지원사업 공고를 분석하는 전문가입니다.
주어진 공고 원문을 읽고 핵심 내용을 3~4문장으로 간결하게 요약하세요.
반드시 한국어로 작성하고, 마크다운 기호 없이 순수 텍스트로만 출력하세요.`,
    user: `다음 공고를 3~4문장으로 요약하세요.

${noticeContext(notice, { contentLen: 800, fieldLen: 400 })}`,
    maxTokens: 512,
    temperature: 0.3,
  })
}

// ── 사업계획서 항목 구조 추출 ─────────────────────────────────────
export async function analyzeNoticeStructure(notice) {
  const text = await callLM({
    system: `당신은 한국 정부지원사업 공고문 분석 전문가입니다.
공고를 분석해 사업계획서에 필요한 항목 5~7개를 추출하고 JSON 배열로 반환하세요.
반환 형식(예시): [{"key":"1","title":"사업 배경 및 필요성"},{"key":"2","title":"추진 계획"}]
JSON 배열 앞뒤에 짧은 설명을 붙여도 괜찮지만, JSON 자체는 정확하게 작성하세요.`,
    user: `${noticeContext(notice, { contentLen: 600, fieldLen: 300 })}

이 공고에 맞는 사업계획서 항목을 JSON 배열로 반환하세요.`,
    maxTokens: 512,
    temperature: 0.2,
  })

  const match = text.match(/\[[\s\S]*\]/)
  if (match) {
    try {
      const parsed = JSON.parse(match[0])
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    } catch {
      const objMatches = [...text.matchAll(/\{\s*"key"\s*:\s*"[^"]+"\s*,\s*"title"\s*:\s*"[^"]+"\s*\}/g)]
      if (objMatches.length > 0) {
        try {
          const fallback = objMatches.map(m => JSON.parse(m[0]))
          if (fallback.length > 0) return fallback
        } catch {}
      }
    }
  }
  throw new Error('항목 추출 실패 — 기본 구성으로 대체합니다.')
}

// ── 항목별 초안 생성 ──────────────────────────────────────────────
export async function generateDraftSection({ section, notice, profileData, confirmedSections = [] }) {
  const prevCtx = confirmedSections.slice(-3).length > 0
    ? '\n\n[이미 작성된 항목 — 일관성 유지]\n' +
      confirmedSections.slice(-3).map(s => `${s.key}. ${s.title}: ${s.content.slice(0, 100)}...`).join('\n')
    : ''

  return callLM({
    system: `당신은 한국 정부지원사업 사업계획서 작성 전문가입니다.
지정된 항목을 200~300자 분량으로 구체적이고 설득력 있게 작성하세요.
마크다운 기호 없이 순수 텍스트로만 출력하세요.`,
    user: `[공고 정보]
공고명: ${notice.title}
지원 대상: ${trunc(notice.target, 300)}
지원 내용: ${trunc(notice.benefit, 300)}

[기업 정보]
분야: ${profileData?.field || '-'}
요약: ${trunc(profileData?.summary, 200)}
전략: ${trunc(profileData?.strategy, 200)}
${prevCtx}

"${section.key}. ${section.title}" 항목을 작성하세요.`,
    maxTokens: 768,
    temperature: 0.6,
  })
}

// ── 항목 수정 ─────────────────────────────────────────────────────
export async function reviseDraftSection({ section, currentContent, feedback, notice }) {
  return callLM({
    system: `당신은 한국 정부지원사업 사업계획서 작성 전문가입니다.
기존 내용을 사용자 피드백에 맞게 수정하세요.
수정된 내용만 반환하고 마크다운 없이 순수 텍스트로 작성하세요.`,
    user: `공고명: ${notice.title}

[${section.key}. ${section.title}] 현재 내용:
${trunc(currentContent, 400)}

수정 요청: ${feedback}

수정된 내용을 작성하세요.`,
    maxTokens: 768,
    temperature: 0.5,
  })
}

// ── 빠른 초안 (전체 일괄 생성) ───────────────────────────────────
export async function generateDraftWithLM({ notice, draft }) {
  return callLM({
    system: `당신은 한국 정부지원사업 전문 사업계획서 작성 전문가입니다.
주어진 공고 정보와 기업 프로필을 바탕으로 실제 제출 가능한 수준의 사업계획서 초안을 작성하세요.
형식은 마크다운이며, 각 항목은 구체적이고 논리적으로 작성하세요.`,
    user: `[공고 정보]
공고명: ${notice.title}
지원 대상: ${trunc(notice.target, 400)}
지원 내용: ${trunc(notice.benefit, 400)}
필수 서류: ${trunc(notice.documents, 200)}
신청 기간: ${notice.period || '-'}

[기업 정보]
기업명: ${draft.corpName}
사업 참여 목적: ${draft.projectGoal || '(미입력)'}

위 정보를 바탕으로 아래 항목을 포함한 사업계획서 초안을 작성하세요:

## 1. 신청 기업 개요
## 2. 사업 참여 목적 및 필요성
## 3. 세부 추진 계획
## 4. 기대 효과
## 5. 예산 계획 개요`,
    maxTokens: 2048,
    temperature: 0.7,
  })
}

// ── 공고 3줄 요약 (카드용 짧은 요약) ──────────────────────────────
export async function generateNoticeShortSummary(notice) {
  const raw = [notice.content, notice.benefit, notice.target]
    .filter((v) => v && !v.includes('참조') && !v.includes('확인해주세요'))
    .join(' ')

  if (!raw.trim()) throw new Error('요약할 본문 내용이 없습니다.')

  return callLM({
    system: `당신은 한국 정부지원사업 공고를 핵심만 추려 알려주는 전문가입니다.
공고를 정확히 3줄로 요약하세요.
형식:
1. 누가 신청할 수 있는지
2. 무엇을 지원받는지
3. 핵심 조건이나 마감 정보
각 줄은 30자 이내로 간결하게 작성하고, 마크다운 기호 없이 순수 텍스트로 출력하세요.`,
    user: `${noticeContext(notice, { contentLen: 600, fieldLen: 300 })}

위 공고를 3줄로 요약하세요. 각 줄 앞에 "1. ", "2. ", "3. " 번호를 붙이세요.`,
    maxTokens: 2048,  // reasoning 모델(gemma-4-e4b 등) 대응 — reasoning 토큰 + 실제 content 모두 수용
    temperature: 0.3,
  })
}

// ── PDF/문서 내용 분석 후 서류 항목 추출 ─────────────────────────
export async function analyzeUploadedDocument(text, docType) {
  return callLM({
    system: `당신은 한국 정부지원사업 서류 분석 전문가입니다.
업로드된 문서를 분석해 핵심 정보를 JSON 형태로 추출하세요.
반드시 JSON만 반환하고 마크다운 코드블록 없이 순수 JSON만 출력하세요.`,
    user: `문서 유형: ${docType}
문서 내용:
${text.slice(0, 2000)}

위 문서에서 다음 정보를 추출해 JSON으로 반환하세요:
{
  "companyName": "기업명",
  "representative": "대표자",
  "businessNumber": "사업자번호",
  "address": "주소",
  "mainBusiness": "주요 사업",
  "employees": "직원 수",
  "revenue": "매출액",
  "extractedFields": ["추출된 주요 항목들"]
}
없는 항목은 빈 문자열로 두세요.`,
    maxTokens: 512,
    temperature: 0.1,
  })
}

// ── 제출 서류 초안 자동 작성 ──────────────────────────────────────
export async function generateSubmissionDraft({ notice, section, uploadedData, profileData }) {
  const contextParts = []

  if (uploadedData && Object.keys(uploadedData).length > 0) {
    contextParts.push(`[업로드된 기업 정보]\n${JSON.stringify(uploadedData, null, 2)}`)
  }

  if (profileData) {
    contextParts.push(`[기업 프로필]\n분야: ${profileData.field}\n요약: ${profileData.summary}\n전략: ${profileData.strategy}`)
  }

  return callLM({
    system: `당신은 한국 정부지원사업 사업계획서 작성 전문가입니다.
제공된 기업 정보와 공고 내용을 바탕으로 실제 제출 가능한 수준의 내용을 작성하세요.
마크다운 없이 순수 텍스트로 작성하고 200~400자 분량으로 작성하세요.`,
    user: `[공고 정보]
공고명: ${notice.title}
지원 대상: ${String(notice.target || '').slice(0, 300)}
지원 내용: ${String(notice.benefit || '').slice(0, 300)}

${contextParts.join('\n\n')}

"${section}" 항목을 작성하세요.`,
    maxTokens: 768,
    temperature: 0.6,
  })
}

// ── 전략 검토 챗봇 ────────────────────────────────────────────────
export async function chatWithDraftReviewer({ message, draftContent, notice, history = [] }) {
  const historyText = history.slice(-6).map(h => `${h.role === 'user' ? '사용자' : 'AI'}: ${h.content}`).join('\n')

  return callLM({
    system: `당신은 정부지원사업 사업계획서 전문 컨설턴트입니다.
작성된 초안을 검토하고 사용자의 수정 요청에 답변하세요.
수정이 필요하면 수정된 내용을 직접 제공하고, 질문이면 명확히 답변하세요.`,
    user: `[공고명] ${notice.title}

[현재 초안 내용]
${draftContent.slice(0, 1500)}

[이전 대화]
${historyText}

[사용자 메시지]
${message}`,
    maxTokens: 1024,
    temperature: 0.5,
  })
}

// ── 업로드 자료 충족도 검사 ──────────────────────────────────────
// parsedTexts: parseUploadedFiles()의 반환값 (있으면 파일 내용 요약 포함)
export async function checkUploadCompleteness({ notice, uploads, profileData, parsedTexts = {} }) {
  const uploadList = Object.entries(uploads).map(([cat, files]) => {
    const fileNames = (files || []).map(f => f.name || f).filter(Boolean).join(', ')
    const parsed = parsedTexts[cat]
    const snippet = parsed
      ?.map(p => p.text?.slice(0, 300))
      ?.filter(Boolean)
      ?.join(' ')
    return `- ${cat}: ${fileNames || '(없음)'}${snippet ? `\n  내용 발췌: ${snippet.slice(0, 400)}` : ''}`
  }).join('\n')

  return callLM({
    system: `당신은 한국 정부지원사업 서류 분석 전문가입니다.
업로드된 자료를 분석해 사업계획서 자동 작성에 필요한 정보의 충족도를 평가하세요.
반드시 JSON 형식으로만 반환하고 마크다운 코드블록 없이 순수 JSON만 출력하세요.`,
    user: `[공고 정보]
공고명: ${notice.title}
지원 대상: ${String(notice.target || '').slice(0, 200)}
필요 서류: ${String(notice.documents || '').slice(0, 200)}

[업로드 자료]
${uploadList}

[기업 프로필]
회사명: ${profileData?.companyName || '-'}
업종: ${profileData?.industry || '-'} / ${profileData?.subIndustry || '-'}
직원수: ${profileData?.employees || '-'}
주요 사업: ${profileData?.summary || '-'}

위 정보를 바탕으로 다음 JSON 형식으로 평가하세요:
{
  "completeness": 0-100,
  "categories": [
    {"name": "자동완성", "count": 5},
    {"name": "검토필요", "count": 3},
    {"name": "직접입력 필요", "count": 2},
    {"name": "미작성", "count": 5}
  ],
  "missingInfo": ["기업명", "대표자", "주요 사업 및 제품"],
  "recommendations": ["회사소개서 추가 권장", "재무제표 첨부 시 매출 자동 추출 가능"]
}`,
    maxTokens: 768,
    temperature: 0.2,
  })
}

// ── 작성된 초안 평가 (STEP4) ─────────────────────────────────────
export async function evaluateDraft({ notice, drafts, profileData }) {
  const draftSections = Object.entries(drafts)
    .filter(([, content]) => content?.trim())
    .map(([key, content]) => `[${key}]\n${content.slice(0, 400)}`)
    .join('\n\n')

  return callLM({
    system: `당신은 한국 정부지원사업 사업계획서 평가 전문가입니다.
작성된 초안을 평가 기준에 따라 진단하고 보완점을 제시하세요.
반드시 JSON 형식으로만 반환하고 마크다운 코드블록 없이 순수 JSON만 출력하세요.`,
    user: `[공고명] ${notice.title}

[작성된 초안]
${draftSections || '(아직 작성된 내용 없음)'}

[기업 정보]
${profileData?.summary || ''}

다음 JSON 형식으로 평가하세요:
{
  "currentScore": 0-100,
  "expectedImprovement": 0-30,
  "passLine": 70,
  "categories": [
    {"name": "기술성", "level": "우수|보완 필요|보통", "issue": "구체적 감점 이유"},
    {"name": "사업성", "level": "보완 필요", "issue": "..."},
    {"name": "기대효과", "level": "보완 필요", "issue": "..."},
    {"name": "수행역량", "level": "보통", "issue": "..."}
  ],
  "topIssues": [
    {
      "priority": 1,
      "category": "사업성",
      "title": "사업화 전략을 단계별 실행계획으로 구체화",
      "expectedScore": 12,
      "currentText": "기존 추상적 표현",
      "improvedText": "구체화된 보완안",
      "reason": ["실행 가능성", "고객 명확성", "성과 흐름"]
    }
  ],
  "improvementProgress": {
    "applied": 1,
    "inProgress": 1,
    "needsData": 2,
    "waiting": 0
  }
}`,
    maxTokens: 1500,
    temperature: 0.3,
  })
}

// ── 보완안 적용 (특정 섹션 재작성) ────────────────────────────────
export async function applyImprovement({ section, currentText, improvedText, notice }) {
  return callLM({
    system: `당신은 한국 정부지원사업 사업계획서 작성 전문가입니다.
기존 내용을 보완안 방향으로 재작성하세요. 마크다운 없이 순수 텍스트로 작성하세요.`,
    user: `[공고] ${notice.title}
[항목] ${section}
[기존] ${currentText.slice(0, 300)}
[보완 방향] ${improvedText.slice(0, 300)}

위 보완 방향을 반영해 200~300자 분량으로 재작성하세요.`,
    maxTokens: 768,
    temperature: 0.5,
  })
}