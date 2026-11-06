/* Own-only synthetic DOM harness benchmark; not browser latency or competitor evidence. */
const { app } = require('./check_submit_flow.cjs');
const { execFileSync } = require('node:child_process');
const { performance } = require('node:perf_hooks');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const before = execFileSync('git', ['show', 'c809585:service/static/v1.js'], { cwd: root, encoding: 'utf8' });
const after = fs.readFileSync(path.join(root,'service/static/v1.js'),'utf8');
const summary = id => ({id,recorded_revision:2,completion:'COMPLETE',gate_summary:'PASS'});
const side = {verdict:'PASS',complete:true,resolution_status:'RESOLVED',critical_failure:false,error_code:null,input_sha256:'a'.repeat(64),output_sha256:'b'.repeat(64),source_refs:[]};
const result = {baseline:summary('old'),candidate:summary('new'),mode:'SAME_CONTEXT',context_reasons:[],changed_counts:{any_changed:1000},rows:Array.from({length:1000},(_,i)=>({case_id:`case-${String(i).padStart(4,'0')}`,baseline:side,candidate:side,changes:{output_changed:true}}))};
const history={total_runs:2,limit:100,runs:[summary('new'),summary('old')]};
const response=data=>({ok:true,status:200,json:async()=>({data})});
(async()=>{
 const records=[];
 for(const [name,source] of [['before',before],['after',after]]){
  const samples=[]; let rowCount, nodeCount, textBytes;
  for(let i=0;i<25;i++){
   const ui=await app({javascriptOverride:source,extraGet:url=>response(url.includes('/compare?')?result:history)});
   await ui.get('load-run-history').onclick();
   const start=performance.now();await ui.get('compare-runs').onclick();const elapsed=performance.now()-start;
   if(i>=5)samples.push(elapsed);
   rowCount=ui.get('comparison-rows').children.length;nodeCount=ui.connected().length;textBytes=Buffer.byteLength(ui.get('run-comparison').textContent);
  }
  samples.sort((a,b)=>a-b);
  records.push({name,source_sha256:crypto.createHash('sha256').update(source).digest('hex'),samples:20,warmup:5,median_ms:samples[10],p95_ms:samples[18],rowCount,nodeCount,textBytes});
 }
 const output={scope:'own-only synthetic DOM harness, not browser paint/network/competitor',node:process.version,platform:process.platform,fixture_sha256:crypto.createHash('sha256').update(JSON.stringify(result)).digest('hex'),response_bytes:Buffer.byteLength(JSON.stringify(result)),records};
 console.log(JSON.stringify(output,null,2));
})();
