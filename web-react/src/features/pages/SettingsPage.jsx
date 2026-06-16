import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Building2, FileText, Loader2, Save, Sparkles, Trash2, Upload } from 'lucide-react'
import { libraryApi, analysisApi } from '../../api/backendApi'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Separator } from '../../components/ui/separator'
import { Textarea } from '../../components/ui/textarea'
import { cn } from '../../lib/utils'

// 업종 대분류
const INDUSTRY_OPTIONS = [
  '제조업', 'IT/소프트웨어', '바이오/의료', '에너지/환경',
  '건설/부동산', '유통/물류', '금융/보험', '교육', '기타',
]

// 세부 업종 (대분류별)
const SUB_INDUSTRY_MAP = {
  '제조업': ['자동차 부품', '반도체', '전자부품', '기계장비', '소재/화학', '식품', '섬유/의류'],
  'IT/소프트웨어': ['SaaS', 'AI/ML', '보안', '게임', '핀테크', '클라우드'],
  '바이오/의료': ['의료기기', '제약', '헬스케어', '임상'],
  '에너지/환경': ['신재생에너지', '탄소중립', '수소', '폐기물'],
  '건설/부동산': ['건설', '인테리어', '부동산'],
  '유통/물류': ['이커머스', '물류', '유통'],
  '금융/보험': ['핀테크', '보험', '자산관리'],
  '교육': ['에듀테크', '직업훈련', '평생교육'],
  '기타': ['서비스업', '농업', '수산업'],
}

// 지역 옵션
const REGION_OPTIONS = [
  '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
  '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
]

// 매출 규모 옵션
const REVENUE_OPTIONS = [
  '1억 미만', '1억~10억', '10억~50억', '50억~100억',
  '100억~500억', '500억~1천억', '1천억~5천억', '5천억 이상',
]

// 인증/자격 목록
const CERTIFICATIONS = [
  { key: 'venture',    label: '벤처기업 인증' },
  { key: 'inno',       label: '이노비즈 (기술혁신형 중소기업)' },
  { key: 'main',       label: '메인비즈 (경영혁신형 중소기업)' },
  { key: 'patent',     label: '특허/실용신안 보유' },
  { key: 'research',   label: '기업부설연구소/연구개발전담부서' },
  { key: 'iso',        label: 'ISO 인증 (9001/14001 등)' },
  { key: 'women',      label: '여성기업' },
  { key: 'social',     label: '사회적기업' },
  { key: 'disabled',   label: '장애인기업' },
  { key: 'green',      label: '녹색인증/녹색기술' },
]

function Field({ id, label, required, children, hint }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs font-medium text-foreground normal-case tracking-normal">
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  )
}

function SectionHeader({ title, desc }) {
  return (
    <div className="pb-3 border-b border-border mb-4">
      <h3 className="text-sm font-bold text-foreground">{title}</h3>
      {desc && <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>}
    </div>
  )
}

