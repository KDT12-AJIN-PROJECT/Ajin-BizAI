// AJIN BizAI v3.2 C-5b — Step 2 확정 9단계 진행 모달
// 출처: v3.2 c-5 §"Step2 확정 후 호출 순서"
//
// 단계 ID:
//   confirm → announcement → rubric → step3-ready → initialize
//   → mapping-start → polling → fetch-drafts → done
// 실패: failed (error_message 표시 + retry 버튼)

const STAGE_LABELS = {
  confirm: '1/9 분석 결과 확정 중...',
  announcement: '2/9 공고 신호 정규화 중...',
  rubric: '3/9 평가 기준 확정 중...',
  'step3-ready': '4/9 Step 3 진입 확인 중...',
  initialize: '5/9 작성 항목 초기화 중...',
  'mapping-start': '6/9 매핑 시작 중...',
  polling: '7/9 매핑 진행 중... (1~3분 소요)',
  'fetch-drafts': '8/9 초안 데이터 조회 중...',
  done: '9/9 완료 — Step 3으로 이동',
  failed: '⚠ 확정 실패',
}

const PIPELINE_STEPS = [
  { id: 'analyze_company', label: '기업 분석' },
  { id: 'extract_evidence', label: '근거 추출' },
  { id: 'map_evidence', label: '근거 매핑' },
  { id: 'map_eval_criteria', label: '평가기준 매핑' },
  { id: 'check_missing', label: '부족자료 점검' },
]

// UI-C6: failed_step별 친화 안내
const FAILED_STEP_LABELS = {
  analyze_company: '기업 정보 분석에 실패했습니다. Step 1에서 회사 자료(회사소개서/제품소개서 등)를 추가해주세요.',
  extract_evidence: '근거 추출에 실패했습니다. Step 1에서 업로드한 참고자료를 확인하거나 추가해주세요.',
  map_evidence: '근거 매핑에 실패했습니다. 잠시 후 재시도하거나, 양식/공고 분석을 다시 시도해주세요.',
  map_eval_criteria: '평가기준 매핑에 실패했습니다. 평가 rubric 데이터를 확인해주세요.',
  check_missing: '부족자료 점검에 실패했습니다. 매핑 결과를 확인 후 재시도해주세요.',
}

// UI-C6: not_ready_reasons 10종 enum (C-4 backend)
const NOT_READY_REASON_LABELS = {
  pipeline_missing: '매핑 파이프라인이 아직 시작되지 않았습니다',
  pipeline_status_running: '매핑이 진행 중입니다',
  pipeline_status_failed: '매핑 파이프라인이 실패했습니다',
  confirmed_schema_missing: 'Step 2 분석 결과 확정이 누락되었습니다',
  draft_items_missing: '작성 항목 초기화가 누락되었습니다',
  evaluation_rubric_missing: '평가 rubric이 확정되지 않았습니다',
  company_analysis_missing: '기업 분석 결과가 없습니다',
  evidence_missing: '근거 추출 결과가 없습니다',
  mapping_result_missing: '근거 매핑 결과가 없습니다',
  check_missing_not_completed: '부족자료 점검이 완료되지 않았습니다',
}

// UI-C6: Step1 복귀 버튼을 보일 failed_step (회사 자료 / 참고자료 입력 단계)
const STEP1_RECOVERABLE_FAILED_STEPS = new Set(['analyze_company', 'extract_evidence'])

