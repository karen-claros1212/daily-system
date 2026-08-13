import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testIgnore: 'real-*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'node e2e/mock-api.mjs',
      // Puerto dedicado: :8000 lo comparte un servicio del sistema que, si
      // responde, hace que reuseExistingServer levante la suite contra el
      // "servidor equivocado" en vez de este mock.
      url: 'http://localhost:8100/api/inversionista/resumen',
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      env: {
        MOCK_API_PORT: '8100',
      },
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      env: {
        API_BASE: 'http://localhost:8100',
        DAILY_ENV: 'test',
      },
    },
  ],
});