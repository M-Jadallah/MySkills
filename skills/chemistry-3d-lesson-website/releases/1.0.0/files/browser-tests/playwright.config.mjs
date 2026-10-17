import { defineConfig } from '@playwright/test';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

function targetUrl() {
  if (process.env.TARGET_URL) return process.env.TARGET_URL;
  if (process.env.TARGET_FILE) return pathToFileURL(path.resolve(process.env.TARGET_FILE)).href;
  throw new Error('Set TARGET_URL or TARGET_FILE before running Playwright tests.');
}

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: targetUrl(),
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
