// AJIN BizAI v0.2.1 V3 — 평가기준 매핑 편집 e2e
//
// 시나리오:
//   1. /draft-v2 → Step 1 → Step 2 진입
//   2. parse-form 완료 대기
//   3. 평가기준 카드 [✎] 클릭 → 편집 모달 열림 (5단 구조 확인)
//   4. V3 2차 — 검색 input 존재 확인
//   5. scope 변경 + reason 입력 → 저장
//   6. 모달 자동 닫힘 + 카드에 "✎ 사용자 편집됨" 배지
//   7. backend GET list 호출 → user row 영속화 확인 (V4 backend 통합)
//
// 사전: backend uvicorn :8000 살아있음, .env에 VITE_ENABLE_ANALYSIS_DEV_MODE=true

import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const FIXTURE_DIR = path.join(__dirname, 'fixtures')
const NOTICE_FIXTURE = path.join(FIXTURE_DIR, 'notice_sample.txt')
const FORM_FIXTURE = path.join(FIXTURE_DIR, 'form_sample.txt')

test.describe('v0.2.1 V3 평가기준 매핑 편집', () => {
  test.beforeAll(() => {
    // happy-path spec과 동일 fixture 사용 (이미 존재하면 재생성 안 함)
    if (!fs.existsSync(FIXTURE_DIR)) fs.mkdirSync(FIXTURE_DIR, { recursive: true })
    if (!fs.existsSync(NOTICE_FIXTURE)) {
      fs.writeFileSync(NOTICE_FIXTURE, '공고문 샘플 — 정부지원사업', 'utf-8')
    }
    if (!fs.existsSync(FORM_FIXTURE)) {
      fs.writeFileSync(FORM_FIXTURE, '제출양식 샘플\nI-1 시장 문제', 'utf-8')
    }
  })

  test('평가기준 카드 → 편집 모달 → 저장 → user 배지 + backend 영속화', async ({ page, request }) => {
    page.on('pageerror', err => console.log('[pageerror]', err.message))

    // ── 1. sessionStorage clear → /draft-v2 진입 ─────────────
    await page.goto('/')
    await page.evaluate(() => sessionStorage.clear())
    await page.goto('/draft-v2')
    await expect(page.getByText('DraftPage V2', { exact: false })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('heading', { name: '자료 업로드' })).toBeVisible({ timeout: 10_000 })

    // ── 2. Step 1 파일 업로드 ────────────────────────────────
    await page.locator('input[type="file"]').nth(0).setInputFiles(NOTICE_FIXTURE)
    await page.locator('input[type="file"]').nth(1).setInputFiles(FORM_FIXTURE)
    await expect(page.getByText('notice_sample.txt')).toBeVisible({ timeout: 10_000 })

    // ── 3. Step 2 진입 ───────────────────────────────────────
    await page.getByRole('button', { name: /다음.*Step 2 분석|이어 작성|세션 생성 중/ }).click()
    await expect(page.getByText('원문 추출 정보').first()).toBeVisible({ timeout: 15_000 })

    // ── 4. parse-form 완료 대기 + 평가기준 카드 보임 확인 ────
    await page.waitForLoadState('networkidle')
    await expect(page.getByText('평가 기준', { exact: false }).first()).toBeVisible()

    // sessionId 캡처 (마지막 검증용)
    const sessionId = await page.evaluate(() => sessionStorage.getItem('ajin_v2_session_id'))
    expect(sessionId).toBeTruthy()

    // ── 5. 첫 번째 평가기준 카드 [✎] 클릭 → 모달 ─────────────
    const editButtons = page.locator('button[title="평가기준 매핑 편집"]')
    await expect(editButtons.first()).toBeVisible({ timeout: 5_000 })
    await editButtons.first().click()

    // 모달 5단 구조 확인 (모달 안 전용 문구로 정밀 매칭)
    await expect(page.getByText('평가기준 매핑 편집')).toBeVisible()
    await expect(page.getByText(/사용자 편집값으로 보존됩니다/)).toBeVisible()  // info 모달 전용
    await expect(page.getByText('현재 매핑')).toBeVisible()                 // body left
    await expect(page.getByText(/변경 사항.*Before.*After/)).toBeVisible()  // diff strip
    await expect(page.getByRole('button', { name: /변경사항 저장/ })).toBeVisible()  // foot

    // ── 6. V3 2차 — 검색 input 존재 확인 ──────────────────────
    await expect(page.getByPlaceholder(/문항 ID 또는 제목 검색/)).toBeVisible()

    // ── 7. scope 변경 (section → document) ───────────────────
    await page.getByRole('radio', { name: /document/ }).check()

    // ── 8. reason 입력 ───────────────────────────────────────
    await page.getByPlaceholder(/기술성 평가는/).fill('e2e 자동 검증 — scope를 document로 변경')

    // ── 9. 저장 버튼 활성 → 클릭 ─────────────────────────────
    const saveButton = page.getByRole('button', { name: /변경사항 저장/ })
    await expect(saveButton).toBeEnabled()
    await saveButton.click()

    // ── 10. 모달 자동 닫힘 + 카드에 "✎ 사용자 편집됨" 배지 ───
    await expect(page.getByText('평가기준 매핑 편집')).toBeHidden({ timeout: 10_000 })
    await expect(page.getByText('✎ 사용자 편집됨').first()).toBeVisible({ timeout: 5_000 })

    // ── 11. backend GET list 직접 호출 → user row 영속화 확인 (V4 검증) ──
    const res = await request.get(`/api/analysis/eval-criteria-mappings?session_id=${sessionId}`)
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.total).toBeGreaterThanOrEqual(1)
    const userRow = data.items.find(it => it.mapped_by === 'user')
    expect(userRow).toBeTruthy()
    expect(userRow.scope).toBe('document')
    expect(userRow.reason).toContain('e2e 자동 검증')
    expect(userRow.history_count).toBeGreaterThanOrEqual(1)
  })
})
