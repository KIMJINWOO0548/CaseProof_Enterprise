const assert = require('node:assert/strict');
const { RequestClient } = require('../service/static/v1.js');

(async () => {
  let mode = 'lost';
  const firstCalls = [];
  const originalId = '1289d7e7-a2c4-4bda-a832-232c9688fd60';
  const client = new RequestClient(async (path, options) => {
    firstCalls.push({ path, method: options.method || 'GET' });
    if (mode === 'lost') throw Error('response lost after commit');
    return { ok: mode === 200, status: mode,
      json: async () => mode === 200 ? { data: { change_id: originalId, revision: 1 },
          original_status: 201, result_revision: 1, replayed: true }
        : { error: { code: 'FORBIDDEN', message: 'Current permission revoked' } } };
  });
  client.connect('synthetic', { tenant_id: 't', actor_id: 'a' });
  await assert.rejects(client.mutate('/api/v1/changes', { title: 'original' }, null));
  const key = client.pending().key;
  mode = 403;
  await assert.rejects(client.retry(), /FORBIDDEN/);
  assert.equal(client.pending()?.key, key, 'denial cannot prove the earlier request was uncommitted');
  await assert.rejects(client.mutate('/api/v1/changes', { title: 'replacement' }, null), /원래 요청/);
  mode = 200;
  assert.equal((await client.retry()).replayed, true);
  assert.equal(client.pending(), undefined);
  assert.deepEqual(firstCalls, [
    { path: '/api/v1/changes', method: 'POST' },
    { path: '/api/v1/mutations/' + key, method: 'GET' },
    { path: '/api/v1/mutations/' + key, method: 'GET' },
  ], 'denied and committed lookups never repost');
  mode = 403;
  await assert.rejects(client.mutate('/api/v1/changes', {}, null));
  assert.equal(client.pending(), undefined, 'first-attempt denial is a known failed request');

  const entries = new Map();
  const storage = {
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
    removeItem: key => entries.delete(key)
  };
  const actor = { tenant_id: 'fictional', actor_id: 'analyst' };
  const context = 'a'.repeat(64);
  const changeId = '1289d7e7-a2c4-4bda-a832-232c9688fd60';
  const path = '/api/v1/changes/' + changeId + '/domain-decision';
  const calls = [];
  const send = async (path, options) => {
    assert.equal(entries.size, 1, 'intent must already be saved before the request');
    assert.ok(!JSON.stringify([...entries.values()]).includes('volatile-browser-token'));
    calls.push({ path, options });
    if (calls.length === 1) throw Error('original outcome unknown');
    if (calls.length === 2) return { ok: true, status: 200, json: async () => ({
      data: { change_id: '2289d7e7-a2c4-4bda-a832-232c9688fd60', revision: 4 },
      original_status: 200, result_revision: 4, replayed: true,
    }) };
    if (calls.length === 3) return { ok: false, status: 404, json: async () => ({
      error: { code: 'NOT_FOUND' },
    }) };
    return { ok: true, status: 200, json: async () => ({
      data: { change_id: changeId, revision: 4 }, result_revision: 4, replayed: false,
    }) };
  };
  const start = new RequestClient(send, () => storage);
  start.connect('volatile-browser-token', actor, context);
  await assert.rejects(start.mutate(path, { decision: 'APPROVE', reason: 'Synthetic intent' }, 3), /미확정/);
  const reconnect = new RequestClient(send, () => storage);
  reconnect.connect('volatile-browser-token', { ...actor, actor_id: 'other' }, context);
  assert.equal(reconnect.pending(), undefined, 'a different actor must not see the saved intent');
  reconnect.connect('volatile-browser-token', actor, 'b'.repeat(64));
  await assert.rejects(reconnect.retry(), /작업공간/);
  assert.equal(calls.length, 1, 'another database cannot receive the old POST');
  reconnect.connect('volatile-browser-token', actor, context);
  await assert.rejects(reconnect.mutate('/api/v1/changes', { title: 'duplicate' }, null), /원래 요청/);
  await assert.rejects(reconnect.retry(), /원래 요청의 저장 결과/, 'another change cannot confirm this intent');
  assert.equal(entries.size, 1, 'a malformed successful response cannot erase the intent');
  assert.equal((await reconnect.retry()).data.change_id, changeId);
  for (const call of calls.slice(1, 3)) {
    assert.equal(call.path, '/api/v1/mutations/' + calls[0].options.headers['Idempotency-Key']);
    assert.equal(call.options.method || 'GET', 'GET');
    assert.equal(call.options.cache, 'no-store');
  }
  assert.deepEqual(calls[3], calls[0], 'only after authorized not-found, send the same key, bytes and context');
  assert.equal(entries.size, 0, 'confirmed intent is removed');

  const unavailable = new RequestClient(send, () => ({ ...storage, setItem() { throw Error('quota'); } }));
  unavailable.connect('volatile-browser-token', actor, context);
  await assert.rejects(unavailable.mutate('/api/v1/changes', { title: 'never sent' }, null), /저장/);
  assert.equal(calls.length, 4, 'persistence failure must stop the POST');
  console.log('PASS: uncertain outcome survives later authorization denial until original replay');
})().catch(error => { console.error(error); process.exitCode = 1; });
