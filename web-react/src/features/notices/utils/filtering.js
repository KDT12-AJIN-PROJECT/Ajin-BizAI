import { buildNoticeCorpus, similarityScore } from './match'

export function scoreNoticesByProfile(notices, profileText) {
  return notices.map((notice) => {
    const score = similarityScore(profileText, buildNoticeCorpus(notice))
    return { ...notice, ajin_similarity: score }
  })
}

function includesAnyKeyword(text, keywords) {
  if (!keywords.length) return true
  const lower = text.toLowerCase()
  return keywords.some((kw) => lower.includes(kw.toLowerCase()))
}

function includesRegion(notice, selectedRegions) {
  if (!selectedRegions.length) return true
  return selectedRegions.some((r) => notice.region?.includes(r))
}

function includesSize(notice, selectedSizes) {
  if (!selectedSizes.length) return true
  const merged = `${notice.target} ${notice.content} ${notice.category}`
  return selectedSizes.some((s) => merged.includes(s))
}

export function applyFilters(notices, options) {
  const {
    selectedKeywords,
    selectedRegions,
    selectedSizes,
    searchTitle,
    matchMode,
    threshold,
    selectedOrigins,
  } = options

  let filtered = notices.filter((notice) => {
    if (selectedOrigins?.length > 0 && !selectedOrigins.includes(notice.origin)) return false
    const corpus = buildNoticeCorpus(notice)
    if (!includesAnyKeyword(corpus, selectedKeywords)) return false
    if (!includesRegion(notice, selectedRegions)) return false
    if (!includesSize(notice, selectedSizes)) return false

    if (searchTitle?.trim()) {
      const words = searchTitle
        .split(/\s+/)
        .map((w) => w.trim().toLowerCase())
        .filter(Boolean)
      if (!words.every((w) => notice.title.toLowerCase().includes(w))) return false
    }

    if (matchMode === '적합도(유사도)') {
      return (notice.ajin_similarity ?? 0) >= threshold
    }
    return true
  })

  return filtered
}

export function sortNotices(notices, sortBy) {
  const copied = [...notices]
  if (sortBy === '적합도순') {
    copied.sort((a, b) => (b.ajin_similarity ?? 0) - (a.ajin_similarity ?? 0))
  } else if (sortBy === '마감일 가까운 순') {
    copied.sort((a, b) => (a.date?.getTime?.() ?? Infinity) - (b.date?.getTime?.() ?? Infinity))
  } else {
    copied.sort((a, b) => (b.date?.getTime?.() ?? -Infinity) - (a.date?.getTime?.() ?? -Infinity))
  }
  return copied
}

export function paginate(list, page, perPage) {
  const totalPages = Math.max(1, Math.ceil(list.length / perPage))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const start = (safePage - 1) * perPage
  return {
    totalPages,
    page: safePage,
    items: list.slice(start, start + perPage),
  }
}

export function buildNotificationList(notices, threshold, keywords) {
  let list = notices.filter((n) => (n.ajin_similarity ?? 0) >= threshold)
  if (keywords.length) {
    list = list
      .map((n) => {
        const text = `${n.title} ${n.content}`.toLowerCase()
        const priority = keywords.some((kw) => text.includes(kw.toLowerCase())) ? 1 : 0
        return { ...n, priority }
      })
      .sort((a, b) => b.priority - a.priority || (b.ajin_similarity ?? 0) - (a.ajin_similarity ?? 0))
  } else {
    list = list.sort((a, b) => (b.ajin_similarity ?? 0) - (a.ajin_similarity ?? 0))
  }
  return list
}
