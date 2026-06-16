// AJIN BizAI v0.2 — 분석 결과 확정 모달
// 출처: PRD §8 / §19.2 #12 / mockup_final.html (2089~2228)
// 트리거: Step 2 → Step 3 진입 시 부족자료 ≥1건 → 모달 표시

const MISSING_MOCK = [
  { qid: 'II-1', name: '시장 문제', count: 3, examples: ['고객 수요 설문', '경쟁사 비교표', '시장 규모 데이터'] },
  { qid: 'II-2', name: '지원 필요성', count: 2, examples: ['자체 자금 조달 시도 이력', '정부 지원 필요성 정량 근거'] },
  { qid: 'III-2', name: '사업화 전략', count: 2, examples: ['파트너사 LOI / MOU', '3년차 매출 목표 산출 근거'] },
]

export default function AnalysisConfirmModal({ open, onClose, onProceed, busy = false }) {
  if (!open) return null

  const totalMissing = MISSING_MOCK.reduce((s, m) => s + m.count, 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col">
        {/* 헤더 */}
        <div className="px-6 py-4 border-b border-slate-200">
          <div className="flex items-start gap-3">
            <span className="w-8 h-8 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold shrink-0">
              ⚠
            </span>
            <div>
              <h3 className="text-lg font-semibold text-slate-900">분석 결과 확정 — 부족자료 확인</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {MISSING_MOCK.length}개 문항에서 총 <strong>{totalMissing}건</strong>의 부족자료가 발견되었습니다
              </p>
            </div>
          </div>
        </div>

        {/* 본문 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-900 mb-4 leading-relaxed">
            부족자료를 보완하면 작성 품질이 향상됩니다. <br />
            지금 보완하지 않고 진행하면 해당 문항은 <strong>"근거 부족"</strong> 또는 <strong>"자료 없음"</strong> 상태로 Step 3에서 처리됩니다.
          </div>

          <div className="space-y-2.5">
            {MISSING_MOCK.map((m) => (
              <div key={m.qid} className="border border-slate-200 rounded p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500">{m.qid}</span>
                    <span className="text-sm font-medium text-slate-900">{m.name}</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded font-medium">
                    {m.count}건 부족
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {m.examples.map((ex, i) => (
                    <span key={i} className="text-[11px] px-2 py-0.5 bg-slate-50 text-slate-600 rounded">
                      {ex}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 text-[11px] text-slate-500 leading-relaxed">
            🔒 PRD §8 / §19.2 #12 — 부족자료가 있으면 모달 분기. 사용자 명시 동의 후에만 차단된 문항으로 진행 가능.
          </div>
        </div>

        {/* 액션 */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex flex-col sm:flex-row gap-2 sm:justify-end">
          <button
            onClick={onClose}
            className="text-sm px-4 py-2 border border-slate-200 bg-white rounded hover:bg-slate-50"
          >
            ← 부족자료 보완 후 진행
          </button>
          <button
            onClick={onProceed}
            disabled={busy}
            className="text-sm px-4 py-2 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? '확정 중...' : 'Step 3으로 진행 →'}
          </button>
        </div>
      </div>
    </div>
  )
}
