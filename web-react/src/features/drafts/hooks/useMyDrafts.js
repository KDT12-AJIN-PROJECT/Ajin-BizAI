/**
 * useMyDrafts — MyDraftsPage / ArchivePage 공통 데이터 훅
 * DraftListPage와 MyDraftsPage 모두 이 훅을 통해 데이터를 가져옵니다.
 * 별도 캐시/상태관리 로직 없이 단일 fetch 경로 사용.
 */
import { useCallback, useEffect, useState } from 'react'
import { draftsApi } from '../../../api/backendApi'

export function useMyDrafts({ archived = false, status = null } = {}) {
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (archived !== null && archived !== undefined) params.archived = archived
      if (status) params.status = status
      const data = await draftsApi.list(params)
      setDrafts(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [archived, status])

  useEffect(() => { fetch() }, [fetch])

  const updateStatus = useCallback(async (draftId, newStatus, memo) => {
    await draftsApi.updateStatus(draftId, newStatus, memo)
    await fetch()
  }, [fetch])

  const updateResult = useCallback(async (draftId, result, resultDate, memo) => {
    await draftsApi.updateResult(draftId, result, resultDate, memo)
    await fetch()
  }, [fetch])

  const archiveDraft = useCallback(async (draftId) => {
    await draftsApi.archive(draftId)
    await fetch()
  }, [fetch])

  const restoreDraft = useCallback(async (draftId) => {
    await draftsApi.restore(draftId)
    await fetch()
  }, [fetch])

  const permanentDelete = useCallback(async (draftId) => {
    await draftsApi.permanentDelete(draftId)
    await fetch()
  }, [fetch])

  const permanentDeleteBulk = useCallback(async (ids) => {
    await draftsApi.permanentDeleteBulk(ids)
    await fetch()
  }, [fetch])

  const createVersion = useCallback(async (noticeId, versionNote, replaceVersion) => {
    const body = {}
    if (versionNote) body.version_note = versionNote
    if (replaceVersion !== undefined) body.replace_version = replaceVersion
    const result = await draftsApi.createVersion(noticeId, body)
    await fetch()
    return result
  }, [fetch])

  return {
    drafts,
    loading,
    error,
    refetch: fetch,
    updateStatus,
    updateResult,
    archiveDraft,
    restoreDraft,
    permanentDelete,
    permanentDeleteBulk,
    createVersion,
  }
}
