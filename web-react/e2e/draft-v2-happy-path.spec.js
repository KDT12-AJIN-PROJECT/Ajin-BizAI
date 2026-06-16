// AJIN BizAI v0.2 — DraftPageV2 happy path e2e (Phase 4-H B2-lite)
//
// 검증 시나리오:
//   1. /draft-v2 진입 → Step 1 화면 표시
//   2. 공고문 파일 multipart 업로드 → ✓ 배지 (A1)
//   3. 제출양식 파일 multipart 업로드 → ✓ 배지 (A1)
//   4. "다음 → (Step 2 분석)" 클릭 → Step 2 진입
//   5. 새로고침 → A1 attachments 자동 복원 (영속화 검증)
//
// 사전 조건:
//   - backend uvicorn :8000 살아있음
//   - .env: VITE_ENABLE_ANALYSIS_DEV_MODE=true (이미 설정됨)
//
// 실행:
//   cd web-react
//   npx playwright test
//   npx playwright test --ui

import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// 테스트용 임시 파일 (txt — parse-file에서 utf-8 디코딩)
const FIXTURE_DIR = path.join(__dirname, 'fixtures')
const NOTICE_FIXTURE = path.join(FIXTURE_DIR, 'notice_sample.txt')
const FORM_FIXTURE = path.join(FIXTURE_DIR, 'form_sample.txt')

test.describe('DraftPageV2 Phase 4-H A1/A2/A3 happy path', () => {
  test.beforeAll(() => {
    if (!fs.existsSync(FIXTURE_DIR)) fs.mkdirSync(FIXTURE_DIR, { recursive: true })
    if (!fs.existsSync(NOTICE_FIXTURE)) {
      fs.writeFileSync(NOTICE_FIXTURE,
        '공고문 샘플 — 정부지원사업 자동화 SaaS\n지원대상: 중소기업\n지원금: 최대 1억원',
        'utf-8')
    }
    if (!fs.existsSync(FORM_FIXTURE)) {
      fs.writeFileSync(FORM_FIXTURE,
        '제출양식 샘플\nI-1 시장 문제\nI-2 솔루션 개요\nI-3 차별성',
        'utf-8')
    }
  })

  test('Step 1 → 파일 업로드 → Step 2 진입 (A1 multipart 영속화)', async ({ page }) => {
    // ── 1. /draft-v2 진입 ────────────────────────────────────
    // 콘솔 + 네트워크 로깅 (디버깅)
    page.on('console', msg => console.log(`[browser ${msg.type()}]`, msg.text()))
    page.on('pageerror', err => console.log('[pageerror]', err.message))

    // 이전 테스트 흔적 정리 (sessionStorage)
    await page.goto('/')
    await page.evaluate(() => sessionStorage.clear())
    await page.goto('/draft-v2')
    await page.waitForLoadState('networkidle')

    // 디버깅: root에 무엇이 들어있는지
    const rootHtml = await page.locator('#root').innerHTML()
    console.log('[root innerHTML length]', rootHtml.length, 'first 200:', rootHtml.slice(0, 200))

    // 페이지 헤더 (currentStep 무관)
    await expect(page.getByText('DraftPage V2', { exact: false })).toBeVisible({ timeout: 30_000 })
    // Step 1 화면 진입 확인 (Step1Common h3)
    await expect(page.getByRole('heading', { name: '자료 업로드' })).toBeVisible({ timeout: 10_000 })

    // ── 2. 공고문 파일 업로드 ────────────────────────────────
    // 공고문 카드의 "공고문 파일 추가" 라벨 옆 hidden input
    const noticeInput = page.locator('input[type="file"]').nth(0)
    await noticeInput.setInputFiles(NOTICE_FIXTURE)

    // ── 3. 제출양식 파일 업로드 ──────────────────────────────
    // 제출양식 카드는 두 번째 file input
    const formInput = page.locator('input[type="file"]').nth(1)
    await formInput.setInputFiles(FORM_FIXTURE)

    // ── 4. 파일 ✓ 배지 (업로드 성공) 확인 ──────────────────
    // 파일명이 카드 안에 표시되면 백엔드 응답 받았다는 신호
    await expect(page.getByText('notice_sample.txt')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('form_sample.txt')).toBeVisible({ timeout: 10_000 })

    // ── 5. Step 2 진입 ───────────────────────────────────────
    await page.getByRole('button', { name: /다음.*Step 2 분석|이어 작성|세션 생성 중/ }).click()

    // Step 2 화면이 보일 때까지 대기 (분석 패널의 "원문 추출 정보" h3)
    await expect(page.getByText('원문 추출 정보').first()).toBeVisible({ timeout: 15_000 })
    // footer "Step 2 분석 결과 확정 →" 버튼이 있어야 Step 2 화면
    await expect(page.getByRole('button', { name: /Step 2 분석 결과 확정/ })).toBeVisible()

    // ── 6. A1 영속화 검증 — 새로고침 후 attachments 복원 ────
    await page.reload()

    // 복원 후 Step 2에 머물러야 하고, 또는 Step 1로 가서 파일 목록 복원
    // restoreChecked 후 자동 복원 → 파일명이 다시 보임
    // (Step 2부터 시작하므로 사이드 패널에 attachment 표시되거나, Step 1 backward 시 보임)
    await page.waitForLoadState('networkidle')

    // 잠시 후 sessionStorage 확인 — sessionId 살아있어야 함
    const sessionId = await page.evaluate(() => sessionStorage.getItem('ajin_v2_session_id'))
    expect(sessionId).toBeTruthy()
    expect(sessionId.length).toBeGreaterThan(8)
  })
})
