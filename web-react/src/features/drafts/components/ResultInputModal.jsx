/** 채택 / 미채택 결과 입력 모달 */
import { useState } from 'react'

export default function ResultInputModal({ draftId, onConfirm, onClose }) {
  const [result, setResult] = useState('채택')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [memo, setMemo] = useState('')
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try {
      await onConfirm(result, date ? new Date(date).toISOString() : null, memo || null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">결과 입력</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">결과</label>
              <div className="flex gap-3">
                {['채택', '미채택'].map(r => (
                  <button
                    key={r}
                    onClick={() => setResult(r)}
                    className={`flex-1 py-2 rounded-md text-sm font-medium border ${
                      result === r
                        ? r === '채택' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-rose-600 text-white border-rose-600'
                        : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">발표일</label>
              <input
                type="date"
                value={date}
                onChange={e => setDate(e.target.value)}
                className="w-full text-sm border border-slate-200 rounded-md px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">메모 (선택)</label>
              <textarea
                value={memo}
                onChange={e => setMemo(e.target.value)}
                rows={3}
                className="w-full text-sm border border-slate-200 rounded-md px-3 py-2 focus:outline-none focus:border-blue-500 resize-none"
                placeholder="심사 피드백, 보완 요청 내용 등..."
              />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 pb-6">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-slate-300 rounded-md hover:bg-slate-50">취소</button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="px-4 py-2 text-sm bg-slate-900 text-white rounded-md hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}
