export function parseDate(value) {
  if (!value) return null
  const normalized = String(value).replace(/\./g, '-').replace(/\//g, '-')
  const dt = new Date(normalized)
  return Number.isNaN(dt.getTime()) ? null : dt
}

export function formatDate(value) {
  const dt = value instanceof Date ? value : parseDate(value)
  if (!dt) return '기한미상'
  return dt.toISOString().slice(0, 10)
}

export function getDdayText(value) {
  const dt = value instanceof Date ? value : parseDate(value)
  if (!dt) return '기한미상'
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(dt)
  target.setHours(0, 0, 0, 0)
  const diff = Math.floor((target.getTime() - today.getTime()) / (24 * 60 * 60 * 1000))
  if (diff > 0) return `D-${diff}`
  if (diff === 0) return 'D-day'
  return '마감'
}
