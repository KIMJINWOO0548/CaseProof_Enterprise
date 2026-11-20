const assert = require('node:assert/strict');
const { RequestClient } = require('../service/static/v1.js');
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
(async () => {
  const first = Array.from({length: 200}, (_, n) => ({change_id: id(n)}));
  for (const fail of [false, true]) {
    const calls = [];
    const client = new RequestClient(async url => {
      calls.push(url);
      if (calls.length === 2 && fail) throw new Error('synthetic second-page disconnect');
      return {ok: true, json: async () => calls.length === 1
        ? {data: first, pagination: {next_cursor: id(199)}}
        : {data: [{change_id: id(200)}], pagination: {next_cursor: null}}};
    });
    if (fail) await assert.rejects(client.get('/api/v1/changes'), /disconnect/);
    else assert.equal((await client.get('/api/v1/changes')).length, 201);
    assert.deepEqual(calls, ['/api/v1/changes', '/api/v1/changes?after=' + id(199)]);
  }
  for (const second of [
    {data: [{change_id: id(199)}], pagination: {next_cursor: null}},
    {data: [{change_id: id(200)}], pagination: {next_cursor: id(201)}},
    {data: [{change_id: id(201)}, {change_id: id(200)}], pagination: {next_cursor: null}},
  ]) {
    let calls = 0;
    const client = new RequestClient(async () => {
      const page = ++calls === 1 ? {data: first, pagination: {next_cursor: id(199)}}
        : calls === 2 ? second : {data: [], pagination: {next_cursor: null}};
      return {ok: true, json: async () => page};
    });
    await assert.rejects(client.get('/api/v1/changes'), /목록 이어받기 응답/);
  }
  const calls = [];
  const client = new RequestClient(async (url, options) => {
    calls.push(options.method || 'GET');
    if (options.method === 'POST') throw new Error('lost after commit');
    assert.match(url, /^\/api\/v1\/mutations\//);
    return {ok: true, status: 200, json: async () => ({data: {change_id: id(1), revision: 1},
      original_status: 201, result_revision: 1, replayed: true})};
  });
  client.connect('token', {tenant_id: 't', actor_id: 'a'}, 'a'.repeat(64));
  await assert.rejects(client.mutate('/api/v1/changes', {title: 'synthetic'}, null));
  assert.equal((await client.retry()).data.change_id, id(1));
  assert.deepEqual(calls, ['POST', 'GET']);
  assert.equal(client.pending(), undefined);
  console.log('PASS: UI list covers 201; failed page is not success; reconnect queries committed result without repost');
})().catch(error => { console.error(error); process.exitCode = 1; });
