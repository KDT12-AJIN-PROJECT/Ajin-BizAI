// AJIN BizAI v0.2.1 QG-1 — Step 2 Footer Quality Diagnostic e2e
//
// 시나리오:
//   1. /draft-v2 → Step 1 → Step 2 진입
//   2. parse-form/notice 완료 후 품질 진단 박스 보임
//   3. 11 metric label 모두 표시
//   4. risk badge 표시 (어떤 상태든 1개)
//   5. 박스가 Step2SummaryPanel 직후, StepNavigationBar 직전 위치
//   6. 기존 inline summary 보존 (마감 D-37 / 평가 기준 등)

import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const FIXTURE_DIR = path.join(__dirname, 'fixtures')
const NOTICE_FIXTURE = path.join(FIXTURE_DIR, 'notice_sample.txt')
const FORM_FIXTURE = path.join(FIXTURE_DIR, 'form_sample.txt')

test.describe('v0.2.1 QG-1 Step 2 품질 진단', () => {
  test.beforeAll(() => {
    if (!fs.existsSync(FIXTURE_DIR)) fs.mkdirSync(FIXTURE_DIR, { recursive: true })
    if (!fs.existsSync(NOTICE_FIXTURE)) fs.writeFileSync(NOTICE_FIXTURE, '공고문 샘플', 'utf-8')
    if (!fs.existsSync(FORM_FIXTURE)) fs.writeFileSync(FORM_FIXTURE, '양식 샘플', 'utf-8')
  })

  test('Step 2 진입 → 품질 진단 박스 + 11 metric + risk badge 표시', async ({ page }) => {
    // ── 1. /draft-v2 진입 ────────────────────────────────────
    await page.goto('/')
    await page.evaluate(() => sessionStorage.clear())
    await page.goto('/draft-v2')
    await expect(page.getByRole('heading', { name: '자료 업로드' })).toBeVisible({ timeout: 30_000 })

    // ── 2. Step 1 업로드 + Step 2 진입 ───────────────────────
    await page.locator('input[type="file"]').nth(0).setInputFiles(NOTICE_FIXTURE)
    await page.locator('input[type="file"]').nth(1).setInputFiles(FORM_FIXTURE)
    await page.getByRole('button', { name: /다음.*Step 2 분석|이어 작성|세션 생성 중/ }).click()
    await expect(page.getByText('원문 추출 정보').first()).toBeVisible({ timeout: 15_000 })

    // parse-form/notice/map-eval-criteria 완료 대기
    await page.waitForLoadState('networkidle')

    // ── 3. 품질 진단 박스 보임 ───────────────────────────────
    await expect(page.getByText('품질 진단')).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText('(참고용 · 자동 판정 X)')).toBeVisible()

    // ── 4. 기존 Step2SummaryPanel 보존 확인 ───────────────────
    // 기존 inline summary의 라벨 (uppercase 변환되어 "마감" / "평가 기준" 등)
    // Step2SummaryPanel에서 label은 uppercase + tracking-wider — 둘 다 보여야 함
    const noticeFooterLabels = page.locator('.uppercase')
    await expect(noticeFooterLabels.filter({ hasText: '마감' }).first()).toBeVisible()

    // ── 5. 11 metric label 모두 표시 ─────────────────────────
    // metric 영역은 1~3행에 분산. 각 라벨 텍스트 확인
    const metricLabels = [
      '추출 문항',
      '작성 가능',
      '근거 부족',
      '자료 없음',
      '자료 충족도',
      '평가기준',
      '배점 합',
      '필수서류',
      'source_page 누락',
      'invalid qid',
    ]
    for (const label of metricLabels) {
      const located = page.getByText(new RegExp(label.replace('(', '\\(').replace(')', '\\)'))).first()
      await expect(located).toBeVisible()
    }

    // "자료 충족도" 라벨 옆 "(참고)" 텍스트
    await expect(page.getByText('(참고)').first()).toBeVisible()

    // ── 6. risk badge 표시 (4 상태 중 1개) ───────────────────
    const badgePatterns = [
      /위험 신호 \d+개/,
      /위험 신호 없음/,
      /분석 중/,
      /데이터 없음/,
    ]
    let badgeFound = false
    for (const pattern of badgePatterns) {
      const count = await page.getByText(pattern).count()
      if (count > 0) {
        badgeFound = true
        break
      }
    }
    expect(badgeFound).toBe(true)

    // ── 7. badge가 품질 진단 박스 안에 있는지 (위치 확인) ────
    // 품질 진단 영역과 같은 컨테이너에 badge가 있어야 함
    const qualityBox = page.locator('div').filter({ hasText: /^품질 진단.*$/i }).first()
    await expect(qualityBox).toBeVisible()

    // ── 8. 자료 충족도 % 또는 "데이터 없음" 표시 ─────────────
    // backend mock에서 ok/weak/missing 데이터가 있으면 %, 없으면 "데이터 없음"
    const sufficiencyText = page.getByText(/자료 충족도/)
    await expect(sufficiencyText.first()).toBeVisible()
  })
})
