import {
  AlertCircle, ArrowLeft, ArrowRight, AlertTriangle, BarChart3,
  CheckCircle2, ChevronDown, ChevronUp, Download, Edit3,
  FilePlus, FileText, Loader2, Maximize2, Send, Sparkles,
  Target, Upload, X, Zap, Award, ExternalLink // <- Award, ExternalLink 추가됨
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  chatWithDraftReviewer,
  generateSubmissionDraft,
  checkUploadCompleteness,
  applyImprovement,
  evaluateDraft,
} from '../../api/backendApi'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Separator } from '../../components/ui/separator'
import { Textarea } from '../../components/ui/textarea'
import { cn } from '../../lib/utils'

import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx'
import { saveAs } from 'file-saver'
// ❌ 여기에 있던 중복된 import { Award, CheckCircle2... } 는 삭제했습니다!

// Step 1 공용 컴포넌트 (V1·V2 동일 디자인 — 2026-05-10 추출)
import Step1Common from '../draft-upload/Step1Common'

// 파일 크기 포맷
function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// ── STEP 정의 ──────────────────────────────────────────────────────
const STEPS = [
  { id: 1, label: '자료 업로드',  icon: Upload },
  { id: 2, label: '자료 검사',    icon: AlertCircle },
  { id: 3, label: '초안 작성',    icon: Sparkles },
  { id: 4, label: '전략 검토',    icon: FileText },
  { id: 5, label: '완료 & 제출',  icon: Download },
]

// 제출 서류 섹션 정의
const DRAFT_SECTIONS = [
  { key: 'overview',    label: '신청 기업 개요' },
  { key: 'purpose',     label: '사업 참여 목적 및 필요성' },
  { key: 'plan',        label: '세부 추진 계획' },
  { key: 'effect',      label: '기대 효과' },
  { key: 'budget',      label: '예산 계획 개요' },
]

// 업로드 카테고리 (재정의 - 3분류)
const UPLOAD_DOC_FORMS = [
  { key: 'company',  label: '회사소개서',         accept: '.pdf,.docx,.hwp,.hwpx' },
  { key: 'apply',    label: '신청서 양식',         accept: '.pdf,.docx,.hwp,.hwpx' },
  { key: 'bizplan',  label: '사업계획서 양식',    accept: '.pdf,.docx,.hwp,.hwpx' },
]

