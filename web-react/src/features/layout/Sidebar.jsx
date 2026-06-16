import { Building2, FileEdit, X } from 'lucide-react'
import { Card, CardContent } from '../../components/ui/card'
import { Separator } from '../../components/ui/separator'
import { Badge } from '../../components/ui/badge'
import { cn } from '../../lib/utils'

// STEP 라벨 매핑
const STEP_LABELS = {
  1: '자료 업로드',
  2: '자료 검사',
  3: '초안 작성',
  4: '전략 검토',
  5: '완료/제출',
}

function timeAgo(timestamp) {
  if (!timestamp) return ''
  const t = typeof timestamp === 'number' ? timestamp : new Date(timestamp).getTime()
  if (Number.isNaN(t)) return ''
  const diff = Date.now() - t
  if (diff < 0) return '방금 전'
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '방금 전'
  if (minutes < 60) return `${minutes}분 전`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}시간 전`
  const days = Math.floor(hours / 24)
  return `${days}일 전`
}

export default function Sidebar({ profileData, onMove, draftList = [], onResumeDraft, onRemoveDraft }) {
  return (
    <aside className="w-64 shrink-0 border-r border-border bg-white h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* 기업 프로필 카드 */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                <Building2 className="w-4 h-4 text-primary" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-bold text-foreground truncate">
                  {profileData?.companyName || '아진산업(주)'}
                </p>
                <p className="text-[11px] text-muted-foreground truncate">
                  {profileData?.field || '자동차 부품, DX'}
                </p>
              </div>
            </div>
            <Separator className="mb-3" />
            <dl className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">매출</dt>
                <dd className="font-medium text-foreground">{profileData?.sales || '약 5,000억 원'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">근로자</dt>
                <dd className="font-medium text-foreground">{profileData?.emp_count || '1,200명'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">분류</dt>
                <dd className="font-medium text-foreground">중견기업</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* 작성 중인 공고 */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                작성 중인 공고
              </p>
              {draftList.length > 0 && (
                <span className="text-[10px] font-bold bg-primary/10 text-primary rounded-full px-1.5 py-0.5">
                  {draftList.length}
                </span>
              )}
            </div>

            {draftList.length === 0 ? (
              <div className="text-center py-3">
                <FileEdit className="w-6 h-6 mx-auto text-muted-foreground/40 mb-1.5" />
                <p className="text-[11px] text-muted-foreground">
                  작성 중인 공고가 없습니다
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {draftList.slice(0, 5).map((d) => {
                  const completedCount = d.completedSteps?.length || 0
                  const progress = (completedCount / 5) * 100
                  return (
                    <div
                      key={d.notice.id}
                      className={cn(
                        'group relative p-3 rounded-lg border border-border bg-white',
                        'hover:border-primary/40 hover:bg-slate-50 transition-colors',
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => onResumeDraft(d)}
                        className="w-full text-left"
                      >
                        <p className="text-xs font-semibold text-foreground line-clamp-2 leading-snug pr-4 mb-2 group-hover:text-primary transition-colors">
                          {d.notice.title || '제목 없음'}
                        </p>
                        <div className="flex items-center justify-between mt-1.5 text-[10px] text-muted-foreground">
                          <span className="font-medium text-primary">
                            STEP {d.currentStep} · {STEP_LABELS[d.currentStep]}
                          </span>
                          <span>{timeAgo(d.updatedAt)}</span>
                        </div>
                        <div className="mt-2 w-full bg-muted rounded-full h-1.5">
                          <div
                            className="bg-primary h-1.5 rounded-full transition-all"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      </button>
                      {onRemoveDraft && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onRemoveDraft(d.notice.id) }}
                          className="absolute top-1.5 right-1.5 w-5 h-5 rounded hover:bg-destructive hover:text-white opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center text-muted-foreground"
                          aria-label="삭제"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  )
                })}
                {draftList.length > 5 && (
                  <p className="text-[10px] text-center text-muted-foreground pt-1">
                    +{draftList.length - 5}개 더보기
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </aside>
  )
}