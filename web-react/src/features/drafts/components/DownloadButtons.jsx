/** .docx / .pdf 다운로드 버튼 (TODO: 실제 파일 생성 기능은 개발 예정) */
export default function DownloadButtons({ size = 'sm' }) {
  const cls = size === 'xs'
    ? 'px-3 py-1.5 text-xs border border-slate-300 rounded-md hover:bg-slate-50 inline-flex items-center gap-1'
    : 'px-4 py-1.5 text-sm border border-slate-300 rounded-md hover:bg-slate-50 inline-flex items-center gap-1.5'

  const handleDownload = (type) => {
    alert(`${type} 다운로드 기능은 개발 중입니다.`)
  }

  return (
    <>
      <button className={cls} onClick={() => handleDownload('.docx')}>
        <span className="text-blue-600">📄</span> .docx
      </button>
      <button className={cls} onClick={() => handleDownload('.pdf')}>
        <span className="text-rose-600">📕</span> .pdf
      </button>
    </>
  )
}
