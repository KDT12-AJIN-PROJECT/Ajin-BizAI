// AJIN BizAI v0.2 — Step Navigation Bar (좌끝 이전 / 우끝 다음·확정)
// 출처: 사용자 분리 지시
//
// Step 2: prevLabel="← 이전 (Step 1)" / nextLabel="Step 2 분석 결과 확정 →"
// 다른 Step에서도 재사용 가능 (label / variant 자유)

export default function StepNavigationBar({
  onPrev,
  onNext,
  prevLabel = '← 이전',
  nextLabel = '다음 →',
  nextVariant = 'primary', // 'primary' | 'confirm'
  prevDisabled = false,
  nextDisabled = false,
}) {
  const nextCls =
    nextVariant === 'confirm'
      ? 'bg-indigo-950 text-white hover:bg-indigo-900 font-semibold'
      : 'bg-indigo-950 text-white hover:bg-indigo-900'

  return (
    <div className="mt-3 bg-white border border-slate-200 rounded-md px-5 py-3 flex items-center justify-between">
      {/* 좌끝 */}
      <div>
        {onPrev && (
          <button
            onClick={onPrev}
            disabled={prevDisabled}
            className="px-4 py-2 text-sm border border-slate-200 rounded hover:bg-slate-50 whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {prevLabel}
          </button>
        )}
      </div>

      {/* 우끝 */}
      <div>
        {onNext && (
          <button
            onClick={onNext}
            disabled={nextDisabled}
            className={`px-4 py-2 text-sm rounded whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed ${nextCls}`}
          >
            {nextLabel}
          </button>
        )}
      </div>
    </div>
  )
}
