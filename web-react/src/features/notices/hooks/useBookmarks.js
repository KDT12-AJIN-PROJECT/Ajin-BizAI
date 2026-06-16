import { useCallback, useEffect, useState } from 'react'
import { bookmarksApi } from '../../../api/backendApi'

const STORAGE_KEY = 'ajin_bookmarks'

function localLoad() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function localSave(bookmarks) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks))
  } catch {/* ignore */}
}

/** DB 행 → 프론트 형식 변환 */
function dbToLocal(row) {
  const snap = row.notice_snapshot ?? {}
  return {
    id: row.notice_id,
    title: snap.title ?? '',
    origin: snap.origin ?? '',
    region: snap.region ?? '',
    period: snap.period ?? '',
    date: snap.date ?? null,
    url: snap.url ?? '',
    ajin_similarity: snap.ajin_similarity ?? 0,
    bookmarkedAt: row.created_at ? new Date(row.created_at).getTime() : Date.now(),
  }
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState(localLoad)

  // 초기 로드: 백엔드 → 로컬 merge
  useEffect(() => {
    bookmarksApi.getAll()
      .then((rows) => {
        const dbIds = new Set(rows.map((r) => r.notice_id))
        setBookmarks((prev) => {
          const localOnly = prev.filter((b) => !dbIds.has(b.id))
          const fromDb = rows.map(dbToLocal)
          const merged = [...fromDb, ...localOnly]
          localSave(merged)
          return merged
        })
      })
      .catch(() => {/* 백엔드 없으면 localStorage로 동작 */})
  }, [])

  const isBookmarked = useCallback(
    (noticeId) => bookmarks.some((b) => b.id === noticeId),
    [bookmarks],
  )

  const toggleBookmark = useCallback((notice) => {
    setBookmarks((prev) => {
      const exists = prev.some((b) => b.id === notice.id)
      let next
      if (exists) {
        next = prev.filter((b) => b.id !== notice.id)
        bookmarksApi.remove(notice.id).catch(() => {})
      } else {
        const snapshot = {
          title: notice.title,
          origin: notice.origin,
          region: notice.region,
          period: notice.period,
          date: notice.date,
          url: notice.url,
          ajin_similarity: notice.ajin_similarity,
          printFileNm: notice.printFileNm || '',
          printFlpthNm: notice.printFlpthNm || '',
          fileNm: notice.fileNm || '',
          flpthNm: notice.flpthNm || '',
        }
        next = [
          ...prev,
          { id: notice.id, ...snapshot, bookmarkedAt: Date.now() },
        ]
        bookmarksApi.add(notice.id, snapshot).catch(() => {})
      }
      localSave(next)
      return next
    })
  }, [])

  const clearBookmarks = useCallback(() => {
    setBookmarks([])
    localSave([])
    bookmarksApi.clearAll().catch(() => {})
  }, [])

  return { bookmarks, isBookmarked, toggleBookmark, clearBookmarks }
}
