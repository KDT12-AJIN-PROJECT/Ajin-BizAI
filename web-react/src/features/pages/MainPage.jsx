import {
  CalendarDays, ChevronLeft, ChevronRight,
  Clock, Filter, Loader2, MapPin, RotateCcw, Search, TrendingUp
} from 'lucide-react'
import { Alert, AlertDescription } from '../../components/ui/alert'
import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { Input } from '../../components/ui/input'
import { Label } from '../../components/ui/label'
import { Separator } from '../../components/ui/separator'
import { formatDate, getDdayText } from '../notices/utils/date'

function ddayVariant(date) {
  if (!date) return 'secondary'
  const days = Math.ceil((date - Date.now()) / 86400000)
  if (days < 0)   return 'secondary'
  if (days <= 7)  return 'destructive'
  if (days <= 14) return 'warning'
  return 'success'
}

function NoticeCard({ notice, onOpen }) {
  return (
    <Card
      className="cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition-all duration-150 border-l-4 border-l-primary"
      onClick={() => onOpen(notice)}
    >
      <CardHeader className="pb-2 pt-4 px-4">
        <div className="flex items-center justify-between mb-1">
          <Badge variant="blue" className="text-[11px]">{notice.origin}</Badge>
          <Badge variant={ddayVariant(notice.date)} className="text-[11px]">
            {getDdayText(notice.date)}
          </Badge>
        </div>
        <p className="text-sm font-semibold text-foreground line-clamp-2 leading-snug mt-1">
          {notice.title}
        </p>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <div className="space-y-1 mb-3">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="w-3 h-3 shrink-0" /> {notice.region}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CalendarDays className="w-3 h-3 shrink-0" /> {formatDate(notice.date)}
          </div>
        </div>
        <Separator className="mb-3" />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <TrendingUp className="w-3 h-3 text-primary" />
            <span className="font-semibold text-primary">{(notice.ajin_similarity * 100).toFixed(1)}%</span>
            <span>적합</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function NoticeRow({ notice, onOpen }) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 hover:bg-muted/50 transition-colors border-b border-border last:border-0">
      <Badge variant="blue" className="shrink-0 text-[11px]">{notice.origin}</Badge>
      <button
        type="button"
        className="flex-1 text-left text-sm font-medium text-foreground hover:text-primary transition-colors truncate bg-transparent border-none cursor-pointer p-0"
        onClick={() => onOpen(notice)}
      >
        {notice.title}
      </button>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0">
        <Clock className="w-3 h-3" />
        {formatDate(notice.date)}
      </div>
      <Badge variant={ddayVariant(notice.date)} className="shrink-0 text-[11px]">
        {getDdayText(notice.date)}
      </Badge>
      <span className="text-xs font-semibold text-primary shrink-0 w-16 text-right">
        {(notice.ajin_similarity * 100).toFixed(1)}%
      </span>
    </div>
  )
}

