// Exercise the actual inline request function without a browser or external calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');

const html = fs.readFileSync(path.join(__dirname, '../service/static/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const prefix = script.slice(script.indexOf("'use strict';"), script.indexOf('\nfunction report('));

function client(fetch) {
  const context = vm.createContext({fetch, crypto:{randomUUID}});
  vm.runInContext(prefix + '\ntoken="synthetic-test-token";globalThis.request=api;', context);
  context.request.setActor=actor=>vm.runInContext('me='+JSON.stringify(actor),context);
  context.request.nextSession=()=>vm.runInContext('sessionGeneration++',context);
  return context.request;
}
function response(status=200, data={replayed:false}) {
  return {ok:status<400, status, json:async()=>data};
}

(async () => {
  const sent=[];
  let fail=true;
  const request=client(async (url, options)=>{
    sent.push(options);
    if(fail){fail=false;throw new TypeError('synthetic lost response');}
    return response();
  });
  const options={method:'POST',body:{expected_revision:4}};
  await assert.rejects(request('/api/changes/demo/submit',options));
  await request('/api/changes/demo/submit',options);
  const key=sent[0].headers['Idempotency-Key'];
  assert.ok(key && key.length>=12 && key.length<=128,'every mutation needs a key');
  assert.equal(sent[1].headers['Idempotency-Key'],key,'lost response must preserve the key');
  await request('/api/changes/demo/submit',options);
  assert.notEqual(sent[2].headers['Idempotency-Key'],key,'successful requests release the key');
  await request('/api/health');
  assert.equal(sent[3].headers['Idempotency-Key'],undefined,'GET must not reserve a key');

  for(const retryable of [true,false]) {
    const attempts=[];
    const call=client(async (_url,options)=>{
      attempts.push(options.headers['Idempotency-Key']);
      return attempts.length===1 ? response(409,{detail:{code:'CONFLICT',retryable}}) : response();
    });
    await assert.rejects(call('/api/changes', {method:'POST',body:{title:'synthetic'}}));
    await call('/api/changes', {method:'POST',body:{title:'synthetic'}});
    if(retryable)assert.equal(attempts[0],attempts[1]);
    else assert.notEqual(attempts[0],attempts[1]);
  }

  const keys=[];
  const changed=client(async (_url,options)=>{
    keys.push(options.headers['Idempotency-Key']);
    throw new TypeError('synthetic network failure');
  });
  await assert.rejects(changed('/api/changes', {method:'POST',body:{title:'first'}}));
  await assert.rejects(changed('/api/changes', {method:'POST',body:{title:'changed'}}));
  assert.notEqual(keys[0],keys[1],'changed bodies must use a new key');
  const revisions=[];
  const revised=client(async (_url,options)=>{
    revisions.push(options.headers['Idempotency-Key']);
    throw new TypeError('synthetic network failure');
  });
  for(const revision of ['1','2'])await assert.rejects(revised('/api/changes/demo/evaluations',
    {method:'POST',body:{claim_days:30},headers:{'X-Expected-Revision':revision}}));
  assert.notEqual(revisions[0],revisions[1],'changed revision must use a new key');

  const incomplete=[];
  const partial=client(async (_url,options)=>{
    incomplete.push(options.headers['Idempotency-Key']);
    return incomplete.length===1 ? {ok:true,status:201,json:async()=>{throw new SyntaxError('truncated JSON');}} : response();
  });
  await assert.rejects(partial('/api/changes', {method:'POST',body:{title:'partial'}}));
  await partial('/api/changes', {method:'POST',body:{title:'partial'}});
  assert.equal(incomplete[0],incomplete[1],'incomplete success body must preserve the key');

  let resolveResponse;
  const concurrentSends=[];
  const concurrent=client(async (_url,options)=>{
    concurrentSends.push(options);
    return await new Promise(resolve=>{resolveResponse=resolve;});
  });
  const first=concurrent('/api/changes',{method:'POST',body:{title:'concurrent'}});
  const second=concurrent('/api/changes',{method:'POST',body:{title:'concurrent'}});
  assert.equal(concurrentSends.length,1,'double submit must share one in-flight request');
  resolveResponse(response());
  await Promise.all([first,second]);

  const scopedKeys=[];
  const scoped=client(async (_url,options)=>{
    scopedKeys.push(options.headers['Idempotency-Key']);
    throw new TypeError('synthetic response loss');
  });
  scoped.setActor({id:'analyst-a',tenant_id:'tenant-a'});
  await assert.rejects(scoped('/api/changes',options));
  scoped.setActor({id:'analyst-b',tenant_id:'tenant-a'});
  await assert.rejects(scoped('/api/changes',options));
  scoped.setActor({id:'analyst-a',tenant_id:'tenant-a'});
  await assert.rejects(scoped('/api/changes',options));
  assert.notEqual(scopedKeys[0],scopedKeys[1],'pending keys belong to one authenticated actor');
  assert.equal(scopedKeys[0],scopedKeys[2],'returning actor retains the original recovery key');

  let finishLate;
  const late=client(async ()=>await new Promise(resolve=>{finishLate=resolve;}));
  const delayed=late('/api/changes');
  const rejected=assert.rejects(delayed,error=>error.sessionChanged===true);
  late.nextSession();
  finishLate(response(200,[{id:'old-session-record'}]));
  await rejected;
  console.log('UI request retry contract: PASS (lost response, completed request, GET, retryable conflict, changed body)');
})().catch(error=>{console.error(error);process.exitCode=1;});
