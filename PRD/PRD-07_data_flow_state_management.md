# PRD-07: 데이터 흐름 및 상태 관리

> **문서 버전** 1.0 | **선행 문서** PRD-06 | **후행 문서** PRD-08  
> **목적** 전역 상태, localStorage, 데이터 흐름의 완전한 명세

---

## 1. 전역 상태 설계 (AppContext)

```jsx
// src/contexts/AppContext.jsx — 완전한 구현 코드

import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { STORAGE_KEYS, STORAGE_TTL } from '../constants/storageKeys'
import { computeAllSimilarities } from '../features/notices/utils/match'

const DEFAULT_COMPANY_PROFILE = {
  name: '',
  industry: '자동차 부품',
  size: 'Mid',
  employees: '',
  sales: '',
  field: '자동차 부품 제조',
  summary: '',
  strategy: '',
  regions: [],
  keywords: ['자동차', '부품', '스마트공장', 'DX', '제조'],
  simThreshold: 0.02,
}

const DEFAULT_FILTERS = {
  matchMode: 'AI적합도',
  sortBy: '적합도순',
  searchTitle: '',
  threshold: 0.02,
  selectedKeywords: [],
  selectedRegions: [],
  selectedSizes: [],
}

const DEFAULT_APPLY_SESSION = {
  noticeId: null,
  currentStep: 1,
  uploadedFiles: {},
  parsedTexts: {},
  analysisResult: null,
  diagnosisResult: null,
  interviewAnswers: {},
  readinessScore: 0,
}

const DEFAULT_DRAFT_SESSION = {
  mode: 'chat',
  sections: [],
  fullText: '',
  simulationResult: null,
}

export const AppContext = createContext(null)

export function AppProvider({ children }) {
  // ── 공고 데이터 ───────────────────────────────────────────────
  const [notices, setNotices] = useState([])
  const [filteredNotices, setFilteredNotices] = useState([])
  const [selectedNotice, setSelectedNotice] = useState(null)
  const [noticeErrors, setNoticeErrors] = useState([])
  const [isLoadingNotices, setIsLoadingNotices] = useState(false)

  // ── 필터 ─────────────────────────────────────────────────────
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  // ── 기업 프로필 ───────────────────────────────────────────────
  const [companyProfile, setCompanyProfile] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.COMPANY_PROFILE)
      return stored ? { ...DEFAULT_COMPANY_PROFILE, ...JSON.parse(stored) } : DEFAULT_COMPANY_PROFILE
    } catch { return DEFAULT_COMPANY_PROFILE }
  })

  // ── 신청 준비 세션 ────────────────────────────────────────────
  const [applySession, setApplySession] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.APPLY_SESSION)
      return stored ? JSON.parse(stored) : DEFAULT_APPLY_SESSION
    } catch { return DEFAULT_APPLY_SESSION }
  })

  // ── 초안 세션 ────────────────────────────────────────────────
  const [draftSession, setDraftSession] = useState(DEFAULT_DRAFT_SESSION)

  // ── 히스토리 ─────────────────────────────────────────────────
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.HISTORY) || '[]')
    } catch { return [] }
  })

  // ── 북마크 ───────────────────────────────────────────────────
  const [bookmarks, setBookmarks] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.BOOKMARKS) || '[]')
    } catch { return [] }
  })

  // ── 알림 ─────────────────────────────────────────────────────
  const [notifications, setNotifications] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEYS.NOTIFICATIONS) || '[]')
    } catch { return [] }
  })

  // ── 액션: 기업 프로필 저장 ─────────────────────────────────────
  const saveCompanyProfile = useCallback((profile) => {
    setCompanyProfile(profile)
    localStorage.setItem(STORAGE_KEYS.COMPANY_PROFILE, JSON.stringify(profile))
    // 프로필 변경 시 적합도 재계산
    setNotices(prev => computeAllSimilarities(prev, profile, profile.keywords?.join(' ')))
  }, [])

  // ── 액션: 필터 업데이트 ────────────────────────────────────────
  const updateFilter = useCallback((key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }, [])

  // ── 액션: 북마크 토글 ──────────────────────────────────────────
  const toggleBookmark = useCallback((noticeId) => {
    setBookmarks(prev => {
      const next = prev.includes(noticeId)
        ? prev.filter(id => id !== noticeId)
        : [...prev, noticeId]
      localStorage.setItem(STORAGE_KEYS.BOOKMARKS, JSON.stringify(next))
      return next
    })
  }, [])

  // ── 액션: 신청 준비 세션 업데이트 ──────────────────────────────
  const updateApplySession = useCallback((partial) => {
    setApplySession(prev => {
      const next = { ...prev, ...partial }
      localStorage.setItem(STORAGE_KEYS.APPLY_SESSION, JSON.stringify(next))
      return next
    })
  }, [])

  // ── 액션: 신청 준비 세션 시작 (새 공고 선택 시 초기화) ──────────
  const startApplySession = useCallback((noticeId) => {
    const fresh = { ...DEFAULT_APPLY_SESSION, noticeId }
    setApplySession(fresh)
    localStorage.setItem(STORAGE_KEYS.APPLY_SESSION, JSON.stringify(fresh))
  }, [])

  // ── 액션: 초안 섹션 저장 ─────────────────────────────────────
  const saveDraftSection = useCallback((sectionIdx, content, status) => {
    setDraftSession(prev => {
      const next = { ...prev }
      next.sections = prev.sections.map((s, i) =>
        i === sectionIdx ? { ...s, content, status } : s
      )
      next.fullText = next.sections
        .filter(s => s.content)
        .map(s => `# ${s.key}. ${s.title}\n\n${s.content}`)
        .join('\n\n---\n\n')
      return next
    })
  }, [])

  // ── 액션: 이력 추가 ────────────────────────────────────────────
  const addHistoryRecord = useCallback((record) => {
    setHistory(prev => {
      const next = [record, ...prev]
      localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(next))
      return next
    })
  }, [])

  // ── 액션: 이력 상태 업데이트 ──────────────────────────────────
  const updateHistoryRecord = useCallback((id, partial) => {
    setHistory(prev => {
      const next = prev.map(r => r.id === id ? { ...r, ...partial } : r)
      localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(next))
      return next
    })
  }, [])

  // ── 알림 읽음 처리 ────────────────────────────────────────────
  const markNotificationRead = useCallback((id) => {
    setNotifications(prev => {
      const next = prev.map(n => n.id === id ? { ...n, isRead: true } : n)
      localStorage.setItem(STORAGE_KEYS.NOTIFICATIONS, JSON.stringify(next))
      return next
    })
  }, [])

  const markAllNotificationsRead = useCallback(() => {
    setNotifications(prev => {
      const next = prev.map(n => ({ ...n, isRead: true }))
      localStorage.setItem(STORAGE_KEYS.NOTIFICATIONS, JSON.stringify(next))
      return next
    })
  }, [])

  const value = {
    // 상태
    notices, filteredNotices, selectedNotice, noticeErrors, isLoadingNotices,
    filters, companyProfile, applySession, draftSession,
    history, bookmarks, notifications,
    // 액션
    setNotices, setFilteredNotices, setSelectedNotice,
    setNoticeErrors, setIsLoadingNotices,
    saveCompanyProfile, updateFilter, toggleBookmark,
    updateApplySession, startApplySession,
    setDraftSession, saveDraftSection,
    addHistoryRecord, updateHistoryRecord,
    markNotificationRead, markAllNotificationsRead,
  }

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
```

---

## 2. useNotices 훅 (공고 로딩 + 필터 적용)

```javascript
// src/hooks/useNotices.js — 기존 파일 완전 대체

