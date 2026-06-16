// AJIN BizAI v0.2 — Tab 2 중앙: 원본 PDF Preview (react-pdf 실통합)
// v0.3: backend /api/analysis/files/{file_id}/raw 에서 PDF binary 가져와 렌더링.
// 좌측 트리에서 문항 선택 시 해당 source_page로 자동 점프.

import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

export default function FormPreviewPanel({
  sessionId,
  formFileId,        // backend attachment file_id (PDF raw 다운로드용)
  formFileName,      // 표시용 파일명
  currentPage = 1,
  onPageChange,
  currentQuestion,
}) {
  const fileUrl = useMemo(() => {
    if (!sessionId || !formFileId) return null
    return `/api/analysis/files/${encodeURIComponent(formFileId)}/raw?session_id=${encodeURIComponent(sessionId)}`
  }, [sessionId, formFileId])

  const [numPages, setNumPages] = useState(0)
  const [page, setPage] = useState(currentPage)
  const [loadError, setLoadError] = useState(null)
  const containerRef = useRef(null)
  const [containerWidth, setContainerWidth] = useState(560)

  // 부모가 currentPage 바꾸면 (selectedQid → source_page) 동기화
  useEffect(() => {
    if (currentPage && currentPage !== page) setPage(currentPage)
  }, [currentPage])  // eslint-disable-line react-hooks/exhaustive-deps

  // 컨테이너 너비 추적 (반응형)
  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        // 너비의 95% 사용 (좌우 padding 약간)
        setContainerWidth(Math.max(300, Math.floor(w * 0.95)))
      }
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // 2026-05-18: wrap-around — 1에서 ‹ 누르면 numPages, numPages에서 › 누르면 1
  const goPrev = () => {
    if (!numPages) return
    const next = page <= 1 ? numPages : page - 1
    setPage(next)
    onPageChange?.(next)
  }
  const goNext = () => {
    if (!numPages) return
    const next = page >= numPages ? 1 : page + 1
    setPage(next)
    onPageChange?.(next)
  }

  // 파일 없는 경우 안내
  if (!fileUrl) {
    return (
      <div className="bg-slate-100 border border-slate-200 rounded-md flex items-center justify-center h-full">
        <div className="text-sm text-slate-500 text-center p-6">
          {sessionId
            ? '양식 파일이 업로드되지 않았습니다.'
            : '세션이 없습니다.'}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-100 border border-slate-200 rounded-md flex flex-col h-full overflow-hidden">
      {/* 툴바 */}
      <div className="px-3 py-2 bg-white border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm min-w-0">
          <span className="font-medium text-slate-900 truncate">{formFileName || '양식'}</span>
          <span className="font-mono text-xs text-slate-400">· {numPages || '-'}p</span>
          {currentQuestion && (
            <span className="ml-2 text-xs px-2 py-0.5 bg-indigo-50 text-indigo-900 rounded font-medium truncate">
              {currentQuestion}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={goPrev} disabled={!numPages}
            title={page <= 1 ? '마지막 페이지로' : '이전 페이지'}
            className="w-7 h-7 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-30">‹</button>
          <input
            type="number"
            value={page}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10) || 1
              const clamped = Math.min(numPages || v, Math.max(1, v))
              setPage(clamped)
              onPageChange?.(clamped)
            }}
            className="w-12 px-1 text-center text-sm border border-slate-200 rounded"
            min={1}
            max={numPages || 1}
          />
          <span className="text-xs text-slate-400">/ {numPages || '-'}</span>
          <button onClick={goNext} disabled={!numPages}
            title={page >= numPages ? '첫 페이지로' : '다음 페이지'}
            className="w-7 h-7 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-30">›</button>
        </div>
      </div>

      {/* PDF 렌더 영역 */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 flex justify-center bg-slate-200">
        {loadError ? (
          <div className="text-sm text-rose-700 self-center p-4 bg-white rounded">
            ⚠ PDF 로드 실패: {loadError}
          </div>
        ) : (
          <Document
            file={fileUrl}
            onLoadSuccess={({ numPages: n }) => {
              setNumPages(n)
              setLoadError(null)
            }}
            onLoadError={(err) => {
              console.warn('[PDF_LOAD_ERROR]', err)
              setLoadError(err?.message || '로드 오류')
            }}
            loading={<div className="text-sm text-slate-500 self-center p-4">PDF 로딩 중...</div>}
          >
            <Page
              pageNumber={page}
              width={containerWidth}
              renderAnnotationLayer={false}
              renderTextLayer={false}
              loading={<div className="text-sm text-slate-500 p-4">페이지 렌더 중...</div>}
            />
          </Document>
        )}
      </div>
    </div>
  )
}
