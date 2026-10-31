/* Node request checks and a reusable Playwright UI flow; no embedded credentials. */
const assert = require('node:assert/strict');

async function selfTest() {
  const { RequestClient } = require('../service/static/v1.js');
  const calls = [];
  let response = 'lost';
  const client = new RequestClient(async (url, options) => {
    calls.push({ url, options });
    if (response === 'lost') throw new Error('connection lost after commit');
    return { ok: response === 200, status: response, json: async () => response === 200
      ? { data: { change_id: 'committed' }, replayed: true }
      : { error: { code: 'STALE_REVISION', message: 'Refresh', request_id: 'r1' } } };
  });
  client.connect('analyst-secret', { tenant_id: 't', actor_id: 'a' });
  const body = { title: 'original' };
  await assert.rejects(client.mutate('/api/v1/changes', body, null), /결과/);
  body.title = 'edited';
  const original = calls[0];
  assert.equal(client.pending().body, '{"title":"original"}');
  client.connect('reviewer-secret', { tenant_id: 't', actor_id: 'b' });
  assert.equal(client.pending(), undefined);
  client.connect('analyst-secret', { tenant_id: 't', actor_id: 'a' });
  response = 200;
  assert.equal((await client.retry()).replayed, true);
  assert.deepEqual(calls[1], original);
  assert.equal(client.pending(), undefined);
  response = 503;
  await assert.rejects(client.mutate('/x', {}, 4));
  assert.equal(client.pending().revision, 4);
  response = 409;
  await assert.rejects(client.retry(), /STALE_REVISION/);
  assert.equal(client.pending().revision, 4);
  response = 200;
  await client.retry();
  assert.equal(client.pending(), undefined);
  response = 'lost';
  const slow = client.mutate('/x', {}, 2);
  await assert.rejects(client.mutate('/x', {}, 2), /진행/);
  await assert.rejects(slow);
  console.log('PASS: exact replay, actor isolation, immutable body, 503 recovery, uncertain-denial preservation, concurrency');
}

async function checkLayout(page) {
  const original = page.viewportSize();
  try {
    for (const width of [1280, 1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const layout = await page.evaluate(() => {
        const queue = document.querySelector('.queue-panel').getBoundingClientRect();
        const detail = document.querySelector('#detail-title').closest('section').getBoundingClientRect();
        return { queue: { top: queue.top, right: queue.right, bottom: queue.bottom }, detail: { top: detail.top, left: detail.left }, overflow: document.documentElement.scrollWidth > innerWidth,
          closedDialogVisible: [...document.querySelectorAll('dialog:not([open])')].some(dialog => getComputedStyle(dialog).display !== 'none') };
      });
      assert.equal(layout.overflow, false, `${width}px horizontal overflow`);
      assert.equal(layout.closedDialogVisible, false, 'closed native dialogs stay hidden');
      if (width >= 992) {
        assert.ok(Math.abs(layout.queue.top - layout.detail.top) <= 1, `${width}px inspector must start beside queue`);
        assert.ok(layout.queue.right <= layout.detail.left, `${width}px queue and inspector must not overlap`);
      } else assert.ok(layout.queue.bottom <= layout.detail.top, 'mobile inspector follows queue');
    }
  } finally { if (original) await page.setViewportSize(original); }
}

async function errorFocusProbe(page, { decisionSelector = '#decision-APPROVE' } = {}) {
  await page.locator(decisionSelector).waitFor({ state: 'visible' });
  const original = page.viewportSize();
  const snapshot = await page.evaluate(() => ({ status: document.querySelector('#change-status').textContent,
    revision: document.querySelector('.change-meta p').textContent }));
  let posts = 0;
  const count = request => { if (request.method() === 'POST' && request.url().includes('/api/v1/changes')) ++posts; };
  page.on('request', count);
  try {
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.locator(decisionSelector).click();
      for (const reason of ['        ', '       a']) {
        await page.locator('#reason').fill(reason);
        await page.locator('#decision-form button[type=submit]').click();
        await page.locator('#decision-error-summary').waitFor({ state: 'visible' });
        const error = await page.evaluate(() => {
          const dialog = document.querySelector('#decision-dialog'), field = document.querySelector('#reason');
          const background = getComputedStyle(dialog).backgroundColor;
          return { open: dialog.open, focus: document.activeElement.id, invalid: field.getAttribute('aria-invalid'),
            describedBy: field.getAttribute('aria-describedby'), alert: document.querySelector('#decision-error-summary').getAttribute('role'),
            backgroundAlpha: background.startsWith('rgba(') ? Number(background.split(',').at(-1).replace(')', '')) : background.startsWith('rgb(') ? 1 : 0,
            overflow: document.documentElement.scrollWidth > innerWidth };
        });
        assert.equal(error.open, true); assert.equal(error.focus, 'decision-error-summary');
        assert.equal(error.invalid, 'true'); assert.equal(error.describedBy, 'reason-error'); assert.equal(error.alert, 'alert');
        assert.equal(error.backgroundAlpha, 1, 'native modal surface must be opaque'); assert.equal(error.overflow, false);
        assert.equal(posts, 0, 'local invalid reason must not be submitted');
        await page.locator('#reason-error-link').click();
        assert.equal(await page.locator('#reason').evaluate(el => el === document.activeElement), true);
      }
      await page.locator('#reason').fill('a b cdef');
      assert.equal(await page.locator('#decision-error-summary').isVisible(), false);
      assert.equal(await page.locator('#reason-error').isVisible(), false);
      assert.equal(await page.locator('#reason').getAttribute('aria-invalid'), null);
      assert.equal(await page.locator('#reason').getAttribute('aria-describedby'), null);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator(decisionSelector).evaluate(el => el === document.activeElement), true);
      await page.locator(decisionSelector).click();
      assert.equal(await page.locator('#decision-error-summary').isVisible(), false);
      await page.keyboard.press('Escape');
    }
    assert.equal(posts, 0);
    assert.deepEqual(await page.evaluate(() => ({ status: document.querySelector('#change-status').textContent,
      revision: document.querySelector('.change-meta p').textContent })), snapshot);
    return { widths: [1440, 390], posts, browser: page.context().browser().version() };
  } finally { page.off('request', count); if (original) await page.setViewportSize(original); }
}

