import { CalendarDays, FileText, PenLine } from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'

export default function DraftListPage({ draftList = [], onResumeDraft }) {
  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      <div className="mb-4">
        <h2 className="text-xl font-bold text-foreground">작성 중인 사업계획서</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          총 {draftList.length}편
        </p>
      </div>

      {draftList.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-muted-foreground">
          <FileText className="w-16 h-16 mb-4 opacity-20" />
          <p className="text-base font-medium text-foreground">작성 중인 사업계획서가 없습니다</p>
          <p className="text-sm mt-1">공고 검색에서 신청 준비를 시작해 보세요</p>
        </div>
      ) : (
        <div className="space-y-3">
          {draftList.map((d) => {
            const completedCount = d.completedSteps?.length || 0
            const progress = (completedCount / 5) * 100
            const updatedDate = d.updatedAt
              ? new Date(d.updatedAt).toLocaleString('ko-KR', {
                  month: '2-digit', day: '2-digit',
                  hour: '2-digit', minute: '2-digit',
                })
              : '-'

            return (
              <Card
                key={d.notice.id}
                className="hover:shadow-md transition-all border-l-4 border-l-primary"
              >
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="blue" className="text-[11px]">{d.notice.origin}</Badge>
                      <Badge variant="warning" className="text-[11px]">
                        STEP {d.currentStep}/5
                      </Badge>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5 shrink-0"
                      onClick={() => onResumeDraft(d)}
                    >
                      <PenLine className="w-3.5 h-3.5" />
                      이어 작성
                    </Button>
                  </div>

                  <p className="text-base font-semibold text-foreground leading-snug mb-2">
                    {d.notice.title}
                  </p>

                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-3">
                    <CalendarDays className="w-3.5 h-3.5" />
                    마지막 저장: {updatedDate}
                  </div>

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
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
