// AJIN BizAI v0.2 — Playwright e2e 설정 (Phase 4-H B2-lite)
//
// 자동 기동:
//   - backend (uvicorn :8000) — 외부에서 미리 띄워야 함 (CLAUDE.md §7)
//   - frontend (vite :5173) — playwright webServer로 자동 기동
//
// 실행:
//   cd web-react
//   npx playwright test
//   npx playwright test --ui    # 디버깅
//
// 사전 조건:
//   backend가 :8000에서 살아 있어야 함 (별도 터미널에서 uvicorn 기동)

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.{js,ts}',  // tests/ (vitest) 분리
  fullyParallel: false,            // 단일 세션 흐름 → 직렬 실행
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,                       // 단일 worker (세션 상태 충돌 방지)
  reporter: [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
})
