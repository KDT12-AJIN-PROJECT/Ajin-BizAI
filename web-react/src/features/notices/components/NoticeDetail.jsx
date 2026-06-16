export default function NoticeDetail({ notice }) {
  if (!notice) {
    return <div className="panel">왼쪽 목록에서 공고를 선택하세요.</div>
  }

  return (
    <div className="panel detail-panel">
      <h2>{notice.title}</h2>
      <p><b>기관:</b> {notice.agency}</p>
      <p><b>지원대상:</b> {notice.target || '-'}</p>
      <p><b>기간:</b> {notice.period || '-'}</p>
      <p><b>지원내용:</b> {notice.benefit || '-'}</p>
      <p><b>요약:</b> {notice.content || '-'}</p>
      {notice.rawUrl ? (
        <a href={notice.rawUrl} target="_blank" rel="noreferrer">
          원문 링크 열기
        </a>
      ) : (
        <span>원문 링크 없음</span>
      )}
    </div>
  )
}