import { useEffect, useCallback } from 'react'
import { useApp } from '../contexts/AppContext'
import { fetchAllNotices } from '../api/noticesApi'
import { computeAllSimilarities } from '../features/notices/utils/match'
import { filterNotices, sortNotices, extractFilterOptions } from '../features/notices/utils/filtering'

export function useNotices() {
  const {
    notices, setNotices, setFilteredNotices,
    setNoticeErrors, setIsLoadingNotices,
    filters, companyProfile,
  } = useApp()

  // 공고 로딩
  const loadNotices = useCallback(async () => {
    setIsLoadingNotices(true)
    try {
      const { notices: raw, errors } = await fetchAllNotices()
      const withScores = computeAllSimilarities(
        raw, companyProfile, companyProfile.keywords?.join(' ')
      )
      setNotices(withScores)
      setNoticeErrors(errors)
    } catch (err) {
      setNoticeErrors([`공고 로딩 실패: ${err.message}`])
    } finally {
      setIsLoadingNotices(false)
    }
  }, [companyProfile])

  // 최초 로딩
  useEffect(() => {
    if (notices.length === 0) loadNotices()
  }, [])

  // 필터 적용 (notices 또는 filters 변경 시)
  useEffect(() => {
    const filtered = filterNotices(notices, filters)
    const sorted = sortNotices(filtered, filters.sortBy)
    setFilteredNotices(sorted)
  }, [notices, filters])

  const filterOptions = extractFilterOptions(notices)

  return { loadNotices, filterOptions }
}
```

---

## 3. useAutoSave 훅

```javascript
// src/hooks/useAutoSave.js

