import { Download, ExternalLink, FileText, Image as ImageIcon, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { Alert, AlertDescription } from '../../../components/ui/alert'
import { Button } from '../../../components/ui/button'

// PDF.js 워커 설정
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()
// 파일 종류 판별 (HWP/이미지를 PDF보다 먼저 체크)
function getFileType(name = '', url = '') {
  const lname = name.toLowerCase()
  const lurl = url.toLowerCase()
  // name과 url을 분리해서 각각 체크 — 합치면 경계 오판 발생
  if (/\.(hwp|hwpx)(\?|$|\s|\.)/.test(lname) || /\.(hwp|hwpx)(\?|$|\.)/.test(lurl)) return 'hwp'
  if (/\.(jpg|jpeg|png|gif|webp)(\?|$)/.test(lname + lurl)) return 'image'
  if (/\.(doc|docx)(\?|$)/.test(lname + lurl)) return 'doc'
  if (/\.(xls|xlsx)(\?|$)/.test(lname + lurl)) return 'excel'
  if (/\.(zip|rar|7z)(\?|$)/.test(lname + lurl)) return 'archive'
  if (/\.pdf(\?|$)/.test(lname + lurl) || lurl.includes('getimagefile.do')) return 'pdf'
  return 'other'
}

// HWP/DOC/Excel 등 미리보기 불가 안내 + HWP는 backend prefetch로 텍스트 추출 지원
const UNSUPPORTED_LABELS = {
  hwp:     { icon: '📄', name: '한글(HWP)', desc: '브라우저에서는 미리보기가 안 됩니다. 아래 "본문 추출" 버튼을 누르면 텍스트만 보여드립니다.' },
  doc:     { icon: '📄', name: 'Word', desc: '브라우저에서 미리보기를 지원하지 않습니다.' },
  excel:   { icon: '📊', name: 'Excel', desc: '브라우저에서 미리보기를 지원하지 않습니다.' },
  archive: { icon: '🗜️', name: '압축', desc: 'ZIP/RAR 파일은 다운로드 후 압축을 풀어주세요.' },
  other:   { icon: '📎', name: '파일', desc: '미리보기를 지원하지 않는 형식입니다.' },
}

function UnsupportedView({ name, url, originalUrl, type }) {
  const info = UNSUPPORTED_LABELS[type] || UNSUPPORTED_LABELS.other
  const [extracting, setExtracting] = useState(false)
  const [extractedText, setExtractedText] = useState('')
  const [extractError, setExtractError] = useState('')

  const doExtract = async () => {
    if (extracting || extractedText) return
    setExtracting(true)
    setExtractError('')
    setExtractedText('')
    try {
      const backendUrl = originalUrl || url
      const res = await fetch('/api/files/prefetch-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: backendUrl, filename: name }),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({}))
        throw new Error(e.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      if (!data.parse_success) {
        setExtractError(data.warning || '텍스트 추출 실패')
      } else {
        setExtractedText(data.text || data.parsed_text || '(빈 본문)')
      }
    } catch (e) {
      setExtractError(e.message || '추출 실패')
    } finally {
      setExtracting(false)
    }
  }

  // HWP는 선택 즉시 자동 추출
  useEffect(() => {
    if (type === 'hwp') doExtract()
  }, [url]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-3">
      {/* 헤더: 추출 전이거나 비-HWP일 때만 표시 */}
      {(!extractedText || type !== 'hwp') && (
        <div className="flex flex-col items-center justify-center py-8 px-6 bg-amber-50 rounded-lg border border-amber-200">
          <div className="text-4xl mb-2">{info.icon}</div>
          <p className="text-sm font-semibold text-amber-900 mb-1">{info.name} 파일</p>
          <p className="text-xs text-amber-700 mb-3 text-center max-w-md">{info.desc}</p>
          <p className="text-xs text-muted-foreground mb-3 truncate max-w-md">{name}</p>
          <div className="flex items-center gap-2">
            {type === 'hwp' && (
              <Button size="sm" onClick={doExtract} disabled={extracting} className="gap-1.5">
                {extracting ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 추출 중...</> : <><FileText className="w-3.5 h-3.5" /> 본문 추출</>}
              </Button>
            )}
            <Button asChild size="sm" variant={type === 'hwp' ? 'outline' : 'default'} className="gap-1.5">
              <a href={url} download target="_blank" rel="noreferrer">
                <Download className="w-3.5 h-3.5" /> 다운로드
              </a>
            </Button>
          </div>
        </div>
      )}
      {extracting && !extractedText && (
        <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> HWP 본문 추출 중...
        </div>
      )}
      {extractError && (
        <Alert variant="destructive"><AlertDescription className="text-xs">{extractError}</AlertDescription></Alert>
      )}
      {extractedText && (
        <div className="bg-white border border-border rounded-lg">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">HWP 본문</p>
            <div className="flex items-center gap-2">
              <Button asChild size="sm" variant="ghost" className="gap-1 h-7 text-xs">
                <a href={url} download target="_blank" rel="noreferrer">
                  <Download className="w-3 h-3" /> 다운로드
                </a>
              </Button>
            </div>
          </div>
          <div className="text-xs text-foreground leading-relaxed max-h-[600px] overflow-auto p-4 space-y-1">
            {extractedText.split('\n').map((line, i) => {
              const trimmed = line.trim()
              if (!trimmed) return <div key={i} className="h-2" />
              if (/^\[서식\s*\d+\]/.test(trimmed))
                return <p key={i} className="font-bold text-sm text-primary mt-4 mb-1 border-b border-primary/20 pb-1">{trimmed}</p>
              if (/^[-─=]{3,}$/.test(trimmed))
                return <hr key={i} className="border-slate-200 my-2" />
              if (/^[■□▶▷◆◇•*※]/.test(trimmed) || /^\d+\./.test(trimmed))
                return <p key={i} className="pl-2 text-slate-700">{trimmed}</p>
              return <p key={i} className="text-slate-800">{trimmed}</p>
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// 이미지 뷰어
function ImageViewer({ url, name }) {
  const [error, setError] = useState(false)

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="text-xs">
          이미지를 불러올 수 없습니다.
          <a href={url} target="_blank" rel="noreferrer" className="ml-2 underline">
            새 창에서 열기
          </a>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="bg-slate-100 rounded-lg p-4 flex items-center justify-center min-h-[400px]">
      <img
        src={url}
        alt={name}
        className="max-w-full max-h-[800px] object-contain rounded shadow-sm"
        onError={() => setError(true)}
      />
    </div>
  )
}

// PDF 뷰어
function PdfViewer({ url, originalUrl, name }) {
  const [numPages, setNumPages] = useState(null)
  const [pageNumber, setPageNumber] = useState(1)
  const [error, setError] = useState('')
  const [scale, setScale] = useState(1.2)

  useEffect(() => {
    setNumPages(null)
    setPageNumber(1)
    setError('')
  }, [url])

  // 외부 URL은 CORS 때문에 react-pdf가 실패할 수 있음 → file 객체로 우선 fetch 시도
  const fileSource = useMemo(() => ({ url }), [url])

  return (
    <div className="bg-slate-100 rounded-lg overflow-hidden border border-border">
      {/* 컨트롤 바 */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-border">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            disabled={pageNumber <= 1}
          >
            이전
          </Button>
          <span className="text-xs text-muted-foreground min-w-[80px] text-center">
            {pageNumber} / {numPages || '-'}
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPageNumber((p) => Math.min(numPages || p, p + 1))}
            disabled={!numPages || pageNumber >= numPages}
          >
            다음
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={() => setScale((s) => Math.max(0.5, s - 0.2))}>−</Button>
          <span className="text-xs text-muted-foreground">{Math.round(scale * 100)}%</span>
          <Button size="sm" variant="ghost" onClick={() => setScale((s) => Math.min(2.5, s + 0.2))}>＋</Button>
            <Button size="sm" variant="outline" asChild>
            <a href={url} target="_blank" rel="noreferrer">
                <Download className="w-3 h-3" /> 다운로드
            </a>
            </Button>
        </div>
      </div>

      {/* PDF 본체 */}
      <div className="overflow-auto max-h-[800px] flex justify-center py-4">
        {error ? (
          <div className="text-center py-12 px-6">
            <FileText className="w-10 h-10 mx-auto mb-3 text-amber-500" />
            <p className="text-sm font-medium text-foreground mb-1">
              {/\.hwpx?(\?|$|\.)/i.test(`${name || ''} ${url || ''}`) ? 'hwp 파일을 불러올 수 없습니다' : 'PDF를 불러올 수 없습니다'}
            </p>
            <p className="text-xs text-muted-foreground mb-4">
              CORS 정책으로 차단되었거나 파일이 손상되었을 수 있습니다.
            </p>
            <Button asChild size="sm">
            <a href={originalUrl || url} target="_blank" rel="noreferrer">
                <ExternalLink className="w-3 h-3" /> 새 창에서 열기
            </a>
            </Button>
          </div>
        ) : (
          <Document
            file={fileSource}
            onLoadSuccess={({ numPages: n }) => { setNumPages(n); setError('') }}
            onLoadError={(err) => setError(err.message)}
            loading={
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-12">
                <Loader2 className="w-4 h-4 animate-spin" />
                PDF 로딩 중...
              </div>
            }
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              className="shadow-md"
            />
          </Document>
        )}
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function FileViewer({ file }) {
  if (!file?.url) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <FileText className="w-12 h-12 mb-4 opacity-40" />
        <p className="text-sm">미리볼 파일을 선택하세요.</p>
      </div>
    )
  }

  const fileType = getFileType(file.name, file.url)

  return (
    <div className="space-y-3">
      {/* 파일 정보 */}
      <div className="flex items-center justify-between bg-white rounded-lg border border-border px-4 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          {fileType === 'image' ? (
            <ImageIcon className="w-4 h-4 text-primary shrink-0" />
          ) : (
            <FileText className="w-4 h-4 text-primary shrink-0" />
          )}
          <span className="text-sm font-medium text-foreground truncate">{file.name}</span>
        </div>
        <Button asChild size="sm" variant="ghost">
        <a href={file.originalUrl || file.url} target="_blank" rel="noreferrer">
            <ExternalLink className="w-3 h-3" /> 원본 열기
        </a>
        </Button>
      </div>

        {/* 뷰어 */}
        {fileType === 'pdf' && <PdfViewer url={file.url} originalUrl={file.originalUrl} name={file.name} />}
        {fileType === 'image' && <ImageViewer url={file.url} name={file.name} />}
        {(fileType === 'hwp' || fileType === 'doc' || fileType === 'excel' || fileType === 'archive' || fileType === 'other') && (
        <UnsupportedView name={file.name} url={file.url} originalUrl={file.originalUrl} type={fileType} />
        )}
    </div>
  )
}