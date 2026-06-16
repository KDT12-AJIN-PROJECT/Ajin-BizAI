import {
  AlertCircle, ArrowLeft, ArrowRight, Award, Bookmark,
  CheckCircle2, ExternalLink, FileText, Loader2, MapPin,
  MessageCircle, Phone, Sparkles, Target, TrendingUp,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { generateNoticeSummary } from '../../api/lmStudioApi'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Separator } from '../../components/ui/separator'
import { cn } from '../../lib/utils'
import FileViewer from '../notices/components/FileViewer'
import { formatDate, getDdayText } from '../notices/utils/date'
import { parseAttachmentList } from '../notices/utils/normalize'

// ── 정보 항목 (label + value) ─────────────────────────────────────
function InfoChip({ label, value, color = 'blue' }) {
  const colorClasses = {
    blue: 'bg-blue-50 border-blue-100 text-blue-900',
    green: 'bg-green-50 border-green-100 text-green-900',
    amber: 'bg-amber-50 border-amber-100 text-amber-900',
    rose: 'bg-rose-50 border-rose-100 text-rose-900',
    violet: 'bg-violet-50 border-violet-100 text-violet-900',
  }
  return (
    <div className={cn('rounded-lg border px-3 py-2', colorClasses[color])}>
      <p className="text-[10px] font-medium opacity-70 mb-0.5">{label}</p>
      <p className="text-sm font-semibold leading-tight">{value || '-'}</p>
    </div>
  )
}

// ── 체크리스트 항목 ────────────────────────────────────────────────
function ChecklistItem({ title, desc }) {
  return (
    <div className="flex items-start gap-2.5">
      <CheckCircle2 className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {desc && <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>}
      </div>
    </div>
  )
}

// ── 섹션 헤더 (왼쪽 컬러바) ────────────────────────────────────────
function SectionTitle({ color = 'primary', children }) {
  const colors = {
    primary: 'bg-primary',
    amber:   'bg-amber-500',
    green:   'bg-green-500',
    rose:    'bg-rose-500',
  }
  return (
    <div className="flex items-center gap-2 mb-3">
      <div className={cn('w-1 h-4 rounded-full', colors[color])} />
      <h3 className="text-sm font-bold text-foreground">{children}</h3>
    </div>
  )
}