async function browserProbe(page, { baseURL, tokens, presetIndex = 2, passingDays = 24 }) {
  const login = async token => {
    if (await page.locator('#switch-role').isVisible()) await page.locator('#switch-role').click();
    await page.locator('#token').fill(token);
    await page.locator('#login-form button').click();
    await page.locator('#workspace').waitFor({ state: 'visible' });
    await page.locator('#refresh').waitFor({ state: 'visible' });
  };
  const status = async value => {
    await page.waitForFunction(v => document.querySelector('#change-status')?.textContent === v, value);
    const stages = page.locator('.review-stages li');
    assert.equal(await stages.count(), 4, 'all workflow stages remain visible');
    const active = page.locator('.review-stages [aria-current="step"]');
    const labels = { DRAFT: '작성·평가', PENDING_DOMAIN_REVIEW: '현업 검토', PENDING_RELEASE: '최종 검토', APPROVED_FOR_DEMO: '데모 승인' };
    assert.equal(await active.count(), value === 'REJECTED' ? 0 : 1, 'only the actual current state is marked');
    if (labels[value]) assert.equal(await active.textContent(), labels[value]);
  };
  const decision = async (value, reason) => {
    await page.locator(`[data-decision="${value}"]`).click();
    await page.locator('#reason').fill(reason);
    await page.locator('#decision-form button[type=submit]').click();
  };
  await page.goto(baseURL + '/v1');
  await login(tokens.analyst);
  await checkLayout(page);
  await page.locator('#new-change').click();
  await page.locator('#preset').selectOption({ index: presetIndex });
  await page.locator('#title').fill('<img src=x onerror="window.__xss=1">');
  await page.locator('#create-form button[type=submit]').click();
  await status('DRAFT');
  const original = await page.locator('#change-id').textContent();
  await page.locator('[data-case-input]').evaluateAll((els, days) => els.forEach(el => { el.value = days; }), passingDays);
  await page.locator('#evaluate').click();
  await page.waitForFunction(() => document.querySelector('#run-result')?.textContent.includes('PASS'));
  // Commit on the server, then abort only its successful response.
  await page.route('**/api/v1/changes/*/submit', async route => { await route.fetch(); await route.abort(); }, { times: 1 });
  await page.locator('#submit-change').click();
  await page.locator('#retry-request').waitFor({ state: 'visible' });
  await page.locator('#retry-request').click();
  await status('PENDING_DOMAIN_REVIEW');
  await login(tokens.domain);
  await page.locator('[data-change-id="' + original + '"]').click();
  await errorFocusProbe(page, { decisionSelector: '#decision-REJECT' });
  await decision('REJECT', '<svg onload="window.__xss=1"> correction needed');
  await status('REJECTED');
  await login(tokens.analyst);
  await page.locator('[data-change-id="' + original + '"]').click();
  await page.locator('#correct-change').click();
  await page.locator('#create-form button[type=submit]').click();
  await status('DRAFT');
  const corrected = await page.locator('#change-id').textContent();
  assert.notEqual(corrected, original);
  await page.locator('[data-case-input]').evaluateAll((els, days) => els.forEach(el => { el.value = days; }), passingDays);
  await page.locator('#evaluate').click();
  await page.waitForFunction(() => document.querySelector('#run-result')?.textContent.includes('PASS'));
  await page.locator('#submit-change').click();
  await status('PENDING_DOMAIN_REVIEW');
  await login(tokens.domain);
  await page.locator('[data-change-id="' + corrected + '"]').click();
  await decision('APPROVE', 'Corrected full suite reviewed.');
  await status('PENDING_RELEASE');
  await login(tokens.release);
  await page.locator('[data-change-id="' + corrected + '"]').click();
  await decision('APPROVE', 'Independent release review complete.');
  await status('APPROVED_FOR_DEMO');
  await page.locator('#load-evidence').click();
  await page.waitForFunction(() => document.querySelector('#evidence').textContent.includes('VALID'));
  assert.equal(await page.evaluate(() => window.__xss), undefined);
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  await page.setViewportSize({ width: 375, height: 812 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  // Native dialog Escape restores focus to its opener.
  await login(tokens.analyst);
  await page.locator('#new-change').click();
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#new-change').evaluate(el => el === document.activeElement), true);
  return { original, corrected, browser: page.context().browser().version() };
}

module.exports = { browserProbe, checkLayout, errorFocusProbe, selfTest };
if (require.main === module) selfTest().catch(error => { console.error(error); process.exitCode = 1; });
