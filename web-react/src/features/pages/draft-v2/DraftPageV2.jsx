// AJIN BizAI v0.2 — DraftPage V2 wrapper
// 출처: PRD §20 Phase 1 (DraftPageV2 parallel rollout) / §21.2 #18
// 라우트: /draft-v2 (VITE_ENABLE_ANALYSIS_DEV_MODE 게이트, PRD §17.2 #5)
//
// Step 2 → Step 3 흐름:
//   사용자 footer "Step 2 분석 결과 확정 →" 클릭 → AnalysisConfirmModal → 확인 → toast → currentStep=3
//
// Phase 4-G-1: Step 1 → Step 2 진입 시 ApplicationSession 생성 (B안: DB 영속)
//   - sessionStorage 키 'ajin_v2_session_id'에 저장 → 새로고침 시 복원
//   - selectedNotice 있으면 notice_id + snapshot 함께 전송

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analysisApi } from '../../../api/backendApi'
import { resolveSessionStep, ACTIVE_STATUSES } from '../../../lib/sessionStatus'
import StepProgressV2 from './shared/StepProgressV2'
import AnalysisConfirmModal from './shared/AnalysisConfirmModal'
import Step2ProgressModal from './shared/Step2ProgressModal'
import DraftsPreservationModal from './shared/DraftsPreservationModal'
import StepNavigationBar from './components/StepNavigationBar'
import Step1Common from '../../draft-upload/Step1Common'
import Step2Analysis, { adaptFormFromApi } from './Step2Analysis'
import Step2DevMode from './Step2DevMode'
import Step3Draft from './Step3Draft'
import Step4Evaluation from './Step4Evaluation'
import Step5Export from './Step5Export'

const SESSION_STORAGE_KEY = 'ajin_v2_session_id'
const CURRENT_STEP_STORAGE_KEY = 'ajin_v2_current_step'

function readSavedStep() {
  const raw = sessionStorage.getItem(CURRENT_STEP_STORAGE_KEY)
  const n = Number(raw)
  return Number.isInteger(n) && n >= 1 && n <= 5 ? n : null
}

