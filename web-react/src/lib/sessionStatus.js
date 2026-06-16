// AJIN BizAI v0.2 — ApplicationSession status helpers
// 출처: PRD §13.9 + PRD-13 §18.2
//
// V2 frontend는 currentStep만 믿지 않고 backend status를 함께 인식해야 함.
// 새로고침 시 GET /api/analysis/sessions/{id} 응답으로 status + current_step 복원.

export const SESSION_STATUS = {
  CREATED: 'created',
  ANALYZING: 'analyzing',
  ANALYSIS_READY: 'analysis_ready',
  STEP2_CONFIRMED: 'step2_confirmed',
  DRAFTING: 'drafting',
  COMPLETED: 'completed',
  ABANDONED: 'abandoned',
  FAILED: 'failed',
}

// Active = 사용자가 이어 작성 가능한 상태 (active session reuse 대상)
export const ACTIVE_STATUSES = [
  SESSION_STATUS.CREATED,
  SESSION_STATUS.ANALYZING,
  SESSION_STATUS.ANALYSIS_READY,
  SESSION_STATUS.STEP2_CONFIRMED,
  SESSION_STATUS.DRAFTING,
]

// status → step 매핑 (백엔드 current_step 부재 또는 invalid 시 fallback)
export function statusToStep(status) {
  switch (status) {
    case SESSION_STATUS.CREATED:
      return 1
    case SESSION_STATUS.ANALYZING:
    case SESSION_STATUS.ANALYSIS_READY:
      return 2
    case SESSION_STATUS.STEP2_CONFIRMED:
    case SESSION_STATUS.DRAFTING:
      return 3
    case SESSION_STATUS.COMPLETED:
      return 5
    case SESSION_STATUS.ABANDONED:
    case SESSION_STATUS.FAILED:
      return null // 호출자가 결정 (read-only 표시 등)
    default:
      return null
  }
}

// PRD §13.9: backend current_step과 status가 충돌할 수 있음.
//   1순위: backend current_step이 1~5이면 사용
//   2순위: invalid이면 statusToStep(status)
//   3순위: 둘이 다르면 console.warn (조용히 무시 X)
export function resolveSessionStep(session) {
  const backendStep = Number(session?.current_step)
  const mappedStep = statusToStep(session?.status)
  const validBackend = Number.isInteger(backendStep) && backendStep >= 1 && backendStep <= 5
  if (validBackend) {
    if (mappedStep && backendStep !== mappedStep) {
      console.warn('[SESSION_STEP_MISMATCH]', {
        status: session.status,
        current_step: backendStep,
        mappedStep,
      })
    }
    return backendStep
  }
  return mappedStep || 1
}

export function isActiveStatus(status) {
  return ACTIVE_STATUSES.includes(status)
}