export default function Step2ProgressModal({
  open,
  stage = null,           // null | 'confirm' | ... | 'done' | 'failed'
  pipelineState = null,   // { status, steps: {...}, failed_step, error_message }
  errorMessage = null,
  summary = null,         // { announcement: <C-1.5 응답>, rubric: <C-1.6 응답> }
  notReadyReasons = null, // UI-C6: not_ready_reasons (C-4 mapping-status 응답)
  onRetry = null,
  onClose = null,
  onBackToStep1 = null,   // UI-C6: analyze_company / extract_evidence 실패 시만 노출
}) {
  if (!open) return null

  const isFailed = stage === 'failed'
  const isDone = stage === 'done'
  const isPolling = stage === 'polling'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">
            {isFailed ? '⚠ Step 2 확정 실패' : isDone ? '✓ Step 2 확정 완료' : 'Step 2 분석 결과 확정'}
          </h3>
        </div>

        <div className="p-6">
          {/* 진행 단계 라벨 */}
          <div className="mb-4">
            <div className="text-sm font-medium text-slate-700">
              {STAGE_LABELS[stage] || '준비 중...'}
            </div>
            {!isFailed && !isDone && (
              <div className="mt-2">
                <div className="w-full h-1.5 bg-slate-200 rounded">
                  <div
                    className="h-1.5 bg-indigo-600 rounded transition-all duration-300"
                    style={{ width: `${_progressPct(stage)}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* polling 시 5단계 sub-progress */}
          {isPolling && pipelineState?.steps && (
            <div className="space-y-1.5 mt-4 border-t border-slate-100 pt-4">
              <div className="text-xs font-medium text-slate-500 mb-2">5단계 진행 상태</div>
              {PIPELINE_STEPS.map((step) => {
                const status = pipelineState.steps[step.id] || 'pending'
                const icon = {
                  pending: '○',
                  running: '◐',
                  done: '✓',
                  failed: '✗',
                }[status] || '○'
                const color = {
                  pending: 'text-slate-400',
                  running: 'text-indigo-600',
                  done: 'text-green-600',
                  failed: 'text-red-600',
                }[status] || 'text-slate-400'
                return (
                  <div key={step.id} className={`text-xs flex items-center gap-2 ${color}`}>
                    <span className="font-mono">{icon}</span>
                    <span>{step.label}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* 실패 시 에러 표시 + retry 버튼 (UI-C6: 친화 안내 + not_ready_reasons + Step1 복귀) */}
          {isFailed && (() => {
            const failedStep = pipelineState?.failed_step || null
            const friendly = failedStep ? FAILED_STEP_LABELS[failedStep] : null
            const reasons = Array.isArray(notReadyReasons) ? notReadyReasons.filter(Boolean) : []
            const showBackToStep1 = !!onBackToStep1 && STEP1_RECOVERABLE_FAILED_STEPS.has(failedStep)
            return (
              <div className="mt-4 space-y-3">
                <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-900 leading-relaxed">
                  <div className="font-medium">
                    {friendly || errorMessage || '알 수 없는 오류'}
                  </div>
                  {friendly && errorMessage && (
                    <div className="mt-1 text-[11px] text-red-800">{errorMessage}</div>
                  )}
                  {failedStep && (
                    <div className="mt-1 text-[10px] font-mono text-red-700">
                      failed_step: {failedStep}
                    </div>
                  )}
                  {reasons.length > 0 && (
                    <div className="mt-2 border-t border-red-200 pt-2">
                      <div className="text-[11px] font-medium text-red-800 mb-1">
                        진입 차단 사유
                      </div>
                      <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                        {reasons.map((r) => (
                          <li key={r}>{NOT_READY_REASON_LABELS[r] || r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                <div className="flex justify-end gap-2">
                  {showBackToStep1 && (
                    <button
                      onClick={onBackToStep1}
                      className="text-sm px-3 py-1.5 border border-amber-300 bg-amber-50 text-amber-900 rounded hover:bg-amber-100"
                    >
                      Step 1로 돌아가기
                    </button>
                  )}
                  {onClose && (
                    <button
                      onClick={onClose}
                      className="text-sm px-3 py-1.5 border border-slate-200 rounded hover:bg-slate-50"
                    >
                      닫기
                    </button>
                  )}
                  {onRetry && (
                    <button
                      onClick={onRetry}
                      className="text-sm px-3 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900"
                    >
                      재시도
                    </button>
                  )}
                </div>
              </div>
            )
          })()}

          {/* 진행 중 / 완료: 별도 액션 버튼 없음 (자동 이동) */}
          {!isFailed && !isDone && (
            <div className="mt-4 text-[11px] text-slate-500">
              모달을 닫지 마세요. 완료 시 Step 3으로 자동 이동합니다.
            </div>
          )}

          {/* C-5b Q4: announcement_signals + evaluation_rubric 10개 항목 (완료 직전) */}
          {summary && (isDone || stage === 'fetch-drafts') && (
            <div className="mt-4 border-t border-slate-100 pt-4 space-y-3">
              {summary.announcement && (
                <div className="text-xs">
                  <div className="font-medium text-slate-700 mb-1">
                    공고 신호 ({summary.announcement.status || 'unknown'})
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-slate-600">
                    <div>criteria: <strong>{summary.announcement.criteria_count ?? 0}</strong></div>
                    <div>bonuses: <strong>{summary.announcement.bonuses_count ?? 0}</strong></div>
                    <div>preferences: <strong>{summary.announcement.preferences_count ?? 0}</strong></div>
                    <div>eligibility: <strong>{summary.announcement.eligibility_count ?? 0}</strong></div>
                    <div>keywords: <strong>{summary.announcement.emphasis_keywords_count ?? 0}</strong></div>
                    <div>compliance: <strong>{summary.announcement.compliance_constraints_count ?? 0}</strong></div>
                  </div>
                </div>
              )}
              {summary.rubric && (
                <div className="text-xs">
                  <div className="font-medium text-slate-700 mb-1">평가 rubric</div>
                  <div className="grid grid-cols-2 gap-1 text-slate-600">
                    <div>source: <strong>{summary.rubric.source || 'unknown'}</strong></div>
                    <div>template: <strong>{summary.rubric.template_type || '-'}</strong></div>
                    <div>axes: <strong>{summary.rubric.axes_count ?? 0}</strong></div>
                    <div>scored: <strong>{summary.rubric.scored_axes_count ?? 0}</strong></div>
                    <div className="col-span-2">total_weight: <strong>{summary.rubric.total_weight ?? 0}</strong></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function _progressPct(stage) {
  const order = [
    'confirm', 'announcement', 'rubric', 'step3-ready', 'initialize',
    'mapping-start', 'polling', 'fetch-drafts', 'done',
  ]
  const idx = order.indexOf(stage)
  if (idx < 0) return 5
  return Math.round(((idx + 1) / order.length) * 100)
}
