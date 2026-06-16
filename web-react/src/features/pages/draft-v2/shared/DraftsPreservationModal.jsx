// AJIN BizAI v0.2 — drafts_preservation_policy 모달 (PRD §13.9, A2-lite)
//
// Trigger (T1): Step 3 → Step 2 backward 이동 + hasDrafts=true 시 표시.
// 사용자 동의 후 setDraftsPolicy 호출 → 영속화 → Step 2 진입.
//
// A2-lite 범위:
//   - preserve 만 실제 지원 (사용자 검토 결과)
//   - discard 는 노출 X (실제 DraftItem 무효화는 Phase 5+)
// → 모달이 사실상 1회용 확인 다이얼로그. 한 번 확인 후 같은 세션에서는 자동 skip
//   (DraftPageV2.handlePreservationProceed가 preservationSkip=true로 set)

import { useEffect, useRef } from 'react'

export default function DraftsPreservationModal({
  open,
  draftCount = 0,
  onCancel,
  onProceed,
  busy = false,
}) {
  const proceedRef = useRef(null)

  // 모달 열릴 때 "확인" 버튼에 포커스 + Enter 즉시 통과
  useEffect(() => {
    if (open && proceedRef.current) proceedRef.current.focus()
  }, [open])

  if (!open) return null

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onCancel?.()
    if (e.key === 'Enter') onProceed?.()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4"
      onKeyDown={handleKeyDown}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h3 className="text-base font-semibold text-slate-900">초안 보존 확인</h3>
        </div>

        <div className="px-6 py-5 space-y-3 text-sm text-slate-700">
          <p>
            이미 작성된 초안이 <strong>{draftCount}개</strong> 있습니다.
          </p>
          <p className="leading-relaxed">
            Step 2에서 재분석을 실행해도 <strong>기존 초안은 그대로 유지</strong>됩니다.
            다만 분석 결과가 바뀌면 일부 문항은 다시 검토가 필요할 수 있습니다.
          </p>
        </div>

        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={busy}
            className="text-sm px-3 py-1.5 border border-slate-200 bg-white rounded hover:bg-slate-50 disabled:opacity-50"
          >
            취소
          </button>
          <button
            ref={proceedRef}
            onClick={onProceed}
            disabled={busy}
            className="text-sm px-3 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50"
          >
            {busy ? '저장 중...' : '기존 초안 유지하고 이동'}
          </button>
        </div>
      </div>
    </div>
  )
}
