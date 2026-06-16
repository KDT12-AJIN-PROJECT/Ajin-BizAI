function tokenize(value) {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[^0-9a-zA-Z가-힣\s]/g, ' ')
    .split(/\s+/)
    .filter((v) => v.length > 1)
}

export function similarityScore(profile, noticeText) {
  const p = new Set(tokenize(profile))
  const n = new Set(tokenize(noticeText))
  if (p.size === 0 || n.size === 0) return 0
  let inter = 0
  p.forEach((t) => {
    if (n.has(t)) inter += 1
  })
  const union = p.size + n.size - inter
  return union > 0 ? inter / union : 0
}

export function buildNoticeCorpus(notice) {
  return [
    notice.title,
    notice.content,
    notice.target,
    notice.benefit,
    notice.category,
    notice.hashTags,
    notice.region,
  ]
    .filter(Boolean)
    .join(' ')
}