function ScheduleView({ notices, onOpen }) {
  const grouped = notices.reduce((acc, notice) => {
    const key = formatDate(notice.date)
    if (!acc[key]) acc[key] = []
    acc[key].push(notice)
    return acc
  }, {})

  const keys = Object.keys(grouped).sort()

  if (!keys.length) return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <CalendarDays className="w-10 h-10 mb-3 opacity-40" />
      <p className="text-sm">표시할 일정이 없습니다.</p>
    </div>
  )

  return (
    <div className="space-y-3">
      {keys.map((dateKey) => (
        <Card key={dateKey}>
          <CardHeader className="py-3 px-4">
            <div className="flex items-center gap-2">
              <CalendarDays className="w-4 h-4 text-muted-foreground" />
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{dateKey}</span>
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0 space-y-2">
            {grouped[dateKey].map((notice) => (
              <button
                key={notice.id}
                type="button"
                className="w-full text-left flex items-center gap-3 p-2.5 rounded-md hover:bg-muted transition-colors bg-transparent border-none cursor-pointer"
                onClick={() => onOpen(notice)}
              >
                <Badge variant="blue" className="text-[11px] shrink-0">{notice.origin}</Badge>
                <span className="text-sm text-foreground truncate">{notice.title}</span>
              </button>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default function MainPage({
  loading, errors, allCount, filteredCount,
  filters, options, pageState,
  onFilterChange, onReset, onMovePage, onOpenDetail,
  tab, onTabChange,
}) {
  const { matchMode, selectedKeywords, selectedRegions, selectedSizes, searchTitle, sortBy, threshold } = filters

  return (
    <div className="space-y-4">
      {/* 수치 요약 */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: '전체 수집', value: allCount.toLocaleString() + '건', color: 'text-primary' },
          { label: '필터 결과', value: filteredCount.toLocaleString() + '건', color: 'text-green-600' },
          { label: '현재 페이지', value: `${pageState.page} / ${pageState.totalPages}`, color: 'text-sky-600' },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <CardContent className="px-5 py-4">
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">{label}</p>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 필터 패널 */}
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-4 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="match-mode-select">매칭 방식</Label>
              <select
                id="match-mode-select"
                value={matchMode}
                onChange={(e) => onFilterChange({ matchMode: e.target.value, page: 1 })}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option>키워드</option>
                <option>적합도(유사도)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="sort-by-select">정렬</Label>
              <select
                id="sort-by-select"
                value={sortBy}
                onChange={(e) => onFilterChange({ sortBy: e.target.value })}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option>적합도순</option>
                <option>최신순</option>
                <option>마감일 가까운 순</option>
                <option>마감일 늦은 순</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="search-title-input">제목 검색</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                <Input
                  id="search-title-input"
                  className="pl-8"
                  value={searchTitle}
                  placeholder="검색어 입력..."
                  onChange={(e) => onFilterChange({ searchTitle: e.target.value, page: 1 })}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="threshold-range">
                적합도 임계값 <span className="text-primary font-bold normal-case">{(threshold * 100).toFixed(0)}%</span>
              </Label>
              <div className="flex items-center gap-2 h-9">
                <input
                  id="threshold-range"
                  type="range"
                  min="0.01" max="0.1" step="0.005"
                  value={threshold}
                  onChange={(e) => onFilterChange({ threshold: Number(e.target.value), page: 1 })}
                  className="w-full accent-primary"
                />
              </div>
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '키워드', key: 'selectedKeywords', options: options.keywordOptions, value: selectedKeywords },
              { label: '지역',   key: 'selectedRegions',  options: options.regions,        value: selectedRegions },
              { label: '기업 규모', key: 'selectedSizes', options: options.sizes,          value: selectedSizes },
            ].map(({ label, key, options: opts, value }) => (
              <div key={key} className="space-y-1.5">
                <Label>{label}</Label>
                <select
                  multiple
                  aria-label={`${label} 필터`}
                  value={value}
                  onChange={(e) => onFilterChange({ [key]: [...e.target.selectedOptions].map((o) => o.value), page: 1 })}
                  className="flex w-full rounded-md border border-input bg-background px-2 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[88px]"
                >
                  {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              <Filter className="w-3 h-3 inline mr-1" />
              {filteredCount}건 표시 중
            </span>
            <Button variant="outline" size="sm" onClick={onReset}>
              <RotateCcw className="w-3.5 h-3.5" />
              필터 초기화
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 에러 */}
      {errors.length > 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            {errors.map((e) => <p key={e}>{e}</p>)}
          </AlertDescription>
        </Alert>
      )}

      {/* 탭 */}
      <div className="flex items-center justify-between">
        <div className="inline-flex rounded-lg border border-border bg-muted p-1 gap-0.5">
          {[
            { id: 'card',     label: '카드' },
            { id: 'list',     label: '리스트' },
            { id: 'schedule', label: '일정' },
          ].map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => onTabChange(id)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors border-none cursor-pointer ${
                tab === id
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground bg-transparent'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        {loading && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            불러오는 중...
          </div>
        )}
      </div>

      {/* 카드 뷰 */}
      {tab === 'card' && (
        <>
          <div className="grid grid-cols-3 gap-3">
            {pageState.items.map((n) => <NoticeCard key={n.id} notice={n} onOpen={onOpenDetail} />)}
          </div>
          {!loading && pageState.items.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Search className="w-10 h-10 mb-3 opacity-40" />
              <p className="text-sm font-medium">조건에 맞는 공고가 없습니다.</p>
              <p className="text-xs mt-1">필터를 초기화하거나 임계값을 낮춰보세요.</p>
            </div>
          )}
        </>
      )}

      {/* 리스트 뷰 */}
      {tab === 'list' && (
        <Card>
          <CardContent className="p-0">
            {pageState.items.map((n) => <NoticeRow key={n.id} notice={n} onOpen={onOpenDetail} />)}
            {!loading && pageState.items.length === 0 && (
              <p className="text-center text-sm text-muted-foreground py-12">표시할 데이터가 없습니다.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* 일정 뷰 */}
      {tab === 'schedule' && <ScheduleView notices={pageState.items} onOpen={onOpenDetail} />}

      {/* 페이지네이션 */}
      <div className="flex items-center justify-center gap-3 py-2">
        <Button
          variant="outline" size="sm"
          onClick={() => onMovePage(pageState.page - 1)}
          disabled={pageState.page <= 1}
        >
          <ChevronLeft className="w-4 h-4" /> 이전
        </Button>
        <span className="text-sm text-muted-foreground w-24 text-center">
          {pageState.page} / {pageState.totalPages}
        </span>
        <Button
          variant="outline" size="sm"
          onClick={() => onMovePage(pageState.page + 1)}
          disabled={pageState.page >= pageState.totalPages}
        >
          다음 <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
