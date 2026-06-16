import { parseDate } from './date'

// ✅ 외부 PDF/파일 URL을 Vite 프록시 URL로 변환 (CORS 우회)
export function toProxyUrl(url) {
  if (!url) return ''
  const str = String(url).trim()
  if (!str) return ''

  // 이미 프록시 경로면 그대로
  if (str.startsWith('/proxy/')) return str

  // 기업마당
  if (str.includes('bizinfo.go.kr')) {
    return str.replace(/^https?:\/\/(www\.)?bizinfo\.go\.kr/, '/proxy/bizfiles')
  }
  // K-Startup
  if (str.includes('k-startup.go.kr')) {
    return str.replace(/^https?:\/\/(www\.)?k-startup\.go\.kr/, '/proxy/kstartupfiles')
  }

  // 그 외 도메인은 원본 그대로 (CORS 안 막혀 있을 수 있음)
  return str
}

export function stripHtml(value) {
  return String(value ?? '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizePeriod(raw) {
  const text = stripHtml(raw)
  return text || '상세공고 참조'
}

function extractDateText(periodText) {
  const text = normalizePeriod(periodText)
  if (text.includes('~')) return text.split('~').pop()?.trim() ?? ''
  const matched = text.match(/\d{4}[./-]\d{1,2}[./-]\d{1,2}/g)
  if (matched?.length) return matched[matched.length - 1]
  return text
}

export function normalizeNotice(item, origin) {
  const originalTitle = item.pblancNm || item.title || item.btl || item.announcementTitle || ''
  const title = stripHtml(String(originalTitle).replace(/\[.*?\]/g, '').trim()) || '제목 없음'
  const period = normalizePeriod(item.reqstBeginEndDe || item.reqstDt)
  const dateText = extractDateText(period)

  return {
    id: `${origin}-${title}-${period}`,
    origin,
    title,
    full_title: String(originalTitle),
    target: stripHtml(item.trgetNm || item.biz_supt_trgt_info || '공고 참조'),
    benefit: stripHtml(item.suptCn || item.biz_supt_ctnt || '공고 요약 본문을 확인해 주세요.'),
    limit: stripHtml(item.restr_cn || item.biz_supt_trgt_excl_info || '신청 제외 대상은 원본 공고를 참조하세요.'),
    documents: stripHtml(item.subm_doc_nm || '공고 본문을 확인해주세요'),
    region: stripHtml(item.areaNm || item.supt_regin || '전국'),
    url: item.pblancUrl || item.link || item.detailUrl || '',
    period,
    date: parseDate(dateText),
    content: stripHtml(item.bsnsSumryCn || item.hashtags || item.dataContents || '상세 공고 페이지를 참조해 주세요.'),
    jrsdInsttNm: stripHtml(item.jrsdInsttNm || ''),
    excInsttNm: stripHtml(item.excInsttNm || ''),
    hashTags: stripHtml(item.hashTags || ''),
    printFileNm: stripHtml(item.printFileNm || ''),
    printFlpthNm: item.printFlpthNm || '',
    fileNm: item.fileNm || '',
    flpthNm: item.flpthNm || '',
    reqstMthPapersCn: stripHtml(item.reqstMthPapersCn || ''),
    refrncNm: stripHtml(item.refrncNm || ''),
    rceptEngnHmpgUrl: item.rceptEngnHmpgUrl || '',
    category: stripHtml(item.pldirSportRealmLclasCodeNm || ''),
    ajin_similarity: 0,
  }
}

export function dedupeNotices(notices) {
  const seen = new Set()
  return notices.filter((notice) => {
    const key = notice.title.replace(/\s+/g, '')
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function parseAttachmentList(notice) {
  const names = String(notice.fileNm || '').split('@')
  const urls = String(notice.flpthNm || '').split('@')
  const attachments = []

  if (notice.printFlpthNm || notice.url) {
    const rawUrl = notice.printFlpthNm || notice.url
    attachments.push({
      type: '본문',
      name: notice.printFileNm || '공고문 본문',
      url: toProxyUrl(rawUrl),       // ✅ 프록시 변환
      originalUrl: rawUrl,            // ✅ 원본 URL도 보존 (새 창 열기용)
    })
  }

  names.forEach((name, idx) => {
    const url = urls[idx]
    if (url && url !== 'nan') {
      attachments.push({
        type: '첨부',
        name: name || `첨부파일${idx + 1}`,
        url: toProxyUrl(url),         // ✅ 프록시 변환
        originalUrl: url,              // ✅ 원본 URL도 보존
      })
    }
  })

  return attachments
}