import { useEffect, useRef } from 'react'
import { STORAGE_KEYS, STORAGE_TTL } from '../constants/storageKeys'

/**
 * debounce 3초 자동저장
 * @param {string} noticeId - 대상 공고 ID
 * @param {object} draftSession - 저장할 초안 세션
 */
export function useAutoSave(noticeId, draftSession) {
  const timerRef = useRef(null)

  useEffect(() => {
    if (!noticeId || !draftSession.fullText) return
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      const key = `${STORAGE_KEYS.DRAFT_PREFIX}${noticeId}`
      const payload = {
        ...draftSession,
        savedAt: Date.now(),
        expiresAt: Date.now() + STORAGE_TTL.DRAFT,
      }
      try {
        localStorage.setItem(key, JSON.stringify(payload))
      } catch {
        // 저장 실패 무시 (용량 초과 등)
      }
    }, 3000) // 3초 debounce

    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [noticeId, draftSession.fullText])
}

// 저장된 초안 불러오기
export function loadSavedDraft(noticeId) {
  const key = `${STORAGE_KEYS.DRAFT_PREFIX}${noticeId}`
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (data.expiresAt && Date.now() > data.expiresAt) {
      localStorage.removeItem(key)
      return null
    }
    return data
  } catch { return null }
}
```

---

## 4. fileProcessApi.js (백엔드 파일 파싱 API 호출)

```javascript
// src/api/fileProcessApi.js

import { env } from '../config/env'

const BACKEND_URL = env.apiBaseUrl

/**
 * 단일 파일 텍스트 추출
 * @param {File} file
 * @returns {Promise<{filename, text, parse_success, error}>}
 */
export async function parseFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${BACKEND_URL}/api/parse-file`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP_${res.status}`)
  }

  return res.json()
}

/**
 * 여러 파일 파싱 (병렬)
 * @param {Record<string, File>} files - { notice: File, form: File, ... }
 * @returns {Promise<Record<string, {text, parse_success}>>}
 */
export async function parseAllFiles(files) {
  const entries = Object.entries(files).filter(([, file]) => file)
  const results = await Promise.allSettled(
    entries.map(async ([key, file]) => {
      const result = await parseFile(file)
      return [key, result]
    })
  )

  const parsed = {}
  results.forEach((r) => {
    if (r.status === 'fulfilled') {
      const [key, data] = r.value
      parsed[key] = data
    }
  })
  return parsed
}

/**
 * AI 진단 API 호출
 */
export async function runDiagnosis(noticeText, parsedTexts, interviewAnswers) {
  const res = await fetch(`${BACKEND_URL}/api/diagnosis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notice_text: noticeText, uploaded_docs: parsedTexts, interview_answers: interviewAnswers }),
  })
  if (!res.ok) throw new Error(`진단 API HTTP_${res.status}`)
  return res.json()
}
```

---

## 5. 데이터 흐름 요약

### 공고 수집 흐름
```
앱 시작
  → useNotices.loadNotices()
  → fetchAllNotices() [4개 API 병렬]
  → normalizeNotice() × N건
  → dedupeNotices()
  → computeAllSimilarities(notices, companyProfile)
  → setNotices(withScores)
  → filterNotices() + sortNotices()
  → setFilteredNotices()
  → MainPage 렌더링
```

### 초안 생성 흐름
```
선택된 공고 (selectedNotice)
  → ApplyPrepPage STEP 1: 파일 업로드
  → parseAllFiles() → parsedTexts
  → STEP 2: runDiagnosis() → analysisResult
  → STEP 3: diagnosisResult.missing_required 표시
  → STEP 4: interviewAnswers 수집
  → STEP 5: readinessScore 확인
  → ChatDraftPage 진입
  → analyzeNoticeStructure() → sections[]
  → generateDraftSection() × N회
  → useAutoSave() 자동저장
  → SimulationPage: runScoreSimulation()
  → 다운로드
```

---

## 6. localStorage 크기 제한 처리

```javascript
// src/services/storage.js

export function safeSetItem(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch (e) {
    if (e.name === 'QuotaExceededError') {
      // 오래된 초안 삭제
      const draftKeys = Object.keys(localStorage).filter(k => k.startsWith('ajin_draft_'))
      if (draftKeys.length > 0) {
        // 가장 오래된 초안 삭제 (savedAt 기준)
        const oldest = draftKeys
          .map(k => ({ key: k, savedAt: JSON.parse(localStorage.getItem(k) || '{}').savedAt || 0 }))
          .sort((a, b) => a.savedAt - b.savedAt)[0]
        localStorage.removeItem(oldest.key)
        // 재시도
        try { localStorage.setItem(key, JSON.stringify(value)); return true }
        catch { return false }
      }
    }
    return false
  }
}
```
