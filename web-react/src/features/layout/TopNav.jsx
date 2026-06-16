import { Bell, BellDot, Bookmark, FileEdit, FilePlus, FileSearch, FileText, FolderArchive, FolderOpen, LayoutDashboard, Settings, SlidersHorizontal } from 'lucide-react'
import { Button } from '../../components/ui/button'
import { cn } from '../../lib/utils'

export default function TopNav({ view, onMove, notificationCount, bookmarkCount }) {
  const navItems = [
    { id: 'dashboard',    label: '대시보드',    icon: LayoutDashboard },
    { id: 'search',       label: '공고 검색',   icon: FileSearch },
    { id: 'detail',       label: '공고 상세',   icon: FileText,           disabled: true },
    { id: 'draft',        label: '신규 작성',   icon: FilePlus },
    { id: 'resumeDraft',  label: '초안 이어 작성', icon: FileEdit },
    { id: 'myDrafts',     label: '내 사업계획서', icon: FolderOpen },
    { id: 'library',      label: '자료실',      icon: FolderArchive },
    { id: 'bookmark',     label: '북마크',      icon: Bookmark,           count: bookmarkCount },
    { id: 'notification', label: '맞춤 알림',   icon: Bell,               count: notificationCount },
    { id: 'notiSettings', label: '알림 설정',   icon: SlidersHorizontal },
    { id: 'settings',     label: '기업 설정',   icon: Settings },
  ]

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 nav-blur border-b border-border">
      <div className="max-w-[1600px] mx-auto h-full px-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-primary" />
          <span className="text-sm font-bold text-primary tracking-tight">AJIN BizAI</span>
        </div>

        <nav className="flex items-center gap-0.5">
          {navItems.map(({ id, label, icon: Icon, count, disabled }) => (
            <Button
              key={id}
              variant={view === id ? 'default' : 'ghost'}
              size="sm"
              onClick={() => !disabled && onMove(id)}
              disabled={disabled}
              className={cn(
                'relative gap-1.5',
                disabled && 'opacity-40 cursor-not-allowed',
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
              {count > 0 && (
                <span className={cn(
                  'absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full text-[10px] font-bold flex items-center justify-center px-1',
                  view === id ? 'bg-white text-primary' : 'bg-destructive text-white',
                )}>
                  {count}
                </span>
              )}
            </Button>
          ))}
        </nav>
      </div>
    </header>
  )
}