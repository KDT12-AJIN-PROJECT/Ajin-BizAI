// AJIN BizAI v0.2 — Step 4: 제출 전 검토 (Phase 4-G-7b)
// 출처: PRD §11.1 (v0.2 평가 엔진 X) + PRD-13 §18.10 (5 영역 / 정책 6개)
//
// 금지 (정책 #3): V1 Step4Review import / /api/ai/evaluate / /api/ai/improve / V1 5섹션 enum
// 기준: FormSchema + DraftItem + question_id

import { useState } from 'react'
import StepNavigationBar from './components/StepNavigationBar'
import Step4ProceedModal from './shared/Step4ProceedModal'
import {
  computeWriteSummary,
  computeMaterialsSummary,
  computeCriterionProgress,
  buildChecklist,
  deriveWriteStatus,
  deriveEvidence,
  deriveMissing,
  countNeedsRevision,
} from '../../../lib/reviewAdapter'

export default function Step4Evaluation({
  onPrev,
  onNext,
  step2Data,
  drafts = {},
  notice,
  checklistState = {},
  onChecklistChange,
  onJumpToStep3,
  supplementalMaterials: supplementalMaterialsProp = [],  // post-fix 1: DraftPageV2 직접 prop
}) {
  const [showProceedModal, setShowProceedModal] = useState(false)

  // step2Data 분해 (null safe)
  const formData = step2Data?.formData
  const noticeApiResp = step2Data?.noticeApiResp
  const mappingResult = step2Data?.mappingResult
  const missingMaterials = step2Data?.missingMaterials
  // post-fix 1: supplementalMaterials는 step2Data 대신 prop 우선 (DraftPageV2 owner)
  const supplementalMaterials = supplementalMaterialsProp.length > 0
    ? supplementalMaterialsProp
    : (step2Data?.supplementalMaterials || [])
  const evalCriteriaMapping = step2Data?.evalCriteriaMapping

  // ① 작성 요약 통계
  const summary = computeWriteSummary(formData, drafts, mappingResult, noticeApiResp, notice)
  // ⑤ Materials 요약
  const materials = computeMaterialsSummary(missingMaterials, supplementalMaterials)
  // ③ 체크리스트
  const checklist = buildChecklist(noticeApiResp, noticeApiResp?.snapshot || notice)
  const needsRevisionCount = countNeedsRevision(drafts)

  const toggleCheck = (id) => {
    onChecklistChange?.({ ...checklistState, [id]: !checklistState[id] })
  }

  // 다음 클릭 → 미작성/needs_revision/open missing 있으면 모달, 없으면 즉시 진행
  const handleNext = () => {
    const hasIssues = summary.unwritten > 0 || needsRevisionCount > 0 || materials.missing.open > 0
    if (hasIssues) {
      setShowProceedModal(true)
    } else {
      onNext?.()
    }
  }

  const proceed = () => {
    setShowProceedModal(false)
    onNext?.()
  }

  // formData가 없으면 (Step 2 미진행) 안내
  if (!formData?.sections?.length) {
    return (
      <div className="p-6">
        <h2 className="text-2xl font-bold mb-4">Step 4. 제출 전 검토</h2>
        <div className="bg-amber-50 border border-amber-200 rounded p-4">
          <p className="text-sm text-amber-900">
            ⚠ Step 2 분석 데이터가 없습니다. Step 2부터 다시 진행해주세요.
          </p>
        </div>
        <StepNavigationBar onPrev={onPrev} prevLabel="← 이전 (Step 3)" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* 헤더 + v0.3 배너 */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Step 4. 제출 전 검토</h2>
        <p className="text-sm text-slate-500 mt-1">
          Step 3 작성 결과와 Step 2 분석 결과를 요약합니다. Step 5 export 진입 전 검토.
        </p>
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-900">
        ℹ AI 자동 평가 (심사위원 관점 / 점수화 / 자동 보완) 는 v0.3에서 제공됩니다 (PRD §11.2).
      </div>

      {/* ① 작성 요약 통계 — 6 카드 (status 3 segments 통합) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="전체 문항" value={summary.total} unit="개" />
        <StatusCard
          approved={summary.approved}
          written={summary.written}
          unwritten={summary.unwritten}
        />
        <StatCard label="총 글자수" value={summary.totalChars.toLocaleString()} />
        <StatCard label="사용 evidence" value={summary.evidenceCount} unit="개" />
        <StatCard label="Evidence 연결 문항" value={`${summary.evidenceLinkedCount}/${summary.total}`} />
        <StatCard label="마감일" value={summary.deadline} highlight={summary.deadline !== '-'} />
      </div>

      {/* ② 문항별 검토 리스트 (테이블) */}
      <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 font-semibold text-slate-900">
          문항별 검토 ({summary.total}건)
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <th className="px-3 py-2 text-left font-medium">문항 ID</th>
                <th className="px-3 py-2 text-left font-medium">문항명</th>
                <th className="px-3 py-2 text-left font-medium">작성 상태</th>
                <th className="px-3 py-2 text-left font-medium">Evidence</th>
                <th className="px-3 py-2 text-left font-medium">부족자료</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {formData.sections.flatMap(sec =>
                sec.questions.map(q => {
                  const write = deriveWriteStatus(drafts[q.id])
                  const evi = deriveEvidence(q.id, mappingResult)
                  const miss = deriveMissing(q.id, missingMaterials)
                  return (
                    <tr
                      key={q.id}
                      onClick={() => onJumpToStep3?.(q.id)}
                      className="cursor-pointer hover:bg-indigo-50/30 transition"
                    >
                      <td className="px-3 py-2 font-mono text-xs text-slate-500">{q.id}</td>
                      <td className="px-3 py-2 text-slate-900">{q.title}</td>
                      <td className="px-3 py-2">
                        <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                          write.value === 'written' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                        }`}>{write.label}</span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                          evi.value === 'has' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                        }`}>{evi.label}</span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`text-[11px] px-1.5 py-0.5 rounded ${
                          miss.value === 'open' ? 'bg-red-50 text-red-700' :
                          miss.value === 'deferred' ? 'bg-amber-50 text-amber-700' :
                          miss.value === 'resolved' ? 'bg-emerald-50 text-emerald-700' :
                          'bg-slate-100 text-slate-500'
                        }`}>{miss.label}</span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ③ 사전 점검 체크리스트 */}
      <div className="bg-white border border-slate-200 rounded-md p-4">
        <div className="font-semibold text-slate-900 mb-3">사전 점검 체크리스트</div>
        <div className="space-y-2">
          {checklist.map(item => (
            <label key={item.id} className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={!!checklistState[item.id]}
                onChange={() => toggleCheck(item.id)}
                className="mt-0.5"
              />
              <span className="text-slate-700">{item.label}</span>
            </label>
          ))}
        </div>
        <div className="text-[10px] text-slate-400 mt-2">
          ⓘ 항목 출처: {checklist[0]?._source === 'api' ? 'noticeApiResp.required_documents' :
                       checklist[0]?._source === 'snapshot' ? 'session snapshot' : '기본 fallback'}
        </div>
      </div>

      {/* ④ 평가기준 매핑 요약 */}
      <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 font-semibold text-slate-900">
          평가기준 매핑 요약
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 text-xs">
              <tr>
                <th className="px-3 py-2 text-left font-medium">평가기준</th>
                <th className="px-3 py-2 text-left font-medium">매핑 문항</th>
                <th className="px-3 py-2 text-left font-medium">scope</th>
                <th className="px-3 py-2 text-right font-medium">작성 완료 / 전체</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(evalCriteriaMapping?.mappings || []).map((c, i) => {
                const progress = computeCriterionProgress(c, formData, drafts)
                const mqLabels = (c.mapped_questions || []).map(mq =>
                  typeof mq === 'string' ? mq : (mq?.question_id || mq?.qid || '?')
                ).slice(0, 5).join(', ')
                const isUserEdited = c.mapped_by === 'user'
                return (
                  <tr key={i} className={isUserEdited ? 'bg-blue-50/30' : ''}>
                    <td className="px-3 py-2 text-slate-900">
                      <div className="flex items-center gap-2">
                        <span>{c.criteria_name}</span>
                        {isUserEdited && (
                          <span
                            className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200"
                            title="사용자가 편집한 매핑"
                          >
                            ✎ user
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-500">
                      {mqLabels || (c.scope === 'document' ? '(전체)' : '(미매핑)')}
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                        {progress.scope_label}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      <span className={progress.completed === progress.total && progress.total > 0 ? 'text-emerald-700' : 'text-slate-700'}>
                        {progress.completed} / {progress.total}
                      </span>
                    </td>
                  </tr>
                )
              })}
              {(!evalCriteriaMapping?.mappings?.length) && (
                <tr>
                  <td colSpan="4" className="px-3 py-4 text-center text-xs text-slate-400">
                    평가기준 매핑 결과 없음
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ⑤ 부족자료 / 보완자료 요약 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-white border border-slate-200 rounded-md p-4">
          <div className="font-semibold text-slate-900 mb-2">MissingMaterial</div>
          <div className="grid grid-cols-4 gap-2 text-center">
            <MaterialBox label="open" value={materials.missing.open} color="red" />
            <MaterialBox label="resolved" value={materials.missing.resolved} color="emerald" />
            <MaterialBox label="deferred" value={materials.missing.deferred} color="amber" />
            <MaterialBox label="rejected" value={materials.missing.rejected} color="slate" />
          </div>
          {materials.openItems.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1.5">
                open 항목 ({materials.openItems.length})
              </div>
              <div className="space-y-1">
                {materials.openItems.map(m => (
                  <div key={m.missing_id} className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-slate-500 shrink-0">{m.question_id}</span>
                    <span className="text-slate-700 truncate">{m.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="bg-white border border-slate-200 rounded-md p-4">
          <div className="font-semibold text-slate-900 mb-2">SupplementalMaterial</div>
          <div className="grid grid-cols-4 gap-2 text-center">
            <MaterialBox label="uploaded" value={materials.supplemental.uploaded} color="slate" />
            <MaterialBox label="analyzed" value={materials.supplemental.analyzed} color="blue" />
            <MaterialBox label="converted" value={materials.supplemental.converted} color="emerald" />
            <MaterialBox label="failed" value={materials.supplemental.failed} color="red" />
          </div>
        </div>
      </div>

      {/* 네비게이션 */}
      <StepNavigationBar
        onPrev={onPrev}
        onNext={handleNext}
        prevLabel="← 이전 (Step 3)"
        nextLabel="다음 → (Step 5)"
      />

      {/* 진행 확인 모달 */}
      <Step4ProceedModal
        open={showProceedModal}
        onClose={() => setShowProceedModal(false)}
        onProceed={proceed}
        draftCounts={{ unwritten: summary.unwritten, needsRevision: needsRevisionCount }}
        openMissingCount={materials.missing.open}
      />
    </div>
  )
}

// ─── 작은 helper 컴포넌트 ───
function StatCard({ label, value, unit, highlight = false }) {
  return (
    <div className={`border rounded p-3 ${highlight ? 'border-indigo-200 bg-indigo-50/30' : 'border-slate-200 bg-white'}`}>
      <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">{label}</div>
      <div className="text-xl font-bold text-slate-900">
        {value}{unit && <span className="text-xs text-slate-500 ml-1 font-normal">{unit}</span>}
      </div>
    </div>
  )
}

function StatusCard({ approved, written, unwritten }) {
  return (
    <div className="border border-slate-200 rounded p-3 bg-white">
      <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">상태</div>
      <div className="space-y-0.5 text-xs">
        <div className="flex justify-between"><span className="text-slate-600">승인됨</span><span className="font-mono font-semibold text-emerald-700">{approved}</span></div>
        <div className="flex justify-between"><span className="text-slate-600">작성됨</span><span className="font-mono font-semibold text-slate-700">{written}</span></div>
        <div className="flex justify-between"><span className="text-slate-600">미작성</span><span className={`font-mono font-semibold ${unwritten > 0 ? 'text-red-700' : 'text-slate-400'}`}>{unwritten}</span></div>
      </div>
    </div>
  )
}

function MaterialBox({ label, value, color }) {
  const colorMap = {
    red: 'text-red-700',
    emerald: 'text-emerald-700',
    amber: 'text-amber-700',
    blue: 'text-blue-700',
    slate: 'text-slate-600',
  }
  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${colorMap[color]}`}>{value}</div>
      <div className="text-[10px] text-slate-500">{label}</div>
    </div>
  )
}