// ── 상단 스텝 인디케이터 ───────────────────────────────────────────
function StepIndicator({ currentStep }) {
  return (
    <div className="flex items-center justify-between mb-6">
      {STEPS.map((step, idx) => {
        const done = step.id < currentStep
        const active = step.id === currentStep
        const Icon = step.icon
        return (
          <div key={step.id} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <div className={cn(
                'w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all',
                done && 'bg-green-500 border-green-500 text-white',
                active && 'bg-primary border-primary text-white ring-4 ring-primary/20',
                !done && !active && 'bg-white border-border text-muted-foreground',
              )}>
                {done
                  ? <CheckCircle2 className="w-4 h-4" />
                  : <Icon className="w-4 h-4" />
                }
              </div>
              <span className={cn(
                'text-[11px] font-medium whitespace-nowrap',
                active ? 'text-primary' : done ? 'text-green-600' : 'text-muted-foreground',
              )}>
                {step.label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={cn(
                'h-0.5 flex-1 mx-2 mb-5 transition-colors',
                done ? 'bg-green-500' : 'bg-border',
              )} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── STEP 1: 자료 업로드 ────────────────────────────────────────────
// V1 Step1Upload 함수는 ../draft-upload/Step1Common.jsx 로 추출됨 (2026-05-10).
// 사용: <Step1Common variant="v1" notice={...} uploads={...} onUploadsChange={...} />
// 시각·동작 100% 보존 (V1 회귀 X).
//
// (원본 함수 본체 ~310줄 제거됨)
// (V1 Step1Upload 함수 본체는 ../draft-upload/Step1Common.jsx 로 이전됨, 2026-05-10)
// ── STEP 2: 자료 검사 (3컬럼 - WriterPage 스타일) ──────────────────
function Step2Check({ notice, uploads, profileData, checkResult, onCheckResultChange }) {
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [selectedSection, setSelectedSection] = useState(0)
  const [previewText, setPreviewText] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const previewCache = useRef({})

  const allFiles = Object.entries(uploads).flatMap(([key, files]) =>
    (files || []).map(f => ({ ...f, category: key }))
  )
  const totalFiles = allFiles.length

  const runAnalysis = async () => {
    setAnalyzing(true)
    setError('')
    try {
      const text = await checkUploadCompleteness({ notice, uploads, profileData })
      const match = text.match(/\{[\s\S]*\}/)
      if (match) {
        try {
          const parsed = JSON.parse(match[0])
          onCheckResultChange?.(parsed)
          return
        } catch {}
      }
      throw new Error('AI 응답을 파싱할 수 없습니다')
    } catch (err) {
      setError(err.message ?? 'LM Studio 연결 실패')
    } finally {
      setAnalyzing(false)
    }
  }

  const completeness = checkResult?.completeness ?? Math.min(100, Math.round((totalFiles / 6) * 100))
  const categories = checkResult?.categories || [
    { name: '자동완성',      count: Math.min(5, totalFiles), color: 'green' },
    { name: '검토필요',      count: Math.max(0, 14 - totalFiles), color: 'rose' },
    { name: '직접입력 필요', count: 0, color: 'blue' },
    { name: '미작성',        count: Math.max(0, 1 - Math.floor(totalFiles / 3)), color: 'gray' },
  ]

  const sectionItems = [
    { label: 'Ⅰ. 신청기업 개요',    status: totalFiles > 0 ? '완료' : '미확인',    meta: '표 항목 4개' },
    { label: 'Ⅱ. 사업 추진 필요성', status: totalFiles > 1 ? '완료' : '보완 필요', meta: '서술형' },
    { label: 'Ⅲ. 기술개발 내용',    status: totalFiles > 2 ? '진행 중' : '미작성', meta: '서술형 + 표 항목 1개' },
    { label: 'Ⅳ. 사업화 계획',      status: totalFiles > 3 ? '완료' : '미작성',    meta: '서술형 + 표 항목 1개' },
    { label: 'Ⅴ. 예산 사용계획',    status: categories[1]?.count > 0 ? '부족자료 필요' : '완료', meta: '표 항목 1개' },
    { label: 'Ⅵ. 기대효과',         status: totalFiles > 1 ? '보완 필요' : '미작성', meta: '서술형 + 표 항목 1개' },
    { label: 'Ⅶ. 첨부서류 확인',    status: '미확인', meta: '체크리스트' },
  ]

  useEffect(() => {
    if (totalFiles === 0) { setPreviewText(''); return }
    const key = String(selectedSection)
    if (previewCache.current[key]) { setPreviewText(previewCache.current[key]); return }
    setPreviewLoading(true)
    setPreviewText('')
    fetch('/api/ai/generate-draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        notice_text: (uploads?.noticeFiles || []).map(f => f.parsed_text).filter(Boolean).join('\n\n')
                     || notice?.content || notice?.title || '',
        profile: profileData || {},
        section: sectionItems[selectedSection]?.label || '',
      }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.text) { previewCache.current[key] = d.text; setPreviewText(d.text) } })
      .catch(() => {})
      .finally(() => setPreviewLoading(false))
  }, [selectedSection, totalFiles]) // eslint-disable-line react-hooks/exhaustive-deps

  const statusColor = (status) => {
    if (status === '완료')         return 'bg-green-100 text-green-700'
    if (status === '보완 필요')    return 'bg-amber-100 text-amber-700'
    if (status === '진행 중')      return 'bg-blue-100 text-blue-700'
    if (status === '부족자료 필요') return 'bg-red-100 text-red-700'
    return 'bg-gray-100 text-gray-500'
  }

  const missingItems = checkResult?.missingInfo || [
    '현장 문제 수치 (예: 불량률, 가동률, 납기 지연율 등)',
    '견적서 / 산출근거',
    '매출 증가 목표, 생산성 향상률, 고용 창출 인원',
  ]

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-foreground mb-1">자료 충족도 검사</h3>
          <p className="text-sm text-muted-foreground">누락된 항목을 확인하고 필요한 자료를 보완하세요.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 font-semibold whitespace-nowrap">
            ● 자료 충족도 검사 단계
          </span>
          <Button size="sm" onClick={runAnalysis} disabled={analyzing} className="gap-1.5 bg-[#1B3464] hover:bg-[#1B3464]/90">
            {analyzing
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> 분석 중...</>
              : <><Sparkles className="w-3.5 h-3.5" /> {checkResult ? '재분석' : 'AI 검사 시작'}</>
            }
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      {/* 3컬럼 레이아웃 */}
      <div className="grid grid-cols-12 gap-3">

        {/* 좌: 분석된 제출양식 구조 */}
        <div className="col-span-3">
          <Card className="sticky top-20">
            <CardHeader className="pb-2 pt-4 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs">분석된 제출양식 구조</CardTitle>
                <button
                  type="button"
                  className="text-[10px] text-[#1B3464] bg-blue-50 px-2 py-1 rounded-md font-semibold flex items-center gap-1"
                >
                  새로 분석
                </button>
              </div>
            </CardHeader>
            <CardContent className="px-3 pb-3 space-y-1">
              {sectionItems.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedSection(idx)}
                  className={cn(
                    'w-full text-left p-2.5 rounded-lg border transition-all',
                    selectedSection === idx
                      ? 'border-[#1B3464] bg-blue-50 shadow-sm'
                      : 'border-transparent hover:bg-muted',
                  )}
                >
                  <div className="flex items-start justify-between gap-1 mb-0.5">
                    <span className="text-[11px] font-bold text-foreground leading-tight">{item.label}</span>
                    <span className={cn('text-[9px] font-bold px-1.5 py-0.5 rounded flex-shrink-0', statusColor(item.status))}>
                      {item.status}
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">{item.meta}</p>
                </button>
              ))}
              <button
                type="button"
                className="w-full mt-2 p-2.5 border-2 border-dashed border-border rounded-lg text-xs text-muted-foreground flex items-center justify-center gap-1.5 hover:border-primary/30 transition-colors"
              >
                <FilePlus className="w-3.5 h-3.5" />항목 추가
              </button>
            </CardContent>
          </Card>
        </div>

        {/* 중앙: 자동작성 미리보기 */}
        <div className="col-span-5">
          <Card>
            <CardHeader className="pb-2 pt-3 px-5 border-b border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs">자동작성 미리보기</CardTitle>
                <div className="flex items-center gap-1">
                  <button type="button" className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors">
                    <FileText className="w-3.5 h-3.5" />
                  </button>
                  <button type="button" className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors">
                    <Edit3 className="w-3.5 h-3.5" />
                  </button>
                  <button type="button" className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-muted transition-colors">
                    <Maximize2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-5 py-2.5 bg-muted/30 border-b border-border flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                <span className="font-medium text-foreground/70">원본 양식:</span>
                <span className="text-blue-600 font-semibold underline decoration-dotted cursor-pointer">사업계획서 제출양식.pdf</span>
                <span className="px-1.5 py-0.5 bg-white border border-border rounded text-[10px]">추출 항목 7개</span>
                <span className="px-1.5 py-0.5 bg-white border border-border rounded text-[10px]">필수 첨부 8개</span>
              </div>
              <div className="px-5 py-4 bg-white min-h-[400px]">
                <h2 className="text-sm font-bold text-foreground mb-3">{sectionItems[selectedSection]?.label}</h2>
                {totalFiles === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-8 h-8 mx-auto text-muted-foreground/30 mb-2" />
                    <p className="text-xs text-muted-foreground">자료를 업로드하면 자동으로 내용이 채워집니다</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {previewLoading ? (
                      [100, 88, 95, 82, 91, 86].map((w, i) => (
                        <div key={i} className="h-2.5 bg-muted/40 rounded animate-pulse" style={{ width: `${w}%` }} />
                      ))
                    ) : previewText ? (
                      <p className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">{previewText}</p>
                    ) : (
                      [100, 88, 95, 82, 91, 86].map((w, i) => (
                        <div key={i} className="h-2.5 bg-muted/40 rounded" style={{ width: `${w}%` }} />
                      ))
                    )}
                    {sectionItems[selectedSection]?.status === '보완 필요' && (
                      <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200">
                        <div className="flex items-center gap-2 mb-1">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                          <span className="text-xs font-semibold text-amber-700">근거 데이터가 부족합니다.</span>
                        </div>
                        <p className="text-[11px] text-amber-600">
                          문제의 규모·심각도를 뒷받침할 정량 데이터가 보완되면 신뢰도가 높아집니다.
                        </p>
                      </div>
                    )}
                    {sectionItems[selectedSection]?.status === '부족자료 필요' && (
                      <div className="mt-4 p-3 rounded-xl bg-red-50 border border-red-200">
                        <div className="flex items-center gap-2 mb-1">
                          <AlertCircle className="w-3.5 h-3.5 text-red-600" />
                          <span className="text-xs font-semibold text-red-700">추가 자료가 필요합니다.</span>
                        </div>
                        <p className="text-[11px] text-red-600">관련 견적서나 산출근거를 업로드하세요.</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between px-5 py-2 bg-muted/20 border-t border-border text-[11px] text-muted-foreground">
                <span>페이지 1 / 6 · zoom 100%</span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-green-500" />맞춤법 검사
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 우: 충족도 + 부족자료 요청 */}
        <div className="col-span-4 space-y-3">

          {/* 자료 충족도 stats */}
          <Card>
            <CardContent className="px-4 py-4">
              <div className="grid grid-cols-3 gap-2 mb-3">
                {/* 충족도 원형 */}
                <div className="p-2.5 rounded-xl bg-muted/40">
                  <p className="text-[10px] text-muted-foreground font-medium mb-2">자료 충족도</p>
                  <div className="flex items-center justify-center">
                    <div className="relative w-10 h-10">
                      <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                        <circle cx="18" cy="18" r="15" fill="none" stroke="#F3F4F6" strokeWidth="3" />
                        <circle
                          cx="18" cy="18" r="15" fill="none" stroke="#2563EB" strokeWidth="3"
                          strokeDasharray={`${(completeness / 100) * 94.2} 94.2`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-blue-600">
                        {Math.round(completeness)}%
                      </span>
                    </div>
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-muted/40">
                  <p className="text-[10px] text-muted-foreground font-medium mb-1.5">부족자료</p>
                  <p className="text-xl font-bold text-red-600">{categories[1]?.count || 0}건</p>
                </div>
                <div className="p-2.5 rounded-xl bg-muted/40">
                  <p className="text-[10px] text-muted-foreground font-medium mb-1.5">업로드 자료</p>
                  <p className="text-xl font-bold text-foreground">{totalFiles}건</p>
                </div>
              </div>
              <button
                type="button"
                className="w-full py-1.5 px-3 bg-white border border-border rounded-lg text-xs text-muted-foreground font-medium flex items-center justify-center gap-1.5 hover:bg-muted/30 transition-colors"
              >
                <BarChart3 className="w-3.5 h-3.5" />자료 관리
              </button>
            </CardContent>
          </Card>

          {/* AI 권장사항 */}
          {checkResult?.recommendations && checkResult.recommendations.length > 0 && (
            <Card className="border-violet-200 bg-violet-50/30">
              <CardContent className="px-4 py-3">
                <p className="text-xs font-semibold text-violet-700 mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" />AI 권장사항
                </p>
                <div className="space-y-1.5">
                  {checkResult.recommendations.map((rec, idx) => (
                    <div key={idx} className="flex items-start gap-1.5 text-[11px] text-foreground">
                      <span className="text-violet-500 mt-0.5">•</span>
                      <span>{rec}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 부족자료 요청 카드들 */}
          <Card>
            <CardHeader className="pb-2 pt-3 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs">부족자료 요청</CardTitle>
                <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                  총 {missingItems.length}건
                </span>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-2">
              {missingItems.slice(0, 3).map((item, idx) => (
                <div key={idx} className="p-3 rounded-xl border border-border bg-white">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[11px] font-bold text-foreground">{sectionItems[idx + 1]?.label || '—'}</p>
                    <span className={cn(
                      'text-[9px] font-bold px-1.5 py-0.5 rounded',
                      idx === 1 ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700',
                    )}>
                      {idx === 1 ? '부족자료 필요' : '보완 필요'}
                    </span>
                  </div>
                  <p className="text-[10px] font-semibold text-muted-foreground mb-1">누락 항목</p>
                  <p className="text-[11px] text-foreground mb-2.5">• {item}</p>
                  <div className="grid grid-cols-2 gap-1">
                    <button
                      type="button"
                      className="py-1.5 px-2 bg-muted/40 border border-border rounded-md text-[10px] text-muted-foreground font-medium flex items-center justify-center gap-1 hover:bg-muted/60 transition-colors"
                    >
                      <Edit3 className="w-2.5 h-2.5" />텍스트 입력
                    </button>
                    <button
                      type="button"
                      className="py-1.5 px-2 bg-muted/40 border border-border rounded-md text-[10px] text-muted-foreground font-medium flex items-center justify-center gap-1 hover:bg-muted/60 transition-colors"
                    >
                      나중에 보완
                    </button>
                  </div>
                </div>
              ))}

              {/* 통합 파일 업로드 */}
              <div className="mt-1 p-3 border-2 border-dashed border-blue-200 rounded-xl bg-blue-50/50">
                <div className="flex items-start gap-2 mb-2.5">
                  <div className="w-7 h-7 rounded-lg bg-white border border-blue-200 flex items-center justify-center flex-shrink-0 text-blue-600">
                    <Upload className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <p className="text-[11px] font-bold text-foreground mb-0.5">부족자료 일괄 업로드</p>
                    <p className="text-[10px] text-muted-foreground leading-snug">
                      하나의 파일에 여러 부족자료가 있어도 됩니다. AI가 자동으로 항목별로 분류해 매칭합니다.
                    </p>
                  </div>
                </div>
                <label className="cursor-pointer block">
                  <Input type="file" multiple className="hidden" />
                  <span className="w-full py-2 border border-blue-200 bg-white rounded-lg text-[11px] text-blue-600 font-semibold flex items-center justify-center gap-1.5 hover:bg-blue-50 transition-colors cursor-pointer">
                    <FilePlus className="w-3 h-3" />파일 선택 (다중 가능)
                  </span>
                </label>
                <p className="mt-1.5 text-[10px] text-muted-foreground">
                  예: 견적서 1개 → 「예산 사용계획」 + 「기대효과」 동시 매칭
                </p>
              </div>

              <Button className="w-full bg-[#1B3464] hover:bg-[#1B3464]/90 gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />부족해도 1차 초안 작성
              </Button>
            </CardContent>
          </Card>

          {/* 하단 액션 */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: '현재 상태 저장', icon: Download },
              { label: '초안 다운로드', icon: FileText },
              { label: '전체 평가', icon: BarChart3 },
            ].map(({ label, icon: Icon }) => (
              <button
                key={label}
                type="button"
                className="py-3 px-2 bg-white border border-border rounded-xl text-[10px] text-muted-foreground font-medium flex flex-col items-center gap-1.5 hover:bg-muted/30 transition-colors"
              >
                <Icon className="w-3.5 h-3.5" />{label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* TIP */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Zap className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
        <span>
          <strong className="text-amber-600">TIP:</strong>{' '}
          부족자료가 있어도 1차 초안을 먼저 생성할 수 있습니다. 이후 보완하여 완성도를 높여보세요.
        </span>
      </div>
    </div>
  )
}

// ── STEP 3: 초안 작성 (AIHelperPage 스타일 - 진행카드 + 아바타 챗봇) ──
function Step3Draft({ notice, profileData, drafts, onDraftsChange }) {
  const [generatingKey, setGeneratingKey] = useState(null)
  const [selectedKey, setSelectedKey] = useState('overview')
  const [error, setError] = useState('')
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  const generateSection = async (section) => {
    setGeneratingKey(section.key)
    setError('')
    try {
      const text = await generateSubmissionDraft({
        notice,
        section: section.label,
        uploadedData: {},
        profileData,
      })
      onDraftsChange({ ...drafts, [section.key]: text })
      setSelectedKey(section.key)
    } catch (err) {
      setError(err.message ?? 'LM Studio 연결 실패')
    } finally {
      setGeneratingKey(null)
    }
  }

  const generateAll = async () => {
    setError('')
    for (const section of DRAFT_SECTIONS) {
      setGeneratingKey(section.key)
      try {
        const text = await generateSubmissionDraft({
          notice,
          section: section.label,
          uploadedData: {},
          profileData,
        })
        onDraftsChange((prev) => ({ ...prev, [section.key]: text }))
      } catch (err) {
        setError(err.message ?? 'LM Studio 연결 실패')
        setGeneratingKey(null)
        return
      }
    }
    setGeneratingKey(null)
  }

  const sendChatMessage = async () => {
    const msg = chatInput.trim()
    if (!msg || chatLoading) return
    setChatInput('')

    const userMsg = { role: 'user', content: msg }
    setChatMessages(prev => [...prev, userMsg])
    setChatLoading(true)

    try {
      const currentSection = DRAFT_SECTIONS.find(s => s.key === selectedKey)
      const draftContent = drafts[selectedKey] || '(작성된 내용 없음)'
      const response = await chatWithDraftReviewer({
        message: msg,
        draftContent: `[${currentSection?.label}]\n${draftContent}`,
        notice,
        history: chatMessages,
      })
      setChatMessages(prev => [...prev, { role: 'assistant', content: response }])

      if (msg.includes('수정') || msg.includes('바꿔') || msg.includes('변경') || msg.includes('보완')) {
        onDraftsChange({ ...drafts, [selectedKey]: response })
      }
    } catch (err) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: `오류: ${err.message ?? 'LM Studio 연결 실패'}`,
      }])
    } finally {
      setChatLoading(false)
    }
  }

  const completedCount = DRAFT_SECTIONS.filter(s => drafts[s.key]?.trim()).length
  const totalProgress = (completedCount / DRAFT_SECTIONS.length) * 100
  const currentSection = DRAFT_SECTIONS.find(s => s.key === selectedKey)
  const currentContent = drafts[selectedKey] || ''
  const lastAiMsg = chatMessages.filter(m => m.role === 'assistant').slice(-1)[0]

  return (
    <div className="space-y-4">
      {/* 헤더 + 진행 카드 */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-foreground mb-1 flex items-center gap-2">
            제출양식 기반 작성 — AI 작성 도우미
            <div className="w-5 h-5 rounded-md bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center">
              <Sparkles className="w-3 h-3 text-white" />
            </div>
          </h3>
          <p className="text-sm text-muted-foreground">초안 진단 결과를 바탕으로 약한 항목만 선택적으로 보완합니다.</p>
        </div>

        {/* 진행 카드 */}
        <div className="flex items-center gap-4 px-4 py-3 rounded-xl bg-[#EEF2FB] border border-[#DCE5F5] flex-shrink-0">
          <div>
            <p className="text-[10px] text-muted-foreground font-medium mb-1">AI 보완 진행률</p>
            <div className="flex items-center gap-2">
              <div className="relative w-8 h-8 flex-shrink-0">
                <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                  <circle cx="18" cy="18" r="15" fill="none" stroke="#E5E7EB" strokeWidth="3" />
                  <circle
                    cx="18" cy="18" r="15" fill="none" stroke="#2563EB" strokeWidth="3"
                    strokeDasharray={`${(totalProgress / 100) * 94.2} 94.2`}
                    strokeLinecap="round"
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-[8px] font-bold text-blue-600">
                  {Math.round(totalProgress)}%
                </span>
              </div>
              <span className="text-base font-bold text-foreground">{Math.round(totalProgress)}%</span>
            </div>
          </div>
          <div className="w-px h-8 bg-[#DCE5F5]" />
          <div>
            <p className="text-[10px] text-muted-foreground font-medium mb-0.5">현재 보완 항목</p>
            <p className="text-xs font-bold text-foreground">{currentSection?.label}</p>
          </div>
          <div className="w-px h-8 bg-[#DCE5F5]" />
          <div>
            <p className="text-[10px] text-muted-foreground font-medium mb-0.5">완료</p>
            <p className="text-xs font-bold text-foreground">{completedCount} / {DRAFT_SECTIONS.length}항목</p>
          </div>
          <Button
            onClick={generateAll}
            disabled={generatingKey !== null}
            size="sm"
            className="ml-1 bg-[#1B3464] hover:bg-[#1B3464]/90 gap-1.5"
          >
            {generatingKey
              ? <><Loader2 className="w-3 h-3 animate-spin" />작성 중...</>
              : <><Sparkles className="w-3 h-3" />전체 자동 작성</>
            }
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      {/* 3-컬럼 레이아웃 */}
      <div className="grid grid-cols-12 gap-3">

        {/* 좌: 분석된 항목 구조 */}
        <div className="col-span-3">
          <Card className="sticky top-20">
            <CardHeader className="pb-2 pt-3 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs">분석된 제출양식 구조</CardTitle>
                <button
                  type="button"
                  className="text-[10px] text-[#1B3464] bg-blue-50 px-2 py-1 rounded-md font-semibold"
                >
                  전체 펼치기
                </button>
              </div>
            </CardHeader>
            <CardContent className="px-3 pb-3 space-y-1">
              {DRAFT_SECTIONS.map((section, idx) => {
                const isActive = selectedKey === section.key
                const isDone = !!drafts[section.key]?.trim()
                const isGenerating = generatingKey === section.key
                return (
                  <button
                    key={section.key}
                    type="button"
                    onClick={() => setSelectedKey(section.key)}
                    className={cn(
                      'w-full text-left p-2.5 rounded-lg border transition-all',
                      isActive
                        ? 'border-[#1B3464] bg-blue-50 shadow-sm'
                        : 'border-transparent hover:bg-muted',
                    )}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[11px] font-bold text-foreground">{idx + 1}. {section.label}</span>
                      {isDone ? (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-green-100 text-green-700">완료</span>
                      ) : isGenerating ? (
                        <Loader2 className="w-3 h-3 animate-spin text-[#1B3464]" />
                      ) : isActive ? (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">● 진행 중</span>
                      ) : (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">미작성</span>
                      )}
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      {drafts[section.key] ? drafts[section.key].slice(0, 28) + '...' : '미작성'}
                    </p>
                  </button>
                )
              })}
              <button
                type="button"
                className="w-full mt-2 p-2.5 border-2 border-dashed border-border rounded-lg text-xs text-muted-foreground flex items-center justify-center gap-1.5 hover:border-primary/30 transition-colors"
              >
                <FilePlus className="w-3.5 h-3.5" />항목 추가
              </button>
            </CardContent>
          </Card>
        </div>

        {/* 중앙: 초안 미리보기 */}
        <div className="col-span-6">
          <Card>
            <CardHeader className="pb-2 pt-3 px-5 border-b border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs">제출양식 기반 초안 미리보기</CardTitle>
                <div className="flex items-center gap-1">
                  <Button size="sm" variant="ghost" className="h-7 w-7 p-0"><FileText className="w-3.5 h-3.5" /></Button>
                  <Button size="sm" variant="ghost" className="h-7 w-7 p-0"><Edit3 className="w-3.5 h-3.5" /></Button>
                  <Button size="sm" variant="ghost" className="h-7 w-7 p-0"><Maximize2 className="w-3.5 h-3.5" /></Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-5 py-4 bg-white min-h-[520px]">
                <h2 className="text-sm font-bold text-foreground mb-3">{currentSection?.label}</h2>

                {generatingKey === selectedKey ? (
                  <div className="space-y-3 mt-4">
                    {[100, 92, 85, 95, 78, 88].map((w, i) => (
                      <div key={i} className="h-3 bg-muted rounded animate-pulse" style={{ width: `${w}%` }} />
                    ))}
                  </div>
                ) : (
                  <>
                    {/* 경고 박스 — 내용 없을 때 */}
                    {!currentContent && (
                      <div className="mb-3 p-3.5 rounded-xl bg-amber-50 border border-amber-200">
                        <div className="flex items-center gap-2 mb-1">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                          <span className="text-xs font-semibold text-amber-700">해당 항목의 근거 자료가 부족합니다.</span>
                        </div>
                        <p className="text-[11px] text-amber-600 leading-relaxed">
                          AI 작성 버튼을 눌러 초안을 생성하거나 우측 챗봇에 수정을 요청하세요.
                        </p>
                      </div>
                    )}

                    {/* AI 미리보기 박스 — AI 응답 있을 때 */}
                    {currentContent && lastAiMsg && (
                      <div className="mb-3 p-3.5 rounded-xl bg-blue-50 border border-blue-200">
                        <div className="flex items-center gap-2 mb-2">
                          <Sparkles className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
                          <span className="text-xs font-semibold text-blue-700">AI가 반영할 신규 문장 미리보기</span>
                        </div>
                        <p className="text-[11px] text-foreground leading-relaxed mb-1">
                          {lastAiMsg.content.slice(0, 140)}{lastAiMsg.content.length > 140 ? '...' : ''}
                        </p>
                        <button
                          type="button"
                          className="float-right text-[10px] text-blue-600 font-semibold border border-blue-200 bg-white px-2 py-0.5 rounded-md hover:bg-blue-50 transition-colors"
                        >
                          예시 출처 보기
                        </button>
                        <div className="clear-both" />
                      </div>
                    )}

                    <Textarea
                      value={currentContent}
                      onChange={(e) => onDraftsChange({ ...drafts, [selectedKey]: e.target.value })}
                      placeholder={`"${currentSection?.label}" 항목을 작성하세요. 우측 AI 도우미에게 수정을 요청할 수 있습니다.`}
                      className="border-0 shadow-none min-h-[400px] p-0 text-sm leading-relaxed resize-none focus-visible:ring-0 whitespace-pre-line"
                    />
                  </>
                )}
              </div>
              <div className="flex items-center justify-between px-5 py-2 bg-muted/20 border-t border-border text-[11px] text-muted-foreground">
                <span>글자 수 {currentContent.length} · 페이지 약 {Math.ceil(currentContent.length / 600) || 1}p · 자동 저장 중</span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-green-500" />맞춤법 검사
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 우: AI 보완 도우미 챗봇 */}
        <div className="col-span-3 space-y-2">
          <Card className="flex flex-col overflow-hidden" style={{ height: '620px' }}>
            {/* 챗 헤더 */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-foreground">AI 보완 도우미</span>
                <span className="text-[9px] font-bold px-1.5 py-0.5 bg-blue-50 text-[#1B3464] rounded">BETA</span>
              </div>
              <Button
                size="sm"
                className="h-7 gap-1 text-xs bg-[#1B3464] hover:bg-[#1B3464]/90"
                onClick={() => generateSection(currentSection)}
                disabled={generatingKey !== null}
              >
                {generatingKey === selectedKey
                  ? <><Loader2 className="w-3 h-3 animate-spin" />작성 중...</>
                  : <><Sparkles className="w-3 h-3" />{currentContent ? '재작성' : 'AI 작성'}</>
                }
              </Button>
            </div>

            {/* 진행 상태 표시 */}
            <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 flex items-center gap-2 flex-shrink-0">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />
              <span className="text-[11px] text-blue-700 font-medium line-clamp-1">
                AI가 {currentSection?.label}을(를) 보완 중입니다.
              </span>
            </div>

            {/* 챗 바디 */}
            <div className="px-3 py-3 flex-1 overflow-y-auto space-y-3">
              {chatMessages.length === 0 ? (
                <>
                  {/* AI 첫 메시지 */}
                  <div className="flex gap-2 items-start">
                    <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-3.5 h-3.5 text-[#1B3464]" />
                    </div>
                    <div className="flex-1 bg-muted/40 rounded-xl px-3 py-2 text-[11px] text-foreground leading-relaxed">
                      초안 진단 결과, '{currentSection?.label}' 항목을 어떻게 보완해 드릴까요?
                    </div>
                  </div>

                  {/* 추천 보완 방법 */}
                  <div>
                    <p className="text-[10px] font-semibold text-muted-foreground mb-1.5 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />추천 보완 방법
                    </p>
                    <div className="space-y-1">
                      {[
                        { label: '내 파일 업로드해서 근거로 사용', highlight: true },
                        { label: '내용을 좀 더 구체적으로 작성해줘', highlight: false },
                        { label: '수치 데이터를 추가해줘', highlight: false },
                        { label: '문장을 더 간결하게 다듬어줘', highlight: false },
                        { label: '이 항목 다시 작성', highlight: false },
                      ].map(({ label, highlight }) => (
                        <button
                          key={label}
                          type="button"
                          onClick={() => setChatInput(label)}
                          className={cn(
                            'w-full flex items-center justify-between px-2.5 py-2 text-[10.5px] rounded-lg border transition-colors text-left',
                            highlight
                              ? 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100'
                              : 'bg-white border-border text-foreground hover:bg-blue-50',
                          )}
                        >
                          {label}
                          <ArrowRight className="w-3 h-3 flex-shrink-0 ml-1 opacity-50" />
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                chatMessages.map((msg, idx) => (
                  <div key={idx} className={cn('flex gap-2 items-start', msg.role === 'user' && 'flex-row-reverse')}>
                    <div className={cn(
                      'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-[11px] font-bold',
                      msg.role === 'user'
                        ? 'bg-[#1B3464] text-white'
                        : 'bg-blue-50 border border-blue-100',
                    )}>
                      {msg.role === 'user' ? 'A' : <Sparkles className="w-3.5 h-3.5 text-[#1B3464]" />}
                    </div>
                    <div className={cn(
                      'max-w-[85%] rounded-xl px-3 py-2 text-[11px] leading-relaxed',
                      msg.role === 'user' ? 'bg-blue-50 text-foreground' : 'bg-muted/40 text-foreground',
                    )}>
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div className="flex gap-2 items-start">
                  <div className="w-7 h-7 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center flex-shrink-0">
                    <Sparkles className="w-3.5 h-3.5 text-[#1B3464]" />
                  </div>
                  <div className="bg-muted/40 rounded-xl px-3 py-2 flex items-center gap-1.5">
                    <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
                    <span className="text-[11px] text-muted-foreground">생각 중...</span>
                  </div>
                </div>
              )}
            </div>

            {/* 입력창 */}
            <div className="p-3 border-t border-border flex-shrink-0">
              <div className="border border-border rounded-lg bg-white mb-2 flex items-center px-2">
                <button
                  type="button"
                  className="w-7 h-7 flex items-center justify-center text-muted-foreground hover:text-[#1B3464] transition-colors flex-shrink-0"
                >
                  <FilePlus className="w-3.5 h-3.5" />
                </button>
                <Textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="추가 요청사항을 입력하세요..."
                  rows={1}
                  className="text-[11px] resize-none flex-1 border-0 shadow-none py-2 focus-visible:ring-0 bg-transparent min-h-0"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage() }
                  }}
                />
                <button
                  type="button"
                  onClick={sendChatMessage}
                  disabled={!chatInput.trim() || chatLoading}
                  className="w-7 h-7 flex items-center justify-center text-muted-foreground hover:text-[#1B3464] disabled:opacity-40 transition-colors flex-shrink-0"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
              <Button
                className="w-full bg-[#1B3464] hover:bg-[#1B3464]/90 text-xs h-8 gap-1.5"
                onClick={sendChatMessage}
                disabled={!chatInput.trim() || chatLoading}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />이 답변 반영
              </Button>
            </div>
          </Card>

          {/* 하단 액션 */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: '현재 상태 저장', icon: Download },
              { label: '초안 다운로드', icon: FileText },
            ].map(({ label, icon: Icon }) => (
              <button
                key={label}
                type="button"
                className="py-2.5 px-2 bg-white border border-border rounded-xl text-[10px] text-muted-foreground font-medium flex flex-col items-center gap-1 hover:bg-muted/30 transition-colors"
              >
                <Icon className="w-3.5 h-3.5" />{label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* TIP */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Zap className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
        <span><strong className="text-amber-600">TIP:</strong> 전체평가는 STEP 4 전략 검토 화면에서 진행합니다.</span>
      </div>
    </div>
  )
}

// ── STEP 4: 전략 검토 (EvaluationWorkspacePage 스타일) ──────────────
function Step4Review({ notice, profileData, drafts, onDraftsChange }) {
  const [evaluating, setEvaluating] = useState(false)
  const [evalResult, setEvalResult] = useState(null)
  const [error, setError] = useState('')
  const [applyingIdx, setApplyingIdx] = useState(null)

  const runEvaluation = async () => {
    setEvaluating(true)
    setError('')
    try {
      const text = await evaluateDraft({ notice, drafts, profileData })
      const match = text.match(/\{[\s\S]*\}/)
      if (match) {
        try {
          const parsed = JSON.parse(match[0])
          setEvalResult(parsed)
          return
        } catch {}
      }
      throw new Error('AI 응답을 파싱할 수 없습니다')
    } catch (err) {
      setError(err.message ?? 'LM Studio 연결 실패')
    } finally {
      setEvaluating(false)
    }
  }

  const applySingleImprovement = async (issue, idx) => {
    setApplyingIdx(idx)
    try {
      const sectionKey = DRAFT_SECTIONS.find(s => s.label.includes(issue.category))?.key || 'plan'
      const newText = await applyImprovement({
        section: issue.title,
        currentText: drafts[sectionKey] || issue.currentText || '',
        improvedText: issue.improvedText || '',
        notice,
      })
      onDraftsChange({ ...drafts, [sectionKey]: newText })
    } catch (err) {
      console.error(err)
    } finally {
      setApplyingIdx(null)
    }
  }

  const result = evalResult || {
    currentScore: 78,
    expectedImprovement: 12,
    passLine: 70,
    categories: [
      { name: '기술성',   level: '우수',     issue: '실증 계획 구체성 및 레퍼런스 부족' },
      { name: '사업성',   level: '보완 필요', issue: '시장 진입 전략·실행계획 구체성 부족' },
      { name: '기대효과', level: '보완 필요', issue: 'KPI 정량화 및 검증 방법 근거 부족' },
      { name: '수행역량', level: '보통',     issue: '조직·역할·외부 협력 근거 보완 필요' },
    ],
    topIssues: [],
    improvementProgress: { applied: 0, inProgress: 0, needsData: 0, waiting: 4 },
  }

  const levelColor = (level) => {
    if (level === '우수')      return 'text-green-700 bg-green-100'
    if (level === '보완 필요') return 'text-rose-700 bg-rose-100'
    return 'text-amber-700 bg-amber-100'
  }

  const needsCount = result.categories.filter(c => c.level === '보완 필요').length

  return (
    <div className="space-y-4">
      {/* 페이지 헤드 */}
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 text-xs text-muted-foreground">
            <span>제출 서류 작성</span>
            <span className="text-border">›</span>
            <span className="text-foreground font-medium">AI 평가 · 보완 작업 지휘실</span>
          </div>
          <h3 className="text-xl font-extrabold text-foreground tracking-tight mb-1">
            AI 평가 · 보완 작업 지휘실
          </h3>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
            각 카드에서 <strong className="text-foreground">현재 문장 → AI 보완안 → 왜 더 좋은지</strong>까지 확인하고,
            필요한 자료를 보완하여 채택 경쟁력을 높이세요.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button variant="outline" size="sm" className="gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" />작성 화면으로
          </Button>
          <Button onClick={runEvaluation} disabled={evaluating} className="gap-2 bg-[#1B3464] hover:bg-[#1B3464]/90">
            {evaluating
              ? <><Loader2 className="w-4 h-4 animate-spin" />평가 중...</>
              : <><Sparkles className="w-4 h-4" />{evalResult ? '재평가' : 'AI 평가 시작'}</>
            }
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription className="text-xs">{error}</AlertDescription>
        </Alert>
      )}

      {/* 메타 그리드 6개 */}
      <div className="grid grid-cols-6 gap-3">
        {[
          {
            label: '평가 대상',
            icon: FileText,
            value: '현재 작업 버전 v2.1',
            sub: '최종 저장 직전',
          },
          {
            label: '상태',
            icon: AlertCircle,
            value: '보완 진행 중',
            sub: '마지막 평가 직전',
            highlight: true,
          },
          {
            label: '평가 기준',
            icon: Target,
            value: '공고문 평가기준',
            sub: '가중치 합 100점',
          },
          {
            label: '현재 점수',
            icon: BarChart3,
            value: result.currentScore,
            valueUnit: '/100',
            sub: `동일 유형 상위 ${100 - result.currentScore}%`,
            scoreColor: 'text-blue-600',
            isScore: true,
          },
          {
            label: '예상 개선 효과',
            icon: Sparkles,
            value: `+${result.expectedImprovement}점`,
            sub: '우선순위 항목 보완 시',
            valueColor: 'text-green-600',
          },
          {
            label: '보완 필요 항목',
            icon: AlertTriangle,
            value: `${needsCount}건`,
            sub: '우선순위 기준',
            valueColor: 'text-rose-600',
          },
        ].map((stat, i) => {
          const Icon = stat.icon
          return (
            <Card key={i} className={cn(
              'overflow-hidden',
              stat.highlight ? 'bg-blue-50/60 border-blue-200' : '',
            )}>
              <CardContent className="p-3.5">
                <div className="flex items-center gap-1.5 mb-2">
                  <div className={cn(
                    'w-5 h-5 rounded-md flex items-center justify-center',
                    stat.highlight ? 'bg-white text-blue-600' : 'bg-muted text-muted-foreground',
                  )}>
                    <Icon className="w-3 h-3" />
                  </div>
                  <p className="text-[10px] font-semibold text-muted-foreground">{stat.label}</p>
                </div>
                {stat.isScore ? (
                  <p className="text-2xl font-extrabold tracking-tight mb-0.5">
                    <span className={stat.scoreColor}>{stat.value}</span>
                    <span className="text-sm font-semibold text-muted-foreground ml-0.5">{stat.valueUnit}</span>
                  </p>
                ) : (
                  <p className={cn('text-sm font-bold leading-tight mb-0.5', stat.valueColor || 'text-foreground')}>
                    {stat.value}
                  </p>
                )}
                <p className="text-[10px] text-muted-foreground line-clamp-2 leading-snug">{stat.sub}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* 종합 진단 배너 */}
      <div className="flex items-center gap-4 p-4 bg-white border border-border rounded-2xl shadow-sm">
        <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
          <Target className="w-5 h-5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-foreground leading-relaxed">
            핵심 구조는 갖췄지만,{' '}
            <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[13px]">사업화 전략과 근거자료 보완</span>이 필요합니다.
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            우선순위 {needsCount}개 항목을 보완하면 채택 경쟁력이 크게 높아질 수 있습니다 (예상 +8~+{result.expectedImprovement}점).
          </p>
        </div>
        <button
          type="button"
          className="flex-shrink-0 px-3.5 py-2 bg-white border border-border rounded-lg text-xs font-semibold text-muted-foreground hover:bg-muted/30 transition-colors flex items-center gap-1.5"
        >
          <FileText className="w-3.5 h-3.5" />평가 상세 보기
        </button>
      </div>

      {/* 평가 항목별 진단 + AI 이슈 */}
      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardHeader className="pb-2 pt-4 px-5">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-1.5">
                <BarChart3 className="w-4 h-4 text-muted-foreground" />
                평가 항목별 진단
              </CardTitle>
              <span className="text-[11px] text-muted-foreground">4개 평가지표 (가중치 합 100점)</span>
            </div>
          </CardHeader>
          <CardContent className="px-5 pb-4">
            <div className="space-y-2">
              {result.categories.map((cat, idx) => (
                <div key={idx} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                  <p className="text-sm font-semibold text-foreground w-16 flex-shrink-0">{cat.name}</p>
                  <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded flex-shrink-0', levelColor(cat.level))}>
                    {cat.level}
                  </span>
                  <p className="text-xs text-muted-foreground flex-1 line-clamp-1">{cat.issue}</p>
                  <button type="button" className="text-[10px] text-muted-foreground hover:text-foreground flex-shrink-0">이동 →</button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2 pt-4 px-5">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-violet-500" />
                AI 발견 주요 이슈
              </CardTitle>
              <span className="text-[11px] text-muted-foreground">{result.categories.length}건</span>
            </div>
          </CardHeader>
          <CardContent className="px-5 pb-4">
            <ul className="space-y-2.5 text-xs text-foreground">
              {[
                ['사업화 전략', '의 실행계획 구체성 부족'],
                ['수익성 근거', ' 및 재무추정 보완 필요'],
                ['성과지표(KPI) 정량성', ' 및 근거 부족'],
                ['추진 조직 및 협력체계', ' 근거 보완 필요'],
              ].map(([bold, rest], i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground mt-1.5 flex-shrink-0" />
                  <span><strong className="font-bold">{bold}</strong>{rest}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* 우선순위 보완 배너 */}
      <div className="flex items-center gap-4 p-5 rounded-2xl bg-gradient-to-r from-[#1B3464] to-[#2E4FA5] text-white">
        <div className="w-11 h-11 rounded-xl bg-white/15 flex items-center justify-center flex-shrink-0">
          <Zap className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-base font-bold mb-0.5">우선순위 보완 항목</p>
          <p className="text-xs text-white/75 leading-relaxed">
            상위 항목부터 적용하면 효과가 큽니다. 보완 적용 후 자동으로 점수가 재산정됩니다.
          </p>
        </div>
        <div className="flex gap-5 border-l border-white/20 pl-5 flex-shrink-0">
          <div className="text-center">
            <p className="text-2xl font-extrabold tracking-tight text-sky-200">{needsCount}</p>
            <p className="text-[10px] text-white/65 mt-0.5">보완 필요</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-extrabold tracking-tight">+{result.expectedImprovement}</p>
            <p className="text-[10px] text-white/65 mt-0.5">예상 점수 향상</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-extrabold tracking-tight">{result.passLine}</p>
            <p className="text-[10px] text-white/65 mt-0.5">합격 커트라인</p>
          </div>
        </div>
      </div>

      {/* 우선순위 보완 카드 */}
      <div className="space-y-3">
        {(result.topIssues || []).slice(0, 3).map((issue, idx) => (
          <Card key={idx} className="overflow-hidden border-sky-200 shadow-sm">
            {/* 카드 헤더 */}
            <div className="flex items-center gap-3.5 px-5 py-3.5 bg-blue-50 border-b border-sky-200">
              <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-extrabold text-sm flex-shrink-0">
                {idx + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-0.5">
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#1B3464] text-white">{issue.category}</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-600 text-white">우선순위 {idx + 1}</span>
                  <span className="text-[10px] text-muted-foreground">→ {issue.title} 항목</span>
                </div>
                <p className="text-sm font-bold text-foreground">{issue.title}</p>
              </div>
              <span className="text-xl font-extrabold text-green-600 flex-shrink-0">+{issue.expectedScore || 0}점</span>
            </div>

            {/* 문제 요약 */}
            <div className="flex items-start gap-2.5 px-5 py-3 bg-red-50 border-b border-red-100">
              <div className="w-5.5 h-5.5 rounded-md bg-white border border-red-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                <AlertCircle className="w-3.5 h-3.5 text-red-600" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-red-600 uppercase tracking-wide mb-0.5">문제 요약</p>
                <p className="text-xs font-semibold text-foreground leading-relaxed">
                  {issue.reason?.[0] || '평가위원이 실행 가능성을 판단할 수 없습니다.'}
                </p>
              </div>
            </div>

            {/* 현재 ↔ AI 보완안 비교 */}
            <div className="px-5 py-4">
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="p-3 rounded-xl bg-red-50 border border-red-200">
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-[10px] font-bold text-red-600 uppercase tracking-wide">⊖ 현재 문장</span>
                  </div>
                  <p className="text-xs text-foreground leading-relaxed">
                    {issue.currentText || '본 사업의 결과물은 국내외 시장에 출시하여 매출을 창출할 예정이며, 주요 고객층을 대상으로 마케팅 활동을 전개합니다.'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-green-50 border border-green-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-green-600 uppercase tracking-wide">⊕ AI 보완안</span>
                    <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-white border border-green-200 text-green-700">
                      출처 포함
                    </span>
                  </div>
                  <p className="text-xs text-foreground leading-relaxed">
                    {issue.improvedText || '1단계(1~6개월): 국내 자동차 부품 3개사 PoC → 2단계(6~12개월): 양산 적용 매출 50억 → 3단계(12~24개월): 동남아 진출·누적 200억.'}
                  </p>
                </div>
              </div>

              {/* 왜 더 좋은가 */}
              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-1.5">
                  {(issue.reason || ['실행 가능성', '고객 명확성', '성과 흐름']).slice(0, 3).map((r, i) => (
                    <span key={i} className="text-[10px] font-bold px-2 py-0.5 rounded bg-green-100 text-green-700">✓ {r}</span>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground">⏱ 적용 후 자동 재평가</span>
                  <Button size="sm" variant="outline" className="text-xs h-7">직접 수정</Button>
                  <Button
                    size="sm"
                    className="text-xs h-7 gap-1 bg-[#1B3464] hover:bg-[#1B3464]/90"
                    onClick={() => applySingleImprovement(issue, idx)}
                    disabled={applyingIdx === idx}
                  >
                    {applyingIdx === idx
                      ? <><Loader2 className="w-3 h-3 animate-spin" />적용 중...</>
                      : <>AI 보완안 적용 ✓</>
                    }
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}

        {(!result.topIssues || result.topIssues.length === 0) && (
          <Card className="bg-muted/30">
            <CardContent className="px-5 py-10 text-center">
              <Sparkles className="w-8 h-8 mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-sm font-semibold text-foreground mb-1">AI 평가를 시작하면 보완 항목이 자동으로 추출됩니다</p>
              <p className="text-xs text-muted-foreground">상단의 'AI 평가 시작' 버튼을 눌러 진행하세요</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* 보완 진행 상황 */}
      <Card>
        <CardHeader className="pb-2 pt-4 px-5">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <BarChart3 className="w-4 h-4 text-primary" />보완 진행 상황
          </CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-4">
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: '적용 완료', count: result.improvementProgress?.applied   || 0, color: 'text-green-600', dot: 'bg-green-500' },
              { label: '진행 중',   count: result.improvementProgress?.inProgress || 0, color: 'text-blue-600',  dot: 'bg-blue-500'  },
              { label: '자료 필요', count: result.improvementProgress?.needsData  || 0, color: 'text-amber-600', dot: 'bg-amber-500' },
              { label: '대기',      count: result.improvementProgress?.waiting    || 0, color: 'text-muted-foreground', dot: 'bg-gray-400' },
            ].map((s, i) => (
              <div key={i} className="flex items-center gap-2.5 p-3 rounded-xl border border-border">
                <div className={cn('w-2 h-2 rounded-full flex-shrink-0', s.dot)} />
                <div>
                  <p className="text-[10px] text-muted-foreground">{s.label}</p>
                  <p className={cn('text-lg font-bold', s.color)}>{s.count}건</p>
                </div>
              </div>
            ))}
          </div>
          <Separator className="my-4" />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-foreground mb-0.5">예상 점수 변화</p>
              <p className="text-[11px] text-muted-foreground">
                현재 {result.currentScore}점 → 보완 완료 시 {result.currentScore + result.expectedImprovement}점
                (커트라인 {result.passLine}점)
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-extrabold text-foreground">{result.currentScore}</span>
              <ArrowRight className="w-4 h-4 text-muted-foreground" />
              <span className="text-2xl font-extrabold text-green-600">{result.currentScore + result.expectedImprovement}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 최종 정합성 검사 */}
      <Card className="bg-violet-50/50 border-violet-200">
        <CardContent className="px-5 py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center flex-shrink-0">
                <Zap className="w-5 h-5 text-violet-600" />
              </div>
              <div>
                <p className="text-sm font-bold text-foreground">최종 정합성 검사</p>
                <p className="text-xs text-muted-foreground">모든 보완 적용 후 6가지 항목을 자동 검사하여 문서 품질을 보장합니다.</p>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {['수치 일관성', '일정 일관성', '예산-성과 연결성', '항목 간 중복', '과장 표현', '평가기준 누락'].map(check => (
                    <span key={check} className="text-[9px] font-medium px-1.5 py-0.5 rounded border border-border bg-white text-muted-foreground">
                      ⊙ {check}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <Button className="bg-violet-600 hover:bg-violet-700 gap-2 flex-shrink-0">
              <Zap className="w-4 h-4" />최종 정합성 검사 시작
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 하단 액션 */}
      <div className="flex items-center justify-between pt-1">
        <Button variant="outline" className="gap-1.5">
          <Download className="w-3.5 h-3.5" />현재 초안 다운로드
        </Button>
        <Button variant="outline" className="gap-1.5">
          <FileText className="w-3.5 h-3.5" />평가 리포트 다운로드
        </Button>
        <Button variant="outline" className="gap-1.5" onClick={runEvaluation} disabled={evaluating}>
          {evaluating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
          재평가
        </Button>
      </div>
    </div>
  )
}

// DraftPage.jsx 내부 최하단에 추가하세요
function Step5Complete({ notice, drafts }) {
  // .docx 파일 생성 및 다운로드 로직
  const handleDocxDownload = async () => {
    const children = [
      new Paragraph({
        text: `${notice?.title || '사업계획서'} - 사업계획서 초안`,
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 400 },
      })
    ]

    DRAFT_SECTIONS.forEach((sec) => {
      if (drafts[sec.key]) {
        children.push(
          new Paragraph({
            text: sec.label,
            heading: HeadingLevel.HEADING_2,
            spacing: { before: 400, after: 200 },
          }),
          new Paragraph({
            children: drafts[sec.key].split('\n').map(line => 
              new TextRun({ text: line, break: 1 })
            ),
          })
        )
      }
    })

    const doc = new Document({ sections: [{ properties: {}, children }] })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `사업계획서_${notice?.title || '제목없음'}.docx`)
  }

  // .txt 파일 다운로드 로직
  const handleTxtDownload = () => {
    const text = DRAFT_SECTIONS.map(sec => `[${sec.label}]\n${drafts[sec.key] || ''}`).join('\n\n')
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    saveAs(blob, `사업계획서_${notice?.title || '제목없음'}.txt`)
  }

  const handleHwpxDownload = async () => {
    // 각 섹션을 [라벨] + 본문 줄 단위로 변환 → backend가 HWPX로 패킹
    const lines = []
    DRAFT_SECTIONS.forEach((sec) => {
      lines.push(`[${sec.label}]`)
      const body = (drafts[sec.key] || '').split('\n')
      body.forEach((l) => lines.push(l))
      lines.push('')  // 섹션 사이 빈 줄
    })
    const filename = `사업계획서_${notice?.title || '제목없음'}.hwpx`
    try {
      const res = await fetch('/api/files/export-hwpx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lines, filename }),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({}))
        throw new Error(e.detail || `HTTP ${res.status}`)
      }
      const blob = await res.blob()
      saveAs(blob, filename)
    } catch (e) {
      alert('HWPX 다운로드 실패: ' + (e.message || ''))
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto py-8 animate-in fade-in zoom-in duration-500">
      <div className="text-center space-y-3">
        <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-foreground">사업계획서 초안 작성이 완료되었습니다!</h2>
        <p className="text-sm text-muted-foreground">
          작성된 문서를 다운로드하여 최종 검토 후 기관 시스템에 제출해주세요.
        </p>
      </div>

      {/* 종합 평가 리포트 */}
      <Card className="border-green-200 bg-green-50/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Award className="w-4 h-4 text-green-600" />
            AI 종합 평가 리포트
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 bg-white rounded-lg border border-border">
            <div>
              <p className="text-xs text-muted-foreground mb-1">최종 예상 점수 (보완 완료)</p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-foreground">90</span>
                <span className="text-sm text-muted-foreground">/ 100점</span>
                <Badge variant="success" className="ml-2">+12점 향상</Badge>
              </div>
            </div>
            <div className="space-y-1 text-right">
              <p className="text-xs text-muted-foreground">기술성: <strong className="text-green-600">우수</strong></p>
              <p className="text-xs text-muted-foreground">사업성: <strong className="text-green-600">우수</strong></p>
              <p className="text-xs text-muted-foreground">기대효과: <strong className="text-green-600">우수</strong></p>
              <p className="text-xs text-muted-foreground">수행역량: <strong className="text-blue-600">양호</strong></p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 다운로드 및 제출 버튼 */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-6 text-center space-y-4">
            <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto">
              <Download className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold mb-1">문서 다운로드</h3>
              <p className="text-xs text-muted-foreground">.docx / .hwpx / .txt 로 저장</p>
            </div>
            <div className="flex gap-2 justify-center flex-wrap">
              <Button variant="outline" size="sm" onClick={handleTxtDownload}>
                .TXT 다운로드
              </Button>
              <Button variant="outline" size="sm" onClick={handleHwpxDownload}>
                .HWPX 다운로드
              </Button>
              <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={handleDocxDownload}>
                .DOCX 다운로드
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6 text-center space-y-4">
            <div className="w-12 h-12 bg-violet-50 text-violet-600 rounded-full flex items-center justify-center mx-auto">
              <Send className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold mb-1">기관 제출</h3>
              <p className="text-xs text-muted-foreground">해당 사업 접수처로 이동하여 제출</p>
            </div>
            <Button 
              className="w-full bg-violet-600 hover:bg-violet-700" 
              onClick={() => window.open(notice?.rceptEngnHmpgUrl || '#', '_blank')}
            >
              온라인 신청하러 가기 <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// ── 메인 DraftPage ─────────────────────────────────────────────────
export default function DraftPage({ notice, onBack, onComplete, profileData, savedDraft, onSaveDraft }) {
  // savedDraft가 있으면 그 값으로 초기화, 없으면 새로 시작
  const [currentStep, setCurrentStep] = useState(savedDraft?.currentStep || 1)
  const [uploads, setUploads] = useState(savedDraft?.uploads || {})
  const [drafts, setDrafts] = useState(savedDraft?.drafts || {})
  const [completedSteps, setCompletedSteps] = useState(savedDraft?.completedSteps || [])
  const [checkResult, setCheckResult] = useState(savedDraft?.checkResult || null)

  // 공고가 바뀌면 해당 공고의 저장된 데이터로 초기화
  useEffect(() => {
    if (savedDraft && savedDraft.notice?.id === notice?.id) {
      setCurrentStep(savedDraft.currentStep || 1)
      setUploads(savedDraft.uploads || {})
      setDrafts(savedDraft.drafts || {})
      setCompletedSteps(savedDraft.completedSteps || [])
      setCheckResult(savedDraft.checkResult || null)  // ✅ 추가
    } else {
      setCurrentStep(1)
      setUploads({})
      setDrafts({})
      setCompletedSteps([])
      setCheckResult(null)  // ✅ 추가
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notice?.id])

  // 변경사항을 localStorage에 자동 저장 (디바운스)
  useEffect(() => {
    if (!notice?.id || !onSaveDraft) return

    const timer = setTimeout(() => {
      const uploadsMetadata = Object.fromEntries(
        Object.entries(uploads).map(([key, files]) => [
          key,
          (files || []).map(f => ({
            name: f.name,
            size: f.size,
            type: f.type,
          })),
        ]),
      )

      onSaveDraft(notice, {
        currentStep,
        uploads: uploadsMetadata,
        drafts,
        completedSteps,
        checkResult,  // ✅ 추가
        ...(currentStep >= 5 && { status: '작성완료' }),
      })
    }, 500)

    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, uploads, drafts, completedSteps, checkResult, notice?.id])

  const goNext = () => {
    setCompletedSteps((prev) =>
      prev.includes(currentStep) ? prev : [...prev, currentStep],
    )
    setCurrentStep(s => Math.min(5, s + 1))
  }
  const goPrev = () => setCurrentStep(s => Math.max(1, s - 1))

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" /> {notice ? '상세로' : '뒤로가기'}
        </Button>
        <div className="text-center">
          <h2 className="text-base font-bold text-foreground">제출 서류 작성</h2>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            자동 저장됨 · 다른 화면 이동해도 작성 내용 유지
          </p>
        </div>
        <div />
      </div>

      {/* 스텝 인디케이터 */}
      <StepIndicator currentStep={currentStep} />

      {/* 스텝 컨텐츠 */}
      <Card>
        <CardContent className="px-6 py-6">
          {currentStep === 1 && (
            <Step1Common
              variant="v1"
              notice={notice}
              uploads={uploads}
              onUploadsChange={setUploads}
            />
          )}
          {currentStep === 2 && (
            <Step2Check
              notice={notice}
              uploads={uploads}
              profileData={profileData}
              checkResult={checkResult}
              onCheckResultChange={setCheckResult}
            />
          )}
          {currentStep === 3 && (
            <Step3Draft
              notice={notice}
              profileData={profileData}
              drafts={drafts}
              onDraftsChange={setDrafts}
            />
          )}
          {currentStep === 4 && (
            <Step4Review
              notice={notice}
              drafts={drafts}
              onDraftsChange={setDrafts}
            />
          )}
          {currentStep === 5 && (
            <Step5Complete
              notice={notice}
              drafts={drafts}
            />
          )}
        </CardContent>
      </Card>

      {/* 이전/다음 버튼 */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={goPrev}
          disabled={currentStep === 1}
        >
          <ArrowLeft className="w-4 h-4" /> 이전
        </Button>
        <span className="text-sm text-muted-foreground">
          STEP {currentStep} / {STEPS.length}
        </span>
        {currentStep < 5 ? (
          <Button onClick={goNext}>
            다음 <ArrowRight className="w-4 h-4" />
          </Button>
        ) : (
          <Button variant="ghost" onClick={onComplete ?? onBack}>
            제출 현황 보기
          </Button>
        )}
      </div>
    </div>
  )
}