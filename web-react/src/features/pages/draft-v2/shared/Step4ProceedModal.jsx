// AJIN BizAI v0.2 — Step 4 → Step 5 진행 확인 모달 (Phase 4-G-7b)
// 출처: PRD-13 §18.10 (Step 5 차단 X, 모달 only)
// AnalysisConfirmModal과 분리 — 맥락이 다름.

export default function Step4ProceedModal({
  open,
  onClose,
  onProceed,
  draftCounts = { unwritten: 0, needsRevision: 0 },
  openMissingCount = 0,
}) {
  if (!open) return null

  const hasIssues = draftCounts.unwritten > 0 || draftCounts.needsRevision > 0 || openMissingCount > 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-md shadow-xl border border-slate-200 max-w-md w-full mx-4">
        <div className="px-5 py-4 border-b border-slate-200">
          <div className="font-semibold text-slate-900">Step 5 이동 확인</div>
        </div>

        <div className="px-5 py-4 space-y-3">
          {hasIssues ? (
            <>
              <div className="text-sm text-slate-700 leading-relaxed">
                다음 항목이 남아 있습니다.
              </div>
              <ul className="text-sm text-slate-700 space-y-1.5 ml-2">
                {draftCounts.unwritten > 0 && (
                  <li>
                    · 미작성 문항{' '}
                    <strong className="text-red-700">{draftCounts.unwritten}개</strong>
                  </li>
                )}
                {draftCounts.needsRevision > 0 && (
                  <li>
                    · 검토 필요 문항{' '}
                    <strong className="text-amber-700">{draftCounts.needsRevision}개</strong>
                  </li>
                )}
                {openMissingCount > 0 && (
                  <li>
                    · open 부족자료{' '}
                    <strong className="text-red-700">{openMissingCount}건</strong>
                  </li>
                )}
              </ul>
              <div className="text-sm text-slate-700 leading-relaxed pt-1">
                그래도 1차 초안으로 Step 5 Export 단계로 이동하시겠습니까?
              </div>
              <div className="text-[11px] text-slate-500 leading-relaxed pt-1">
                ⓘ Step 5는 미작성 여부와 무관하게 진행할 수 있습니다 (PRD §8 부족해도 1차 초안 작성 정신).
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-700 leading-relaxed">
              모든 문항이 작성 완료 상태입니다. Step 5 Export로 이동하시겠습니까?
            </div>
          )}
        </div>

        <div className="px-5 py-3 border-t border-slate-200 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="text-sm px-4 py-2 border border-slate-200 rounded hover:bg-slate-50"
          >
            계속 검토하기
          </button>
          <button
            onClick={onProceed}
            className="text-sm px-4 py-2 bg-indigo-950 text-white rounded hover:bg-indigo-900"
          >
            Step 5로 이동
          </button>
        </div>
      </div>
    </div>
  )
}
