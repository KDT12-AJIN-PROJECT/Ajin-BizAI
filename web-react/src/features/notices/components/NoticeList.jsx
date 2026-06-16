export default function NoticeList({ notices, selectedId, onSelect }) {
  if (notices.length === 0) {
    return <div className="panel">표시할 공고가 없습니다.</div>
  }

  return (
    <div className="panel list-panel">
      {notices.map((notice) => (
        <button
          type="button"
          key={notice.id}
          className={`notice-item ${selectedId === notice.id ? 'active' : ''}`}
          onClick={() => onSelect(notice)}
        >
          <strong>{notice.title}</strong>
          <span>{notice.agency}</span>
          <small>{notice.period || '기간 정보 없음'}</small>
        </button>
      ))}
    </div>
  )
}
