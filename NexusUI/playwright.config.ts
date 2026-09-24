import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    baseURL: process.env.NEXUS_E2E_BASE_URL || 'http://127.0.0.1:3200',
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 20000,
    navigationTimeout: 30000,
    trace: 'retain-on-failure',
  },
  webServer: process.env.NEXUS_E2E_BASE_URL
    ? undefined
    : {
        command: 'pnpm start --hostname 127.0.0.1 --port 3200',
        url: 'http://127.0.0.1:3200',
      },
});
