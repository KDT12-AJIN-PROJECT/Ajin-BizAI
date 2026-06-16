// AJIN BizAI v0.2 — Step 5: 완료 / 다운로드 (Phase 4-G-8)
// 출처: PRD §12 / PRD §16.6 (no LLM, export-docx)
// 🚨 정책: LLM 호출 금지 (test_03 §3.11.4)

import { useState } from 'react'
import StepNavigationBar from './components/StepNavigationBar'
import { analysisApi } from '../../../api/backendApi'
import { logApi, handleFallback } from '../../../lib/runtimeLog'
import {
  computeWriteSummary,
  deriveWriteStatus,
  computeMaterialsSummary,
} from '../../../lib/reviewAdapter'

function sanitizeForFilename(s) {
  return (s || '').replace(/[\\/:*?"<>|]/g, '_').replace(/\s+/g, '_').slice(0, 80)
}

// V1 Step5 status badge 라벨 → V2 ApplicationSession 기준으로 정합
const STATUS_BADGE = {
  approved: { label: '✓ 승인', cls: 'bg-emerald-50 text-emerald-700' },
  written: { label: '작성됨', cls: 'bg-slate-50 text-slate-700' },
  unwritten: { label: '✕ 미작성', cls: 'bg-red-50 text-red-700' },
}

export default function Step5Export({ onPrev, sessionId, step2Data, drafts = {}, notice }) {
  const [sourceMode, setSourceMode] = useState('footnote')
  const [includeTable, setIncludeTable] = useState(true)
  const [consent, setConsent] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [exportResult, setExportResult] = useState(null)
  const [error, setError] = useState(null)

  // step2Data 분해
  const formData = step2Data?.formData
  const noticeApiResp = step2Data?.noticeApiResp
  const mappingResult = step2Data?.mappingResult
  const missingMaterials = step2Data?.missingMaterials
  const supplementalMaterials = step2Data?.supplementalMaterials

  // 요약 통계
  const summary = formData
    ? computeWriteSummary(formData, drafts, mappingResult, noticeApiResp, notice)
    : null
  const materials = computeMaterialsSummary(missingMaterials, supplementalMaterials)

  // 파일명 생성 — notice.title + 기본 정보 + 날짜
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  const noticeTitle = notice?.title || noticeApiResp?.target || '사업계획서'
  const fileName = `${sanitizeForFilename(noticeTitle)}_초안_${today}.docx`

  // formData가 없으면 안내
  if (!formData?.sections?.length) {
    return (
      <div className="p-6">
        <h2 className="text-2xl font-bold mb-4">Step 5. 완료 / 다운로드</h2>
        <div className="bg-amber-50 border border-amber-200 rounded p-4">
          <p className="text-sm text-amber-900">
            ⚠ Step 2 분석 데이터가 없습니다. Step 2부터 다시 진행해주세요.
          </p>
        </div>
        <StepNavigationBar onPrev={onPrev} prevLabel="← 이전 (Step 4)" />
      </div>
    )
  }

  // 모든 문항 status 평탄화 (테이블 + 통계용)
  const questionRows = formData.sections.flatMap(sec =>
    sec.questions.map(q => {
      const draft = drafts[q.id]
      const write = deriveWriteStatus(draft)
      const groupKey = draft?.status === 'approved' ? 'approved' : write.value
      return {
        qid: q.id,
        title: q.title,
        groupKey,  // approved / written / unwritten
        chars: draft?.content?.length || 0,
        warning: draft?.warnings?.join(', ') || '',
      }
    })
  )

  // 다운로드 핸들러 — POST /api/analysis/export-docx
  const handleDownload = async () => {
    if (!sessionId) {
      // 오프라인 mock fallback
      setDownloading(true)
      setTimeout(() => {
        setDownloading(false)
        setError('[오프라인] 세션 없이 export 불가')
      }, 500)
      return
    }
    setDownloading(true)
    setError(null)
    try {
      const res = await analysisApi.exportDocx({
        sessionId,
        includeTableData: includeTable,
      })
      logApi('export-docx raw', {
        export_id: res.export_id,
        status: res.status,
        file_name: res.file_name,
        unapproved_count: res.unapproved_items?.length || 0,
      })
      setExportResult(res)
    } catch (err) {
      handleFallback('export-docx', err, { onError: setError })
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="p-6">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-slate-900">Step 5. 완료 / 다운로드</h2>
        <p className="text-sm text-slate-500 mt-1">DOCX 다운로드 (LLM 호출 없음 · python-docx 조합)</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-3">
        {/* 좌측: 작성 완료 요약 */}
        <div className="space-y-3">
          {/* 요약 카드 */}
          <div className="bg-white border border-slate-200 rounded">
            <div className="px-4 py-3 border-b border-slate-200">
              <span className="font-semibold text-slate-900">작성 완료 요약</span>
            </div>
            <div className="p-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <div className="text-[10px] text-slate-500 mb-0.5">총 문항</div>
                <div className="text-2xl font-bold text-slate-900">{summary.total}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500 mb-0.5">승인됨</div>
                <div className="text-2xl font-bold text-emerald-700">{summary.approved}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500 mb-0.5">작성됨 (검토 포함)</div>
                <div className="text-2xl font-bold text-slate-700">{summary.written}</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500 mb-0.5">미작성</div>
                <div className={`text-2xl font-bold ${summary.unwritten > 0 ? 'text-red-600' : 'text-slate-400'}`}>
                  {summary.unwritten}
                </div>
              </div>
            </div>
            <div className="px-4 py-2 border-t border-slate-200 bg-slate-50 text-xs text-slate-600 flex flex-wrap gap-x-4 gap-y-1">
              <span>총 글자수 <strong className="font-mono text-slate-900">{summary.totalChars.toLocaleString()}</strong></span>
              <span>사용 evidence <strong className="font-mono text-slate-900">{summary.evidenceCount}</strong></span>
              <span>Evidence 연결 <strong className="font-mono text-slate-900">{summary.evidenceLinkedCount}/{summary.total}</strong></span>
              <span>생성일 <strong className="font-mono text-slate-900">{new Date().toISOString().slice(0,10)}</strong></span>
            </div>
          </div>

          {/* 문항별 상태 리스트 */}
          <div className="bg-white border border-slate-200 rounded">
            <div className="px-4 py-3 border-b border-slate-200">
              <span className="font-semibold text-slate-900">문항별 상태</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">id</th>
                    <th className="px-3 py-2 text-left font-medium">제목</th>
                    <th className="px-3 py-2 text-left font-medium">상태</th>
                    <th className="px-3 py-2 text-right font-medium">글자수</th>
                    <th className="px-3 py-2 text-left font-medium">메모</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {questionRows.map((q) => (
                    <tr key={q.qid} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-mono text-xs text-slate-500">{q.qid}</td>
                      <td className="px-3 py-2 text-slate-900">{q.title}</td>
                      <td className="px-3 py-2">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_BADGE[q.groupKey].cls}`}>
                          {STATUS_BADGE[q.groupKey].label}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-600">{q.chars}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">{q.warning}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 우측: 다운로드 옵션 */}
        <div className="space-y-3">
          {/* 정책 알림 */}
          <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-900 leading-relaxed">
            🚨 <strong>정책 (test_03 §3.11.4):</strong> 이 단계는 LLM 호출 없음.
            <br />
            DOCX = python-docx 조합만. ai_call_logs 비용 발생 X.
          </div>

          {/* 출처 표시 옵션 */}
          <div className="bg-white border border-slate-200 rounded">
            <div className="px-4 py-3 border-b border-slate-200">
              <span className="font-semibold text-slate-900">다운로드 옵션</span>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <div className="text-xs font-semibold text-slate-700 mb-1.5">출처 표시 방식</div>
                <div className="space-y-1">
                  {[
                    { v: 'footnote', label: '각주 (footnote)' },
                    { v: 'endnote', label: '미주 (endnote)' },
                    { v: 'none', label: '표시 안 함' },
                  ].map((o) => (
                    <label key={o.v} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="radio"
                        checked={sourceMode === o.v}
                        onChange={() => setSourceMode(o.v)}
                      />
                      <span>{o.label}</span>
                    </label>
                  ))}
                </div>
                <div className="text-[10px] text-slate-400 mt-1">
                  ⓘ v0.2: 출처 표시 방식 UI만 — backend export-docx는 include_table_data만 인식
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm cursor-pointer pt-2 border-t border-slate-100">
                <input
                  type="checkbox"
                  checked={includeTable}
                  onChange={(e) => setIncludeTable(e.target.checked)}
                />
                <span>표 데이터 포함 (include_table_data)</span>
              </label>

              <label className="flex items-start gap-2 text-xs cursor-pointer pt-2 border-t border-slate-100">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-0.5"
                />
                <span className="text-slate-600 leading-relaxed">
                  <strong>골든 케이스 보존 동의</strong> (베타)
                  <br />
                  <span className="text-slate-400">test_05 §5.1.4 — 동의 시 무제한 보존</span>
                </span>
              </label>
            </div>
          </div>

          {/* 파일명 미리보기 */}
          <div className="bg-slate-50 border border-slate-200 rounded p-3">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1">파일명</div>
            <div className="text-xs font-mono text-slate-700 break-all">{fileName}</div>
            <div className="text-[10px] text-slate-400 mt-1">
              규칙: {`{사업명}_초안_{YYYYMMDD}.docx`} (OS 금지문자 정규화)
            </div>
          </div>

          {/* Missing 경고 (v0.2.1 unapproved 정책) */}
          {summary.unwritten > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded p-2.5 text-xs text-amber-900">
              ⚠ 미작성 {summary.unwritten}건 / open 부족자료 {materials.missing.open}건 — 그래도 export 가능 (PRD §8 정신)
            </div>
          )}

          {/* 다운로드 버튼 */}
          <button
            onClick={handleDownload}
            disabled={downloading || !sessionId}
            className="w-full text-sm px-4 py-3 bg-indigo-950 text-white rounded hover:bg-indigo-900 disabled:bg-slate-300 font-semibold"
          >
            {downloading ? '⏳ 생성 중...' : '⬇ DOCX export 호출'}
          </button>

          {/* Export 결과 표시 */}
          {exportResult && (
            <div className="bg-emerald-50 border border-emerald-200 rounded p-3 text-xs">
              <div className="font-semibold text-emerald-900 mb-1">✓ export-docx 호출 성공</div>
              <div className="space-y-0.5 text-emerald-800 font-mono">
                <div>export_id: {exportResult.export_id}</div>
                <div>status: {exportResult.status}</div>
                <div className="break-all">file_url: {exportResult.file_url}</div>
                <div className="break-all">file_name: {exportResult.file_name}</div>
              </div>
              <div className="mt-2 text-[10px] text-emerald-700 leading-relaxed">
                ⓘ v0.2 mock: backend가 실제 docx 파일을 만들지 않습니다. Phase 4-G 후반에 python-docx 실제 생성.
              </div>
            </div>
          )}

          {/* 에러 표시 */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded p-2.5 text-xs text-red-800">
              ❌ {error}
            </div>
          )}

          <div className="text-[10px] text-slate-400 leading-relaxed">
            🚧 v0.2: backend export-docx mock URL만 반환. 실제 다운로드 (python-docx) 는 Phase 4-G 후반.
          </div>
        </div>
      </div>

      {/* 네비게이션 바 (Step 5 = 마지막, 다음 없음) */}
      <StepNavigationBar
        onPrev={onPrev}
        prevLabel="← 이전 (Step 4)"
      />
    </div>
  )
}
