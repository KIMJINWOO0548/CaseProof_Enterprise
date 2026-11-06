/* Actual application handlers in a small DOM/transport harness, not a browser test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');

const root = path.join(__dirname, '..');
const javascript = fs.readFileSync(path.join(root, 'service/static/v1.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'service/static/v1.html'), 'utf8');

class Element {
  constructor(tag = 'div', rootElement = false) {
    this.tagName = tag.toUpperCase(); this.rootElement = rootElement;
    this.children = []; this.dataset = {}; this.attributes = {}; this.value = '';
    this._text = ''; this.disabled = false; this.hidden = false;
    this.classList = { toggle() {} };
  }
  get isConnected() { return this.rootElement || !!this.parent?.isConnected; }
  set textContent(value) { this._text = String(value); this.children.forEach(e => { e.parent = null; }); this.children = []; }
  get textContent() { return this._text + this.children.map(e => e.textContent).join(''); }
  append(...children) { children.forEach(e => { e.parent = this; this.children.push(e); }); }
  replaceChildren(...children) { this.textContent = ''; this.append(...children); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; }
  closest(tag) { return this.tagName === tag.toUpperCase() ? this : this.parent?.closest(tag); }
  focus() {}
  addEventListener() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
}

const plain = value => JSON.parse(JSON.stringify(value));
const settle = async () => { for (let turn = 0; turn < 12; turn++) await new Promise(setImmediate); };

function state(kind, revision = kind === 'NO_RUN' ? 1 : 2) {
  const snapshot = { change_id: 'synthetic-change', title: 'Synthetic ' + kind,
    revision, status: 'DRAFT', requester_id: 'analyst', owner_id: 'analyst',
    pack_version_id: 'synthetic', candidate_snapshot_id: 'candidate',
    source_bundle_id: 'bundle', suite_version_id: 'suite',
    active_run_id: kind === 'NO_RUN' ? null : 'run-' + revision };
  const incomplete = kind === 'INCOMPLETE';
  const run = kind === 'NO_RUN' ? null : { id: snapshot.active_run_id,
    completion: incomplete ? 'INCOMPLETE' : 'COMPLETE',
    gate_summary: kind === 'PASS' ? 'PASS' : 'BLOCK', case_results: [{ case_id: 'case',
      verdict: incomplete ? 'INCONCLUSIVE' : kind === 'PASS' ? 'PASS' : 'FAIL',
      resolution_status: incomplete ? 'INCONCLUSIVE' : 'RESOLVED' }] };
  return { historical_integrity: 'VALID', snapshot, latest_run: run };
}

async function app({ initial = 'PASS', rejection = null, refreshStatus = 200, uncertainEvaluation = false, extraGet = null, javascriptOverride = null } = {}) {
  const roots = new Map(), created = [], calls = [];
  for (const match of html.matchAll(/<([a-z][a-z0-9]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
    const element = new Element(match[1], true); element.id = match[3];
    element.disabled = /\bdisabled\b/.test(match[2]); element.hidden = /\bhidden\b/.test(match[2]);
    if (/\bdata-mutation\b/.test(match[2])) element.dataset.mutation = '';
    roots.set(element.id, element);
  }
  const connected = () => [...roots.values(), ...created].filter(e => e.isConnected);
  const get = id => created.find(e => e.id === id && e.isConnected) || roots.get(id) || null;
  const document = {
    getElementById: get,
    createElement: tag => { const element = new Element(tag); created.push(element); return element; },
    querySelectorAll: selector => {
      if (selector === '[data-change-id]') return connected().filter(e => Object.hasOwn(e.dataset, 'changeId'));
      if (selector === '[data-mutation]') return connected().filter(e => Object.hasOwn(e.dataset, 'mutation'));
      if (selector === '[data-case-input]') return connected().filter(e => Object.hasOwn(e.dataset, 'caseInput'));
      if (selector === 'dialog') return connected().filter(e => e.tagName === 'DIALOG');
      if (selector === 'dialog[open]') return connected().filter(e => e.tagName === 'DIALOG' && e.open);
      return [];
    },
  };
  let current = state(initial), reads = 0, posts = 0;
  const preset = { create_body: { suite_version_id: 'suite', pack_version_id: 'synthetic' },
    case_inputs: [{ case_id: 'case', claim_days: 30, case_context: {} }] };
  const error = (status, code) => ({ ok: false, status, json: async () => ({ error: {
    code, message: 'Synthetic request rejected', request_id: 'synthetic-request' } }) });
  const fetch = async (url, options = {}) => {
    const method = options.method || 'GET'; calls.push({ url, method, options: plain(options) });
    if (method === 'POST') {
      posts++;
      if (uncertainEvaluation) {
        assert.equal(url, '/api/v1/changes/synthetic-change/evaluation-runs');
        if (posts === 1) return error(503, 'OUTCOME_UNKNOWN');
        current = state('PASS', 2);
        return { ok: true, status: 201, json: async () => ({ data: { ...current.snapshot, run: current.latest_run }, replayed: true }) };
      }
      assert.equal(url, '/api/v1/changes/synthetic-change/submit');
      assert.ok(rejection, 'unexpected mutation without a configured outcome');
      return error(rejection.status, rejection.code);
    }
    if (url === '/api/v1/workspace') return { ok: true, status: 200, json: async () => ({ data: {
      actor: { tenant_id: 'fictional', actor_id: 'analyst', roles: ['ANALYST'] }, presets: [preset] } }) };
    if (url === '/api/v1/changes') return { ok: true, status: 200, json: async () => ({ data: [current.snapshot] }) };
    if (url === '/api/v1/changes/synthetic-change') {
      reads++;
      if (reads > 1 && rejection?.status === 409) {
        if (refreshStatus !== 200) return error(refreshStatus, { 401: 'UNAUTHENTICATED', 403: 'FORBIDDEN', 404: 'NOT_FOUND' }[refreshStatus]);
        current = state(rejection.code === 'EVALUATION_INCOMPLETE' ? 'INCOMPLETE' : 'BLOCK', 3);
      }
      return { ok: true, status: 200, json: async () => ({ data: current }) };
    }
    if (extraGet) return extraGet(url, options);
    throw new Error('Unexpected URL ' + url);
  };
  vm.runInNewContext(javascriptOverride ?? javascript, { document, fetch, crypto: webcrypto });
  get('token').value = 'synthetic-fixture-only';
  await get('login-form').onsubmit({ preventDefault() {}, submitter: new Element('button') });
  await connected().find(e => e.dataset.changeId === 'synthetic-change').onclick();
  return { get, connected, calls, get reads() { return reads; }, get current() { return current; } };
}

async function readiness(kind) {
  const ui = await app({ initial: kind });
  const submit = ui.get('submit-change');
  assert.ok(submit, 'normal submission remains a visible action');
  assert.equal(submit.disabled, kind !== 'PASS', kind + ': normal submit readiness must match the latest run');
  const help = ui.get('submit-help');
  assert.ok(help && help.textContent.trim(), kind + ': explain submission readiness beside the action');
  if (kind === 'NO_RUN') assert.match(help.textContent, /평가/);
  if (kind === 'BLOCK') assert.match(help.textContent, /BLOCK|통과|실패|차단/);
  if (kind === 'INCOMPLETE') assert.match(help.textContent, /INCOMPLETE|완료|미완료|원인/);
  if (kind === 'PASS') assert.match(help.textContent, /서버|조건|PASS/);
  assert.equal(ui.calls.filter(call => call.method === 'POST').length, 0, 'rendering readiness must not mutate the server');
}

async function safeRejection(code) {
  const ui = await app({ rejection: { status: 409, code } });
  ui.get('case-0').value = '29';
  await ui.get('submit-change').onclick();
  await settle();
  assert.equal(ui.reads, 2, code + ': fetch authoritative current state after a known actionable conflict');
  assert.ok(ui.get('detail').textContent.includes('Revision 3'), code + ': show the fresh server revision');
  assert.ok(ui.get('detail').textContent.includes('run-3'), code + ': show the fresh latest evaluation');
  assert.equal(ui.get('case-0')?.value, '29', code + ': retain typed case correction on the same authorized suite');
  assert.equal(ui.connected().find(e => e.dataset.changeId === 'synthetic-change').getAttribute('aria-current'), 'true');
  assert.ok(ui.connected().find(e => e.dataset.changeId === 'synthetic-change').closest('tr').textContent.includes('Revision 3'), code + ': selected queue row must show the fresh revision already displayed in detail');
  assert.equal(ui.get('load-evidence').disabled, false, 'fresh authorized detail remains inspectable');
  assert.equal(ui.get('recovery').hidden, true, 'known conflict is not an uncertain committed request');
  assert.ok(ui.get('message').textContent.includes(code), code + ': keep the known rejection explanation after refresh');
  assert.ok(ui.get('message').textContent.includes('synthetic-request'), 'keep the request ID for the rejected operation');
  assert.equal(ui.calls.filter(call => call.method === 'POST').length, 1, 'never automatically resubmit a known conflict');
}

async function unauthorizedPost(status) {
  const code = { 401: 'UNAUTHENTICATED', 403: 'FORBIDDEN', 404: 'NOT_FOUND' }[status];
  const ui = await app({ rejection: { status, code } });
  await ui.get('submit-change').onclick(); await settle();
  assert.equal(ui.get('case-0'), null, 'known unauthorized/not-found response clears correction data');
  assert.equal(ui.get('load-evidence').disabled, true);
  assert.ok(!ui.get('detail').textContent.includes('Synthetic PASS'));
  assert.equal(ui.reads, 1, 'do not recover rejected permission with old snapshots');
  assert.match(ui.get('message').textContent, new RegExp(code));
}

async function unauthorizedRefresh(status) {
  const ui = await app({ rejection: { status: 409, code: 'STALE_REVISION' }, refreshStatus: status });
  ui.get('case-0').value = '29';
  await ui.get('submit-change').onclick(); await settle();
  assert.equal(ui.reads, 2, 'the authoritative GET was actually attempted');
  assert.equal(ui.get('case-0'), null, 'do not restore stale typed inputs after a failed authorized read');
  assert.equal(ui.get('load-evidence').disabled, true);
  assert.ok(!ui.get('detail').textContent.includes('Synthetic PASS'));
  assert.match(ui.get('message').textContent, new RegExp(String(status)), 'retain the latest read error');
}

async function uncertainEvaluation() {
  const ui = await app({ initial: 'NO_RUN', uncertainEvaluation: true });
  assert.equal(ui.get('submit-change').disabled, true, 'evaluation readiness remains independent from recovery');
  ui.get('case-form').onsubmit({ preventDefault() {} }); await settle();
  assert.equal(ui.get('recovery').hidden, false);
  assert.equal(ui.get('retry-request').disabled, false, 'an uncertain evaluation can be recovered without a passing run');
  assert.ok(ui.get('pending-key').textContent);
  const original = ui.calls.find(call => call.method === 'POST');
  await ui.get('retry-request').onclick(); await settle();
  const posts = ui.calls.filter(call => call.method === 'POST');
  assert.equal(posts.length, 2);
  assert.deepEqual(posts[1], original, 'recovery resends the exact path, serialized body, key, actor and revision');
  assert.equal(ui.get('recovery').hidden, true);
  assert.equal(ui.get('submit-change').disabled, false, 'normal readiness follows the recovered passing evaluation');
}

module.exports = { app, Element, settle };
if (require.main === module) (async () => {
  const checks = [
    ...['NO_RUN', 'BLOCK', 'INCOMPLETE', 'PASS'].map(kind => [kind + ' readiness', () => readiness(kind)]),
    ...['RELEASE_GATE_BLOCKED', 'EVALUATION_INCOMPLETE', 'SOURCE_NOT_ELIGIBLE', 'STALE_REVISION'].map(code => [code + ' refresh', () => safeRejection(code)]),
    ...[401, 403, 404].map(status => [status + ' mutation rejection', () => unauthorizedPost(status)]),
    ...[401, 403, 404].map(status => [status + ' recovery GET rejection', () => unauthorizedRefresh(status)]),
    ['uncertain evaluation exact replay', uncertainEvaluation],
  ];
  let failed = 0;
  for (const [name, check] of checks) {
    try { await check(); console.log('PASS ' + name); }
    catch (error) { failed++; console.error('FAIL ' + name + ': ' + error.message); }
  }
  if (failed) { console.error(`Submit flow: ${checks.length - failed} passed, ${failed} failed`); process.exitCode = 1; }
  else console.log(`PASS: submit flow (${checks.length} scenarios), known conflicts and original uncertain replay remain distinct`);
})().catch(error => { console.error(error); process.exitCode = 1; });
