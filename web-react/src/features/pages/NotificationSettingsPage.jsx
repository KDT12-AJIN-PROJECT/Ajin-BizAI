import { ArrowLeft, Bell, Save, TrendingUp } from 'lucide-react'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Label } from '../../components/ui/label'
import { Separator } from '../../components/ui/separator'
import { Textarea } from '../../components/ui/textarea'

const PRESET_KEYWORDS = {
  '아진특화': ['자동차', '부품', '제조', '프레스', '금형', '에너지', '혁신'],
  '스마트공장': ['스마트공장', 'DX', '자동화', 'AI', '디지털전환'],
  'R&D/기술': ['R&D', '기술개발', '인증', '특허', '기술이전'],
  '금융지원': ['자금', '대출', '보증', '투자', '융자'],
  '수출/마케팅': ['해외진출', '수출', '마케팅', '판로개척'],
}

export default function NotificationSettingsPage({ settings, onChange, onSave, onBack }) {
  const { simThreshold, notiKeywordsStr } = settings

  const addPreset = (keywords) => {
    const current = notiKeywordsStr
      .split(',')
      .map(k => k.trim())
      .filter(Boolean)
    const toAdd = keywords.filter(k => !current.includes(k))
    const next = [...current, ...toAdd].join(', ')
    onChange('notiKeywordsStr', next)
  }

  const currentCount = notiKeywordsStr
    .split(',')
    .map(k => k.trim())
    .filter(Boolean).length

  // 임계값별 예상 매칭 건수 레이블
  const getThresholdLabel = (val) => {
    if (val <= 0.02) return { text: '넓게 (많은 공고)', color: 'text-blue-600' }
    if (val <= 0.04) return { text: '보통', color: 'text-green-600' }
    if (val <= 0.06) return { text: '좁게', color: 'text-amber-600' }
    return { text: '매우 좁게 (엄격)', color: 'text-red-600' }
  }

  const label = getThresholdLabel(simThreshold)

  return (
    <div className="space-y-4 max-w-3xl">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="w-4 h-4" /> 대시보드
        </Button>
        <h2 className="text-base font-bold text-foreground">알림 설정</h2>
        <div />
      </div>

      {/* AI 적합도 임계값 */}
      <Card>
        <CardHeader className="pb-2 pt-5 px-5">
          <CardTitle className="flex items-center gap-2 text-sm">
            <TrendingUp className="w-4 h-4 text-primary" />
            AI 적합도 임계값
          </CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">현재 임계값</span>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-primary">
                {(simThreshold * 100).toFixed(0)}%
              </span>
              <Badge variant="secondary" className={label.color}>
                {label.text}
              </Badge>
            </div>
          </div>

          <input
            type="range"
            min="0.01" max="0.1" step="0.005"
            value={simThreshold}
            onChange={(e) => onChange('simThreshold', Number(e.target.value))}
            className="w-full accent-primary"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>1% (많이)</span>
            <span>5% (보통)</span>
            <span>10% (엄격)</span>
          </div>

          <Alert variant="info">
            <AlertDescription className="text-xs">
              임계값이 낮을수록 더 많은 공고가 매칭되고, 높을수록 아진산업과 가장 관련성 높은 공고만 표시됩니다.
              현재 <strong>{(simThreshold * 100).toFixed(0)}%</strong> 이상인 공고가 맞춤 알림에 표시됩니다.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* 알림 강조 키워드 */}
      <Card>
        <CardHeader className="pb-2 pt-5 px-5">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Bell className="w-4 h-4 text-primary" />
            알림 강조 키워드
            <Badge variant="secondary" className="ml-auto text-[11px]">
              {currentCount}개
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-5 space-y-4">

          {/* 프리셋 버튼 */}
          <div>
            <Label className="mb-2 block">빠른 추가 (프리셋)</Label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(PRESET_KEYWORDS).map(([group, keywords]) => (
                <button
                  key={group}
                  type="button"
                  onClick={() => addPreset(keywords)}
                  className="px-3 py-1.5 text-xs rounded-md border border-border bg-white hover:bg-primary/5 hover:border-primary/40 transition-colors"
                >
                  + {group}
                </button>
              ))}
            </div>
          </div>

          <Separator />

          {/* 직접 입력 */}
          <div className="space-y-1.5">
            <Label htmlFor="noti-keywords">직접 입력 (쉼표로 구분)</Label>
            <Textarea
              id="noti-keywords"
              rows={4}
              value={notiKeywordsStr}
              placeholder="예: 자동차, 스마트공장, DX, 에너지, R&D"
              onChange={(e) => onChange('notiKeywordsStr', e.target.value)}
            />
          </div>

          {/* 현재 키워드 미리보기 */}
          {currentCount > 0 && (
            <div>
              <Label className="mb-2 block">현재 설정된 키워드</Label>
              <div className="flex flex-wrap gap-1.5">
                {notiKeywordsStr.split(',').map(k => k.trim()).filter(Boolean).map((kw) => (
                  <Badge key={kw} variant="blue" className="text-xs">
                    {kw}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <Alert variant="info">
            <AlertDescription className="text-xs">
              키워드가 포함된 공고는 맞춤 알림 목록 <strong>상단</strong>에 표시됩니다.
              아진산업 특화 키워드를 설정하면 중요 공고를 더 빠르게 찾을 수 있습니다.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <div className="flex justify-end pb-6">
        <Button onClick={onSave} className="gap-2 px-8" size="lg">
          <Save className="w-4 h-4" /> 알림 설정 저장
        </Button>
      </div>
    </div>
  )
}