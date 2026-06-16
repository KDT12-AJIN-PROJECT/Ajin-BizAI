// AJIN BizAI v0.2 — Step 2 Summary Panel (요약 정보만)
// 출처: 사용자 분리 지시 (이전 Step2SummaryFooter에서 요약과 액션 분리)
//
// 좌측 = Tab별 stat / 우측 = 다음 단계 안내 hint
// 액션 버튼은 StepNavigationBar 별도 컴포넌트로 분리됨

export default function Step2SummaryPanel({ stats = [], hint }) {
  return (
    <div className="mt-6 bg-white border border-slate-200 rounded-md px-5 py-4">
      <div className="flex items-center gap-6 flex-wrap">
        {/* 좌측: 요약 stats */}
        <div className="flex items-center gap-6 flex-wrap flex-1 min-w-0">
          {stats.map((s, i) => (
            <div key={i} className={`flex flex-col gap-0.5 ${s.isText ? 'basis-full' : ''}`}>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                {s.label}
              </div>
              <div className="flex items-baseline gap-1">
                {s.chips ? (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {s.chips.map((chip, j) => (
                      <span
                        key={j}
                        className="text-[11px] px-1.5 py-0.5 rounded font-medium bg-slate-100 text-slate-700"
                      >
                        {chip.label}
                        {chip.value != null && <span className="ml-0.5 font-semibold">{chip.value}</span>}
                      </span>
                    ))}
                  </div>
                ) : s.isText ? (
                  // 자유 텍스트(예: 지원 한도) — 별도 행으로 내려가 전체 폭 사용 (basis-full) + 분석 본문 크기
                  <span
                    className={`text-sm font-medium leading-snug whitespace-normal break-words ${
                      s.highlight === 'red' ? 'text-red-600' : 'text-slate-800'
                    }`}
                    title={s.value}
                  >
                    {s.value}
                  </span>
                ) : (
                  <>
                    <span className={`text-lg font-bold ${s.highlight === 'red' ? 'text-red-600' : 'text-slate-900'}`}>
                      {s.value}
                    </span>
                    {s.suffix && <span className="text-xs text-slate-500">{s.suffix}</span>}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* 우측: 다음 단계 안내 */}
        {hint && (
          <div className="flex flex-col gap-0.5 text-right ml-auto">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              다음 단계 안내
            </div>
            <div className="text-xs text-slate-600 max-w-[360px]">{hint}</div>
          </div>
        )}
      </div>
    </div>
  )
}
