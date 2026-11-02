/* Real workspace handlers under the existing DOM harness; no browser claim. */
const assert = require('node:assert/strict');
const { app, settle } = require('./check_submit_flow.cjs');
const response = data => ({ ok: true, status: 200, json: async () => ({ data }) });
const summary = (id, gate = 'PASS') => ({ id, recorded_revision: id === 'older' ? 2 : 3,
  completion: gate === 'BLOCK' ? 'INCOMPLETE' : 'COMPLETE', gate_summary: gate });
const history = { schema: 'evaluation_run_history_v1', total_runs: 2, limit: 100,
  truncated: false, runs: [summary('latest', 'BLOCK'), summary('older')] };
const comparison = { schema: 'evaluation_comparison_v1', baseline: summary('older'),
  candidate: summary('latest', 'BLOCK'), mode: 'INCOMPLETE', context_reasons: ['INPUT_CHANGED'],
  changed_counts: { any_changed: 1, input_changed: 1, output_changed: 1, source_refs_changed: 0,
    result_state_changed: 1, presence_changed: 0 }, rows: [{ case_id: '<img src=x onerror=bad()>',
    baseline: { verdict: 'PASS', complete: true, resolution_status: 'RESOLVED', error_code: null,
      critical_failure: false, input_sha256: 'a', output_sha256: 'b', source_refs: [] },
    candidate: { verdict: 'INCONCLUSIVE', complete: false, resolution_status: 'INCONCLUSIVE',
      error_code: 'ADAPTER_TIMEOUT', critical_failure: null, input_sha256: 'c', output_sha256: 'd', source_refs: [] },
    changes: { input_changed: true, result_state_changed: true, output_changed: true,
      source_refs_changed: false, presence_changed: false } }] };
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

async function lazyAndReadOnly() {
  const ui = await app({ initial: 'INCOMPLETE', extraGet: url => response(url.includes('/compare?') ? comparison : history) });
  assert.equal(ui.calls.filter(c => c.url.endsWith('/evaluation-runs')).length, 0, 'history loads only on request');
  assert.ok(ui.get('load-run-history'), 'offer saved-run history beside latest result');
  ui.get('case-0').value = '29';
  await ui.get('load-run-history').onclick();
  assert.match(ui.get('run-history').textContent, /100/);
  assert.equal(ui.get('baseline-run').children.length, 2);
  assert.match(ui.get('baseline-run').children[0].textContent, /^revision 3 · INCOMPLETE\/BLOCK · latest$/,
    'revision and status must remain visible before long run IDs on narrow screens');
  ui.get('baseline-run').value = 'older'; ui.get('candidate-run').value = 'latest';
  await ui.get('compare-runs').onclick();
  assert.match(ui.get('run-comparison').textContent, /INCOMPLETE/);
  assert.match(ui.get('run-comparison').textContent, /INPUT_CHANGED/);
  assert.match(ui.get('run-comparison').textContent, /ADAPTER_TIMEOUT/);
  assert.match(ui.get('run-comparison').textContent, /<img src=x onerror=bad\(\)>/);
  assert.equal(ui.connected().some(e => e.tagName === 'IMG'), false, 'untrusted identifiers remain text');
  assert.equal(ui.get('submit-change').disabled, true, 'an older PASS never changes latest readiness');
  assert.equal(ui.get('case-0').value, '29', 'history never erases correction input');
  assert.equal(ui.get('recovery').hidden, true);
  assert.equal(ui.calls.filter(c => c.method === 'POST').length, 0);
  assert.ok(ui.calls.some(c => c.url.endsWith('/compare?baseline_run_id=older&candidate_run_id=latest')));
}

async function smallHistory(count) {
  const ui = await app({ extraGet: () => response({ ...history, total_runs: count, runs: history.runs.slice(0, count) }) });
  assert.ok(ui.get('load-run-history'));
  await ui.get('load-run-history').onclick();
  assert.match(ui.get('run-history').textContent, /2.*평가|평가.*2/);
  assert.equal(ui.get('compare-runs'), null);
}

