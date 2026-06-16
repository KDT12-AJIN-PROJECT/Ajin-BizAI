// AJIN BizAI v0.2 — StepProgress (PRD §20 Phase 1 라벨 5개)
// 출처: PRD v0.2 FINAL §20 / §11~§12 Step 정의

const STEPS = [
  { id: 1, label: '자료 업로드' },
  { id: 2, label: '분석' },
  { id: 3, label: 'AI 초안 작성' },
  { id: 4, label: '평가' },
  { id: 5, label: '완료 / 다운로드' },
]

export default function StepProgressV2({ currentStep = 1, onStepClick }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200">
      {STEPS.map((step, idx) => {
        const isActive = step.id === currentStep
        const isDone = step.id < currentStep
        return (
          <div key={step.id} className="flex items-center flex-1">
            <button
              onClick={() => onStepClick?.(step.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md transition
                ${isActive ? 'bg-blue-100 text-blue-900 font-semibold' : ''}
                ${isDone ? 'text-emerald-700' : ''}
                ${!isActive && !isDone ? 'text-slate-400' : ''}
              `}
            >
              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-sm
                ${isActive ? 'bg-blue-600 text-white' : ''}
                ${isDone ? 'bg-emerald-600 text-white' : ''}
                ${!isActive && !isDone ? 'bg-slate-200' : ''}
              `}>
                {isDone ? '✓' : step.id}
              </span>
              <span className="text-sm whitespace-nowrap">{step.label}</span>
            </button>
            {idx < STEPS.length - 1 && (
              <div className={`flex-1 h-px mx-2 ${isDone ? 'bg-emerald-300' : 'bg-slate-200'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export { STEPS }
