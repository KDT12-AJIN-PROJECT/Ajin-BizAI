import { useCallback, useEffect, useState } from 'react'
import { Download, FileText, FolderArchive, Loader2, Trash2, Upload, X } from 'lucide-react'
import { libraryApi } from '../../api/backendApi'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'

const CATEGORIES = ['전체', '회사자료', '첨부자료', '필요자료']
const UPLOAD_CATEGORIES = ['회사자료', '첨부자료', '필요자료']

function formatBytes(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toISOString().slice(0, 10).replace(/-/g, '.')
}

export default function MaterialsLibraryPage() {
  const [items, setItems] = useState([])
  const [category, setCategory] = useState('전체')
  const [sort, setSort] = useState('recent')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [uploadCategory, setUploadCategory] = useState('회사자료')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')

  const [selected, setSelected] = useState(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await libraryApi.list({ category, sort })
      setItems(res.items || [])
    } catch (e) {
      setError(e.message || '불러오기 실패')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [category, sort])

  useEffect(() => { reload() }, [reload])

  const onUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setUploading(true)
    setUploadError('')
    try {
      for (const file of files) {
        await libraryApi.upload({ file, category: uploadCategory })
      }
      await reload()
    } catch (err) {
      setUploadError(err.message || '업로드 실패')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const onDelete = async (fileId) => {
    if (!window.confirm('이 자료를 삭제할까요? (복구 불가)')) return
    try {
      await libraryApi.remove(fileId)
      if (selected?.file_id === fileId) setSelected(null)
      await reload()
    } catch (e) {
      alert('삭제 실패: ' + (e.message || ''))
    }
  }

  const openPreview = async (fileId) => {
    try {
      const res = await libraryApi.get(fileId)
      setSelected(res)
    } catch (e) {
      alert('상세 조회 실패: ' + (e.message || ''))
    }
  }

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-3 mb-5">
        <FolderArchive className="w-7 h-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold text-foreground">자료실</h1>
          <p className="text-sm text-muted-foreground">회사 자료 / 첨부 자료 / 필요 자료를 한 곳에서 관리합니다</p>
        </div>
      </div>

      {/* 업로드 영역 */}
      <Card className="mb-4">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Upload className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold">파일 업로드</span>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground">카테고리:</label>
              <select
                value={uploadCategory}
                onChange={(e) => setUploadCategory(e.target.value)}
                disabled={uploading}
                className="h-8 text-xs rounded border border-input bg-background px-2"
              >
                {UPLOAD_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <label className="block">
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.hwp,.hwpx,.xlsx,.xls,.png,.jpg,.jpeg"
              onChange={onUpload}
              disabled={uploading}
              className="hidden"
            />
            <div className={`border-2 border-dashed rounded-lg py-8 text-center transition cursor-pointer ${
              uploading ? 'border-muted bg-muted/30' : 'border-border hover:border-primary/40 hover:bg-primary/5'
            }`}>
              {uploading ? (
                <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" /> 업로드 중...
                </div>
              ) : (
                <>
                  <Upload className="w-7 h-7 mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm text-foreground font-medium">클릭해서 파일 선택 (다중 가능)</p>
                  <p className="text-xs text-muted-foreground mt-1">PDF · DOCX · HWP · XLSX · 이미지 — PDF는 내용까지 자동 추출됩니다</p>
                </>
              )}
            </div>
          </label>
          {uploadError && (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription className="text-xs">{uploadError}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* 정렬 + 카테고리 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5 flex-wrap">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategory(c)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                category === c
                  ? 'bg-foreground text-background border-foreground'
                  : 'bg-background text-muted-foreground border-border hover:border-foreground hover:text-foreground'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground">정렬:</label>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="h-8 text-xs rounded border border-input bg-background px-2"
          >
            <option value="recent">최근 업데이트순</option>
            <option value="name">이름순</option>
          </select>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      {/* 리스트 + 상세 */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2">
          <CardContent className="p-0">
            {loading ? (
              <div className="py-16 flex items-center justify-center text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> 불러오는 중...
              </div>
            ) : items.length === 0 ? (
              <div className="py-16 text-center text-muted-foreground">
                <FolderArchive className="w-10 h-10 mx-auto mb-3 opacity-40" />
                <p className="text-sm">등록된 자료가 없습니다.</p>
                <p className="text-xs mt-1">위 업로드 영역에서 파일을 추가하세요.</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {items.map((it) => (
                  <button
                    key={it.file_id}
                    type="button"
                    onClick={() => openPreview(it.file_id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/50 transition ${
                      selected?.file_id === it.file_id ? 'bg-primary/5' : ''
                    }`}
                  >
                    <FileText className="w-4 h-4 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">{it.file_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatBytes(it.file_size_bytes)} · {it.char_count?.toLocaleString() || 0}자
                        {it.parsed_text_truncated && ' (일부 잘림)'}
                      </p>
                    </div>
                    <Badge variant="blue" className="text-[11px] shrink-0">{it.category}</Badge>
                    <span className="text-xs text-muted-foreground w-20 text-right shrink-0">{formatDate(it.uploaded_at)}</span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onDelete(it.file_id) }}
                      className="p-1 text-muted-foreground hover:text-destructive transition shrink-0"
                      aria-label="삭제"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* 상세 패널 */}
        <Card className="col-span-1 sticky top-20 max-h-[calc(100vh-7rem)] overflow-hidden flex flex-col">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <span className="text-sm font-semibold">파일 상세</span>
            {selected && (
              <button onClick={() => setSelected(null)} className="text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
              </button>
            )}
          </CardHeader>
          <CardContent className="overflow-auto flex-1">
            {!selected ? (
              <p className="text-xs text-muted-foreground">왼쪽 리스트에서 파일을 선택하세요.</p>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="text-sm font-semibold text-foreground break-all">{selected.file_name}</p>
                  <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                    <Badge variant="blue" className="text-[10px]">{selected.category}</Badge>
                    <span className="text-[11px] text-muted-foreground">
                      {formatBytes(selected.file_size_bytes)} · {selected.char_count?.toLocaleString() || 0}자
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">업로드: {formatDate(selected.uploaded_at)}</p>
                  {selected.warning && (
                    <p className="text-[11px] text-amber-700 mt-1">⚠ {selected.warning}</p>
                  )}
                </div>
                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">내용 미리보기</p>
                  {selected.parsed_text ? (
                    <pre className="text-xs text-foreground whitespace-pre-wrap bg-muted/30 rounded p-3 border border-border leading-relaxed max-h-[60vh] overflow-auto">
                      {selected.parsed_text}
                    </pre>
                  ) : (
                    <p className="text-xs text-muted-foreground">텍스트 추출 결과가 없습니다.</p>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
