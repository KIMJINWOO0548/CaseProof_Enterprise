const assert = require('node:assert/strict');
const { RequestClient } = require('../service/static/v1.js');

(async () => {
  let mode = 'lost';
  const client = new RequestClient(async () => {
    if (mode === 'lost') throw Error('response lost after commit');
    return { ok: mode === 200, status: mode,
      json: async () => mode === 200 ? { data: { change_id: 'original' }, replayed: true }
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
  mode = 403;
  await assert.rejects(client.mutate('/api/v1/changes', {}, null));
  assert.equal(client.pending(), undefined, 'first-attempt denial is a known failed request');
  console.log('PASS: uncertain outcome survives later authorization denial until original replay');
})().catch(error => { console.error(error); process.exitCode = 1; });
