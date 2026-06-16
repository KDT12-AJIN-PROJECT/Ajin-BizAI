/** 이전 버전 펼침 영역 — 목업 기준 bg-slate-50 */
export default function VersionHistory({ versions = [] }) {
  return (
    <div className="bg-slate-50 border-t border-slate-200 px-4 py-3 space-y-2">
      {versions.map(v => (
        <div key={v.id} className="flex items-center gap-3 text-xs">
          <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-200 text-slate-700 shrink-0 font-medium">
            v{v.version}
          </span>
          <div className="flex-1 min-w-0">
            {v.submitted_at && (
              <p className="text-slate-700">
                {v.submitted_at.slice(0, 10)} 제출
                {v.result && <span className="text-rose-600 font-medium ml-1">{v.result === '미채택' ? '보완 요청' : v.result}</span>}
              </p>
            )}
            {v.version_note && <p className="text-slate-500 mt-0.5">메모: {v.version_note}</p>}
          </div>
          <div className="flex gap-1 shrink-0">
            <button className="px-2 py-1 border border-slate-300 rounded hover:bg-white">상세</button>
            <button className="px-2 py-1 border border-slate-300 rounded hover:bg-white">.docx</button>
            <button className="px-2 py-1 border border-slate-300 rounded hover:bg-white">.pdf</button>
          </div>
        </div>
      ))}
      {versions.length >= 2 && (
        <p className="text-xs text-amber-700 italic mt-1">
          ⚠️ 다음 수정본 작성 시 가장 오래된 버전이 영구 삭제됩니다.
        </p>
      )}
    </div>
  )
}
