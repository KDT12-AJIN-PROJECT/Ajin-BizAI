// AJIN BizAI — Step 1 Upload Common (V1·V2 공용)
// 출처: V1 DraftPage.jsx 의 Step1Upload 함수 추출 (시각 동일 유지)
// variant 분기:
//   - "v1" → 3 카드 (공고문/제출양식/참고자료) 기존 동작 그대로
//   - "v2" → 3 카드 + 4번째 기업프로필 자료 카드 (선택만, PRD §3.2)
//
// 사용처:
//   - /draft     (V1 DraftPage.jsx)
//   - /draft-v2  (V2 DraftPageV2.jsx)

import { useEffect, useState } from 'react'
import {
  AlertCircle, Building2, CheckCircle2, FilePlus, FileText,
  Loader2, Settings, Upload, RefreshCw, X,
} from 'lucide-react'

// 우선순위 순서로 유효한 http/https URL 반환. 없으면 null + console.warn
function resolveNoticeUrl(notice) {
  if (!notice) return null
  const fields = [
    ['url',                notice.url],
    ['pblancUrl',          notice.pblancUrl],
    ['rceptEngnHmpgUrl',   notice.rceptEngnHmpgUrl],
    ['rcept_engn_hmpg_url',notice.rcept_engn_hmpg_url],
    ['printFlpthNm',       notice.printFlpthNm],
    ['print_flpth_nm',     notice.print_flpth_nm],
    ['flpthNm',            notice.flpthNm],
    ['flpth_nm',           notice.flpth_nm],
  ]
  for (const [, val] of fields) {
    if (val && /^https?:\/\//i.test(String(val))) return String(val)
  }
  console.warn('[원본확인] 유효한 URL 없음. 후보 필드 값:', Object.fromEntries(fields))
  return null
}
import { analysisApi, companyApi, noticesApi } from '../../api/backendApi'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Card, CardContent } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { cn } from '../../lib/utils'

