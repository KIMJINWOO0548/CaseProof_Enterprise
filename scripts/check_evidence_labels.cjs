/* Execute the real evidence click handler with synthetic responses; not a browser test. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {};
    this.attributes = {}; this.value = ''; this._text = ''; this.classList = { toggle() {} };
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  append(...children) { children.forEach(child => { child.parent = this; this.children.push(child); }); }
  replaceChildren(...children) { this._text = ''; this.children = []; this.append(...children); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  removeAttribute(key) { delete this.attributes[key]; }
  closest(tag) { return this.tagName === tag.toUpperCase() ? this : this.parent?.closest(tag); }
  focus() {}
  addEventListener() {}
}

async function main() {
  const ids = new Map(), created = [];
  const get = id => { if (!ids.has(id)) ids.set(id, new Element()); return ids.get(id); };
  const document = {
    getElementById: get,
    createElement: tag => { const element = new Element(tag); created.push(element); return element; },
    querySelectorAll: selector => selector === '[data-change-id]' ? created.filter(e => e.dataset.changeId) : [],
  };
  const snapshot = { change_id: 'synthetic-change', title: 'Synthetic blocked evaluation', revision: 2,
    status: 'DRAFT', requester_id: 'analyst', owner_id: 'analyst', pack_version_id: 'synthetic',
    candidate_snapshot_id: 'candidate', source_bundle_id: 'bundle', suite_version_id: 'suite' };
  const evidence = { historical_integrity: 'VALID', current_approval_eligibility: 'ELIGIBLE',
    external_anchor: 'NOT_CONFIGURED', approved_revision: null, envelope_sha256: null };
  const fetch = async url => {
    const responses = {
      '/api/v1/workspace': { actor: { tenant_id: 'fictional', actor_id: 'analyst', roles: ['ANALYST'] }, presets: [] },
      '/api/v1/changes': [snapshot],
      '/api/v1/changes/synthetic-change': { historical_integrity: 'VALID', snapshot,
        latest_run: { id: 'failed-run', completion: 'COMPLETE', gate_summary: 'BLOCK', case_results: [] } },
      '/api/v1/changes/synthetic-change/evidence': evidence,
    };
    assert.ok(Object.hasOwn(responses, url), 'unexpected request ' + url);
    return { ok: true, status: 200, json: async () => ({ data: responses[url] }) };
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../service/static/v1.js'), 'utf8'), { document, fetch });
  get('token').value = 'synthetic-test-token';
  await get('login-form').onsubmit({ preventDefault() {}, submitter: new Element('button') });
  await created.find(e => e.dataset.changeId === snapshot.change_id).onclick();
  assert.ok(get('detail').textContent.includes('BLOCK'), 'latest blocked run stays visible');
  await get('load-evidence').onclick();
  const rows = get('evidence').children[0].children;
  const sourceLabel = rows.findIndex(e => e.tagName === 'DT' && e.textContent === '현재 출처 적격성');
  assert.ok(sourceLabel >= 0, 'source-only ELIGIBLE must be labeled as current source eligibility');
  assert.equal(rows[sourceLabel + 1].textContent, 'ELIGIBLE', 'preserve the existing API source verdict');
  assert.equal(rows.some(e => e.tagName === 'DT' && e.textContent === '현재 승인 적격성'), false);
  assert.deepEqual(JSON.parse(get('evidence').children[1].children[1].textContent), evidence, 'raw evidence stays unchanged');
  const html = fs.readFileSync(path.join(__dirname, '../service/static/v1.html'), 'utf8');
  assert.ok(html.includes('출처 적격성이 ELIGIBLE이어도 평가 통과·검토 단계·역할 분리 조건을 충족해야 승인할 수 있습니다.'));
  console.log('PASS: source eligibility stays distinct from a blocked evaluation and approval authorization');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
