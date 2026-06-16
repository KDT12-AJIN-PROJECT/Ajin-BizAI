import { useCallback, useEffect, useState } from 'react'
import { draftsApi } from '../../../api/backendApi'

/**
 * 초안 관리 hook — 백엔드 DB 연동 버전
 * 백엔드 실패 시 localStorage fallback 유지
 */

const STORAGE_KEY = 'ajin_drafts'

function localLoad() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

function localSave(drafts) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts))
  } catch {/* ignore */}
}

/** DB 행 → 프론트 형식 변환 */
function dbToLocal(row) {
  return {
    notice: row.notice_snapshot ?? {},
    currentStep: row.current_step ?? 1,
    completedSteps: row.completed_steps ?? [],
    uploads: row.uploads ?? {},
    drafts: row.drafts ?? {},
    updatedAt: row.updated_at ? new Date(row.updated_at).getTime() : Date.now(),
    createdAt: row.created_at ? new Date(row.created_at).getTime() : Date.now(),
  }
}

export function useDrafts() {
  const [drafts, setDrafts] = useState(localLoad)
  const [loading, setLoading] = useState(false)

  // 초기 로드: 백엔드 → 로컬 merge
  useEffect(() => {
    setLoading(true)
    draftsApi.getAll()
      .then((rows) => {
        const fromDb = {}
        rows.forEach((row) => { fromDb[row.notice_id] = dbToLocal(row) })
        setDrafts((prev) => {
          const merged = { ...prev, ...fromDb }
          localSave(merged)
          return merged
        })
      })
      .catch(() => {/* 백엔드 없어도 localStorage로 동작 */})
      .finally(() => setLoading(false))
  }, [])

  const getDraft = useCallback((noticeId) => drafts[noticeId] || null, [drafts])

  const saveDraft = useCallback((notice, partialData) => {
    if (!notice?.id) return
    setDrafts((prev) => {
      const existing = prev[notice.id] || {
        notice: {
          id: notice.id,
          title: notice.title,
          origin: notice.origin,
          region: notice.region,
          period: notice.period,
          date: notice.date,
          url: notice.url,
          rceptEngnHmpgUrl: notice.rceptEngnHmpgUrl,
          target: notice.target,
          benefit: notice.benefit,
          documents: notice.documents,
          ajin_similarity: notice.ajin_similarity,
        },
        currentStep: 1,
        uploads: {},
        drafts: {},
        completedSteps: [],
        createdAt: Date.now(),
      }
      const next = {
        ...prev,
        [notice.id]: { ...existing, ...partialData, updatedAt: Date.now() },
      }
      localSave(next)

      // 백엔드 비동기 저장 (실패해도 무시)
      const entry = next[notice.id]
      draftsApi.upsert(notice.id, {
        notice_snapshot: entry.notice ?? {},
        current_step: entry.currentStep ?? 1,
        completed_steps: entry.completedSteps ?? [],
        uploads: entry.uploads ?? {},
        drafts: entry.drafts ?? {},
        ...(entry.status && { status: entry.status }),
      }).catch(() => {})

      return next
    })
  }, [])

  const removeDraft = useCallback((noticeId) => {
    setDrafts((prev) => {
      const next = { ...prev }
      delete next[noticeId]
      localSave(next)
      draftsApi.remove(noticeId).catch(() => {})
      return next
    })
  }, [])

  const draftList = Object.values(drafts).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))

  return { drafts, draftList, getDraft, saveDraft, removeDraft, loading }
}