export default function DraftPageV2({ selectedNotice, onRestoreNotice }) {
  const navigate = useNavigate()
  const initialNoticeRef = useRef(selectedNotice)
  // 세션 복원 전 임시 notice — snapshot에서 직접 채워 Step1 빈 화면 방지
  const [localNotice, setLocalNotice] = useState(selectedNotice)
  const [currentStep, setCurrentStep] = useState(() => readSavedStep() || 1)
  const [step2DevMode, setStep2DevMode] = useState(false)
  const [uploads, setUploads] = useState({
    noticeFiles: [],
    formFiles: [],
    references: [],
  })
  const [selectedCompanyFileIds, setSelectedCompanyFileIds] = useState([])

  // Phase 4-G-1: ApplicationSession (DB 영속)
  const [sessionId, setSessionId] = useState(() => sessionStorage.getItem(SESSION_STORAGE_KEY) || null)
  const [sessionStatus, setSessionStatus] = useState(null)  // P0: backend status 추적
  const [creatingSession, setCreatingSession] = useState(false)

  // Phase 4-G P0: restore 완료 여부 (prefetch + 방어 useEffect 게이트)
  const [restoreChecked, setRestoreChecked] = useState(false)

  // selectedNotice prop이 바뀌면 localNotice도 동기화
  useEffect(() => {
    if (selectedNotice) setLocalNotice(selectedNotice)
  }, [selectedNotice])

  // Phase 4-G P0: prefetch로 발견한 active session (handleStep1Next에서 reuse)
  const [reusableSession, setReusableSession] = useState(null)

  // Phase 4-G-6: Step 2 분석 결과 (Step 3에서 draft_writer 호출 시 사용)
  const [step2Data, setStep2Data] = useState(null)

  // form_prd/2.md: DB form_schema_json.schema 복원값 (sessionStorage 캐시가 없을 때 fallback)
  const [restoredFormSchema, setRestoredFormSchema] = useState(null)

  // 동일 패턴: DB notice_schema_json.schema 복원값
  const [restoredNoticeSchema, setRestoredNoticeSchema] = useState(null)

  // Phase 4-G-7b: Step 3 drafts lift up (R1=빈 객체) + selectedQid lift up
  const [step3Drafts, setStep3Drafts] = useState({})
  const [step3SelectedQid, setStep3SelectedQid] = useState(null)
  // Phase 4-G-7b: Step 4 사전 점검 체크 상태 (R6=휘발, DraftPageV2 mount 시 초기화)
  const [checklistState, setChecklistState] = useState({})  // {itemId: boolean}
  // Phase 4-G-7b post-fix 1: supplementalMaterials lift up (Step 2 ↔ 3 ↔ 4 이동 시 유지)
  const [supplementalMaterials, setSupplementalMaterials] = useState([])
  const handleSupplementalChange = (item) => {
    setSupplementalMaterials(prev => {
      const idx = prev.findIndex(s => s.supplemental_id === item.supplemental_id)
      if (idx === -1) return [...prev, item]
      const next = [...prev]
      next[idx] = { ...next[idx], ...item }
      return next
    })
  }

  // Step 2 → 3 confirm modal + toast
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  // Phase 4-G P0: mount 시 sessionStorage 키 있으면 GET /sessions/{id}로 복원
  // - status / current_step 복원
  // - notice_schema_json.snapshot → onRestoreNotice() 로 App.jsx selectedNotice 갱신
  // - Step 3+ 복원 시 step2Data 손실 → toast + Step 2 강제 복귀 (재분석 자동 시작)
  useEffect(() => {
    const savedId = sessionStorage.getItem(SESSION_STORAGE_KEY)
    if (!savedId) {
      setRestoreChecked(true)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const session = await analysisApi.getSession(savedId)
        if (cancelled) return
        if (session.error) {
          console.warn('[SESSION_RESTORE_FAILED]', session)
          sessionStorage.removeItem(SESSION_STORAGE_KEY)
          sessionStorage.removeItem(CURRENT_STEP_STORAGE_KEY)
          sessionStorage.removeItem('ajin_v2_step2_active_tab')
          // step2 분석 결과 캐시도 정리 (session별 키)
          for (const k of Object.keys(sessionStorage)) {
            if (k.startsWith('ajin_v2_step2_cache_')) sessionStorage.removeItem(k)
          }
          return
        }
        // selectedNotice 복원 검사 (notice_schema_json.snapshot)
        const snapshot = session.notice_schema_json?.snapshot
        const noticeIdFromSession = session.notice_schema_json?.notice_id
        // Search 공고는 id 필드, backend 세션은 notice_id 필드 → 둘 다 확인
        const incomingNoticeId =
          initialNoticeRef.current?.notice_id || initialNoticeRef.current?.id
        // 새 공고로 진입했는데 세션이 다른 공고(또는 빈)면 → 세션 초기화 후 새로 시작
        if (
          incomingNoticeId &&
          String(incomingNoticeId) !== String(noticeIdFromSession || '')
        ) {
          sessionStorage.removeItem(SESSION_STORAGE_KEY)
          sessionStorage.removeItem(CURRENT_STEP_STORAGE_KEY)
          sessionStorage.removeItem('ajin_v2_step2_active_tab')
          for (const k of Object.keys(sessionStorage)) {
            if (k.startsWith('ajin_v2_step2_cache_')) sessionStorage.removeItem(k)
          }
          setSessionId(null)
          setRestoreChecked(true)
          return
        }
        setSessionId(session.session_id)
        setSessionStatus(session.status)
        // form_prd/2.md: form_schema_json.schema 복원 (sessionStorage 캐시 비었을 때 fallback)
        const persistedSchema = session.form_schema_json?.schema || null
        if (persistedSchema && persistedSchema.sections?.length) {
          setRestoredFormSchema(persistedSchema)
        }
        // 동일 패턴: notice_schema_json.schema 복원
        const persistedNoticeSchema = session.notice_schema_json?.schema || null
        if (persistedNoticeSchema) {
          setRestoredNoticeSchema(persistedNoticeSchema)
        }
        // 2026-05-18: step2Data 복원 — 새로고침 후 Step 3 진입 시 FORM_MOCK 표시 방지.
        // step2Data는 React state라 새로고침 시 reset → Step3Draft가 FORM_MOCK fallback 표시 버그.
        // backend session 데이터로 step2Data shape 빌드해서 즉시 set.
        try {
          const fsj = session.form_schema_json || {}
          const nsj = session.notice_schema_json || {}
          const csj = session.company_schema_json || {}
          // confirmed_schema 우선 (Step 2 확정 후) — 없으면 schema 그대로
          const formApiResp = fsj.confirmed_schema || fsj.schema || null
          if (formApiResp && formApiResp.sections?.length) {
            const mp = fsj.mapping_pipeline?.results || {}
            setStep2Data({
              formApiResp,
              formData: adaptFormFromApi(formApiResp),
              noticeApiResp: nsj.schema || null,
              mappingResult: mp.map_evidence || null,
              evidenceData: mp.extract_evidence || null,
              companyData: mp.analyze_company || (csj ? { company: csj.company, fit_analysis: csj.fit_analysis } : null),
              missingMaterials: mp.check_missing || null,
            })
          }
        } catch (err) {
          console.warn('[STEP2DATA_RESTORE_FAILED]', err)
        }
        // fresh notice가 이미 있으면 (Search→Detail→Draft 경로) snapshot으로 덮어쓰기 X
        // (snapshot이 stale일 수 있어 URL 등 필드 손실 방지)
        if (snapshot && onRestoreNotice && !initialNoticeRef.current) {
          const restoredNotice = { ...snapshot, notice_id: noticeIdFromSession }
          onRestoreNotice(restoredNotice)
          setLocalNotice(restoredNotice)
        } else if (!initialNoticeRef.current && !snapshot) {
          // snapshot 없어도 localNotice는 현재 selectedNotice로 유지
        }
        // Phase 4-H A1: notice/form attachments 복원 (JSON-piggyback)
        // 2026-05-18: references도 별도 호출로 복원 (backend default는 notice/form만, kind=reference 명시 필요)
        try {
          const [defaultRes, refRes] = await Promise.all([
            analysisApi.listFiles({ sessionId: session.session_id }),
            analysisApi.listFiles({ sessionId: session.session_id, kind: 'reference' }).catch(() => null),
          ])
          if (!cancelled && defaultRes?.items) {
            const toMeta = (a) => ({
              file_id: a.file_id,
              name: a.file_name,
              size: a.size_bytes,
              ext: a.ext,
              parsed_text: a.parsed_text,
              char_count: a.char_count,
              parsed_text_stored_char_count: a.parsed_text_stored_char_count,
              parsed_text_truncated: a.parsed_text_truncated,
              parse_success: a.parse_success,
              warning: a.warning,
              persisted: true,
            })
            const referenceItems = refRes?.items?.reference || []
            setUploads(prev => ({
              ...prev,
              noticeFiles: (defaultRes.items.notice || []).map(toMeta),
              formFiles: (defaultRes.items.form || []).map(toMeta),
              references: referenceItems.map(toMeta),
            }))
          }
        } catch (err) {
          console.warn('[FILES_RESTORE_FAILED]', err)
        }
        // sessionStorage의 currentStep을 우선 사용 (frontend 단독 진행 상태).
        // backend current_step은 fallback (Step 1 → 2 진입 시 backend update API 없음).
        const savedStep = readSavedStep()
        let restoredStep = savedStep ?? resolveSessionStep(session)
        // v0.2 dashboard resume 보완: 새 탭에서 savedStep 비어있고 backend current_step=1이지만
        // parse-notice / parse-form schema가 이미 있으면 사용자가 Step 2까지 진행한 증거 → Step 2로 자동 추론
        if (restoredStep < 2 && (persistedNoticeSchema || persistedSchema)) {
          restoredStep = 2
        }

        // v3.2 C-5c Q6: 새로고침 복원 6-case 매트릭스
        //   case 1 (session 없음): 이미 위에서 처리 (savedId 없을 때 return)
        //   case 2 (status != step2_confirmed): savedStep 그대로 — Step 1/2 진입
        //   case 3-6: status == step2_confirmed → mapping-status로 세부 분기
        if (session.status === 'step2_confirmed' && restoredStep >= 3) {
          // mapping-status + draft_items 호출 (Q6 정책)
          try {
            const [mappingRes, draftsRes] = await Promise.all([
              analysisApi.getMappingStatus(session.session_id).catch(() => null),
              analysisApi.getDraftItems(session.session_id).catch(() => null),
            ])
            if (cancelled) return
            const mappingReady = mappingRes?.mapping_ready
            const pipeline = mappingRes?.mapping_pipeline || {}
            const draftItems = draftsRes?.draft_items || []

            if (mappingReady && draftItems.length > 0) {
              // case 5: 정상 Step 3 복원
              // draft_items (list) → step3Drafts (qid map) 변환
              const draftMap = {}
              for (const di of draftItems) {
                const qid = di.question_id
                if (!qid) continue
                draftMap[qid] = {
                  content: di.draft_text || '',
                  maxLength: di.constraints?.max_length || 1000,
                  status: di.status === 'empty' ? 'draft' : (di.status || 'draft'),
                  evidenceIds: di.matched_evidence_ids || [],
                  tableData: di.table_draft || null,
                  draftItemId: di.draft_item_id,
                }
              }
              setStep3Drafts(draftMap)
              // C-5c: mapping_pipeline.results.check_missing → step2Data.missingMaterials
              const checkMissingRestore = pipeline?.results?.check_missing || []
              setStep2Data(prev => ({ ...(prev || {}), missingMaterials: checkMissingRestore }))
              setToast(`✓ 세션 복원 — Step 3 (drafts ${draftItems.length}건)`)
              setCurrentStep(3)
            } else if (pipeline.status === 'running') {
              // case 3: mapping 진행 중
              setToast('세션 복원됨 — Step 2 mapping 진행 중 (모달 다시 띄우려면 확정 재시도)')
              setCurrentStep(2)
            } else if (pipeline.status === 'failed') {
              // case 4: failed
              setToast(`세션 복원됨 — Step 2 mapping 실패 (${pipeline.failed_step}). 재시도 필요`)
              setCurrentStep(2)
            } else if (draftItems.length === 0) {
              // case 6: draft_items 없음 → initialize 필요
              setToast('세션 복원됨 — Step 2 mapping 미완료. 분석 결과 확정부터 다시 시도하세요')
              setCurrentStep(2)
            } else {
              // 그 외 (mapping_ready=false인데 draft_items는 있는 케이스)
              setToast(`세션 복원됨 — Step 2부터 확인 (reasons: ${(mappingRes?.not_ready_reasons || []).join(', ')})`)
              setCurrentStep(2)
            }
          } catch (err) {
            console.warn('[STEP3_RESTORE_FAILED]', err)
            setToast(`세션 복원됨 (status=${session.status}) — Step 2부터 다시 분석합니다`)
            setCurrentStep(2)
          }
        } else if (restoredStep >= 3) {
          // step2_confirmed 아닌데 Step 3+? — 비정상. Step 2 강등
          setToast(`세션 복원됨 (status=${session.status}) — Step 2부터 다시 분석합니다`)
          setCurrentStep(2)
        } else {
          setCurrentStep(restoredStep)
        }
      } catch (err) {
        console.warn('[SESSION_RESTORE_FAILED]', err)
        sessionStorage.removeItem(SESSION_STORAGE_KEY)
        sessionStorage.removeItem(CURRENT_STEP_STORAGE_KEY)
        sessionStorage.removeItem('ajin_v2_step2_active_tab')
      } finally {
        if (!cancelled) setRestoreChecked(true)
      }
    })()
    return () => { cancelled = true }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Phase 4-G P0: Step 2+ 진입 방어막 — sessionId 없으면 Step 1 강제 복귀 (restore 완료 후만 판정)
  useEffect(() => {
    if (!restoreChecked) return
    if (currentStep >= 2 && !sessionId) {
      setToast('세션이 없습니다 — Step 1부터 다시 시작')
      setCurrentStep(1)
    }
  }, [restoreChecked, currentStep, sessionId])

  // currentStep 변경 시 sessionStorage에 영속화 (새로고침 시 현재 step 복원용)
  useEffect(() => {
    if (!restoreChecked) return
    if (sessionId && currentStep >= 1 && currentStep <= 5) {
      sessionStorage.setItem(CURRENT_STEP_STORAGE_KEY, String(currentStep))
    }
  }, [restoreChecked, currentStep, sessionId])

  // Phase 4-G P0: Step 1 prefetch — 같은 notice_id에 active session 있으면 reuse 후보로 보관
  // (restore 완료 후만 실행 — restore가 session 설정한 경우 sessionId 분기로 skip)
  useEffect(() => {
    if (!restoreChecked) return
    if (sessionId) return  // 이미 세션 있으면 skip
    if (!selectedNotice?.notice_id) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await analysisApi.listSessions({
          userId: 'anonymous',
          noticeId: selectedNotice.notice_id,
          limit: 20,
        })
        if (cancelled) return
        // backend가 status 단일만 받으므로 frontend에서 active 필터링
        const reusable = (res.items || []).find(s => ACTIVE_STATUSES.includes(s.status))
        if (reusable) setReusableSession(reusable)
      } catch (err) {
        console.warn('[PREFETCH_FAILED]', err)
      }
    })()
    return () => { cancelled = true }
  }, [restoreChecked, selectedNotice?.notice_id, sessionId])

  // A2 (PRD §13.9): Step 3 → Step 2 backward + hasDrafts 시 preservation 모달
  const [preservationOpen, setPreservationOpen] = useState(false)
  const [preservationBusy, setPreservationBusy] = useState(false)
  const [preservationSkip, setPreservationSkip] = useState(false)     // "다시 묻지 않음" 세션 플래그
  const [pendingStepTarget, setPendingStepTarget] = useState(null)

  // draft 작성 여부 — content 있거나 의미 있는 status (사용자 검토 결과)
  const hasWrittenDrafts = (drafts) =>
    Object.values(drafts || {}).some((it) => {
      if (!it) return false
      if (['generated', 'user_edited', 'needs_revision', 'approved', 'completed'].includes(it.status)) return true
      const content = it.content || it.answer || it.draft_text || ''
      return String(content).trim().length > 0
    })

  // C-5a (v3.2): Step1 → Step2 이동 시 selected_company_file_ids backend PATCH 저장
  //   sessionId 있을 때만 시도. 실패해도 이동은 막지 않음 (network error tolerant).
  const next = async () => {
    if (currentStep === 1 && sessionId) {
      try {
        await analysisApi.patchSession({
          sessionId,
          selectedCompanyFileIds: selectedCompanyFileIds || [],
        })
      } catch (err) {
        console.warn('[STEP1_NEXT_PATCH_FAILED]', err)
        // toast은 부족자료 누락 같은 critical 알림 외에는 silent — 사용자 흐름 방해 X
      }
    }
    setCurrentStep((s) => Math.min(s + 1, 5))
  }

  // Step 3 → Step 2 backward 시 모달 가드 (hasDrafts && !skip)
  const requestStepChange = (target) => {
    if (currentStep === 3 && target === 2 && !preservationSkip && hasWrittenDrafts(step3Drafts)) {
      setPendingStepTarget(target)
      setPreservationOpen(true)
      return
    }
    setCurrentStep(target)
  }
  const prev = () => requestStepChange(Math.max(currentStep - 1, 1))
  const goTo = (step) => requestStepChange(step)

  const handlePreservationProceed = async () => {
    // 한 번 확인 후 같은 세션에서는 자동 skip (체크박스 없음 — A2-lite)
    setPreservationSkip(true)
    if (!sessionId) {
      setPreservationOpen(false)
      if (pendingStepTarget) setCurrentStep(pendingStepTarget)
      return
    }
    setPreservationBusy(true)
    try {
      await analysisApi.setDraftsPolicy({ sessionId, draftsPolicy: 'preserve' })
    } catch (err) {
      console.warn('[SET_DRAFTS_POLICY_FAILED]', err)
    } finally {
      setPreservationBusy(false)
      setPreservationOpen(false)
      if (pendingStepTarget) setCurrentStep(pendingStepTarget)
      setPendingStepTarget(null)
    }
  }
  const handlePreservationCancel = () => {
    setPreservationOpen(false)
    setPendingStepTarget(null)
  }

  // Step 1 → Step 2 진입 시:
  //   (a) sessionId 이미 있음 → 그대로 next
  //   (b) reusableSession 발견 → 재사용 (Notice:Session 1:N 정책)
  //   (c) 없으면 새 세션 생성
  const handleStep1Next = async () => {
    if (sessionId) {
      next()
      return
    }
    // (b) reuse 분기
    if (reusableSession) {
      setSessionId(reusableSession.session_id)
      setSessionStatus(reusableSession.status)
      sessionStorage.setItem(SESSION_STORAGE_KEY, reusableSession.session_id)
      const restoredStep = resolveSessionStep(reusableSession)
      setToast(`기존 세션 이어가기 — ${reusableSession.session_id.slice(0, 8)}... (status=${reusableSession.status})`)
      // Step 3+ reuse 시에도 step2Data 없음 → Step 2부터 재분석 자동
      setCurrentStep(restoredStep >= 3 ? 2 : Math.max(restoredStep, 2))
      return
    }
    // (c) 새 세션 생성
    setCreatingSession(true)
    try {
      const noticeSnapshot = selectedNotice
        ? {
            title: selectedNotice.title,
            org: selectedNotice.org,
            target: selectedNotice.target,
            benefit: selectedNotice.benefit,
            url: selectedNotice.url || '',
            rceptEngnHmpgUrl: selectedNotice.rceptEngnHmpgUrl || '',
            rcept_engn_hmpg_url: selectedNotice.rcept_engn_hmpg_url || '',
            pblancUrl: selectedNotice.pblancUrl || '',
            printFlpthNm: selectedNotice.printFlpthNm || '',
            flpthNm: selectedNotice.flpthNm || '',
            origin: selectedNotice.origin || '',
            period: selectedNotice.period || '',
            region: selectedNotice.region || '',
            notice_id: selectedNotice.notice_id || selectedNotice.id || '',
            id: selectedNotice.id || selectedNotice.notice_id || '',
          }
        : null
      const res = await analysisApi.createSession({
        noticeId: selectedNotice?.notice_id || selectedNotice?.id || null,
        noticeSnapshot,
      })
      const newSessionId = res.session_id
      setSessionId(newSessionId)
      setSessionStatus(res.status)
      sessionStorage.setItem(SESSION_STORAGE_KEY, newSessionId)
      setToast(`새 세션 생성 — ${newSessionId.slice(0, 8)}...`)

      // A1 race 해결: sessionId 없을 때 선택한 client-side 파일 (__local=true)을
      // session 생성 직후 backend에 자동 업로드 후 state 갱신
      const uploadLocal = async (kind, files) => {
        const localFiles = (files || []).filter(f => f?.__local && f.file)
        if (localFiles.length === 0) return files
        const uploaded = []
        for (const f of localFiles) {
          try {
            const r = await analysisApi.uploadFile({ sessionId: newSessionId, kind, file: f.file })
            uploaded.push({
              file_id: r.file_id, name: r.file_name, size: r.size_bytes, ext: r.ext,
              char_count: r.char_count,
              parsed_text_stored_char_count: r.parsed_text_stored_char_count,
              parsed_text_truncated: r.parsed_text_truncated,
              parse_success: r.parse_success, warning: r.warning, persisted: true,
            })
          } catch (err) {
            console.warn('[A1_RACE_UPLOAD_FAILED]', kind, f?.name, err)
            uploaded.push({ ...f, upload_error: err.message })
          }
        }
        // 비-local 파일과 새로 uploaded 파일 합침
        return [...(files || []).filter(f => !f?.__local), ...uploaded]
      }
      const newNoticeFiles = await uploadLocal('notice', uploads.noticeFiles)
      const newFormFiles = await uploadLocal('form', uploads.formFiles)
      const newReferences = await uploadLocal('reference', uploads.references)
      setUploads({
        ...uploads,
        noticeFiles: newNoticeFiles,
        formFiles: newFormFiles,
        references: newReferences,
      })

      next()
    } catch (err) {
      setToast(`세션 생성 실패: ${err.message}`)
    } finally {
      setCreatingSession(false)
    }
  }

  const toggleCompanyFile = (fileId) => {
    setSelectedCompanyFileIds((prev) =>
      prev.includes(fileId) ? prev.filter((x) => x !== fileId) : [...prev, fileId]
    )
  }

  // Step 2 footer "분석 결과 확정" → 모달 → 확인 시
  const [confirmingStep2, setConfirmingStep2] = useState(false)
  const requestConfirmStep2 = () => setShowConfirmModal(true)

  // C-5b (v3.2 c-5): Step 2 확정 9단계 흐름 + mapping polling
  const [progressOpen, setProgressOpen] = useState(false)
  const [progressStage, setProgressStage] = useState(null)
  const [progressError, setProgressError] = useState(null)
  const [progressPipeline, setProgressPipeline] = useState(null)
  // UI-C6: mapping-status 응답의 not_ready_reasons (failed 모달 안내용)
  const [progressNotReadyReasons, setProgressNotReadyReasons] = useState(null)
  // C-5b Q4: announcement_signals + evaluation_rubric 10개 항목 표시
  const [progressSummary, setProgressSummary] = useState(null)

  // mapping-status polling (2초 간격 / 5분 timeout — Q5 보강 정책)
  const pollMappingStatus = async () => {
    const intervalMs = 2000
    const timeoutMs = 300000  // 5분
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      const res = await analysisApi.getMappingStatus(sessionId)
      const pipeline = res?.mapping_pipeline || null
      setProgressPipeline(pipeline)
      setProgressNotReadyReasons(res?.not_ready_reasons || [])
      const st = pipeline?.status
      if (st === 'success') return res
      if (st === 'failed') {
        throw new Error(
          pipeline?.error_message
          || `mapping failed at ${pipeline?.failed_step || 'unknown'}`
        )
      }
      await new Promise((r) => setTimeout(r, intervalMs))
    }
    throw new Error('mapping timeout (5분 초과)')
  }

  const finalizeStep2 = async () => {
    if (!sessionId) {
      // session 없으면 (오프라인 모드) 그냥 진행
      setShowConfirmModal(false)
      setToast('Step 2 분석 결과 확정 — Step 3로 이동합니다 (오프라인)')
      setCurrentStep(3)
      return
    }
    setConfirmingStep2(true)
    setShowConfirmModal(false)
    setProgressOpen(true)
    setProgressStage(null)
    setProgressError(null)
    setProgressPipeline(null)
    setProgressNotReadyReasons(null)

    try {
      // 1. confirm-step2
      setProgressStage('confirm')
      await analysisApi.confirmStep2({ sessionId })

      // 2. announcement-signals normalize (실패 시 silent — 선택적)
      // Q4: criteria/bonuses/preferences/eligibility/compliance/emphasis_keywords count + status
      let announcement = null
      setProgressStage('announcement')
      try { announcement = await analysisApi.normalizeAnnouncementSignals(sessionId) }
      catch (e) { console.warn('[NORMALIZE_ANNOUNCEMENT_FAIL]', e) }

      // 3. evaluation-rubric resolve (실패 시 silent — 선택적)
      // Q4: source / template_type / axis_count / scored_axes_count / total_weight
      let rubric = null
      setProgressStage('rubric')
      try { rubric = await analysisApi.resolveEvaluationRubric(sessionId) }
      catch (e) { console.warn('[RESOLVE_RUBRIC_FAIL]', e) }

      setProgressSummary({
        announcement: announcement || null,
        rubric: rubric || null,
      })

      // 4. step3-ready
      setProgressStage('step3-ready')
      const readyRes = await analysisApi.getStep3Ready(sessionId)
      if (!readyRes?.step3_ready) {
        throw new Error(`step3 not ready: ${readyRes?.reason || 'unknown'}`)
      }

      // 5. draft-items/initialize
      setProgressStage('initialize')
      await analysisApi.initializeDraftItems({ sessionId })

      // 6. run-step2-mapping
      setProgressStage('mapping-start')
      await analysisApi.runStep2Mapping({ sessionId })

      // 7. mapping-status polling (2초, 5분 timeout)
      setProgressStage('polling')
      const mappingStatusRes = await pollMappingStatus()

      // 8. GET /draft-items — C-5c: 결과를 step3Drafts에 hydrate
      setProgressStage('fetch-drafts')
      const draftsRes = await analysisApi.getDraftItems(sessionId)
      const draftItems = draftsRes?.draft_items || []
      const draftMap = {}
      for (const di of draftItems) {
        const qid = di.question_id
        if (!qid) continue
        draftMap[qid] = {
          content: di.draft_text || '',
          maxLength: di.constraints?.max_length || 1000,
          status: di.status === 'empty' ? 'draft' : (di.status || 'draft'),
          evidenceIds: di.matched_evidence_ids || [],
          tableData: di.table_draft || null,
          draftItemId: di.draft_item_id,
        }
      }
      setStep3Drafts(draftMap)

      // C-5c: mapping_pipeline.results.check_missing → step2Data.missingMaterials
      const checkMissing = mappingStatusRes?.mapping_pipeline?.results?.check_missing || []
      setStep2Data(prev => ({ ...(prev || {}), missingMaterials: checkMissing }))

      // 9. Step3 이동
      setProgressStage('done')
      setToast(`✓ Step 2 확정 + 매핑 완료 — Step 3로 이동 (drafts ${draftItems.length}건)`)
      // progress modal 닫기 + 이동 (약간 지연으로 사용자 인지)
      setTimeout(() => {
        setProgressOpen(false)
        setProgressStage(null)
        setCurrentStep(3)
      }, 500)
    } catch (err) {
      setProgressError(err?.message || String(err))
      setProgressStage('failed')
      setToast(`Step 2 확정 실패: ${err?.message || err}`)
    } finally {
      setConfirmingStep2(false)
    }
  }

  // mapping failed 시 retry-step2-mapping → polling 재개
  const retryStep2Mapping = async () => {
    if (!sessionId) return
    setProgressStage('mapping-start')
    setProgressError(null)
    try {
      await analysisApi.retryStep2Mapping({ sessionId })
      setProgressStage('polling')
      await pollMappingStatus()

      setProgressStage('fetch-drafts')
      await analysisApi.getDraftItems(sessionId)

      setProgressStage('done')
      setToast('✓ 매핑 재실행 완료 — Step 3로 이동')
      setTimeout(() => {
        setProgressOpen(false)
        setProgressStage(null)
        setCurrentStep(3)
      }, 500)
    } catch (err) {
      setProgressError(err?.message || String(err))
      setProgressStage('failed')
    }
  }

  const closeProgressModal = () => {
    if (progressStage && progressStage !== 'failed' && progressStage !== 'done') {
      // 진행 중에는 닫기 차단
      return
    }
    setProgressOpen(false)
    setProgressStage(null)
    setProgressError(null)
  }

  return (
    <div className="min-h-[calc(100vh-3.5rem)] bg-slate-50">
      {/* dev 환경 배너 (PRD §17.2 #4) */}
      <div className="bg-yellow-100 border-b-2 border-yellow-400 px-6 py-2">
        <span className="text-sm font-semibold text-yellow-900">
          🚧 DraftPage V2 (개발 중) — /draft-v2 dev 라우트 ·
          PRD v0.2 FINAL §20 Phase 1 / §21.2 #18
        </span>
      </div>

      <StepProgressV2 currentStep={currentStep} onStepClick={goTo} />

      <div className="max-w-[1400px] mx-auto">
        {currentStep === 1 && (
          <div className="px-6 py-6">
            {/* B.1.1: Resume session UI 배너 (PRD-13 §18.2 — Notice:Session 1:N reuse default) */}
            {reusableSession && !sessionId && (
              <div className="mb-3 bg-amber-50 border border-amber-200 rounded-md px-4 py-3 flex items-center gap-3">
                <span className="text-amber-700 text-lg">↺</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-amber-900">
                    이 공고에 작성 중인 세션이 있습니다
                  </div>
                  <div className="text-[11px] text-amber-800 font-mono mt-0.5">
                    session: {reusableSession.session_id.slice(0, 12)}... · status={reusableSession.status} · step{reusableSession.current_step}
                  </div>
                </div>
                <button
                  onClick={handleStep1Next}
                  disabled={creatingSession}
                  className="text-xs px-3 py-1.5 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:opacity-50 whitespace-nowrap"
                >
                  이어 작성하기 →
                </button>
                <button
                  onClick={() => setReusableSession(null)}
                  className="text-xs px-3 py-1.5 border border-amber-300 text-amber-900 rounded hover:bg-amber-100 whitespace-nowrap"
                >
                  새 세션 시작
                </button>
              </div>
            )}

            <Step1Common
              variant="v2"
              notice={localNotice || selectedNotice}
              onNoticeReset={() => onRestoreNotice?.(null)}
              uploads={uploads}
              onUploadsChange={setUploads}
              selectedCompanyFileIds={selectedCompanyFileIds}
              onCompanyFileToggle={toggleCompanyFile}
              sessionId={sessionId}
            />
            <StepNavigationBar
              onPrev={() => navigate('/detail')}
              prevLabel="← 이전 (공고 상세보기)"
              onNext={handleStep1Next}
              nextLabel={
                creatingSession ? '세션 생성 중...' :
                reusableSession ? '다음 → (이어 작성)' :
                '다음 → (Step 2 분석)'
              }
              nextDisabled={creatingSession}
            />
            {sessionId && (
              <div className="mt-3 text-[11px] text-slate-500 font-mono">
                session_id: {sessionId.slice(0, 12)}... (sessionStorage 저장됨)
              </div>
            )}
          </div>
        )}
        {currentStep === 2 && !step2DevMode && (
          <Step2Analysis
            onPrev={prev}
            onConfirmStep2={requestConfirmStep2}
            onToggleDevMode={() => setStep2DevMode(true)}
            sessionId={sessionId}
            notice={selectedNotice}
            uploads={uploads}
            onAnalysisReady={setStep2Data}
            supplementalMaterials={supplementalMaterials}
            onSupplementalChangeLifted={handleSupplementalChange}
            restoredFormSchema={restoredFormSchema}
            restoredNoticeSchema={restoredNoticeSchema}
            restoreChecked={restoreChecked}
          />
        )}
        {currentStep === 2 && step2DevMode && (
          <Step2DevMode
            onPrev={prev}
            onConfirmStep2={requestConfirmStep2}
            onToggleDevMode={() => setStep2DevMode(false)}
            sessionId={sessionId}
            step2Data={step2Data}
            uploads={uploads}
            notice={selectedNotice}
          />
        )}
        {currentStep === 3 && (
          <Step3Draft
            onPrev={prev}
            onNext={next}
            sessionId={sessionId}
            step2Data={step2Data}
            notice={selectedNotice}
            drafts={step3Drafts}
            onDraftsChange={setStep3Drafts}
            selectedQid={step3SelectedQid}
            onSelectQid={setStep3SelectedQid}
            supplementalMaterials={supplementalMaterials}
            onSupplementalChange={handleSupplementalChange}
          />
        )}
        {currentStep === 4 && (
          <Step4Evaluation
            onPrev={prev}
            onNext={next}
            step2Data={step2Data}
            drafts={step3Drafts}
            notice={selectedNotice}
            checklistState={checklistState}
            onChecklistChange={setChecklistState}
            supplementalMaterials={supplementalMaterials}
            onJumpToStep3={(qid) => {
              setStep3SelectedQid(qid)
              setCurrentStep(3)
            }}
          />
        )}
        {currentStep === 5 && (
          <Step5Export
            onPrev={prev}
            sessionId={sessionId}
            step2Data={step2Data}
            drafts={step3Drafts}
            notice={selectedNotice}
          />
        )}
      </div>

      {/* Step 2 분석 결과 확정 모달 (PRD §8) */}
      <AnalysisConfirmModal
        open={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        onProceed={finalizeStep2}
        onForce={finalizeStep2}
        busy={confirmingStep2}
      />

      {/* C-5b (v3.2): Step 2 확정 9단계 진행 모달 */}
      <Step2ProgressModal
        open={progressOpen}
        stage={progressStage}
        pipelineState={progressPipeline}
        errorMessage={progressError}
        summary={progressSummary}
        notReadyReasons={progressNotReadyReasons}
        onRetry={retryStep2Mapping}
        onClose={closeProgressModal}
        onBackToStep1={() => {
          setProgressOpen(false)
          setProgressStage(null)
          setCurrentStep(1)
        }}
      />

      {/* A2 (PRD §13.9): Step 3 → Step 2 backward + hasDrafts 시 preservation 모달 */}
      <DraftsPreservationModal
        open={preservationOpen}
        draftCount={Object.values(step3Drafts || {}).filter(Boolean).length}
        onCancel={handlePreservationCancel}
        onProceed={handlePreservationProceed}
        busy={preservationBusy}
      />

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-slate-900 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg flex items-center gap-2">
          <span>✓</span>
          <span>{toast}</span>
        </div>
      )}
    </div>
  )
}