// 파일 크기 포맷
function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export default function Step1Common({
  variant = 'v1',
  notice,
  onNoticeReset = null,
  uploads,
  onUploadsChange,
  selectedCompanyFileIds = [],
  onCompanyFileToggle,
  sessionId = null,  // Phase 4-H A1: 있으면 multipart 업로드 → JSON-piggyback 영속화
}) {
  const noticeAttachments = notice ? [
    notice.printFileNm || '공고문 본문',
    notice.fileNm?.split('@').filter(Boolean) || [],
  ].flat().filter(Boolean) : []

  // Phase 4-H A1: 업로드 중 표시 (kind별)
  const [uploading, setUploading] = useState({ notice: false, form: false })
  const [autoLoading, setAutoLoading] = useState(false)
  const [autoLoadError, setAutoLoadError] = useState('')
  const [enrichedNotice, setEnrichedNotice] = useState(null)

  // printFlpthNm 없으면 DB에서 최신 데이터로 보강 (북마크/저장 초안 경로 대응)
  useEffect(() => {
    const hasFileUrl = notice?.printFlpthNm || notice?.print_flpth_nm ||
                       notice?.flpthNm || notice?.flpth_nm
    if (hasFileUrl) return
    // 1차: ID로 직접 조회
    const tryById = notice?.id
      ? noticesApi.getById(notice.id).catch(() => null)
      : Promise.resolve(null)
    // 2차: 제목+출처 검색 폴백
    tryById.then(data => {
      if (data?.printFlpthNm || data?.flpthNm) {
        setEnrichedNotice(data)
        return
      }
      const q = notice?.title?.slice(0, 30)
      if (!q) return
      fetch(`/api/notices/search?q=${encodeURIComponent(q)}&limit=10`)
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          const match = (d?.notices || []).find(n =>
            n.title === notice.title && (n.printFlpthNm || n.flpthNm)
          )
          if (match) setEnrichedNotice(match)
        })
        .catch(() => {})
    })
  }, [notice?.id, notice?.title]) // eslint-disable-line react-hooks/exhaustive-deps

  const effectiveNotice = enrichedNotice || notice

  const handleAutoLoadNotice = async () => {
    const fileUrl = effectiveNotice?.printFlpthNm || effectiveNotice?.print_flpth_nm ||
                    effectiveNotice?.flpthNm || effectiveNotice?.flpth_nm
    if (!fileUrl) {
      setAutoLoadError('공고문 파일 URL이 없습니다. 직접 업로드해 주세요.')
      return
    }
    setAutoLoading(true)
    setAutoLoadError('')
    try {
      const filename = notice?.printFileNm || notice?.print_file_nm || '공고문'
      let meta
      if (sessionId) {
        meta = await analysisApi.uploadFromUrl({ sessionId, kind: 'notice', url: fileUrl, filename })
        meta = { file_id: meta.file_id, name: meta.file_name, size: meta.size_bytes,
                  ext: meta.ext, char_count: meta.char_count, parse_success: meta.parse_success,
                  warning: meta.warning, persisted: true }
      } else {
        // sessionId 없음(V1): 백엔드로 다운로드만 하고 텍스트 반환
        const res = await fetch('/api/files/prefetch-url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: fileUrl, filename }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        meta = { __local: true, name: filename, size: data.size_bytes || 0,
                  parsed_text: data.parsed_text, parse_success: data.parse_success }
      }
      onUploadsChange({ ...uploads, noticeFiles: [...(uploads.noticeFiles || []), meta] })
    } catch (e) {
      setAutoLoadError(e.message || '자동 불러오기 실패')
    } finally {
      setAutoLoading(false)
    }
  }

  // Phase 4-H A3: CompanyFile 실제 API 연동
  const [companyFiles, setCompanyFiles] = useState([])
  const [companyLoading, setCompanyLoading] = useState(false)
  const [companyError, setCompanyError] = useState(null)

  const loadCompanyFiles = async () => {
    if (variant !== 'v2') return
    setCompanyLoading(true)
    setCompanyError(null)
    try {
      const res = await companyApi.listFiles({ companyProfileId: 'anonymous' })
      setCompanyFiles(res.items || [])
    } catch (err) {
      console.warn('[COMPANY_FILES_LOAD_FAILED]', err)
      setCompanyError(err.message || 'CompanyFile 목록 조회 실패')
      setCompanyFiles([])
    } finally {
      setCompanyLoading(false)
    }
  }

  useEffect(() => {
    if (variant === 'v2') loadCompanyFiles()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variant])

  // 단일 파일 업로드 — sessionId 있으면 backend, 없으면 File 객체 그대로 push (V1 호환)
  async function uploadOne(kind, file) {
    if (!sessionId) {
      return { __local: true, name: file.name, size: file.size, file }
    }
    try {
      const res = await analysisApi.uploadFile({ sessionId, kind, file })
      return {
        file_id: res.file_id,
        name: res.file_name,
        size: res.size_bytes,
        ext: res.ext,
        parsed_text: undefined,           // listFiles 또는 별도 fetch 시 채움
        char_count: res.char_count,
        parsed_text_stored_char_count: res.parsed_text_stored_char_count,
        parsed_text_truncated: res.parsed_text_truncated,
        parse_success: res.parse_success,
        warning: res.warning,
        persisted: true,
      }
    } catch (err) {
      console.warn('[STEP1_UPLOAD_FAILED]', kind, file?.name, err)
      return { __local: true, name: file.name, size: file.size, file, upload_error: err.message }
    }
  }

  async function uploadMany(kind, fileList, currentList, onChange) {
    const arr = Array.from(fileList || [])
    if (!arr.length) return
    if (sessionId) setUploading(prev => ({ ...prev, [kind]: true }))
    const uploaded = []
    for (const f of arr) {
      const meta = await uploadOne(kind, f)
      uploaded.push(meta)
    }
    if (sessionId) setUploading(prev => ({ ...prev, [kind]: false }))
    onChange([...currentList, ...uploaded])
  }

  const refFiles = uploads.references || []
  // C-5a (v3.2): references도 backend 업로드 (kind="reference")
  //   sessionId 있으면 backend persisted, 없으면 V1 호환 client-side state.
  //   raw_b64 미저장 (C-1 §"raw binary 저장 금지" 정책).
  const handleRefFiles = (newFiles) => {
    if (!newFiles) return
    uploadMany('reference', newFiles, refFiles,
      (next) => onUploadsChange({ ...uploads, references: next }))
  }
  const removeRefFile = async (idx) => {
    const target = refFiles[idx]
    if (sessionId && target?.file_id) {
      try { await analysisApi.deleteFile({ sessionId, fileId: target.file_id }) }
      catch (err) { console.warn('[STEP1_DELETE_REF_FAILED]', target.file_id, err) }
    }
    const next = refFiles.filter((_, i) => i !== idx)
    onUploadsChange({ ...uploads, references: next })
  }
  const removeAllRefs = async () => {
    if (sessionId) {
      for (const f of refFiles) {
        if (f?.file_id) {
          try { await analysisApi.deleteFile({ sessionId, fileId: f.file_id }) }
          catch (err) { console.warn('[STEP1_DELETE_REF_FAILED]', f.file_id, err) }
        }
      }
    }
    onUploadsChange({ ...uploads, references: [] })
  }

  const noticeFiles = uploads.noticeFiles || []
  const handleNoticeFiles = (newFiles) => {
    if (!newFiles) return
    uploadMany('notice', newFiles, noticeFiles,
      (next) => onUploadsChange({ ...uploads, noticeFiles: next }))
  }
  const removeNoticeFile = async (idx) => {
    const target = noticeFiles[idx]
    if (sessionId && target?.file_id) {
      try { await analysisApi.deleteFile({ sessionId, fileId: target.file_id }) }
      catch (err) { console.warn('[STEP1_DELETE_FAILED]', err) }
    }
    onUploadsChange({ ...uploads, noticeFiles: noticeFiles.filter((_, i) => i !== idx) })
  }

  const formFiles = uploads.formFiles || []
  const handleFormFiles = (newFiles) => {
    if (!newFiles) return
    uploadMany('form', newFiles, formFiles,
      (next) => onUploadsChange({ ...uploads, formFiles: next }))
  }
  const removeFormFile = async (idx) => {
    const target = formFiles[idx]
    if (sessionId && target?.file_id) {
      try { await analysisApi.deleteFile({ sessionId, fileId: target.file_id }) }
      catch (err) { console.warn('[STEP1_DELETE_FAILED]', err) }
    }
    onUploadsChange({ ...uploads, formFiles: formFiles.filter((_, i) => i !== idx) })
  }
  const removeAllFormFiles = async () => {
    if (sessionId) {
      for (const f of formFiles) {
        if (f?.file_id) {
          try { await analysisApi.deleteFile({ sessionId, fileId: f.file_id }) }
          catch (err) { console.warn('[STEP1_DELETE_FAILED]', err) }
        }
      }
    }
    onUploadsChange({ ...uploads, formFiles: [] })
  }

  const [dragOver, setDragOver] = useState(false)
  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleRefFiles(e.dataTransfer.files)
  }

  const [formDragOver, setFormDragOver] = useState(false)
  const handleFormDrop = (e) => {
    e.preventDefault()
    setFormDragOver(false)
    handleFormFiles(e.dataTransfer.files)
  }

  const totalRefSize = refFiles.reduce((sum, f) => sum + (f.size || 0), 0)
  const totalFormSize = formFiles.reduce((sum, f) => sum + (f.size || 0), 0)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-foreground mb-1">자료 업로드</h3>
          <p className="text-sm text-muted-foreground">
            공고문 · 제출양식 · 참고자료 3종을 업로드하세요. 자료가 부족해도 1차 초안은 만들 수 있습니다.
          </p>
        </div>
        <span className="text-[11px] px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 font-semibold whitespace-nowrap">
          ● 자료 업로드 단계
        </span>
      </div>

      {/* ── 1. 공고문 ── */}
      <Card className="border-green-200 bg-green-50/50">
        <CardContent className="px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-white border border-green-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-sm font-bold text-foreground">1. 공고문</h4>
                  {notice && (
                    <button
                      type="button"
                      onClick={handleAutoLoadNotice}
                      disabled={autoLoading}
                      className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border border-green-400 bg-green-50 text-green-700 hover:bg-green-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {autoLoading
                        ? <><Loader2 className="w-3 h-3 animate-spin" /> 불러오는 중...</>
                        : <><RefreshCw className="w-3 h-3" /> 공고 원문 자동 불러오기</>}
                    </button>
                  )}
                </div>
                {notice?.title && (
                  <p className="text-xs font-semibold text-foreground truncate max-w-md mb-0.5" title={notice.title}>
                    {notice.title}
                  </p>
                )}
                {(() => {
                  const deadline = notice?.date instanceof Date && !isNaN(notice.date.getTime())
                    ? notice.date.toISOString().slice(0, 10)
                    : null
                  const parts = []
                  if (notice?.origin) parts.push(`출처: ${notice.origin}`)
                  if (notice?.period) parts.push(`기간: ${notice.period}`)
                  if (deadline) parts.push(`마감일: ${deadline}`)
                  return parts.length > 0 ? (
                    <p className="text-xs text-muted-foreground">
                      {parts.map((t, i) => (
                        <span key={i}>
                          {i > 0 && <span className="mx-1.5">·</span>}
                          {t}
                        </span>
                      ))}
                    </p>
                  ) : null
                })()}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {onNoticeReset && notice && (
                <button
                  type="button"
                  disabled
                  className="text-xs font-medium flex items-center px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-slate-300 cursor-not-allowed"
                  title="공고 재선택은 검색 화면으로 돌아가세요"
                >
                  원본 초기화
                </button>
              )}
              {(() => {
                const targetUrl = resolveNoticeUrl(notice)
                return (
                  <button
                    type="button"
                    className={`text-sm font-bold flex items-center px-5 py-1.5 rounded-lg border bg-white transition-colors ${
                      targetUrl
                        ? 'text-red-600 hover:text-red-700 border-border cursor-pointer'
                        : 'text-slate-300 border-slate-200 cursor-not-allowed'
                    }`}
                    onClick={() => targetUrl && window.open(targetUrl, '_blank')}
                    disabled={!targetUrl}
                    title={targetUrl || 'URL 정보 없음'}
                  >
                    원본확인
                  </button>
                )
              })()}
            </div>
          </div>
          {autoLoadError && (
            <p className="mt-2 text-xs text-red-600">{autoLoadError}</p>
          )}
          <div className="mt-3 pt-3 border-t border-green-200">
            <p className="text-xs text-muted-foreground mb-2">공고문 파일을 직접 추가할 수도 있습니다.</p>
            <label className="cursor-pointer">
              <Input
                type="file"
                multiple
                accept=".pdf,.docx,.hwp,.hwpx"
                className="hidden"
                onChange={(e) => handleNoticeFiles(e.target.files)}
              />
              <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-green-300 bg-white text-xs font-medium text-green-700 hover:bg-green-50 transition-colors">
                <Upload className="w-3.5 h-3.5" /> 공고문 파일 추가
              </span>
            </label>
            {noticeFiles.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {noticeFiles.map((file, idx) => (
                  <div
                    key={file.file_id || idx}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-green-200 bg-white"
                  >
                    <FileText className="w-3.5 h-3.5 shrink-0 text-green-600" />
                    <p className="text-xs font-medium flex-1 truncate">{file.name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {formatFileSize(file.size)}
                      {file.upload_error && <span className="text-amber-600 ml-2">⚠️ 업로드 실패</span>}
                      {file.parsed_text_truncated && (
                        <span className="text-amber-600 ml-2" title="200K char 초과 — 일부만 저장">
                          ⚠️ 일부만 저장 ({file.parsed_text_stored_char_count?.toLocaleString()}/{file.char_count?.toLocaleString()})
                        </span>
                      )}
                    </p>
                    {file.file_id && (
                      <Badge variant="success" className="text-[10px] px-1.5 h-4 shrink-0">
                        <CheckCircle2 className="w-2.5 h-2.5" />
                      </Badge>
                    )}
                    <button
                      type="button"
                      onClick={() => removeNoticeFile(idx)}
                      className="w-5 h-5 rounded hover:bg-destructive/10 flex items-center justify-center text-muted-foreground hover:text-destructive"
                      aria-label="삭제"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {uploading.notice && (
                  <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> 업로드 중...
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── 2. 제출양식 ── */}
      <Card>
        <CardContent className="px-5 py-4">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center flex-shrink-0">
              <FileText className="w-4 h-4 text-muted-foreground" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-0.5">
                <h4 className="text-sm font-bold text-foreground">2. 제출양식</h4>
                <Badge variant="outline" className="text-[10px]">선택</Badge>
              </div>
              <p className="text-xs text-muted-foreground">기관 별 별첨 양식이 따로 있다면 업로드하세요 (.docx, .pdf, .hwp)</p>
            </div>
          </div>

          {/* 드래그 앤 드롭 영역 */}
          <div
            onDragOver={(e) => { e.preventDefault(); setFormDragOver(true) }}
            onDragLeave={() => setFormDragOver(false)}
            onDrop={handleFormDrop}
            className={cn(
              'border-2 border-dashed rounded-xl py-8 px-6 text-center transition-colors',
              formDragOver ? 'border-[#1B3464] bg-blue-50' : 'border-border bg-[#F4F6FB]',
            )}
          >
            <div className={cn(
              'w-11 h-11 rounded-xl mx-auto flex items-center justify-center mb-3 shadow-sm transition-colors',
              formDragOver ? 'bg-[#1B3464] text-white' : 'bg-white text-[#1B3464]',
            )}>
              <Upload className="w-5 h-5" />
            </div>
            <p className="text-sm font-semibold text-foreground mb-1">파일을 드래그하거나 클릭해서 업로드</p>
            <p className="text-xs text-muted-foreground mb-4">
              DOCX · PDF · HWP / 파일당 최대 200MB · 다중 선택 가능
            </p>
            <label className="cursor-pointer">
              <Input
                type="file"
                multiple
                accept=".pdf,.docx,.hwp,.hwpx"
                className="hidden"
                onChange={(e) => handleFormFiles(e.target.files)}
              />
              <span className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-[#1B3464] text-white text-xs font-bold hover:bg-[#1B3464]/90 transition-colors">
                <FilePlus className="w-3.5 h-3.5" />
                파일 선택
              </span>
            </label>
          </div>

          {/* 업로드된 파일 리스트 */}
          {formFiles.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-foreground">
                  업로드된 파일 · {formFiles.length}개 · {formatFileSize(totalFormSize)}
                </p>
                <button
                  type="button"
                  onClick={removeAllFormFiles}
                  className="text-xs text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1"
                >
                  <X className="w-3 h-3" />모두 삭제
                </button>
              </div>
              <div className="space-y-1.5 max-h-[200px] overflow-y-auto pr-1">
                {formFiles.map((file, idx) => (
                  <div
                    key={file.file_id || `${file.name}-${idx}`}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-white"
                  >
                    <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{file.name}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {formatFileSize(file.size)}
                        {file.upload_error && <span className="text-amber-600 ml-2">⚠️ 업로드 실패</span>}
                        {file.parsed_text_truncated && (
                          <span className="text-amber-600 ml-2" title="200K char 초과 — 일부만 저장">
                            ⚠️ 일부만 저장 ({file.parsed_text_stored_char_count?.toLocaleString()}/{file.char_count?.toLocaleString()})
                          </span>
                        )}
                        {!file.file_id && !file.upload_error && !file.file && (
                          <span className="text-amber-600 ml-2">⚠️ 재업로드 필요</span>
                        )}
                      </p>
                    </div>
                    {file.file_id && (
                      <Badge variant="success" className="text-[10px] px-1.5 h-4 shrink-0">
                        <CheckCircle2 className="w-2.5 h-2.5" />
                      </Badge>
                    )}
                    <button
                      type="button"
                      onClick={() => removeFormFile(idx)}
                      className="w-5 h-5 rounded hover:bg-destructive/10 flex items-center justify-center text-muted-foreground hover:text-destructive transition-colors"
                      aria-label="삭제"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {uploading.form && (
                  <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> 업로드 중...
                  </div>
                )}
              </div>
            </div>
          )}

        </CardContent>
      </Card>

      {/* ── 3. 참고자료 ── */}
      <Card>
        <CardContent className="px-5 py-4">
          <div className="flex items-center justify-between gap-2 mb-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center flex-shrink-0">
                <Upload className="w-4 h-4 text-muted-foreground" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-foreground mb-0.5">3. 참고자료</h4>
                <p className="text-xs text-muted-foreground">공고작성에 필요한 참고자료</p>
              </div>
            </div>
            {refFiles.length > 0 && (
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {refFiles.length}개 · {formatFileSize(totalRefSize)}
              </span>
            )}
          </div>

          {/* 드래그 앤 드롭 영역 */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={cn(
              'border-2 border-dashed rounded-xl py-10 px-6 text-center transition-colors',
              dragOver ? 'border-[#1B3464] bg-blue-50' : 'border-border bg-[#F4F6FB]',
            )}
          >
            <div className={cn(
              'w-11 h-11 rounded-xl mx-auto flex items-center justify-center mb-3 shadow-sm transition-colors',
              dragOver ? 'bg-[#1B3464] text-white' : 'bg-white text-[#1B3464]',
            )}>
              <Upload className="w-5 h-5" />
            </div>
            <p className="text-sm font-semibold text-foreground mb-1">파일을 드래그하거나 클릭해서 한번에 업로드</p>
            <p className="text-xs text-muted-foreground mb-4">
              PDF · DOCX · XLSX · 이미지 / 파일당 최대 200MB · 다중 선택 가능
            </p>
            <label className="cursor-pointer">
              <Input
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.xls,.hwp,.hwpx,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => handleRefFiles(e.target.files)}
              />
              <span className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-lg bg-[#1B3464] text-white text-xs font-bold hover:bg-[#1B3464]/90 transition-colors">
                <FilePlus className="w-3.5 h-3.5" />
                파일 선택
              </span>
            </label>
          </div>

          {/* 업로드된 파일 리스트 */}
          {refFiles.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-foreground">업로드된 파일</p>
                <button
                  type="button"
                  onClick={removeAllRefs}
                  className="text-xs text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1"
                >
                  <X className="w-3 h-3" />모두 삭제
                </button>
              </div>
              <div className="space-y-1.5 max-h-[240px] overflow-y-auto pr-1">
                {refFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-white"
                  >
                    <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">{file.name}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {formatFileSize(file.size)}
                        {!file.file && !file.file_id && (
                          <span className="text-amber-600 ml-2">⚠️ 재업로드 필요 (A3)</span>
                        )}
                      </p>
                    </div>
                    <Badge variant="success" className="text-[10px] px-1.5 h-4 shrink-0">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                    </Badge>
                    <button
                      type="button"
                      onClick={() => removeRefFile(idx)}
                      className="w-5 h-5 rounded hover:bg-destructive/10 flex items-center justify-center text-muted-foreground hover:text-destructive transition-colors"
                      aria-label="삭제"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Alert variant="info" className="mt-3">
            <AlertCircle className="w-4 h-4" />
            <AlertDescription className="text-xs">
              업로드한 자료는 <strong>자동 분류</strong>되어 사업계획서 항목별로 매핑됩니다.
              긴 문서는 페이지·섹션 단위로 청킹되어 필요한 부분만 작성에 사용됩니다.
              자료가 부족해도 1차 초안 작성은 가능합니다.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* ── 4. 기업프로필 자료 (V2 전용, PRD §3.2 / §13.10) ── */}
      {variant === 'v2' && (
        <Card>
          <CardContent className="px-5 py-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center flex-shrink-0">
                <Building2 className="w-4 h-4 text-muted-foreground" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <h4 className="text-sm font-bold text-foreground">4. 기업프로필 자료</h4>
                  <Badge variant="outline" className="text-[10px]">선택만</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  기업설정에서 업로드·관리하며, 이번 공고에 사용할 자료만 선택합니다.
                </p>
              </div>
            </div>

            {/* 저장된 기업자료 체크박스 리스트 — A3: 실제 GET /api/company/files */}
            <div className="space-y-1.5 mb-4">
              {companyLoading && (
                <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> 기업자료 목록 로딩...
                </div>
              )}
              {companyError && !companyLoading && (
                <div className="px-3 py-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded">
                  ⚠️ {companyError}
                </div>
              )}
              {!companyLoading && !companyError && companyFiles.length === 0 && (
                <div className="px-3 py-3 text-xs text-muted-foreground text-center border border-dashed border-border rounded">
                  저장된 기업자료가 없습니다. 기업설정에서 업로드하세요.
                </div>
              )}
              {companyFiles.map((f) => {
                const isSelected = selectedCompanyFileIds.includes(f.file_id)
                const uploadedDate = f.uploaded_at?.slice(0, 10) || ''
                return (
                  <label
                    key={f.file_id}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-lg border bg-white cursor-pointer transition-colors',
                      isSelected
                        ? 'border-[#1B3464] bg-blue-50/50'
                        : 'border-border hover:bg-muted/40',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onCompanyFileToggle?.(f.file_id)}
                      className="shrink-0"
                    />
                    <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <p className="text-xs font-medium text-foreground flex-1 truncate">{f.file_name}</p>
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">{f.file_type}</span>
                    <span className="text-[10px] text-muted-foreground/70 whitespace-nowrap">{uploadedDate}</span>
                  </label>
                )
              })}
            </div>

            {/* 버튼 2개 */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => alert('기업설정 페이지는 v0.3에서 제공됩니다 (PRD §13.10). 현재는 API 직접 호출만 가능.')}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border bg-white text-xs font-medium text-foreground hover:bg-muted/40 transition-colors"
              >
                <Settings className="w-3.5 h-3.5" />
                기업설정에서 자료 관리
              </button>
              <button
                type="button"
                onClick={loadCompanyFiles}
                disabled={companyLoading}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border bg-white text-xs font-medium text-foreground hover:bg-muted/40 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={cn('w-3.5 h-3.5', companyLoading && 'animate-spin')} />
                저장된 기업자료 불러오기
              </button>
            </div>

            <p className="mt-3 text-[10px] text-muted-foreground">
              🔒 직접 업로드는 기업설정에서만 가능 (PRD §3.2 / §13.10 CompanyFile) — 기업설정 페이지 v0.3 예정
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
