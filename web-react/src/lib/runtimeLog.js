// AJIN BizAI v0.2 — Runtime API 가시성 helper
// 출처: PRD-13 §18 + 사용자 정책 — 검증 시 mock fallback이 문제를 은폐하면 안 됨.
//
// VITE_DISABLE_MOCK_FALLBACK=true 환경에서:
//   - API 실패 시 mock 데이터로 대체하지 않음
//   - handleFallback이 'blocked' 반환 → 호출자가 state를 explicit하게 비워야 함
//   - UI에 명확한 에러 노출

const DISABLE_FALLBACK = import.meta.env.VITE_DISABLE_MOCK_FALLBACK === 'true'

// 성공한 API 호출 + 응답 요약 로그
export function logApi(label, summary) {
  console.log(`[REAL_API] ${label}`, summary)
}

// API 실패 처리.
//   - DISABLE_FALLBACK=true: 'blocked' 반환 + console.error + onError/onClear 호출
//   - DISABLE_FALLBACK=false: 'fallback' 반환 + console.warn (현재 state 유지 = mock 사용)
//
// 호출자 예:
//   const result = handleFallback('parse-form', err, { onError: setFormError, onClear: () => setFormData(EMPTY_FORM) })
//   if (result === 'blocked') {
//     // 추가 cleanup 필요 시 여기서
//   }
export function handleFallback(label, error, { onError, onClear } = {}) {
  const errMsg = error?.message || error?.toString() || 'unknown error'
  if (DISABLE_FALLBACK) {
    console.error(`[MOCK_FALLBACK_BLOCKED] ${label}:`, errMsg)
    onError?.(`[BLOCKED] ${label}: ${errMsg}`)
    onClear?.()
    return 'blocked'
  }
  console.warn(`[MOCK_FALLBACK] ${label}:`, errMsg)
  return 'fallback'
}

export function isFallbackBlocked() {
  return DISABLE_FALLBACK
}
