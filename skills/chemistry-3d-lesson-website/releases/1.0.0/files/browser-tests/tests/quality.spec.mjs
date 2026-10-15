import { test, expect } from '@playwright/test';
import { openTarget, changeRangeContinuously, isRemote } from './helpers.mjs';

const desktopViewports = [
  { width: 1024, height: 768 },
  { width: 1280, height: 720 },
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];

const mobileViewports = [
  { width: 360, height: 800 },
  { width: 375, height: 812 },
  { width: 390, height: 844 },
  { width: 412, height: 915 },
  { width: 430, height: 932 },
  { width: 800, height: 360 },
  { width: 812, height: 375 },
  { width: 844, height: 390 },
  { width: 915, height: 412 },
  { width: 932, height: 430 },
];

test('page loads with no uncaught console errors or failed required requests', async ({ page }) => {
  const audit = await openTarget(page);
  expect(audit.errors, audit.errors.join('\n')).toEqual([]);
  expect(audit.failedRequests, audit.failedRequests.join('\n')).toEqual([]);
});

test('required lesson and simulation hooks are present', async ({ page }) => {
  await openTarget(page);
  await expect(page.locator('[data-lesson-section]').first()).toBeVisible();
  await expect(page.locator('[data-science-sim]').first()).toBeAttached();
  await expect(page.locator('[data-verification-card]').first()).toBeAttached();
  await expect(page.locator('[data-final-assessment]').first()).toBeAttached();
});

test('every form control has an accessible name', async ({ page }) => {
  await openTarget(page);
  const unnamed = await page.locator('input, select, textarea, button').evaluateAll((elements) =>
    elements
      .filter((element) => {
        const aria = element.getAttribute('aria-label') || element.getAttribute('aria-labelledby');
        const id = element.getAttribute('id');
        const label = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`) : null;
        const text = element.textContent?.trim();
        const title = element.getAttribute('title');
        return !aria && !label && !text && !title;
      })
      .map((element) => element.outerHTML.slice(0, 240))
  );
  expect(unnamed, unnamed.join('\n')).toEqual([]);
});

test('same canvas and renderer persist during continuous slider input', async ({ page }) => {
  await openTarget(page);
  const canvas = page.locator('canvas[data-simulation-canvas], [data-science-sim] canvas').first();
  const slider = page.locator('input[type="range"][data-control-id], [data-science-sim] input[type="range"]').first();
  test.skip((await canvas.count()) === 0 || (await slider.count()) === 0, 'No simulation canvas or range control found.');

  await page.evaluate(() => {
    window.__SKILL_ORIGINAL_CANVAS__ = document.querySelector('canvas[data-simulation-canvas], [data-science-sim] canvas');
    window.__SKILL_DEBUG_BEFORE__ = JSON.parse(JSON.stringify(window.__SCIENCE_DEBUG__ || {}));
  });

  await changeRangeContinuously(page, await slider.evaluate((element) => {
    if (!element.id) element.id = `skill-control-${Math.random().toString(36).slice(2)}`;
    return `#${CSS.escape(element.id)}`;
  }));
  await page.waitForTimeout(500);

  const result = await page.evaluate(() => {
    const current = document.querySelector('canvas[data-simulation-canvas], [data-science-sim] canvas');
    const before = window.__SKILL_DEBUG_BEFORE__ || {};
    const after = window.__SCIENCE_DEBUG__ || {};
    return {
      sameCanvas: current === window.__SKILL_ORIGINAL_CANVAS__,
      sceneBefore: before.sceneInitCount || null,
      sceneAfter: after.sceneInitCount || null,
      rendererBefore: before.rendererCreateCount || null,
      rendererAfter: after.rendererCreateCount || null,
    };
  });

  expect(result.sameCanvas).toBe(true);
  if (result.sceneBefore && result.sceneAfter) expect(result.sceneAfter).toEqual(result.sceneBefore);
  if (result.rendererBefore && result.rendererAfter) expect(result.rendererAfter).toEqual(result.rendererBefore);
});

for (const viewport of [...desktopViewports, ...mobileViewports]) {
  test(`no unexplained horizontal overflow at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await openTarget(page);
    const overflow = await page.evaluate(() => {
      const pageOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
      const offenders = [...document.querySelectorAll('body *')]
        .filter((element) => {
          const style = getComputedStyle(element);
          if (['auto', 'scroll'].includes(style.overflowX)) return false;
          const rect = element.getBoundingClientRect();
          return rect.right > document.documentElement.clientWidth + 2 || rect.left < -2;
        })
        .slice(0, 10)
        .map((element) => ({ tag: element.tagName, className: element.className, id: element.id }));
      return { pageOverflow, offenders };
    });
    expect(overflow.pageOverflow, JSON.stringify(overflow.offenders, null, 2)).toBeLessThanOrEqual(2);
  });
}

test('all local images load', async ({ page }) => {
  await openTarget(page);
  const broken = await page.locator('img').evaluateAll((images) =>
    images
      .filter((image) => !image.complete || image.naturalWidth === 0)
      .map((image) => image.getAttribute('src'))
  );
  expect(broken, broken.join('\n')).toEqual([]);
});

test('standalone page makes no remote network requests', async ({ page }) => {
  const remote = [];
  page.on('request', (request) => {
    if (isRemote(request.url())) remote.push(request.url());
  });
  await openTarget(page);
  expect(remote, remote.join('\n')).toEqual([]);
});

test('locked footer markers and footer are present', async ({ page }) => {
  await openTarget(page);
  const html = await page.content();
  expect(html).toContain('FOOTER_LOCK_START');
  expect(html).toContain('FOOTER_LOCK_END');
  await expect(page.locator('footer').last()).toBeAttached();
});
