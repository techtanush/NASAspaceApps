import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
const chromePath='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const executable=process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync(chromePath)?chromePath:undefined);
const mock = process.env.E2E_TARGET === 'mock';
export default defineConfig({
 testDir: '../../tests/e2e', timeout: 90000, expect: { timeout: 15000 }, fullyParallel: false, workers: 1,
 reporter: [['list'], ['json', { outputFile: `../../out/e2e-results-${process.env.E2E_RUN_NAME || 'default'}.json` }]],
 use: { actionTimeout: 15000, navigationTimeout: 30000, baseURL: process.env.E2E_BASE_URL || 'http://127.0.0.1:5176', viewport: { width: 1440, height: 900 }, acceptDownloads: true, trace: /^(visual|M\d)/.test(process.env.E2E_RUN_NAME||'') ? 'off' : 'retain-on-failure', screenshot: 'only-on-failure', launchOptions: { executablePath: executable, args: ['--no-sandbox'] } },
 webServer: mock ? { command: 'pnpm run dev:mock', url: 'http://127.0.0.1:5176', reuseExistingServer: !process.env.CI, timeout: 30000 } : undefined,
 outputDir: `../../out/playwright-${process.env.E2E_RUN_NAME || 'default'}`,
});
