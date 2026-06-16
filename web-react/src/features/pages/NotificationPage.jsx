import { ArrowLeft, Bell, CalendarDays, MapPin, TrendingUp } from 'lucide-react'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import { formatDate, getDdayText } from '../notices/utils/date'

export default function NotificationPage({ notices, threshold, onBack, onOpenDetail }) {
  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      {/* 상단 헤더 영역 */}
      <div className="flex items-center relative mb-6">
        <Button variant="ghost" size="sm" onClick={onBack} className="absolute left-0">
          <ArrowLeft className="w-4 h-4 mr-1.5" /> 대시보드
        </Button>
        <h2 className="text-xl font-bold text-foreground w-full text-center">
          아진산업 맞춤형 알림
        </h2>
      </div>

      <Alert className="bg-blue-50 border-blue-200 text-blue-900 mb-6">
        <Bell className="w-4 h-4 text-blue-600" />
        <AlertDescription className="font-medium">
          적합도 {(threshold * 100).toFixed(0)}% 이상 공고 <strong className="text-blue-700">{notices.length}건</strong>이 매칭되었습니다.
        </AlertDescription>
      </Alert>

      {notices.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Bell className="w-12 h-12 mx-auto opacity-20 mb-3" />
          <p className="text-sm">조건에 맞는 새로운 공고 알림이 없습니다.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {notices.map((notice) => (
            <Card 
              key={notice.id} 
              // 💡 카드 전체 클릭 가능 & 마우스 오버 효과
              className="cursor-pointer hover:shadow-md hover:border-blue-500 hover:bg-slate-50 transition-all border-l-4 border-l-blue-500 group"
              onClick={() => onOpenDetail(notice)}
            >
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="blue" className="text-[11px] font-medium bg-blue-100 text-blue-800">{notice.origin}</Badge>
                      {notice.ajin_similarity != null && (
                        <Badge variant="secondary" className="text-[11px] gap-1 font-medium">
                          <TrendingUp className="w-2.5 h-2.5" />
                          {(notice.ajin_similarity * 100).toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                    {/* 타이틀 호버 시 색상 변경으로 클릭 유도 */}
                    <p className="text-base font-bold text-foreground leading-snug mb-3 group-hover:text-blue-600 transition-colors">
                      {notice.title}
                    </p>
                    <div className="flex flex-wrap items-center gap-4">
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                        <MapPin className="w-3.5 h-3.5" /> {notice.region}
                      </span>
                      <span className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                        <CalendarDays className="w-3.5 h-3.5" /> {formatDate(notice.date)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end justify-start gap-3 shrink-0">
                    <Badge variant="destructive" className="text-xs px-2 py-0.5">{getDdayText(notice.date)}</Badge>
                    {/* 상세 보기 버튼 제거 완료 */}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}