// ── AI 요약 카드 ──────────────────────────────────────────────────
function SummaryCard({ notice }) {
  const [summary, setSummary] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    try {
      const text = await generateNoticeSummary(notice)
      setSummary(text)
    } catch (err) {
      setError(err.message ?? 'LM Studio 연결 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="border-violet-100 bg-violet-50/30">
      <CardHeader className="pb-2 pt-4 px-5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-violet-500" />
            AI 공고 요약
          </CardTitle>
          {!summary && (
            <Button size="sm" variant="outline" onClick={handleGenerate} disabled={loading} className="h-7 text-xs gap-1.5">
              {loading
                ? <><Loader2 className="w-3 h-3 animate-spin" /> 요약 중...</>
                : <><Sparkles className="w-3 h-3" /> 생성</>
              }
            </Button>
          )}
          {summary && (
            <Button size="sm" variant="ghost" onClick={() => { setSummary(''); setError('') }} className="h-7 text-xs">
              다시 생성
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-4">
        {error && (
          <Alert variant="destructive" className="mb-2">
            <AlertDescription className="text-xs">{error}</AlertDescription>
          </Alert>
        )}
        {summary ? (
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">{summary}</p>
        ) : (
          <p className="text-xs text-muted-foreground leading-relaxed">
            {loading
              ? '잠시만 기다려주세요...'
              : '공고문을 분석해서 핵심 내용을 정리해드립니다.'
            }
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// ── 메인 컴포넌트 ──────────────────────────────────────────────────
export default function DetailPage({
  notice, onBack, onStartDraft,
  isBookmarked, onToggleBookmark,
}) {
  const [selectedFile, setSelectedFile] = useState(null)

  // 💡 [핵심 방어 코드] 첨부파일 파싱 중 에러(하얀 화면)가 발생해도 다운되지 않도록 try-catch 처리
  let attachments = [];
  try {
    attachments = notice ? parseAttachmentList(notice) : []
  } catch (err) {
    console.warn("첨부파일 파싱 우회 완료:", err)
    attachments = []
  }

  useEffect(() => {
    if (attachments.length > 0) setSelectedFile(attachments[0])
    else setSelectedFile(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notice?.id])

  if (!notice) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <FileText className="w-12 h-12 mb-4 opacity-40" />
        <p className="text-sm">선택된 공고가 없습니다.</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={onBack}>목록으로</Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* ── 상단 액션 바 ── */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" /> 목록으로
        </Button>
        <div className="flex items-center gap-2">
          <Button
            variant={isBookmarked ? 'default' : 'outline'}
            size="sm"
            onClick={onToggleBookmark}
            className={cn(isBookmarked && 'bg-amber-500 hover:bg-amber-600')}
          >
            <Bookmark className={cn('w-3.5 h-3.5', isBookmarked && 'fill-current')} />
            {isBookmarked ? '북마크됨' : '북마크'}
          </Button>
          {notice.url && (
            <Button variant="outline" size="sm" asChild>
              <a href={notice.url} target="_blank" rel="noreferrer">
                <ExternalLink className="w-3.5 h-3.5" /> 공고 원문
              </a>
            </Button>
          )}
          {notice.rceptEngnHmpgUrl && (
            <Button variant="outline" size="sm" asChild>
              <a href={notice.rceptEngnHmpgUrl} target="_blank" rel="noreferrer">
                <ExternalLink className="w-3.5 h-3.5" /> 온라인 신청
              </a>
            </Button>
          )}
          <Button
            size="sm"
            onClick={onStartDraft}
            className="gap-1.5 bg-primary hover:bg-primary/90 shadow-md font-semibold"
          >
            <FileText className="w-4 h-4" /> 제출 서류 작성
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* ── 타이틀 카드 ── */}
      <Card className="border-l-4 border-l-primary overflow-hidden">
        <CardContent className="px-5 py-4">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="blue" className="text-[11px]">{notice.origin || '-'}</Badge>
              <Badge variant="secondary" className="text-[11px]">
                <TrendingUp className="w-2.5 h-2.5" /> {((notice.ajin_similarity || 0) * 100).toFixed(1)}% 적합
              </Badge>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Badge variant="destructive" className="text-sm px-3">{getDdayText(notice.date)}</Badge>
              <span className="text-xs text-muted-foreground">마감: {formatDate(notice.date)}</span>
            </div>
          </div>
          <h2 className="text-lg font-bold text-foreground leading-snug mb-3">{notice.title || '제목 없음'}</h2>
          <Separator className="mb-3" />
          <div className="grid grid-cols-4 gap-2">
            <InfoChip label="소관기관" value={notice.jrsdInsttNm || '-'} color="blue" />
            <InfoChip label="수행기관" value={notice.excInsttNm || '-'} color="blue" />
            <InfoChip label="지역" value={notice.region || '-'} color="green" />
            <InfoChip label="신청기간" value={notice.period || '-'} color="violet" />
          </div>
        </CardContent>
      </Card>

      {/* ── 좌우 분할: 지원대상·내용 / AI요약·유의사항 ── */}
      <div className="grid grid-cols-2 gap-4">
        {/* 왼쪽: 지원 대상 */}
        <Card>
          <CardContent className="px-5 py-4">
            <SectionTitle color="primary">지원 대상</SectionTitle>
            <div className="space-y-2">
              <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                <p className="text-[11px] text-blue-700 font-semibold mb-1">지원대상</p>
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-line">
                  {notice.target || '공고 본문을 확인해 주세요.'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 오른쪽: AI 요약 */}
        <SummaryCard notice={notice} />
      </div>

      {/* ── 지원 내용 (체크리스트 형식) ── */}
      <Card>
        <CardContent className="px-5 py-4">
          <SectionTitle color="primary">지원 내용</SectionTitle>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <ChecklistItem
              title="지원 항목"
              desc={typeof notice.benefit === 'string' ? notice.benefit.slice(0, 80) : '공고 본문을 확인해 주세요'}
            />
            <ChecklistItem
              title="지원 형태"
              desc="컨설팅 / 비용 지원 / 장비 도입 등"
            />
            {notice.documents && notice.documents !== '공고 본문을 확인해주세요' && (
              <ChecklistItem
                title="필요 서류"
                desc={typeof notice.documents === 'string' ? notice.documents.slice(0, 80) : ''}
              />
            )}
            {notice.category && (
              <ChecklistItem
                title="사업 분류"
                desc={notice.category}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── 지원 혜택 + 유의사항 (좌우) ── */}
      <div className="grid grid-cols-2 gap-4">
        {/* 지원 혜택 */}
        <Card>
          <CardContent className="px-5 py-4">
            <SectionTitle color="green">지원 혜택</SectionTitle>
            <div className="grid grid-cols-2 gap-2">
              <InfoChip label="지원 내용" value={typeof notice.benefit === 'string' ? notice.benefit.slice(0, 30) : '본문 참조'} color="green" />
              <InfoChip label="지원 형태" value="정부지원금 + 자부담" color="green" />
              <InfoChip label="신청 기간" value={typeof notice.period === 'string' ? notice.period.slice(0, 30) : '-'} color="green" />
              <InfoChip label="지역" value={notice.region || '-'} color="green" />
            </div>
          </CardContent>
        </Card>

        {/* 유의사항 (제한사항 → 유의사항) */}
        <Card>
          <CardContent className="px-5 py-4">
            <SectionTitle color="amber">유의사항</SectionTitle>
            <div className="space-y-2">
              <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <p className="text-sm text-amber-900 leading-relaxed flex-1">
                  {notice.limit && notice.limit !== '신청 제외 대상은 원본 공고를 참조하세요.'
                    ? notice.limit
                    : '신청 제외 대상 및 중복 지원 금지 등 세부 사항은 원본 공고를 반드시 확인하시기 바랍니다.'
                  }
                </p>
              </div>
              <div className="flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-lg p-3">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-rose-900 mb-0.5">중복 지원 금지</p>
                  <p className="text-xs text-rose-800">동일·유사 사업계획서 중복 지원 시 선정 취소됩니다.</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── 평가 기준 / 문의처 ── */}
      <div className="grid grid-cols-2 gap-4">
        {/* 평가 기준 (예시) */}
        <Card>
          <CardContent className="px-5 py-4">
            <SectionTitle color="green">
              <span className="flex items-center gap-1.5">
                평가 기준 요약
                <Badge variant="success" className="text-[10px] ml-1">선정 가능성 판단</Badge>
              </span>
            </SectionTitle>
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1.5">서면평가 항목 · 배점</p>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {[
                  { label: '필요성', score: 30 },
                  { label: '역량', score: 20 },
                  { label: '계획', score: 25 },
                  { label: '기대효과', score: 25 },
                ].map(item => (
                  <Badge key={item.label} variant="blue" className="text-xs px-2 py-0.5">
                    {item.label} <span className="font-bold ml-1">{item.score}점</span>
                  </Badge>
                ))}
              </div>
              <p className="text-xs font-semibold text-muted-foreground mb-1.5">가점 항목</p>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {['수준확인서', '솔루션 가동률', '글로벌강소기업'].map(t => (
                  <Badge key={t} variant="success" className="text-xs px-2 py-0.5">{t}</Badge>
                ))}
              </div>
              <Alert variant="info">
                <Award className="w-4 h-4" />
                <AlertDescription className="text-xs">
                  동점 처리: 정량 평가 우선 → 기업 규모 우선 순
                </AlertDescription>
              </Alert>
            </div>
          </CardContent>
        </Card>

        {/* 문의 및 신청방법 */}
        <Card>
          <CardContent className="px-5 py-4">
            <SectionTitle color="primary">문의 및 신청방법</SectionTitle>
            <div className="space-y-2.5">
              <div className="flex items-start gap-2">
                <MessageCircle className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-muted-foreground font-medium">신청방법</p>
                  <p className="text-sm text-foreground leading-relaxed">
                    {notice.reqstMthPapersCn || '공고 본문 참조'}
                  </p>
                </div>
              </div>
              <Separator />
              <div className="flex items-start gap-2">
                <Phone className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-muted-foreground font-medium">문의처</p>
                  <p className="text-sm text-foreground leading-relaxed">
                    {notice.refrncNm || '공고 본문 참조'}
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── AI 본문 분석 (HWP/PDF 첨부 → LLM이 각 칸으로 분류) ── */}
      <AIExtractCard attachments={attachments} notice={notice} />

      {/* ── 첨부파일 + 미리보기 ── */}
      <Card>
        <CardHeader className="pb-3 pt-4 px-5">
          <CardTitle className="text-sm flex items-center gap-2">
            <FileText className="w-4 h-4 text-primary" />
            공고문 / 첨부파일
          </CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5">
          {attachments.length === 0 ? (
            <p className="text-sm text-muted-foreground">첨부 파일 정보가 없습니다.</p>
          ) : (
            <>
              {/* 파일 탭 */}
              <div className="flex flex-wrap gap-2 mb-4">
                {attachments.map((file, idx) => {
                  const isActive = selectedFile?.url === file.url
                  return (
                    <button
                      key={`${file.url}-${idx}`}
                      type="button"
                      onClick={() => setSelectedFile(file)}
                      className={cn(
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors',
                        isActive
                          ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                          : 'bg-white border-border text-foreground hover:bg-muted hover:border-primary/40',
                      )}
                    >
                      <Badge
                        variant={isActive ? 'secondary' : 'outline'}
                        className="text-[10px] px-1.5 h-4"
                      >
                        {file.type}
                      </Badge>
                      <span className="truncate max-w-[200px]">{file.name}</span>
                    </button>
                  )
                })}
              </div>
              <Separator className="mb-4" />
              <FileViewer key={selectedFile?.url} file={selectedFile} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ── AI 본문 분석 카드 (2026-05-25 C 그룹) ────────────────────────
//   첨부파일(HWP/PDF)을 backend가 prefetch → text 추출 → LM Studio 분류
//   결과: 지원대상/지원내용/제출서류/기간/지역/유의사항 등 카드 그리드
function AIExtractCard({ attachments, notice }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [debug, setDebug] = useState(null)

  if (!attachments || attachments.length === 0) return null

  const runAnalysis = async () => {
    setBusy(true)
    setError('')
    setResult(null)
    setDebug(null)
    try {
      // 1) 첫 번째 첨부파일 prefetch (HWP/PDF/DOCX)
      //    backend는 외부 절대 URL이 필요 — file.url은 Vite proxy 경로이므로 originalUrl 사용
      const file = attachments[0]
      const backendUrl = file.originalUrl || file.url
      const prefetchRes = await fetch('/api/files/prefetch-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: backendUrl, filename: file.name }),
      })
      if (!prefetchRes.ok) {
        const e = await prefetchRes.json().catch(() => ({}))
        throw new Error(e.detail || `prefetch HTTP ${prefetchRes.status}`)
      }
      const fileData = await prefetchRes.json()
      if (!fileData.parse_success || !fileData.text) {
        throw new Error(fileData.warning || '첨부파일 본문이 비어있습니다.')
      }

      // 2) LLM 구조화 분류
      const extractRes = await fetch('/api/notices/extract-structured', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: fileData.text, title: notice?.title || '' }),
      })
      if (!extractRes.ok) {
        const e = await extractRes.json().catch(() => ({}))
        throw new Error(e.detail || `extract HTTP ${extractRes.status}`)
      }
      const extracted = await extractRes.json()
      if (!extracted.ok) {
        setDebug(extracted.raw || extracted.warning)
        throw new Error(extracted.warning || 'LLM JSON 파싱 실패')
      }
      setResult(extracted.data)
    } catch (e) {
      setError(e.message || '분석 실패')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="border-l-4 border-l-violet-500">
      <CardHeader className="pb-3 pt-4 px-5">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-500" />
            AI 본문 분석
            <Badge variant="secondary" className="text-[10px]">LM Studio · {attachments.length}개 첨부 중 첫 파일</Badge>
          </CardTitle>
          <Button size="sm" onClick={runAnalysis} disabled={busy}>
            {busy ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 분석 중...</> : '첨부파일 → 각 칸 자동 채우기'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="px-5 pb-5">
        {!result && !error && !busy && (
          <p className="text-xs text-muted-foreground">
            첨부파일(HWP/PDF)을 다운로드 후 본문을 추출하고, AI(LM Studio · google/gemma-4-e4b)가 각 항목으로 분류합니다.
          </p>
        )}
        {error && (
          <Alert variant="destructive">
            <AlertDescription className="text-xs">{error}</AlertDescription>
          </Alert>
        )}
        {debug && (
          <details className="mt-2 text-[11px]">
            <summary className="cursor-pointer text-muted-foreground">LLM 원본 응답 (디버그)</summary>
            <pre className="mt-1 bg-muted/30 p-2 rounded whitespace-pre-wrap">{debug}</pre>
          </details>
        )}
        {result && (
          <div className="grid grid-cols-2 gap-3">
            <ResultCell label="공고 제목" value={result.title} full />
            <ResultCell label="지원 대상" value={result.target} />
            <ResultCell label="지원 내용" value={result.benefit} />
            <ResultCell label="제출 서류" value={result.documents} />
            <ResultCell label="신청 기간" value={result.period} />
            <ResultCell label="마감일" value={result.deadline} />
            <ResultCell label="지역" value={result.region} />
            <ResultCell label="제한 사항" value={result.limit} />
            <ResultCell label="사업 개요" value={result.content} full />
            <ResultCell label="문의처" value={result.contact} full />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ResultCell({ label, value, full = false }) {
  const text = (value || '').toString().trim()
  return (
    <div className={cn('bg-violet-50/40 border border-violet-100 rounded p-3', full && 'col-span-2')}>
      <p className="text-[10px] font-semibold text-violet-700 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
        {text || <span className="text-muted-foreground italic">— (없음)</span>}
      </p>
    </div>
  )
}
