/**
 * FastAPI 백엔드 파일 파싱 API 연결
 * POST /api/parse-file → { text, parse_success, warning, ... }
 */

/**
 * uploads 상태에 있는 File 객체들을 모두 백엔드에 파싱 요청합니다.
 * 백엔드가 꺼져 있거나 파싱 실패해도 예외 없이 빈 텍스트로 처리합니다.
 *
 * @param {Object} uploads  DraftPage의 uploads 상태 { category: File[] }
 * @returns {Object}        { category: [{ name, text, parseSuccess, warning }] }
 */
export async function parseUploadedFiles(uploads) {
  const results = {}

  const allEntries = Object.entries(uploads).flatMap(([cat, files]) =>
    (files || []).filter((f) => f instanceof File).map((f) => ({ cat, file: f }))
  )

  if (allEntries.length === 0) return results

  const settled = await Promise.allSettled(
    allEntries.map(async ({ cat, file }) => {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('/api/parse-file', { method: 'POST', body: formData })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      return { cat, name: file.name, text: data.text || '', parseSuccess: data.parse_success, warning: data.warning }
    })
  )

  for (const result of settled) {
    if (result.status === 'fulfilled') {
      const { cat, ...rest } = result.value
      if (!results[cat]) results[cat] = []
      results[cat].push(rest)
    } else {
      console.warn('[fileProcessApi] 파싱 실패:', result.reason?.message)
    }
  }

  return results
}
