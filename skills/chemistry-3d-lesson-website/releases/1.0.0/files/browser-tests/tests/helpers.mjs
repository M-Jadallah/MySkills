export async function openTarget(page) {
  const errors = [];
  const warnings = [];
  const failedRequests = [];

  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
    if (message.type() === 'warning') warnings.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('requestfailed', (request) => {
    failedRequests.push(`${request.method()} ${request.url()} :: ${request.failure()?.errorText || 'failed'}`);
  });

  await page.goto('/', { waitUntil: 'load' });
  await page.waitForTimeout(250);
  return { errors, warnings, failedRequests };
}

export async function changeRangeContinuously(page, selector) {
  await page.locator(selector).evaluate((element) => {
    const input = /** @type {HTMLInputElement} */ (element);
    const min = Number(input.min || 0);
    const max = Number(input.max || 100);
    const values = [min, min + (max - min) * 0.25, min + (max - min) * 0.5, min + (max - min) * 0.75, max];
    for (const value of values) {
      input.value = String(value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
}

export function isRemote(url) {
  return /^https?:\/\//i.test(url);
}
