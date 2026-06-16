import {
  AlertTriangle, Award, Bell, Bookmark, FileSearch, FileText,
  TrendingUp,
} from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'
import { Separator } from '../../components/ui/separator'
import { cn } from '../../lib/utils'
import { formatDate, getDdayText } from '../notices/utils/date'

function StatCard({ label, value, color = 'text-primary', icon: Icon, onClick }) {
  return (
    <Card
      className={onClick ? 'cursor-pointer hover:shadow-md hover:border-primary/40 transition-all' : ''}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
            {label}
          </p>
          {Icon && <Icon className="w-4 h-4 text-muted-foreground/40" />}
        </div>
        <p className={`text-2xl font-bold ${color}`}>{value}</p>
      </CardContent>
    </Card>
  )
}

function toDateObj(v) {
  if (!v) return null
  if (v instanceof Date) return isNaN(v.getTime()) ? null : v
  const d = new Date(v)
  return isNaN(d.getTime()) ? null : d
}

// 마감 임박 공고 (D-7 이내)
function getUrgentNotices(notices, limit = 5) {
  const today = Date.now()
  return notices
    .filter(n => {
      const d = toDateObj(n.date)
      if (!d) return false
      const days = Math.ceil((d.getTime() - today) / 86400000)
      return days >= 0 && days <= 7
    })
    .sort((a, b) => (toDateObj(a.date)?.getTime() ?? 0) - (toDateObj(b.date)?.getTime() ?? 0))
    .slice(0, limit)
}

