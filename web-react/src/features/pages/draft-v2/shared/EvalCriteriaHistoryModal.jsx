// AJIN BizAI v0.2.1 V3 2차 — 변경 이력 sub-modal
//
// 트리거: EvalCriteriaMappingEditModal 좌측 패널의 "이력 N건" 클릭
// z-index: 60 (main modal 50보다 위)
// 닫기: ESC / backdrop / X / 닫기 버튼
//
// history 배열 entry 구조 (backend 결정):
//   { at, by, action: "create" | "update", snapshot? (create), changes? (update) }

import { useEffect } from 'react'
import { X, History } from 'lucide-react'

function formatAt(at) {
  if (!at) return '-'
  try {
    const d = new Date(at)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return String(at)
  }
}

function formatVal(v) {
  if (Array.isArray(v)) return `[${v.join(', ')}]`
  if (v === null || v === undefined) return '-'
  return String(v)
}

export default function EvalCriteriaHistoryModal({ open, history = [], criteriaName, onClose }) {
  useEffect(() => {
    if (!open) return
    const handleEsc = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  if (!open) return null

  const handleBackdrop = (e) => {
    if (e.target === e.currentTarget) onClose?.()
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4"
      onClick={handleBackdrop}
    >
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-xl max-h-[80vh] flex flex-col overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">변경 이력</h3>
            {criteriaName && (
              <span className="text-xs text-slate-500 font-mono bg-white border border-slate-200 rounded px-2 py-0.5">
                {criteriaName}
              </span>
            )}
            <span className="text-xs text-slate-400 ml-1">· {history.length}건</span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {history.length === 0 && (
            <div className="text-center text-xs text-slate-400 py-8">
              아직 변경 이력이 없습니다.
            </div>
          )}
          {history.map((entry, idx) => (
            <div key={idx} className="border border-slate-200 rounded-md overflow-hidden">
              <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100 flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2">
                  <span className={`px-1.5 py-0.5 rounded font-semibold ${
                    entry.action === 'create'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-indigo-100 text-indigo-800'
                  }`}>
                    {entry.action === 'create' ? '생성' : '수정'}
                  </span>
                  <span className="text-slate-500">{formatAt(entry.at)}</span>
                </div>
                <span className="text-slate-400 font-mono">by {entry.by}</span>
              </div>
              <div className="px-3 py-2 text-xs">
                {entry.action === 'create' && entry.snapshot && (
                  <div className="space-y-0.5 font-mono text-[11px]">
                    {Object.entries(entry.snapshot).map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <span className="text-slate-500 min-w-[120px]">{k}</span>
                        <span className="text-slate-700">{formatVal(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {entry.action === 'update' && entry.changes && (
                  <div className="space-y-1 font-mono text-[11px]">
                    {Object.entries(entry.changes).map(([k, [before, after]]) => (
                      <div key={k} className="flex gap-2 items-baseline">
                        <span className="text-slate-500 min-w-[120px]">{k}</span>
                        <span className="text-rose-600 line-through decoration-rose-300">{formatVal(before)}</span>
                        <span className="text-slate-400">→</span>
                        <span className="text-emerald-700 font-semibold">{formatVal(after)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="px-5 py-2.5 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs bg-white border border-slate-200 rounded hover:bg-slate-50"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  )
}
