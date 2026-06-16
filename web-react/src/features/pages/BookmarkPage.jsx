import { Bookmark, BookmarkX, CalendarDays, MapPin, TrendingUp, Trash2 } from 'lucide-react'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import { formatDate, getDdayText } from '../notices/utils/date'

export default function BookmarkPage({ bookmarks, notices = [], onOpenDetail, onToggleBookmark, onClearAll }) {
  const ORIGIN_URLS = {
    '기업마당':     'https://www.bizinfo.go.kr',
    '과기부':       'https://www.msit.go.kr',
    '중기부':       'https://www.mss.go.kr',
    '창진원(통합)': 'https://www.k-startup.go.kr',
    '샘플데이터':   'https://www.bizinfo.go.kr',
  }

  const handleOpen = (bookmark) => {
    const full = notices.find((n) => n.id === bookmark.id)
    if (full) {
      onOpenDetail(full)
    } else {
      const siteUrl = bookmark.url || ORIGIN_URLS[bookmark.origin] || 'https://www.bizinfo.go.kr'
      window.open(siteUrl, '_blank')
    }
  }
  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-foreground">북마크</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            저장한 공고 {bookmarks.length}건
          </p>
        </div>
        {bookmarks.length > 0 && (
          <Button variant="outline" size="sm" onClick={onClearAll} className="text-muted-foreground">
            <Trash2 className="w-3.5 h-3.5 mr-1.5" /> 전체 삭제
          </Button>
        )}
      </div>

      {bookmarks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-muted-foreground">
          <BookmarkX className="w-16 h-16 mb-4 opacity-20" />
          <p className="text-base font-medium text-foreground">저장된 북마크가 없습니다</p>
          <p className="text-sm mt-1">공고 검색에서 관심 공고를 저장해 보세요</p>
        </div>
      ) : (
        <div className="space-y-3">
          {bookmarks.map((notice) => (
            <Card
              key={notice.id}
              className="cursor-pointer hover:shadow-md hover:border-amber-500 hover:bg-slate-50 transition-all border-l-4 border-l-amber-500 group"
              onClick={() => handleOpen(notice)}
            >
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="blue" className="text-[11px] font-medium">{notice.origin}</Badge>
                      {notice.ajin_similarity != null && (
                        <Badge variant="secondary" className="text-[11px] gap-1 font-medium bg-amber-100 text-amber-800 hover:bg-amber-100">
                          <TrendingUp className="w-2.5 h-2.5" />
                          {(notice.ajin_similarity * 100).toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                    <p className="text-base font-bold text-foreground leading-snug mb-3 group-hover:text-amber-600 transition-colors">
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
                  <div className="flex flex-col items-end gap-3 shrink-0">
                    <Badge variant="destructive" className="text-xs px-2 py-0.5">{getDdayText(notice.date)}</Badge>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 hover:bg-amber-100 z-10"
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleBookmark(notice);
                        }}
                      >
                        <Bookmark className="w-4 h-4 fill-amber-500 text-amber-500" />
                      </Button>
                    </div>
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
