/** v4 시도 시 교체할 버전 선택 모달 */
import { useState } from 'react'

export default function VersionReplaceModal({ versions = [], onConfirm, onClose }) {
  const [selected, setSelected] = useState(versions[versions.length - 1]?.version)
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    try { await onConfirm(selected) } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-2">버전 교체</h2>
          <p className="text-sm text-slate-500 mb-4">
            버전이 3개입니다. 새 버전을 저장하려면 기존 버전 하나를 선택해 교체하세요.
          </p>
          <div className="space-y-2">
            {versions.map(v => (
              <label key={v.version} className="flex items-center gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
                <input
                  type="radio"
                  name="replace_version"
                  value={v.version}
                  checked={selected === v.version}
                  onChange={() => setSelected(v.version)}
                  className="w-4 h-4"
                />
                <div>
                  <span className="text-sm font-medium text-slate-900">v{v.version}</span>
                  {v.version_note && <span className="text-xs text-slate-500 ml-2">{v.version_note}</span>}
                </div>
              </label>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 pb-6">
          <button onClick={onClose} className="px-4 py-2 text-sm border border-slate-300 rounded-md hover:bg-slate-50">취소</button>
          <button
            onClick={handleConfirm}
            disabled={loading || !selected}
            className="px-4 py-2 text-sm bg-rose-600 text-white rounded-md hover:bg-rose-700 disabled:opacity-50"
          >
            {loading ? '처리 중...' : `v${selected} 교체 후 새 버전 시작`}
          </button>
        </div>
      </div>
    </div>
  )
}
