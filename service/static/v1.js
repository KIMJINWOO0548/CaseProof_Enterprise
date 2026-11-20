/* Plain DOM rendering: all server-controlled strings are text nodes. */
(function () {
  'use strict';
  const intentPrefix = 'caseproof.v1.pending:';
  const v4 = '[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}';
  const changeIdPattern = new RegExp('^' + v4 + '$');
  const changeCommand = new RegExp('^/api/v1/changes/(' + v4 + ')/(evaluation-runs|submit|domain-decision|release-decision)$');
  const contextPattern = /^[0-9a-f]{64}$/;

  class RequestClient {
    constructor(fetcher = (...args) => fetch(...args), storage, exclusive = (_, action) => action()) {
      this.fetcher = fetcher;
      this.storage = storage;
      this.exclusive = exclusive;
      this.requests = new Map();
      this.busy = false;
    }
    connect(token, actor, context) {
      this.token = token;
      this.scope = actor ? intentPrefix + JSON.stringify([actor.tenant_id, actor.actor_id]) : null;
      this.context = contextPattern.test(context) ? context : null;
    }
    readIntent(scope) {
      if (!scope) return;
      if (!this.storage) return this.requests.get(scope);
      try {
        const saved = this.storage().getItem(scope);
        if (saved === null) return;
        const intent = JSON.parse(saved);
        const create = intent.path === '/api/v1/changes';
        const body = JSON.parse(intent.body);
        if (intent.version !== 1 || !contextPattern.test(intent.context) || typeof intent.body !== 'string' ||
            !body || typeof body !== 'object' || Array.isArray(body) ||
            typeof intent.key !== 'string' || !/^[A-Za-z0-9_-]{12,128}$/.test(intent.key) ||
            !(create ? intent.revision === null : typeof intent.path === 'string' && changeCommand.test(intent.path) &&
              Number.isSafeInteger(intent.revision) && intent.revision > 0)) throw new Error();
        return intent;
      } catch (_) {
        throw new Error('이 브라우저에서 저장된 원래 요청을 읽을 수 없습니다.');
      }
    }
    pending() {
      this.storageError = null;
      try { return this.readIntent(this.scope); }
      catch (error) { this.storageError = error; }
    }
    saveIntent(scope, intent) {
      if (!this.storage) {
        if (intent) this.requests.set(scope, intent);
        else this.requests.delete(scope);
        return;
      }
      try {
        if (intent) this.storage().setItem(scope, JSON.stringify(intent));
        else this.storage().removeItem(scope);
      } catch (_) {
        throw new Error('원래 요청의 브라우저 저장을 변경할 수 없습니다.');
      }
    }
    async get(path, token = this.token) {
      const rows = []; let cursor = null;
      do {
        const response = await this.fetcher(path + (cursor ? '?after=' + encodeURIComponent(cursor) : ''), { headers: { Authorization: 'Bearer ' + token }, cache: 'no-store' });
        const payload = await response.json();
        if (!response.ok) throw this.responseError(response.status, payload);
        if (path !== '/api/v1/changes') return payload.data;
        const invalidPage = () => new Error('목록 이어받기 응답이 유효하지 않습니다. 새로고침하세요.');
        const page = payload?.data, next = payload?.pagination?.next_cursor;
        if (!Array.isArray(page)) throw invalidPage();
        let previous = cursor;
        for (const row of page) {
          const id = row?.change_id;
          if (typeof id !== 'string' || !changeIdPattern.test(id) || (previous && id <= previous)) throw invalidPage();
          previous = id;
        }
        if (next !== null && (!page.length || next !== previous)) throw invalidPage();
        rows.push(...page); cursor = next;
      } while (cursor);
      return rows;
    }
    error(status, payload) { const e = payload?.error; return `${status} ${e?.code || 'INVALID_RESPONSE'}: ${e?.message || '요청 실패'}${e?.request_id ? ' · 요청 ' + e.request_id : ''}`; }
    responseError(status, payload) { return Object.assign(new Error(this.error(status, payload)), { status, code: payload?.error?.code || 'INVALID_RESPONSE' }); }
    async previewCsv(path, file, revision, signal) {
      const headers = { Authorization: 'Bearer ' + this.token, 'Content-Type': 'text/csv', 'X-Expected-Revision': String(revision) };
      if (this.context) headers['X-CaseProof-Request-Context'] = this.context;
      const response = await this.fetcher(path + '/preview-csv', { method: 'POST', headers, body: file, cache: 'no-store', signal, redirect: 'error' });
      const payload = await response.json();
      if (!response.ok) throw this.responseError(response.status, payload);
      const result = payload?.data;
      if (typeof result?.ready !== 'boolean' || result.revision !== revision || !Array.isArray(result.errors) ||
          (result.ready ? !result.evaluation || result.errors.length !== 0 : result.evaluation !== null)) {
        throw new Error('CSV 점검 응답을 확인할 수 없습니다.');
      }
      return result;
    }
    async mutate(path, body, revision) {
      const serialized = JSON.stringify(body);
      return this.withIntent(async (scope, token, context) => {
        if (this.readIntent(scope)) throw new Error('결과가 미확정인 원래 요청을 먼저 복구하세요.');
        const intent = { version: 1, context, path, body: serialized, revision, key: globalThis.crypto.randomUUID() };
        this.saveIntent(scope, intent);
        return this.send(scope, token, intent, true);
      });
    }
    async retry() {
      return this.withIntent(async (scope, token, context) => {
        const intent = this.readIntent(scope);
        if (!intent) throw new Error('복구할 요청이 없습니다.');
        if (intent.context !== context) throw new Error('원래 요청을 보낸 작업공간에서 다시 연결하세요.');
        const response = await this.fetcher('/api/v1/mutations/' + encodeURIComponent(intent.key), {
          headers: { Authorization: 'Bearer ' + token }, cache: 'no-store'
        });
        const payload = await response.json();
        if (response.ok) {
          if (!this.matchesIntent({status: payload.original_status}, payload, intent)) throw new Error('원래 요청의 저장 결과를 확인할 수 없습니다.');
          this.saveIntent(scope, null);
          return payload;
        }
        if (response.status !== 404 || payload?.error?.code !== 'NOT_FOUND') throw this.responseError(response.status, payload);
        return this.send(scope, token, intent, false);
      });
    }
    async withIntent(action) {
      if (this.busy) throw new Error('다른 요청이 진행 중입니다.');
      const { scope, token, context } = this;
      if (!scope) throw new Error('로그인이 필요합니다.');
      if (this.storage && !context) throw new Error('이 작업공간에서 요청 복구를 확인할 수 없습니다.');
      this.busy = true;
      try {
        return await this.exclusive(scope, () => action(scope, token, context));
      } finally { this.busy = false; }
    }
    async send(scope, token, intent, firstAttempt) {
      const headers = { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json', 'Idempotency-Key': intent.key };
      if (intent.revision !== null) headers['X-Expected-Revision'] = String(intent.revision);
      if (intent.context) headers['X-CaseProof-Request-Context'] = intent.context;
      let response, payload;
      try {
        response = await this.fetcher(intent.path, { method: 'POST', headers, body: intent.body, redirect: 'error' });
        payload = await response.json();
      } catch (error) {
        throw new Error('처리 결과 미확정 · 원래 요청을 복구하세요.');
      }
      if (!response.ok) {
        const error = this.responseError(response.status, payload);
        // A later denial says nothing about an earlier interrupted attempt.
        if (firstAttempt && response.status >= 400 && response.status < 500 &&
            typeof payload?.error?.code === 'string' && error.code !== 'REQUEST_CONTEXT_CHANGED') {
          this.saveIntent(scope, null);
          throw error;
        }
        error.message = '처리 결과 미확정 · ' + error.message;
        throw error;
      }
      if (typeof payload?.data?.change_id !== 'string' || (this.storage && !this.matchesIntent(response, payload, intent))) {
        throw new Error('처리 결과 미확정 · 원래 요청을 복구하세요.');
      }
      this.saveIntent(scope, null);
      return payload;
    }
    matchesIntent(response, payload, intent) {
      const change = changeCommand.exec(intent.path);
      const status = !change || change[2] === 'evaluation-runs' ? 201 : 200;
      const revision = (intent.revision ?? 0) + 1;
      return response.status === status && changeIdPattern.test(payload.data.change_id) &&
        (!change || change[1] === payload.data.change_id) && payload.result_revision === revision &&
        payload.data.revision === revision && typeof payload.replayed === 'boolean';
    }
  }
  if (typeof module !== 'undefined') module.exports = { RequestClient };
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  const client = new RequestClient(undefined, () => window.localStorage, (scope, action) =>
    navigator.locks.request(scope, { ifAvailable: true }, lock => {
      if (!lock) throw new Error('다른 탭에서 이 계정의 요청을 처리 중입니다.');
      return action();
    }));
  let epoch = 0, selection = 0, queueRequest = 0, queueReady = false;
  let workspace, rows = [], current, parent, decision, opener;
  const queueStatuses = new Map([
    ['DRAFT', '작성·평가'], ['PENDING_DOMAIN_REVIEW', '현업 검토 대기'],
    ['PENDING_RELEASE', '최종 검토 대기'], ['REJECTED', '반려'], ['APPROVED_FOR_DEMO', '데모 승인'],
  ]);
  const evidenceLabels = new Map([
    ['VALID', '기록 검증됨'], ['INVALID', '기록 검증 실패'], ['LEGACY_UNVERIFIED', '이전 형식 · 검증 안 됨'],
    ['ELIGIBLE', '출처 요건 충족'], ['BLOCKED', '출처 요건 미충족'], ['NOT_APPLICABLE', '확인 대상 아님'],
    ['NOT_CONFIGURED', '외부 연결 미설정'], ['SKIPPED', '확인 생략'],
  ]);
  function node(tag, text, className) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; }
  function message(value = '') {
    const target = $('message'), error = value instanceof Error;
    target.textContent = value.message || value;
    target.dataset.kind = error ? 'error' : 'notice';
    target.setAttribute('role', error ? 'alert' : 'status');
    target.setAttribute('aria-live', error ? 'assertive' : 'polite');
    if (error) target.focus();
  }
  function validReason() { const value = $('reason').value; return [...value.trim()].length >= 8 && [...value].length <= 500; }
  function clearDecisionError() {
    $('decision-error-summary').hidden = true; $('reason-error').hidden = true;
    $('reason').removeAttribute('aria-invalid'); $('reason').removeAttribute('aria-describedby');
  }
  function role(name) { return workspace?.actor.roles.includes(name); }
  function lock() {
    const pending = client.pending();
    const unavailable = client.storageError?.message ||
      (!client.context || !navigator.locks ? '이 브라우저 또는 작업공간에서 요청 복구를 사용할 수 없습니다.' : '');
    const changed = pending && pending.context !== client.context;
    const blocked = client.busy || !!pending || !!unavailable;
    document.querySelectorAll('[data-mutation]').forEach(el => { el.disabled = blocked || el.dataset.unavailable === 'true'; });
    $('recovery').hidden = !pending && !unavailable;
    $('recovery-message').textContent = unavailable || (changed
      ? '복원본이거나 다른 작업공간입니다. 원래 작업공간에 연결하면 이 요청을 확인할 수 있습니다.'
      : '결과를 확인하지 못한 요청입니다. 원래 키와 입력으로 처리 결과를 확인하세요.');
    $('pending-key').textContent = pending?.key || '';
    $('retry-request').disabled = client.busy || !pending || !!changed || !!unavailable;
    $('switch-role').disabled = client.busy;
    $('new-change').hidden = !role('ANALYST');
  }
  function syncSelectedRow() {
    $('return-queue').hidden = !current;
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
  function csvPreview(data, target) {
    const form = node('form'), heading = node('h3', '합성 사례 CSV 점검', 'h3');
    const file = node('input'), label = node('label', 'UTF-8 CSV 파일'), result = node('div');
    form.id = 'case-csv-form'; file.id = 'case-csv'; label.htmlFor = file.id; file.type = 'file';
    file.accept = '.csv,text/csv'; file.required = true; file.className = 'form-control';
    result.id = 'case-csv-result'; result.setAttribute('aria-live', 'polite'); result.tabIndex = -1;
    const example = node('details');
    example.append(node('summary', 'CSV 열과 입력 예시'),
      node('pre', 'case_id,claim_days,case_context\n등록된-사례-ID,3,{}'),
      node('p', '위 사례 ID를 변경에 등록된 사례 ID로 바꾸고 전체 모음을 넣으세요. 사례 문맥과 예상 결과는 기존 평가 규칙을 따릅니다.'));
    form.append(heading, label, file, example);
    const inspect = button('preview-case-csv', 'CSV 점검', () => {}, form, false);
    inspect.type = 'submit';
    const path = '/api/v1/changes/' + data.change_id + '/evaluation-runs';
    let prepared, pending;
    const e = epoch, s = selection;
    const valid = () => e === epoch && s === selection && current === data && form.isConnected;
    const evaluate = button('evaluate-case-csv', '점검한 사례로 평가', () => {
      if (valid() && prepared && !evaluate.disabled && !client.pending()) void mutate(path, prepared, data.revision);
    }, form);
    evaluate.dataset.unavailable = 'true';
    form.append(result);
    target.append(form);

    function clear() {
      pending?.abort(); pending = null; prepared = null;
      result.replaceChildren(); result.removeAttribute('aria-busy'); inspect.disabled = false;
      evaluate.dataset.unavailable = 'true'; lock();
    }
    file.onchange = clear;
    form.onsubmit = async event => {
      event.preventDefault();
      clear();
      const chosen = file.files?.[0];
      if (!chosen || !valid()) return;
      if (chosen.size > 256 * 1024) {
        result.textContent = '256 KiB 이하의 합성 사례 CSV를 선택하세요.'; result.focus(); return;
      }
      const controller = new AbortController(); pending = controller; inspect.disabled = true;
      result.textContent = 'CSV 점검 중…'; result.setAttribute('aria-busy', 'true');
      try {
        const preview = await client.previewCsv(path, chosen, data.revision, controller.signal);
        if (!valid() || pending !== controller) return;
        if (preview.ready && preview.evaluation.suite_version_id === data.suite_version_id &&
            Array.isArray(preview.evaluation.case_inputs)) {
          prepared = preview.evaluation; evaluate.dataset.unavailable = 'false';
          result.textContent = `${prepared.case_inputs.length}개 사례를 점검했습니다. 평가를 별도로 실행하세요.`;
        } else if (preview.ready) {
          throw new Error('현재 평가 모음과 CSV 점검 결과가 일치하지 않습니다.');
        } else {
          const list = node('ul');
          for (const error of preview.errors) list.append(node('li',
            [error.row == null ? '파일' : error.row + '행', error.column, error.code, error.case_id].filter(Boolean).join(' · ')));
          result.replaceChildren(node('p', preview.errors_truncated ? '처음 50개 오류를 표시합니다.' : '오류를 고친 파일을 다시 선택하세요.'), list);
        }
      } catch (error) {
        if (!valid() || pending !== controller) return;
        result.textContent = error.message || 'CSV를 점검할 수 없습니다.';
      } finally {
        if (valid() && pending === controller) {
          pending = null; inspect.disabled = false; result.removeAttribute('aria-busy'); result.focus(); lock();
        }
      }
    };
  }
  function render(data, run) {
    current = data; syncSelectedRow(); $('detail').replaceChildren(); $('evidence').textContent = '선택 후 별도로 조회하세요.'; $('load-evidence').disabled = false;
    const target = $('detail'); target.append(node('h3', data.title, 'detail-heading')); const id = node('p', data.change_id); id.id = 'change-id'; target.append(id);
    const state = node('strong', data.status); state.id = 'change-status'; state.dataset.status = data.status;
    const meta = node('div', undefined, 'change-meta'); meta.append(state, node('p', 'Revision ' + data.revision)); target.append(meta);
    const stages = node('ol', undefined, 'review-stages'); stages.setAttribute('aria-label', '검토 단계 · 현재 상태만 표시');
    for (const [status, label] of [['DRAFT', '작성·평가'], ['PENDING_DOMAIN_REVIEW', '현업 검토'], ['PENDING_RELEASE', '최종 검토'], ['APPROVED_FOR_DEMO', '데모 승인']]) {
      const item = node('li', label); item.dataset.state = status === data.status ? 'current' : 'other';
      if (status === data.status) item.setAttribute('aria-current', 'step');
      stages.append(item);
    }
    target.append(stages);
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
      csvPreview(data, target);
      const ready = run?.completion === 'COMPLETE' && run.gate_summary === 'PASS';
      const submit = button('submit-change', '현업 검토 제출', () => mutate('/api/v1/changes/' + data.change_id + '/submit', {}, data.revision), actions);
      submit.dataset.unavailable = String(!ready); submit.setAttribute('aria-describedby', 'submit-help');
      const guidance = !run ? '전체 사례를 평가한 뒤 PASS 결과를 확인하면 제출할 수 있습니다.'
        : run.completion !== 'COMPLETE' ? '최신 평가가 완료되지 않았습니다. 원인을 확인하고 전체 모음을 다시 평가하세요.'
        : !ready ? '최신 평가가 BLOCK입니다. 사례를 수정하고 전체 모음을 다시 평가하세요.'
        : '최신 평가가 PASS입니다. 서버가 현재 출처·검토 단계·권한 조건을 다시 확인한 뒤 제출합니다.';
      const help = node('p', guidance, 'w-100 mb-0'); help.id = 'submit-help'; actions.append(help);
    }
    const actor = workspace.actor.actor_id;
    const stage = data.status === 'PENDING_DOMAIN_REVIEW' && role('DOMAIN_REVIEWER') ? 'domain-decision' : data.status === 'PENDING_RELEASE' && role('RELEASE_APPROVER') && actor !== data.domain_reviewer_id ? 'release-decision' : null;
    if (stage && actor !== data.requester_id && actor !== data.owner_id) for (const [value, label] of [['APPROVE', '승인'], ['REJECT', '반려']]) { const b = button('decision-' + value, label, () => { decision = { path: '/api/v1/changes/' + data.change_id + '/' + stage, value, revision: data.revision }; $('decision-title').textContent = label + ' 기록'; $('reason').value = ''; showDialog('decision-dialog'); }, actions); b.dataset.decision = value; }
    const result = node('div'); result.id = 'run-result';
    if (run) { result.append(node('h3', '최신 평가 결과', 'h3'), node('p', `${run.completion} · ${run.gate_summary} · ${run.id}`)); const table = node('table', undefined, 'table'); const header = node('thead'), tr = node('tr'); ['사례', '판정', '해석 상태'].forEach(v => tr.append(node('th', v))); header.append(tr); table.append(header); const body = node('tbody'); (run.case_results || []).forEach(c => { const row = node('tr'); [c.case_id, c.verdict, c.resolution_status].forEach(v => row.append(node('td', v))); body.append(row); }); table.append(body); result.append(table); const disclosure = node('details'); disclosure.append(node('summary', '출처·결과 해시 참조'), node('pre', JSON.stringify({ run_id: run.id, case_results: run.case_results }, null, 2))); result.append(disclosure); }
    else result.append(node('p', '평가 결과가 없습니다.'));
    target.append(result); runHistory(target, data.change_id); lock();
  }
  function runHistory(target, id) {
    const e = epoch, s = selection, section = node('section', undefined, 'mt-4');
    section.setAttribute('aria-labelledby', 'run-history-title');
    const title = node('h3', '저장된 평가 비교', 'h3'); title.id = 'run-history-title';
    const history = node('div'); history.id = 'run-history'; history.setAttribute('aria-live', 'polite');
    section.append(title);
    history.append(node('p', '최근 100개 실행을 조회한 뒤 기준·대상 실행을 선택하세요. 이 비교는 최신 평가나 제출 조건을 바꾸지 않습니다.'));
    const valid = () => e === epoch && s === selection && current?.change_id === id;
    const load = button('load-run-history', '평가 이력 조회', async () => {
      load.disabled = true; history.textContent = '평가 이력 불러오는 중…'; history.setAttribute('aria-busy', 'true');
      try {
        const data = await client.get('/api/v1/changes/' + id + '/evaluation-runs');
        if (!valid()) return;
        history.replaceChildren(node('p', `전체 ${data.total_runs}개 · 최근 ${data.limit}개까지 표시${data.truncated ? ' · 이전 실행은 목록에서 생략되었습니다.' : ''}`));
        if (data.runs.length) {
          const label = node('label', '검증할 평가'), picker = node('select');
          picker.id = 'coverage-run'; label.htmlFor = picker.id;
          for (const run of data.runs) {
            const option = node('option', 'revision ' + run.recorded_revision); option.value = run.id; picker.append(option);
          }
          const report = node('div'); report.setAttribute('aria-live', 'polite');
          let sequence = 0;
          picker.onchange = () => { ++sequence; report.replaceChildren(); };
          history.append(label, picker); picker.value = data.runs[0].id;
          button('read-coverage', '조항별 검증', async () => {
            const generation = ++sequence;
            report.textContent = '조회 중…';
            try {
              const result = await client.get('/api/v1/changes/' + id + '/evaluation-runs/' + encodeURIComponent(picker.value) + '/coverage');
              if (!valid() || generation !== sequence) return;
              if (result.availability !== 'AVAILABLE') { report.textContent = '저장된 조항별 기록이 없습니다.'; return; }
              report.textContent = result.clause_count === null ? '대상 조항 확인 불가' : '대상 조항 ' + result.clause_count + '개';
              const caption = node('label', '표시할 조항'), filter = node('select'), list = node('div');
              filter.id = 'coverage-filter'; caption.htmlFor = filter.id;
              for (const [value, text] of [['all','전체 조항'],['executed','실행 조항'],['missing','미검증 경계']]) {
                const option = node('option', text); option.value = value; filter.append(option);
              }
              report.append(node('p', '전체 사례 ' + result.case_count + ' · 실행 ' + result.executed_case_count + ' · 판단 불가 ' + result.inconclusive_case_count));
              const cases = new Map(result.cases.map(c => [c.case_id, c]));
              const caseDetail = c => {
                const box = node('details');
                box.append(node('summary', c.case_id + ' · ' + c.verdict),
                  node('p', [c.basis_date, c.recorded_as_of, c.selected_rule_id, ...c.reason_codes, ...c.tie_rule_ids].filter(Boolean).join(' · ')));
                if (c.tie_rule_ids.length) box.append(node('p', '동순위 충돌 후보 · ' + c.tie_rule_ids.join(', ')));
                if (c.reason_codes.includes('NO_APPLICABLE_APPROVED_RULE')) box.append(node('p', '적용 공백 후보'));
                for (const candidate of c.candidates) box.append(node('p', [candidate.rule_id, candidate.clause_id, candidate.policy_version,
                  candidate.eligible ? '적격' : '제외', ...candidate.reason_codes].join(' · ')));
                return box;
              };
              function renderCoverage() {
                list.replaceChildren();
                for (const row of result.clauses) {
                  const missing = row.boundaries.filter(b => !b.case_ids.length);
                  if ((filter.value === 'missing' && !missing.length) || (filter.value === 'executed' && !row.case_ids.length)) continue;
                  const box = node('details'); box.append(node('summary', [row.clause_id, row.rule_id, row.policy_version].join(' · ')),
                    node('p', 'PASS ' + row.passed + ' · FAIL ' + row.failed + ' · 후보 미선택 ' + row.unselected_candidate_count));
                  for (const b of missing) box.append(node('p', '경계 미검증 · ' + b.boundary + ' · ' + b.date));
                  for (const caseId of row.case_ids) box.append(caseDetail(cases.get(caseId)));
                  list.append(box);
                }
              }
              filter.onchange = renderCoverage; renderCoverage();
              report.append(caption, filter, list, node('h4', '사례별 해석'));
              for (const c of result.cases) report.append(caseDetail(c));
            } catch (error) {
              if (valid() && generation === sequence) { report.textContent = '조항별 기록을 불러오지 못했습니다.'; message(error); }
            }
          }, history, false);
          history.append(report);
        }
        if (data.runs.length < 2) { history.append(node('p', '비교하려면 저장된 평가가 2개 이상 필요합니다. 전체 사례를 다시 평가한 뒤 조회하세요.')); return; }
        let request = 0;
        const controls = node('div', undefined, 'run-compare-controls');
        function selector(key, label, index) {
          const group = node('div'), caption = node('label', label, 'form-label'), select = node('select');
          caption.htmlFor = key; select.id = key; select.className = 'form-select';
          data.runs.forEach(run => { const option = node('option', `revision ${run.recorded_revision} · ${run.completion}/${run.gate_summary} · ${run.id}`); option.value = run.id; select.append(option); });
          select.value = data.runs[index].id; group.append(caption, select); controls.append(group); return select;
        }
        const baseline = selector('baseline-run', '기준 실행', 1), candidate = selector('candidate-run', '대상 실행', 0);
        const output = node('div'); output.id = 'run-comparison'; output.setAttribute('aria-live', 'polite');
        const compare = button('compare-runs', '선택한 실행 비교', async () => {
          const sequence = ++request;
          output.textContent = '평가 비교 조회 중…'; output.setAttribute('aria-busy', 'true'); compare.disabled = true;
          try {
            const result = await client.get('/api/v1/changes/' + id + '/evaluation-runs/compare?baseline_run_id=' + encodeURIComponent(baseline.value) + '&candidate_run_id=' + encodeURIComponent(candidate.value));
            if (!valid() || sequence !== request) return;
            const warning = node('p', `${result.mode} · ${result.context_reasons.length ? result.context_reasons.join(', ') : '입력·출처·설정 문맥이 같습니다.'}`, result.mode === 'SAME_CONTEXT' ? '' : 'alert alert-warning');
            output.replaceChildren(warning, node('p', '저장된 결과와 해시만 비교합니다. 입력·출처·설정이 다르면 결과의 원인을 단정할 수 없습니다. 모델 품질 평가나 자동 승인 권고가 아닙니다.'), node('p', `변경 사례 ${result.changed_counts.any_changed}개 · 각 변경 항목 수는 중복 집계될 수 있습니다.`));
            const wrap = node('div', undefined, 'table-responsive'), table = node('table', undefined, 'table'), head = node('thead'), header = node('tr');
            ['사례', '기준 결과', '대상 결과', '변경 항목'].forEach(label => header.append(node('th', label))); head.append(header); table.append(head);
            const body = node('tbody'); body.id = 'comparison-rows';
            const state = side => side ? `${side.verdict} · ${side.complete ? 'COMPLETE' : 'INCOMPLETE'} · ${side.resolution_status}${side.error_code ? ' · ' + side.error_code : ''}` : '없음';
            const filters = node('div', undefined, 'run-compare-controls');
            const caption = node('label', '변경 항목', 'form-label'), filter = node('select', undefined, 'form-select');
            filter.id = 'comparison-filter'; caption.htmlFor = filter.id;
            for (const [value, label] of [['all', '전체 사례'], ['any_changed', '변경된 사례'], ['presence_changed', '사례 추가·누락'], ['input_changed', '입력 변경'], ['output_changed', '출력 변경'], ['source_refs_changed', '출처 변경'], ['result_state_changed', '결과 상태 변경']]) {
              const option = node('option', label); option.value = value; filter.append(option);
            }
            filter.value = 'all';
            const searchLabel = node('label', '사례 ID 검색', 'form-label'), search = node('input', undefined, 'form-control');
            search.id = 'comparison-search'; search.type = 'search'; searchLabel.htmlFor = search.id;
            const visible = node('p'); visible.id = 'comparison-visible'; visible.setAttribute('role', 'status');
            const empty = node('p', '조건에 맞는 사례가 없습니다. 변경 항목이나 사례 ID 검색을 조정하세요.'); empty.id = 'comparison-empty';
            const pager = node('nav', undefined, 'comparison-pager'); pager.setAttribute('aria-label', '사례 비교 페이지');
            let page = 0;
            const pageSize = 50;
            const inspector = node('section', undefined, 'comparison-inspector'); inspector.id = 'comparison-case-detail';
            inspector.setAttribute('aria-label', '선택한 사례 근거'); inspector.tabIndex = -1;
            const resetInspector = () => { inspector.replaceChildren(node('p', '사례 ID를 선택하면 기준과 후보의 근거 해시를 나란히 확인합니다.')); };
            function inspectCase(row) {
              inspector.replaceChildren(node('h4', row.case_id), node('p', '저장된 투영 · 원문과 모델 응답은 포함하지 않습니다. 비교 조건 경고는 전체 실행 기준입니다.'));
              const sides = node('div', undefined, 'comparison-sides');
              for (const [label, side] of [['기준', row.baseline], ['후보', row.candidate]]) {
                const panel = node('div'); panel.append(node('h5', label));
                if (!side) panel.append(node('p', '이 실행에 사례 없음'));
                else {
                  panel.append(node('p', state(side)));
                  const fields = node('dl');
                  for (const field of ['input_sha256', 'output_sha256', 'critical_failure']) fields.append(node('dt', field), node('dd', String(side[field] ?? '미확인')));
                  panel.append(fields, node('h6', '출처 참조'));
                  if (!side.source_refs.length) panel.append(node('p', '참조 없음'));
                  side.source_refs.forEach(ref => { const entry = node('p'); entry.append(node('strong', ref.id), node('code', ref.payload_sha256)); panel.append(entry); });
                }
                sides.append(panel);
              }
              inspector.append(sides); inspector.focus();
            }
            const previous = button('comparison-previous', '이전 50개', () => { page--; renderRows(); }, pager, false);
            const position = node('span'); position.id = 'comparison-page'; position.setAttribute('role', 'status'); pager.append(position);
            const next = button('comparison-next', '다음 50개', () => { page++; renderRows(); }, pager, false);
            function renderRows() {
              const query = search.value.trim().toLowerCase();
              const rows = result.rows.filter(row => row.case_id.toLowerCase().includes(query) &&
                (filter.value === 'all' || (filter.value === 'any_changed' ? Object.values(row.changes).some(Boolean) : row.changes[filter.value] === true)));
              const pages = Math.max(1, Math.ceil(rows.length / pageSize)); page = Math.max(0, Math.min(page, pages - 1));
              const start = page * pageSize, shown = rows.slice(start, start + pageSize);
              body.replaceChildren(); resetInspector();
              shown.forEach(row => {
                const tr = node('tr'), cell = node('td'), inspect = node('button', row.case_id, 'btn btn-link comparison-case');
                inspect.type = 'button'; inspect.setAttribute('aria-controls', inspector.id); inspect.onclick = () => inspectCase(row); cell.append(inspect); tr.append(cell);
                [state(row.baseline), state(row.candidate), Object.keys(row.changes).filter(key => row.changes[key]).join(', ') || '변경 없음'].forEach(value => tr.append(node('td', value))); body.append(tr);
              });
              visible.textContent = `표시 ${rows.length} / 전체 ${result.rows.length}개 · 현재 ${shown.length}개 · 비교 맥락 경고는 전체 실행 기준입니다.`;
              position.textContent = `${page + 1} / ${pages} 페이지 · ${rows.length ? start + 1 : 0}–${start + shown.length}`;
              previous.disabled = page === 0; next.disabled = page >= pages - 1;
              empty.hidden = rows.length !== 0;
            }
            filter.onchange = search.oninput = () => { page = 0; renderRows(); };
            filters.append(caption, filter, searchLabel, search); renderRows();
            table.append(body); wrap.append(table);
            const details = node('details'); details.append(node('summary', '실행·입출력·출처 해시 참조')); let rawLoaded = false;
            details.ontoggle = () => { if (details.open && !rawLoaded) { details.append(node('pre', JSON.stringify(result, null, 2))); rawLoaded = true; } };
            output.append(filters, visible, empty, wrap, pager, inspector, details);
          } catch (error) { if (valid() && sequence === request) { output.textContent = '평가 비교 조회 실패. 선택을 확인하고 다시 조회하세요.'; message(error); } }
          finally { if (valid() && sequence === request) { compare.disabled = false; output.setAttribute('aria-busy', 'false'); } }
        }, controls, false);
        baseline.onchange = candidate.onchange = () => { ++request; output.textContent = '선택이 바뀌었습니다. 다시 비교하세요.'; output.setAttribute('aria-busy', 'false'); compare.disabled = false; };
        history.append(controls, output);
      } catch (error) { if (valid()) { history.textContent = '평가 이력 조회 실패. 다시 조회하세요.'; message(error); } }
      finally { if (valid()) { load.disabled = false; history.setAttribute('aria-busy', 'false'); } }
    }, section, false);
    section.append(history); target.append(section);
  }
  function renderQueue() {
    if (!queueReady) return;
    const q = $('search').value.toLowerCase(), state = $('status-filter').value;
    const filtered = rows.filter(r => (!state || r.status === state) && (r.title + r.change_id).toLowerCase().includes(q));
    $('queue-summary').textContent = q || state ? `검색 결과 ${filtered.length}건 / 전체 ${rows.length}건` : `전체 ${rows.length}건`;
    $('queue').replaceChildren(); if (!filtered.length) { $('queue').append(node('p', '표시할 변경 요청이 없습니다.', 'p-3')); return; }
    const table = node('table', undefined, 'table table-vcenter'), head = node('thead'), hr = node('tr'); hr.append(node('th', '변경 요청')); head.append(hr); table.append(head); const body = node('tbody');
    filtered.forEach(row => {
      const tr = node('tr'), td = node('td'), b = node('button', row.title, 'btn btn-link p-0 text-start');
      b.type = 'button'; b.dataset.changeId = row.change_id;
      b.onclick = async () => {
        if (await select(row.change_id) && document.activeElement === b) $('detail-title').focus();
      };
      const meta = node('div', undefined, 'queue-meta'); meta.append(node('span', row.pack_version_id), node('span', 'Revision ' + row.revision));
      const status = node('div', queueStatuses.get(row.status) ?? row.status, 'queue-status'); status.dataset.status = row.status;
      td.append(b, status, meta); tr.append(td); body.append(tr);
    }); table.append(body); $('queue').append(table); syncSelectedRow();
  }
  async function refresh() {
    const e = epoch, request = ++queueRequest;
    const valid = () => e === epoch && request === queueRequest;
    rows = []; queueReady = false;
    $('queue-summary').textContent = '';
    $('queue').setAttribute('aria-busy', 'true'); $('queue').textContent = '불러오는 중…';
    try {
      const data = await client.get('/api/v1/changes');
      if (!valid()) return false;
      rows = data; queueReady = true; renderQueue();
      return true;
    } catch (error) {
      if (valid()) {
        $('queue').textContent = '목록을 불러오지 못했습니다. 새로고침하세요.';
        clearDetail('목록 조회 실패'); message(error);
      }
      return false;
    } finally {
      if (valid()) $('queue').setAttribute('aria-busy', 'false');
    }
  }
  async function select(id) {
    const e = epoch, s = ++selection; clearDetail('불러오는 중…'); $('detail').setAttribute('aria-busy', 'true'); message();
    try { const data = await client.get('/api/v1/changes/' + id); if (e !== epoch || s !== selection) return; if (data.historical_integrity === 'INVALID') { clearDetail('기록 무결성이 유효하지 않습니다.'); return; } if (data.historical_integrity === 'LEGACY_UNVERIFIED') { clearDetail('이전 실행 형식의 기록입니다. 기록을 보존하고 새 프로필에서 평가하세요.'); return; } render(data.snapshot || data, data.latest_run || data.run); return true; }
    catch (error) { if (e === epoch && s === selection) { clearDetail('변경을 불러오지 못했습니다.'); message(error); } } finally { if (e === epoch && s === selection) $('detail').setAttribute('aria-busy', 'false'); }
  }
  async function mutate(path, body, revision, retry = false) {
    const e = epoch, s = ++selection, previous = current;
    const inputs = new Map([...document.querySelectorAll('[data-case-input]')].map(input => [input.dataset.caseInput, input.value]));
    message(); const promise = retry ? client.retry() : client.mutate(path, body, revision); lock();
    try {
      const result = await promise;
      if (e !== epoch) return;
      document.querySelectorAll('dialog[open]').forEach(d => d.close());
      if (s !== selection) return;
      if (await refresh() && e === epoch && s === selection && await select(result.data.change_id)) {
        message(result.replayed ? '원래 요청의 결과를 복구하고 현재 상태를 확인했습니다.' : '기록했습니다.');
      }
    }
    catch (error) { if (e === epoch) {
      document.querySelectorAll('dialog[open]').forEach(d => d.close());
      if (s !== selection) { message(error); return; }
      const actionable = error.status === 409 && ['RELEASE_GATE_BLOCKED', 'EVALUATION_INCOMPLETE', 'SOURCE_NOT_ELIGIBLE', 'STALE_REVISION'].includes(error.code);
      if (actionable && !client.pending() && previous && current?.change_id === previous.change_id && s === selection) {
        // Reauthorize the read before preserving correction context; never restore an old snapshot.
        const refresh = select(previous.change_id), refreshedSelection = selection;
        await refresh;
        if (e === epoch && refreshedSelection === selection && current?.change_id === previous.change_id) {
          const summary = { title: current.title, status: current.status, revision: current.revision, pack_version_id: current.pack_version_id };
          rows = rows.map(row => row.change_id === current.change_id ? { ...row, ...summary } : row);
          renderQueue();
          if (current.suite_version_id === previous.suite_version_id) document.querySelectorAll('[data-case-input]').forEach(input => {
            if (inputs.has(input.dataset.caseInput)) input.value = inputs.get(input.dataset.caseInput);
          });
          message(error);
        }
      } else {
        clearDetail(client.pending() ? '처리 결과가 미확정입니다. 원래 요청 복구를 이용하세요.' : '요청을 처리하지 못했습니다. 최신 변경을 다시 선택하세요.'); message(error);
      }
    } } finally { if (e === epoch) lock(); }
  }
  function showDialog(id) { message(); if (id === 'decision-dialog') clearDecisionError(); opener = document.activeElement; $(id).showModal(); }
  function openCreate(source) {
    parent = source || null; $('preset').replaceChildren(); workspace.presets.forEach((p, i) => { const option = node('option', p.label); option.value = i; $('preset').append(option); });
    const index = source ? workspace.presets.indexOf(presetFor(source)) : 0; $('preset').value = Math.max(index, 0); $('preset').disabled = !!source; $('title').value = source ? source.title + ' · 시정' : workspace.presets[0]?.create_body.title || ''; $('parent-description').textContent = source ? '원본 ' + source.change_id + ' · CORRECTS_REJECTED' : ''; showDialog('create-dialog'); lock();
  }
  $('login-form').onsubmit = async event => {
    event.preventDefault(); const token = $('token').value; $('token').value = ''; const e = ++epoch; ++selection; message(); const submit = event.submitter; submit.disabled = true;
    try { const data = await client.get('/api/v1/workspace', token); if (e !== epoch) return; workspace = data; client.connect(token, data.actor, data.request_context); rows = []; clearDetail(); $('actor').textContent = `${data.actor.tenant_id} / ${data.actor.actor_id} · ${data.actor.roles.join(', ')}`; $('workspace').hidden = false; $('login').hidden = true; lock(); await refresh(); if ($('message').dataset.kind !== 'error') $('main').focus(); } catch (error) { if (e === epoch) message(error); } finally { submit.disabled = false; }
  };
  $('switch-role').onclick = () => { ++epoch; ++selection; client.connect(null, null); workspace = null; rows = []; clearDetail(); $('search').value = ''; $('status-filter').value = ''; $('queue-summary').textContent = ''; document.querySelectorAll('dialog[open]').forEach(d => d.close()); $('workspace').hidden = true; $('login').hidden = false; message(); $('token').focus(); };
  $('refresh').onclick = () => { message(); ++selection; clearDetail(); refresh(); };
  $('return-queue').onclick = () => {
    const selected = document.querySelector('#queue [aria-current="true"]');
    (selected || $('queue-title')).focus();
  };
  $('new-change').onclick = () => openCreate(); $('search').oninput = renderQueue; $('status-filter').onchange = renderQueue;
  $('preset').onchange = () => { $('title').value = workspace.presets[Number($('preset').value)].create_body.title; };
  $('create-form').onsubmit = event => { event.preventDefault(); const body = { ...workspace.presets[Number($('preset').value)].create_body, title: $('title').value }; if (parent) Object.assign(body, { parent_change_id: parent.change_id, parent_relation: 'CORRECTS_REJECTED' }); mutate('/api/v1/changes', body, null); };
  $('decision-form').onsubmit = event => {
    event.preventDefault();
    if (!validReason()) {
      $('decision-error-summary').hidden = false; $('reason-error').hidden = false;
      $('reason').setAttribute('aria-invalid', 'true'); $('reason').setAttribute('aria-describedby', 'reason-error');
      $('decision-error-summary').focus(); return;
    }
    clearDecisionError(); mutate(decision.path, { decision: decision.value, reason: $('reason').value }, decision.revision);
  };
  $('reason-error-link').onclick = event => { event.preventDefault(); $('reason').focus(); };
  $('reason').oninput = () => { if (validReason()) clearDecisionError(); };
  $('retry-request').onclick = () => mutate(null, null, null, true);
  window.addEventListener('storage', event => {
    if (workspace && (event.key === null || event.key === client.scope)) lock();
  });
  $('load-evidence').onclick = async () => {
    if (!current) return;
    const id = current.change_id, e = epoch, s = selection;
    const target = $('evidence');
    target.textContent = '확인 중…';
    try {
      const data = await client.get('/api/v1/changes/' + id + '/evidence');
      if (e !== epoch || s !== selection) return;
      const list = node('dl', undefined, 'evidence-result');
      for (const [label, key] of [['역사적 무결성', 'historical_integrity'], ['현재 출처 적격성', 'current_approval_eligibility'], ['외부 앵커', 'external_anchor'], ['승인 개정', 'approved_revision'], ['Envelope SHA-256', 'envelope_sha256']]) {
        const raw = data[key];
        const value = node('dd', evidenceLabels.get(raw) ?? raw ?? '—');
        value.dataset.result = String(raw ?? '');
        list.append(node('dt', label), value);
      }
      const details = node('details');
      details.append(node('summary', '증거 원본 JSON'), node('pre', JSON.stringify(data, null, 2)));
      target.replaceChildren(list, details);
    } catch (error) {
      if (e === epoch && s === selection) { target.textContent = '증거 조회 실패'; message(error); }
    }
  };
  document.querySelectorAll('[data-close]').forEach(b => { b.onclick = () => b.closest('dialog').close(); });
  document.querySelectorAll('dialog').forEach(d => d.addEventListener('close', () => {
    if ($('message').dataset.kind === 'error') $('message').focus();
    else if (opener?.isConnected) opener.focus();
  }));
}());
