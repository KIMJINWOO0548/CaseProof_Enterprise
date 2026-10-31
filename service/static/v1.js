/* Plain DOM rendering: all server-controlled strings are text nodes. */
(function () {
  'use strict';
  class RequestClient {
    constructor(fetcher = (...args) => fetch(...args)) { this.fetcher = fetcher; this.requests = new Map(); this.busy = false; }
    connect(token, actor) { this.token = token; this.actor = actor; this.scope = actor ? JSON.stringify([actor.tenant_id, actor.actor_id]) : null; }
    pending() { return this.requests.get(this.scope); }
    async get(path, token = this.token) {
      const response = await this.fetcher(path, { headers: { Authorization: 'Bearer ' + token }, cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) throw new Error(this.error(response.status, payload));
      return payload.data;
    }
    error(status, payload) { const e = payload?.error; return `${status} ${e?.code || 'INVALID_RESPONSE'}: ${e?.message || '요청 실패'}${e?.request_id ? ' · 요청 ' + e.request_id : ''}`; }
    async mutate(path, body, revision) {
      if (this.busy) throw new Error('다른 요청이 진행 중입니다.');
      if (this.pending()) throw new Error('결과가 미확정인 원래 요청을 먼저 복구하세요.');
      if (!this.scope) throw new Error('로그인이 필요합니다.');
      this.requests.set(this.scope, { path, body: JSON.stringify(body), revision, key: globalThis.crypto.randomUUID() });
      return this.retry();
    }
    async retry() {
      if (this.busy) throw new Error('다른 요청이 진행 중입니다.');
      const scope = this.scope, request = this.pending(), token = this.token;
      if (!request) throw new Error('복구할 요청이 없습니다.');
      const wasUncertain = request.uncertain === true;
      const headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', 'Idempotency-Key': request.key };
      if (request.revision !== null) headers['X-Expected-Revision'] = String(request.revision);
      this.busy = true;
      try {
        const response = await this.fetcher(request.path, { method: 'POST', headers, body: request.body });
        let payload;
        try { payload = await response.json(); } catch (_) { throw new Error('처리 결과를 확인하지 못했습니다. 원래 요청을 복구하세요.'); }
        if (!response.ok) {
          // A server failure can follow a commit. Retain the exact request until known.
          if (response.status < 500 && !wasUncertain) this.requests.delete(scope);
          throw new Error(this.error(response.status, payload));
        }
        if (!payload || !payload.data) throw new Error('처리 결과를 확인하지 못했습니다. 원래 요청을 복구하세요.');
        this.requests.delete(scope);
        return payload;
      } catch (error) {
        if (this.requests.has(scope)) { request.uncertain = true; throw new Error('처리 결과 미확정 · ' + error.message); }
        throw error;
      } finally { this.busy = false; }
    }
  }
  if (typeof module !== 'undefined') module.exports = { RequestClient };
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id), client = new RequestClient();
  let epoch = 0, selection = 0, workspace, rows = [], current, parent, decision, opener;
  function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; }
  function message(error = '') { $('message').textContent = error.message || error; }
  function role(name) { return workspace?.actor.roles.includes(name); }
  function lock() {
    const blocked = client.busy || !!client.pending();
    document.querySelectorAll('[data-mutation]').forEach(el => { el.disabled = blocked; });
    $('recovery').hidden = !client.pending();
    $('pending-key').textContent = client.pending()?.key || '';
    $('retry-request').disabled = client.busy;
    $('switch-role').disabled = client.busy;
    $('new-change').hidden = !role('ANALYST');
  }
  function syncSelectedRow() {
    document.querySelectorAll('[data-change-id]').forEach(button => {
      const selected = button.dataset.changeId === current?.change_id;
      button.setAttribute('aria-current', String(selected));
      button.closest('tr')?.classList.toggle('is-selected', selected);
    });
  }
  function clearDetail(text = '변경을 선택하세요.') { current = null; syncSelectedRow(); $('detail').replaceChildren(node('p', text)); $('evidence').textContent = '선택 후 별도로 조회하세요.'; $('load-evidence').disabled = true; }
  function refs(data, container) {
    const list = node('dl');
    for (const [label, key] of [['팩', 'pack_version_id'], ['요청자', 'requester_id'], ['현업 검토자', 'domain_reviewer_id'], ['최종 승인자', 'release_approver_id']]) {
      list.append(node('dt', label), node('dd', data[key] || '—'));
    }
    if (data.parent_change_id) { const link = node('button', data.parent_change_id, 'btn btn-link p-0'); link.type = 'button'; link.onclick = () => select(data.parent_change_id); const dd = node('dd'); dd.append(link, node('div', data.parent_relation)); list.append(node('dt', '원본 변경'), dd); }
    const versions = node('details'), versionList = node('dl');
    for (const [label, key] of [['후보', 'candidate_snapshot_id'], ['출처 묶음', 'source_bundle_id'], ['평가 모음', 'suite_version_id']]) {
      versionList.append(node('dt', label), node('dd', data[key] || '—'));
    }
    versions.append(node('summary', '고정된 버전 참조'), versionList);
    container.append(list, versions);
  }
  function button(id, label, action, container, mutation = true) { const b = node('button', label, 'btn'); b.id = id; b.type = 'button'; if (mutation) b.dataset.mutation = ''; b.onclick = action; container.append(b); return b; }
  function presetFor(data) { return workspace.presets.find(p => p.create_body.suite_version_id === data.suite_version_id && p.create_body.pack_version_id === data.pack_version_id); }
  function render(data, run) {
    current = data; syncSelectedRow(); $('detail').replaceChildren(); $('evidence').textContent = '선택 후 별도로 조회하세요.'; $('load-evidence').disabled = false;
    const target = $('detail'); target.append(node('h3', data.title, 'h3')); const id = node('p', data.change_id); id.id = 'change-id'; target.append(id);
    const state = node('strong', data.status); state.id = 'change-status';
    const meta = node('div', undefined, 'change-meta'); meta.append(state, node('p', 'Revision ' + data.revision)); target.append(meta);
    const actions = node('div', undefined, 'btn-list'); target.append(actions);
    refs(data, target);
    const own = workspace.actor.actor_id === data.requester_id;
    if (role('ANALYST') && data.status === 'REJECTED') button('correct-change', '반려 변경 시정', () => openCreate(data), actions);
    if (role('ANALYST') && own && data.status === 'DRAFT') {
      const preset = presetFor(data);
      if (preset) {
        const form = node('form'); form.id = 'case-form'; form.append(node('h3', '전체 사례 평가', 'h3'), node('p', '공개 합성 주장 일수를 수정해 전체 모음을 다시 평가합니다. 실제 답변 내용 변경은 새 후보 snapshot이 필요합니다.'));
        preset.case_inputs.forEach((item, index) => { const row = node('div', undefined, 'case-row'), label = node('label', item.case_id), input = node('input'); label.htmlFor = 'case-' + index; input.id = label.htmlFor; input.type = 'number'; input.min = '0'; input.max = '9999'; input.step = '1'; input.required = true; input.value = item.claim_days; input.dataset.caseInput = item.case_id; input.className = 'form-control'; row.append(label, input); form.append(row); });
        const evaluate = button('evaluate', '전체 모음 평가', () => {}, form); evaluate.type = 'submit';
        form.onsubmit = event => { event.preventDefault(); const case_inputs = preset.case_inputs.map((item, i) => ({ ...item, claim_days: Number($('case-' + i).value) })); mutate('/api/v1/changes/' + data.change_id + '/evaluation-runs', { suite_version_id: data.suite_version_id, case_inputs }, data.revision); };
        target.append(form);
      } else target.append(node('p', '등록된 평가 입력을 찾지 못했습니다. 서버 팩 설정을 확인하세요.'));
      button('submit-change', '현업 검토 제출', () => mutate('/api/v1/changes/' + data.change_id + '/submit', {}, data.revision), actions);
    }
    const actor = workspace.actor.actor_id;
    const stage = data.status === 'PENDING_DOMAIN_REVIEW' && role('DOMAIN_REVIEWER') ? 'domain-decision' : data.status === 'PENDING_RELEASE' && role('RELEASE_APPROVER') && actor !== data.domain_reviewer_id ? 'release-decision' : null;
    if (stage && actor !== data.requester_id && actor !== data.owner_id) for (const [value, label] of [['APPROVE', '승인'], ['REJECT', '반려']]) { const b = button('decision-' + value, label, () => { decision = { path: '/api/v1/changes/' + data.change_id + '/' + stage, value, revision: data.revision }; $('decision-title').textContent = label + ' 기록'; $('reason').value = ''; showDialog('decision-dialog'); }, actions); b.dataset.decision = value; }
    const result = node('div'); result.id = 'run-result';
    if (run) { result.append(node('h3', '최신 평가 결과', 'h3'), node('p', `${run.completion} · ${run.gate_summary} · ${run.id}`)); const table = node('table', undefined, 'table'); const header = node('thead'), tr = node('tr'); ['사례', '판정', '해석 상태'].forEach(v => tr.append(node('th', v))); header.append(tr); table.append(header); const body = node('tbody'); (run.case_results || []).forEach(c => { const row = node('tr'); [c.case_id, c.verdict, c.resolution_status].forEach(v => row.append(node('td', v))); body.append(row); }); table.append(body); result.append(table); const disclosure = node('details'); disclosure.append(node('summary', '출처·결과 해시 참조'), node('pre', JSON.stringify({ run_id: run.id, case_results: run.case_results }, null, 2))); result.append(disclosure); }
    else result.append(node('p', '평가 결과가 없습니다.'));
    target.append(result); lock();
  }
  function renderQueue() {
    const q = $('search').value.toLowerCase(), state = $('status-filter').value;
    const filtered = rows.filter(r => (!state || r.status === state) && (r.title + r.change_id).toLowerCase().includes(q));
    $('queue').replaceChildren(); if (!filtered.length) { $('queue').append(node('p', '표시할 변경 요청이 없습니다.', 'p-3')); return; }
    const table = node('table', undefined, 'table table-vcenter'), head = node('thead'), hr = node('tr'); hr.append(node('th', '변경 요청')); head.append(hr); table.append(head); const body = node('tbody');
    filtered.forEach(row => {
      const tr = node('tr'), td = node('td'), b = node('button', row.title, 'btn btn-link p-0 text-start');
      b.type = 'button'; b.dataset.changeId = row.change_id; b.onclick = () => select(row.change_id);
      const meta = node('div', undefined, 'queue-meta'); meta.append(node('span', row.pack_version_id), node('span', 'Revision ' + row.revision));
      td.append(b, node('div', row.status, 'queue-status'), meta); tr.append(td); body.append(tr);
    }); table.append(body); $('queue').append(table); syncSelectedRow();
  }
  async function refresh() {
    const e = epoch; $('queue').setAttribute('aria-busy', 'true'); $('queue').textContent = '불러오는 중…';
    try { const data = await client.get('/api/v1/changes'); if (e !== epoch) return; rows = data; renderQueue(); } catch (error) { if (e === epoch) { rows = []; $('queue').textContent = '목록을 불러오지 못했습니다. 새로고침하세요.'; clearDetail('목록 조회 실패'); message(error); } } finally { if (e === epoch) $('queue').setAttribute('aria-busy', 'false'); }
  }
  async function select(id) {
    const e = epoch, s = ++selection; clearDetail('불러오는 중…'); $('detail').setAttribute('aria-busy', 'true'); message();
    try { const data = await client.get('/api/v1/changes/' + id); if (e !== epoch || s !== selection) return; if (data.historical_integrity === 'INVALID') { clearDetail('기록 무결성이 유효하지 않습니다.'); return; } render(data.snapshot || data, data.latest_run || data.run); }
    catch (error) { if (e === epoch && s === selection) { clearDetail('변경을 불러오지 못했습니다.'); message(error); } } finally { if (e === epoch && s === selection) $('detail').setAttribute('aria-busy', 'false'); }
  }
  async function mutate(path, body, revision, retry = false) {
    const e = epoch; ++selection; message(); const promise = retry ? client.retry() : client.mutate(path, body, revision); lock();
    try { const result = await promise; if (e !== epoch) return; document.querySelectorAll('dialog[open]').forEach(d => d.close()); const data = result.data; message(result.replayed ? '원래 요청의 확정 결과를 복구했습니다.' : '기록했습니다.'); await refresh(); if (e === epoch) await select(data.change_id); }
    catch (error) { if (e === epoch) { document.querySelectorAll('dialog[open]').forEach(d => d.close()); clearDetail('요청 실패 또는 결과 미확정입니다. 최신 변경을 다시 선택하세요.'); message(error); } } finally { if (e === epoch) lock(); }
  }
  function showDialog(id) { opener = document.activeElement; $(id).showModal(); }
  function openCreate(source) {
    parent = source || null; $('preset').replaceChildren(); workspace.presets.forEach((p, i) => { const option = node('option', p.label); option.value = i; $('preset').append(option); });
    const index = source ? workspace.presets.indexOf(presetFor(source)) : 0; $('preset').value = Math.max(index, 0); $('preset').disabled = !!source; $('title').value = source ? source.title + ' · 시정' : workspace.presets[0]?.create_body.title || ''; $('parent-description').textContent = source ? '원본 ' + source.change_id + ' · CORRECTS_REJECTED' : ''; showDialog('create-dialog'); lock();
  }
  $('login-form').onsubmit = async event => {
    event.preventDefault(); const token = $('token').value; $('token').value = ''; const e = ++epoch; ++selection; message(); const submit = event.submitter; submit.disabled = true;
    try { const data = await client.get('/api/v1/workspace', token); if (e !== epoch) return; workspace = data; client.connect(token, data.actor); rows = []; clearDetail(); $('actor').textContent = `${data.actor.tenant_id} / ${data.actor.actor_id} · ${data.actor.roles.join(', ')}`; $('workspace').hidden = false; $('login').hidden = true; lock(); await refresh(); $('main').focus(); } catch (error) { if (e === epoch) message(error); } finally { submit.disabled = false; }
  };
  $('switch-role').onclick = () => { ++epoch; ++selection; client.connect(null, null); workspace = null; rows = []; clearDetail(); document.querySelectorAll('dialog[open]').forEach(d => d.close()); $('workspace').hidden = true; $('login').hidden = false; message(); $('token').focus(); };
  $('refresh').onclick = () => { message(); ++selection; clearDetail(); refresh(); };
  $('new-change').onclick = () => openCreate(); $('search').oninput = renderQueue; $('status-filter').onchange = renderQueue;
  $('preset').onchange = () => { $('title').value = workspace.presets[Number($('preset').value)].create_body.title; };
  $('create-form').onsubmit = event => { event.preventDefault(); const body = { ...workspace.presets[Number($('preset').value)].create_body, title: $('title').value }; if (parent) Object.assign(body, { parent_change_id: parent.change_id, parent_relation: 'CORRECTS_REJECTED' }); mutate('/api/v1/changes', body, null); };
  $('decision-form').onsubmit = event => { event.preventDefault(); const reason = $('reason').value; if ([...reason.trim()].length < 8 || [...reason].length > 500) { message('사유는 공백을 제외한 8–500자로 입력하세요.'); return; } mutate(decision.path, { decision: decision.value, reason }, decision.revision); };
  $('retry-request').onclick = () => mutate(null, null, null, true);
  $('load-evidence').onclick = async () => { if (!current) return; const id = current.change_id, e = epoch, s = selection; $('evidence').textContent = '확인 중…'; try { const data = await client.get('/api/v1/changes/' + id + '/evidence'); if (e !== epoch || s !== selection) return; const list = node('dl'); for (const [label, key] of [['역사적 무결성', 'historical_integrity'], ['현재 승인 적격성', 'current_approval_eligibility'], ['외부 앵커', 'external_anchor'], ['승인 revision', 'approved_revision'], ['Envelope SHA-256', 'envelope_sha256']]) list.append(node('dt', label), node('dd', data[key] ?? '—')); const details = node('details'); details.append(node('summary', '원본 JSON'), node('pre', JSON.stringify(data, null, 2))); $('evidence').replaceChildren(list, details); } catch (error) { if (e === epoch && s === selection) { $('evidence').textContent = '증거 조회 실패'; message(error); } } };
  document.querySelectorAll('[data-close]').forEach(b => { b.onclick = () => b.closest('dialog').close(); });
  document.querySelectorAll('dialog').forEach(d => d.addEventListener('close', () => { if (opener?.isConnected) opener.focus(); }));
}());