async function historyError() {
  const ui = await app({ extraGet: () => ({ ok: false, status: 409, json: async () => ({ error: { code: 'EVIDENCE_RECORD_TAMPERED', message: 'Rejected' } }) }) });
  await ui.get('load-run-history').onclick();
  assert.match(ui.get('run-history').textContent, /실패/);
  assert.equal(ui.get('load-run-history').disabled, false, 'failed read can retry');
  assert.match(ui.get('message').textContent, /EVIDENCE_RECORD_TAMPERED/);
  assert.equal(ui.get('submit-change').disabled, false, 'read errors do not rewrite latest run');
}

async function staleHistory(switchRole) {
  const late = deferred();
  const ui = await app({ extraGet: () => late.promise });
  const pending = ui.get('load-run-history').onclick();
  assert.match(ui.get('run-history').textContent, /불러오는|조회/);
  if (switchRole) ui.get('switch-role').onclick(); else await ui.connected().find(e => e.dataset.changeId).onclick();
  late.resolve(response(history)); await pending; await settle();
  assert.equal(ui.get('baseline-run'), null, 'ignore history from a prior role/selection');
}

async function staleComparison() {
  const late = deferred();
  const ui = await app({ extraGet: url => url.includes('/compare?') ? late.promise : response(history) });
  await ui.get('load-run-history').onclick();
  const pending = ui.get('compare-runs').onclick();
  ui.get('baseline-run').value = 'latest'; ui.get('baseline-run').onchange();
  late.resolve(response(comparison)); await pending;
  assert.doesNotMatch(ui.get('run-comparison').textContent, /ADAPTER_TIMEOUT|INPUT_CHANGED/,
    'changing selected run invalidates a delayed comparison');
}

async function staleComparisonScope(switchRole) {
  const late = deferred();
  const ui = await app({ extraGet: url => url.includes('/compare?') ? late.promise : response(history) });
  await ui.get('load-run-history').onclick();
  const pending = ui.get('compare-runs').onclick();
  if (switchRole) ui.get('switch-role').onclick(); else await ui.connected().find(e => e.dataset.changeId).onclick();
  late.resolve(response(comparison)); await pending; await settle();
  assert.equal(ui.get('run-comparison'), null, 'ignore comparison from a prior role/selection');
  assert.doesNotMatch(ui.get('message').textContent, /INPUT_CHANGED|ADAPTER_TIMEOUT/);
}

async function comparisonErrorRetry() {
  let comparisons = 0;
  const ui = await app({ initial: 'INCOMPLETE', extraGet: url => {
    if (!url.includes('/compare?')) return response(history);
    if (++comparisons === 1) return { ok: false, status: 422, json: async () => ({ error: { code: 'COMPARISON_LIMIT_EXCEEDED', message: 'Rejected' } }) };
    return response(comparison);
  } });
  await ui.get('load-run-history').onclick();
  await ui.get('compare-runs').onclick();
  assert.match(ui.get('run-comparison').textContent, /실패/);
  assert.match(ui.get('message').textContent, /COMPARISON_LIMIT_EXCEEDED/);
  assert.equal(ui.get('compare-runs').disabled, false);
  await ui.get('compare-runs').onclick();
  assert.match(ui.get('run-comparison').textContent, /ADAPTER_TIMEOUT/);
  assert.equal(ui.get('submit-change').disabled, true);
  assert.equal(ui.calls.filter(c => c.method === 'POST').length, 0);
}

(async () => {
  const checks = [['lazy read-only comparison and latest veto', lazyAndReadOnly],
    ['zero runs', () => smallHistory(0)], ['one run', () => smallHistory(1)],
    ['history error', historyError], ['history after role change', () => staleHistory(true)],
    ['history after selection change', () => staleHistory(false)], ['comparison after selector change', staleComparison],
    ['comparison after role change', () => staleComparisonScope(true)],
    ['comparison after change selection', () => staleComparisonScope(false)], ['comparison error and retry', comparisonErrorRetry]];
  let failures = 0;
  for (const [name, check] of checks) {
    try { await check(); console.log('PASS ' + name); }
    catch (error) { failures++; console.error('FAIL ' + name + ': ' + error.message); }
  }
  console.log(`Run comparison: ${checks.length - failures} passed, ${failures} failed`);
  if (failures) process.exitCode = 1;
})();
