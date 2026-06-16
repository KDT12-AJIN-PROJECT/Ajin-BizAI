import { dedupeNotices } from '../features/notices/utils/normalize'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// 마감 지난 공고를 결과에서 아예 제외 (검색/조회 단계에서 drop)
// notice.date가 null/invalid면 포함 (기한미상은 노출)
function dropExpired(notices) {
  const todayStart = new Date()
  todayStart.setHours(0, 0, 0, 0)
  return notices.filter((n) => {
    if (!n.date) return true
    const t = n.date instanceof Date ? n.date.getTime() : new Date(n.date).getTime()
    if (Number.isNaN(t)) return true
    return t >= todayStart.getTime()
  })
}

export async function fetchAllNotices({ q = '자동차', refresh = false } = {}) {
  try {
    const params = new URLSearchParams({ q, refresh: String(refresh) })
    const res = await fetch(`${API_BASE}/api/notices/search?${params}`)
    if (!res.ok) throw new Error(`HTTP_${res.status}`)
    const { notices, errors } = await res.json()
    return {
      notices: dropExpired(dedupeNotices(notices)),
      errors,
    }
  } catch (err) {
    return {
      notices: [],
      errors: [`백엔드 연결 실패: ${err.message}`],
    }
  }
}