export default function SettingsPage({ settings, onChange, onSave, onBack }) {
  const { profileData } = settings

  const updateProfile = (key, value) =>
    onChange('profileData', { ...profileData, [key]: value })

  const toggleCert = (key) => {
    const current = profileData.certifications || []
    const next = current.includes(key)
      ? current.filter(k => k !== key)
      : [...current, key]
    updateProfile('certifications', next)
  }

  const subOptions = SUB_INDUSTRY_MAP[profileData.industry] || []

  return (
    <div className="space-y-5 max-w-3xl">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" /> 대시보드
        </Button>
        <h2 className="text-base font-bold text-foreground">내 기업 프로필</h2>
        <div />
      </div>

      <Alert variant="info">
        <Building2 className="w-4 h-4" />
        <AlertDescription className="text-xs">
          정보를 상세히 입력할수록 AI 매칭 정확도와 사업계획서 품질이 올라갑니다.
        </AlertDescription>
      </Alert>

      {/* ── 기본 정보 ── */}
      <Card>
        <CardHeader className="pb-0 pt-5 px-5">
          <CardTitle className="text-sm">기본 정보</CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5 pt-4 space-y-4">
          <SectionHeader title="" desc="" />
          <div className="grid grid-cols-2 gap-4">
            <Field id="company-name" label="회사명" required>
              <Input
                id="company-name"
                value={profileData.companyName || '아진산업(주)'}
                placeholder="예: 아진산업(주)"
                onChange={(e) => updateProfile('companyName', e.target.value)}
              />
            </Field>
            <Field id="rep-name" label="대표자">
              <Input
                id="rep-name"
                value={profileData.representative || ''}
                placeholder="예: 홍길동"
                onChange={(e) => updateProfile('representative', e.target.value)}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field id="biz-number" label="사업자등록번호">
              <Input
                id="biz-number"
                value={profileData.bizNumber || ''}
                placeholder="예: 123-45-67890"
                onChange={(e) => updateProfile('bizNumber', e.target.value)}
              />
            </Field>
            <Field id="founded" label="설립일">
              <Input
                id="founded"
                type="date"
                value={profileData.foundedDate || ''}
                onChange={(e) => updateProfile('foundedDate', e.target.value)}
              />
            </Field>
          </div>
          <Field id="address" label="주소 (본사 소재지)" required>
            <div className="grid grid-cols-[200px_1fr] gap-2">
              <select
                value={profileData.region || ''}
                onChange={(e) => updateProfile('region', e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="">시/도 선택</option>
                {REGION_OPTIONS.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              <Input
                id="address"
                value={profileData.address || ''}
                placeholder="상세 주소"
                onChange={(e) => updateProfile('address', e.target.value)}
              />
            </div>
          </Field>
        </CardContent>
      </Card>

      {/* ── 공고 매칭 필수 항목 ── */}
      <Card>
        <CardHeader className="pb-0 pt-5 px-5">
          <CardTitle className="text-sm text-primary">공고 매칭 필수 항목</CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5 pt-2 space-y-4">
          <p className="text-xs text-muted-foreground">
            이 정보를 기반으로 AI가 적합한 지원사업을 매칭합니다. 정확히 입력해주세요.
          </p>

          <div className="grid grid-cols-2 gap-4">
            <Field id="industry" label="업종 (산업)" required>
              <select
                id="industry"
                value={profileData.industry || ''}
                onChange={(e) => {
                  updateProfile('industry', e.target.value)
                  updateProfile('subIndustry', '')
                }}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="">선택해주세요</option>
                {INDUSTRY_OPTIONS.map(o => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </Field>

            <Field id="sub-industry" label="세부 업종">
              <select
                id="sub-industry"
                value={profileData.subIndustry || ''}
                onChange={(e) => updateProfile('subIndustry', e.target.value)}
                disabled={!profileData.industry}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
              >
                <option value="">상위 업종을 먼저 선택하세요</option>
                {subOptions.map(o => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field id="employees" label="직원 수" required>
              <Input
                id="employees"
                type="number"
                min="0"
                value={profileData.employees || ''}
                placeholder="예: 1200"
                onChange={(e) => updateProfile('employees', e.target.value)}
              />
            </Field>
            <Field id="revenue" label="매출 규모 (연간)" required>
              <select
                id="revenue"
                value={profileData.revenueRange || ''}
                onChange={(e) => updateProfile('revenueRange', e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="">선택해주세요</option>
                {REVENUE_OPTIONS.map(o => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </Field>
          </div>

          <Separator />

          {/* 보유 인증/자격 */}
          <Field id="certs" label="보유 인증/자격 (매칭 시 가점 반영)">
            <div className="grid grid-cols-2 gap-2 mt-1">
              {CERTIFICATIONS.map(cert => {
                const checked = (profileData.certifications || []).includes(cert.key)
                return (
                  <label
                    key={cert.key}
                    className={cn(
                      'flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-colors text-sm',
                      checked
                        ? 'border-primary bg-primary/5 text-primary'
                        : 'border-border hover:border-primary/40 text-foreground',
                    )}
                  >
                    <input
                      type="checkbox"
                      className="w-4 h-4 accent-primary"
                      checked={checked}
                      onChange={() => toggleCert(cert.key)}
                    />
                    {cert.label}
                  </label>
                )
              })}
            </div>
          </Field>

          <Separator />

          {/* 매칭/제외 키워드 */}
          <div className="grid grid-cols-2 gap-4">
            <Field
              id="match-keywords"
              label="매칭 키워드 (가점)"
              hint="이 키워드가 포함된 공고를 우선 표시합니다 (쉼표로 구분, 5~10개 권장)"
            >
              <Textarea
                id="match-keywords"
                rows={3}
                value={profileData.matchKeywords || ''}
                placeholder="예: 스마트공장, 자동차, DX, 프레스"
                onChange={(e) => updateProfile('matchKeywords', e.target.value)}
              />
            </Field>
            <Field
              id="exclude-keywords"
              label="제외 키워드 (필터링)"
              hint="이 키워드가 포함된 공고는 매칭에서 제외됩니다 (쉼표로 구분)"
            >
              <Textarea
                id="exclude-keywords"
                rows={3}
                value={profileData.excludeKeywords || ''}
                placeholder="예: 농업, 수산업, 관광"
                onChange={(e) => updateProfile('excludeKeywords', e.target.value)}
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      {/* ── 사업계획서 품질 향상 항목 ── */}
      <Card>
        <CardHeader className="pb-0 pt-5 px-5">
          <CardTitle className="text-sm">사업계획서 품질 향상 항목</CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5 pt-2 space-y-4">
          <p className="text-xs text-muted-foreground">
            AI 사업계획서 생성 시 이 정보를 활용합니다. 구체적으로 입력할수록 초안 품질이 높아집니다.
          </p>

          <Field
            id="main-business"
            label="주요 사업 내용"
            required
            hint="핵심 제품/서비스를 구체적으로 기술하세요."
          >
            <Textarea
              id="main-business"
              rows={3}
              value={profileData.summary || ''}
              placeholder="예: 자동차 차체 프레스 부품 및 조립 전문 제조기업으로, 현대·기아차 1차 협력사입니다."
              onChange={(e) => updateProfile('summary', e.target.value)}
            />
          </Field>

          <Field
            id="achievements"
            label="주요 실적"
            hint="예: 매출, 수주, 수출, 투자유치 등"
          >
            <Textarea
              id="achievements"
              rows={3}
              value={profileData.achievements || ''}
              placeholder="예: 2025년 매출 5,000억, 수출 200억, 스마트공장 2등급 인증"
              onChange={(e) => updateProfile('achievements', e.target.value)}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field
              id="core-tech"
              label="핵심 기술 / 지적재산권"
              hint="특허, 기술 명칭 등"
            >
              <Textarea
                id="core-tech"
                rows={3}
                value={profileData.coreTech || ''}
                placeholder="예: AI 기반 용접 품질 검사 기술 특허 2건, 스마트 팩토리 솔루션"
                onChange={(e) => updateProfile('coreTech', e.target.value)}
              />
            </Field>
            <Field
              id="core-team"
              label="핵심 인력 구성"
              hint="대표자 경력, 핵심 팀원"
            >
              <Textarea
                id="core-team"
                rows={3}
                value={profileData.coreTeam || ''}
                placeholder="예: 대표 - 제조업 20년, 연구소장 - KAIST 박사"
                onChange={(e) => updateProfile('coreTeam', e.target.value)}
              />
            </Field>
          </div>

          <Field id="strategy" label="중장기 성장 전략">
            <Textarea
              id="strategy"
              rows={3}
              value={profileData.strategy || ''}
              placeholder="예: 미래 모빌리티 전환, 스마트 팩토리 고도화, 해외 시장 진출"
              onChange={(e) => updateProfile('strategy', e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      {/* 회사 자료 업로드 + 기업 분석 (E-4) */}
      <CompanyMaterialsCard noticeSchema={null} />

      {/* 저장 버튼 */}
      <div className="flex justify-end pb-6">
        <Button onClick={onSave} className="gap-2 px-8" size="lg">
          <Save className="w-4 h-4" /> 저장하기
        </Button>
      </div>
    </div>
  )
}

// ─── 회사 자료 업로드 + 기업 분석 카드 (E-4, 2026-05-25) ───
//   업로드된 파일은 자료실(file_type='회사자료')에 자동 반영됨 (같은 company_files 테이블)
function CompanyMaterialsCard({ noticeSchema }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')

  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const res = await libraryApi.list({ category: '회사자료', sort: 'recent' })
      setItems(res.items || [])
    } catch (e) {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { reload() }, [reload])

  const onUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setUploading(true)
    setUploadError('')
    try {
      for (const f of files) {
        await libraryApi.upload({ file: f, category: '회사자료' })
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
    if (!window.confirm('이 자료를 삭제할까요?')) return
    try {
      await libraryApi.remove(fileId)
      await reload()
    } catch (e) {
      alert('삭제 실패: ' + (e.message || ''))
    }
  }

  const runAnalysis = async () => {
    setAnalyzing(true)
    setAnalysisError('')
    setAnalysis(null)
    try {
      const res = await analysisApi.analyzeCompany({
        sessionId: '',
        companyFiles: items.map((it) => ({ file_id: it.file_id, file_name: it.file_name })),
        noticeSchema: noticeSchema || {},
      })
      setAnalysis(res)
    } catch (e) {
      setAnalysisError(e.message || '분석 실패')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <Card>
      <CardHeader className="pb-0 pt-5 px-5">
        <CardTitle className="text-sm flex items-center gap-2">
          <Building2 className="w-4 h-4 text-primary" /> 회사 자료 + 기업 분석
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-1">
          여기 업로드한 파일은 <strong>자료실</strong>의 회사 자료 카테고리에도 자동 반영됩니다.
        </p>
      </CardHeader>
      <CardContent className="px-5 pb-5 pt-4 space-y-4">
        {/* 업로드 */}
        <label className="block">
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.hwp,.hwpx,.xlsx,.xls,.png,.jpg,.jpeg"
            onChange={onUpload}
            disabled={uploading}
            className="hidden"
          />
          <div className={`border-2 border-dashed rounded-lg py-6 text-center transition cursor-pointer ${
            uploading ? 'border-muted bg-muted/30' : 'border-border hover:border-primary/40 hover:bg-primary/5'
          }`}>
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> 업로드 중...
              </div>
            ) : (
              <>
                <Upload className="w-6 h-6 mx-auto mb-1.5 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">회사 자료 업로드</p>
                <p className="text-xs text-muted-foreground mt-0.5">사업보고서 / 재무제표 / 회사소개서 등 — PDF는 내용 자동 추출</p>
              </>
            )}
          </div>
        </label>
        {uploadError && (
          <Alert variant="destructive"><AlertDescription className="text-xs">{uploadError}</AlertDescription></Alert>
        )}

        {/* 자료 리스트 */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            등록된 회사 자료 ({items.length})
          </p>
          {loading ? (
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> 불러오는 중...
            </div>
          ) : items.length === 0 ? (
            <p className="text-xs text-muted-foreground py-2">아직 업로드된 자료가 없습니다.</p>
          ) : (
            <div className="divide-y divide-border border border-border rounded">
              {items.map((it) => (
                <div key={it.file_id} className="flex items-center gap-2 px-3 py-2">
                  <FileText className="w-3.5 h-3.5 text-primary shrink-0" />
                  <span className="flex-1 text-xs text-foreground truncate">{it.file_name}</span>
                  <Badge variant="blue" className="text-[10px] shrink-0">{it.category}</Badge>
                  <span className="text-[10px] text-muted-foreground">{it.char_count?.toLocaleString() || 0}자</span>
                  <button
                    onClick={() => onDelete(it.file_id)}
                    className="p-1 text-muted-foreground hover:text-destructive"
                    aria-label="삭제"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 기업 분석 */}
        <div className="border-t border-border pt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" /> 기업 분석
            </p>
            <Button size="sm" variant="outline" onClick={runAnalysis} disabled={analyzing || items.length === 0}>
              {analyzing ? (<><Loader2 className="w-3.5 h-3.5 animate-spin" /> 분석 중...</>) : '기업 분석 실행'}
            </Button>
          </div>
          {analysisError && (
            <Alert variant="destructive" className="mt-2">
              <AlertDescription className="text-xs">{analysisError}</AlertDescription>
            </Alert>
          )}
          {analysis && (
            <pre className="text-[11px] text-foreground whitespace-pre-wrap bg-muted/30 rounded p-3 border border-border max-h-[300px] overflow-auto leading-relaxed mt-2">
              {typeof analysis === 'string' ? analysis : JSON.stringify(analysis, null, 2)}
            </pre>
          )}
          {!analysis && !analysisError && (
            <p className="text-xs text-muted-foreground">
              업로드한 회사 자료를 바탕으로 AI가 기업 강점·약점·역량을 정리합니다.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}