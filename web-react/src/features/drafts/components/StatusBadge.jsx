const CONFIG = {
  '작성중':  'bg-blue-100 text-blue-800',
  '작성완료': 'bg-emerald-100 text-emerald-800',
  '제출완료': 'bg-violet-100 text-violet-800',
  '채택':    'bg-emerald-100 text-emerald-800',
  '미채택':  'bg-rose-100 text-rose-800',
  '미제출':  'bg-amber-100 text-amber-800',
}

export default function StatusBadge({ status }) {
  const cls = CONFIG[status] || 'bg-slate-100 text-slate-700'
  const label = status === '채택' ? '채택 진행' : status
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}
