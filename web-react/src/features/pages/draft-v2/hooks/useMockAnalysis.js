// AJIN BizAI v0.2 — Mock Analysis Hook
// 백엔드 API (PRD §16.1 /api/analysis/*) 미구현 동안 mock data 제공
// Phase 4 시점에 실제 API 호출로 교체 예정

import { useState, useCallback } from 'react'

/**
 * useMockAnalysis — Step 2 분석 mock 데이터 hook
 *
 * 향후 교체 (Phase 4):
 * - parseNotice → POST /api/analysis/parse-notice
 * - parseForm → POST /api/analysis/parse-form
 * - extractEvidence → POST /api/analysis/extract-evidence
 * - analyzeCompany → POST /api/analysis/analyze-company
 * - mapEvidence → POST /api/analysis/map-evidence
 * - checkMissing → POST /api/analysis/check-missing
 * - mapEvalCriteria → POST /api/analysis/map-eval-criteria
 */
export function useMockAnalysis() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const parseNotice = useCallback(async (noticeText) => {
    // TODO: PRD §13.2 NoticeSchema mock 데이터 반환
    setLoading(true)
    await new Promise((r) => setTimeout(r, 500))
    setLoading(false)
    return { _placeholder: 'NoticeSchema mock — Phase 4 교체 예정' }
  }, [])

  const parseForm = useCallback(async (formText) => {
    // TODO: PRD §13.2 FormSchema mock 데이터 반환
    setLoading(true)
    await new Promise((r) => setTimeout(r, 500))
    setLoading(false)
    return { _placeholder: 'FormSchema mock — Phase 4 교체 예정' }
  }, [])

  return {
    loading,
    error,
    parseNotice,
    parseForm,
    // TODO: extractEvidence, analyzeCompany, mapEvidence, checkMissing, mapEvalCriteria
  }
}