export default function DashboardPage({
  totalNotices, matchedCount, bookmarkCount,
  draftsInProgress = [],
  scoredNotices = [],
  onMove,
  onResumeDraft,
  onOpenDetail,
}) {
  const urgentNotices = getUrgentNotices(scoredNotices)

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div>
        <h1 className="text-2xl font-bold text-foreground mb-1">오늘의 작업</h1>
        <p className="text-sm text-muted-foreground">
          진행 중인 사업계획서, 마감 임박 공고, 최근 평가 결과를 한눈에
        </p>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="작성 중"
          value={`${draftsInProgress.length}편`}
          color="text-foreground"
          icon={FileText}
          onClick={() => onMove('draft-list')}
        />
        <StatCard
          label="북마크"
          value={`${bookmarkCount}건`}
          color="text-amber-600"
          icon={Bookmark}
          onClick={() => onMove('bookmark')}
        />
        <StatCard
          label="마감 임박"
          value={`${urgentNotices.length}건`}
          color="text-rose-600"
          icon={AlertTriangle}
          onClick={() => onMove('search')}
        />
        <StatCard
          label="맞춤 매칭"
          value={`${matchedCount}건`}
          color="text-green-600"
          icon={TrendingUp}
          onClick={() => onMove('notification')}
        />
      </div>

      {/* 좌측 메인 / 우측 사이드 */}
      <div className="grid grid-cols-3 gap-4">
        {/* ── 왼쪽: 작성 중인 사업계획서 (2/3 폭) ── */}
        <div className="col-span-2 space-y-4">
          {/* 새 공고 검색 버튼 */}
          <Button
            size="lg"
            className="w-full h-14 bg-slate-800 hover:bg-slate-900 gap-2 text-base"
            onClick={() => onMove('search')}
          >
            <FileSearch className="w-5 h-5" /> 새 공고 검색
          </Button>

          <Card>
            <CardHeader className="pb-3 pt-5 px-5">
              <CardTitle className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" />
                작성 중인 사업계획서
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 pb-5">
              {draftsInProgress.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <FileText className="w-10 h-10 mb-3 opacity-40" />
                  <p className="text-sm font-medium">작성 중인 사업계획서가 없습니다</p>
                  <p className="text-xs mt-1">공고 검색에서 신청 준비를 시작해 보세요</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {draftsInProgress.map((d) => {
                    const completedCount = d.completedSteps?.length || 0
                    const progress = (completedCount / 5) * 100
                    const updatedDate = d.updatedAt
                      ? new Date(d.updatedAt).toLocaleString('ko-KR', {
                          month: '2-digit', day: '2-digit',
                          hour: '2-digit', minute: '2-digit',
                        })
                      : '-'
                    return (
                      <div
                        key={d.notice.id}
                        className="p-4 rounded-lg border border-border hover:border-primary/40 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant="blue" className="text-[11px]">{d.notice.origin}</Badge>
                            <Badge variant="warning" className="text-[11px]">
                              자료 충족도 검사 단계
                            </Badge>
                          </div>
                          <Button size="sm" variant="outline" onClick={() => onResumeDraft(d)}>
                            <span>이어 작성</span>
                          </Button>
                        </div>
                        <p className="text-sm font-semibold text-foreground mb-2">{d.notice.title}</p>
                        <p className="text-xs text-muted-foreground mb-2">
                          마지막 저장: {updatedDate} · STEP {d.currentStep}/5
                        </p>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-muted rounded-full h-1.5">
                            <div
                              className="bg-primary h-1.5 rounded-full transition-all"
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                          <span className="text-xs font-bold text-primary w-10 text-right">
                            {Math.round(progress)}%
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
              {draftsInProgress.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full mt-2 text-xs h-7 text-muted-foreground"
                  onClick={() => onMove('draft-list')}
                >
                  모두 보기 →
                </Button>
              )}
            </CardContent>
          </Card>

          {/* 빠른 액션 */}
          <Separator />
          <div className="grid grid-cols-3 gap-3">
            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => onMove('bookmark')}>
              <CardContent className="p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                  <Bookmark className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">북마크</p>
                  <p className="text-xs text-muted-foreground">{bookmarkCount}건 저장됨</p>
                </div>
              </CardContent>
            </Card>

            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => onMove('notification')}>
              <CardContent className="p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <Bell className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">맞춤 알림</p>
                  <p className="text-xs text-muted-foreground">{matchedCount}건 매칭</p>
                </div>
              </CardContent>
            </Card>

            <Card className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => onMove('settings')}>
              <CardContent className="p-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-violet-100 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-violet-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">기업 설정</p>
                  <p className="text-xs text-muted-foreground">프로필 정확도</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* ── 우측 사이드 (1/3 폭) ── */}
        <div className="space-y-4">
          {/* 마감 임박 공고 */}
          <Card className="border-rose-200">
            <CardHeader className="pb-3 pt-4 px-4">
              <CardTitle className="flex items-center gap-2 text-sm">
                <AlertTriangle className="w-4 h-4 text-rose-500" />
                마감 임박 공고
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              {urgentNotices.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">
                  7일 이내 마감 공고가 없습니다
                </p>
              ) : (
                <div className="space-y-2">
                  {urgentNotices.map(notice => (
                    <button
                      key={notice.id}
                      type="button"
                      className="w-full text-left p-2.5 rounded-lg border border-border hover:border-rose-300 hover:bg-rose-50/50 transition-colors group"
                      onClick={() => onOpenDetail?.(notice)}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <p className="text-xs font-semibold text-foreground line-clamp-2 leading-snug flex-1">
                          {notice.title}
                        </p>
                        <Badge variant="destructive" className="text-[10px] px-1.5 h-4 shrink-0">
                          {getDdayText(notice.date)}
                        </Badge>
                      </div>
                      <p className="text-[10px] text-muted-foreground">
                        {formatDate(notice.date)} · {notice.region}
                      </p>
                    </button>
                  ))}
                </div>
              )}
              {urgentNotices.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full mt-2 text-xs h-7 text-muted-foreground"
                  onClick={() => onMove('search')}
                >
                  모두 보기 →
                </Button>
              )}
            </CardContent>
          </Card>

          {/* 최근 평가 결과 (예시 데이터 - 추후 LLM 평가 연동) */}
          <Card className="border-green-200">
            <CardHeader className="pb-3 pt-4 px-4">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Award className="w-4 h-4 text-green-600" />
                최근 평가 결과
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              {draftsInProgress.length === 0 ? (
                <div className="text-center py-6">
                  <Award className="w-8 h-8 mx-auto text-muted-foreground/30 mb-2" />
                  <p className="text-xs text-muted-foreground">
                    아직 평가된 사업계획서가 없습니다
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {draftsInProgress.slice(0, 3).map((d) => {
                    // 임시 점수 계산 (작성 진행률 기반)
                    const completedCount = d.completedSteps?.length || 0
                    const score = Math.min(95, 50 + completedCount * 9)
                    const passed = score >= 70
                    return (
                      <div key={d.notice.id} className="p-2.5 rounded-lg border border-border">
                        <p className="text-xs font-semibold text-foreground line-clamp-1 mb-1.5">
                          {d.notice.title}
                        </p>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-muted-foreground">
                            커트라인 70점 {passed ? '✓ 통과' : '미달'}
                          </span>
                          <div className="flex items-center gap-1">
                            <span className="text-lg font-bold text-foreground">{score}</span>
                            <Badge variant={passed ? 'success' : 'warning'} className="text-[9px] px-1 h-4">
                              {passed ? '+11' : '-3'}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}