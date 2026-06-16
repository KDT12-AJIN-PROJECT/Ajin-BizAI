import { defineConfig } from 'vitest/config'

// Phase 4-H B1-β — vitest 설정 (Phase 4-G lock-in)
export default defineConfig({
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['tests/**/*.test.{js,jsx,mjs,ts,tsx}'],
    exclude: ['node_modules', 'dist', 'tests/adapters.mjs'],  // dependency-free 기존 script는 제외
  },
})
