/* Actual Chromium DOM/layout checks with intercepted synthetic local API. No server or external calls. */
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_CORE);
const root=path.resolve(__dirname,'..'),out=path.resolve(process.argv[2]||path.join(root,'.runtime/depth-browser'));
fs.mkdirSync(out,{recursive:true});
const summary=id=>({id,recorded_revision:2,completion:'COMPLETE',gate_summary:'PASS'});
const side={verdict:'PASS',complete:true,resolution_status:'RESOLVED',error_code:null,critical_failure:false,input_sha256:'a'.repeat(64),output_sha256:'b'.repeat(64),source_refs:[{id:'synthetic-source',payload_sha256:'c'.repeat(64)}]};
const comparison={baseline:summary('old'),candidate:summary('new'),mode:'CONTEXT_CHANGED',context_reasons:['INPUT_CHANGED'],changed_counts:{any_changed:1000},rows:Array.from({length:1000},(_,i)=>({case_id:'case-'+String(i).padStart(4,'0'),baseline:side,candidate:side,changes:{input_changed:true}}))};
const snapshot={change_id:'synthetic-change',title:'Synthetic review benchmark',revision:2,status:'DRAFT',requester_id:'analyst',owner_id:'analyst',pack_version_id:'synthetic',candidate_snapshot_id:'candidate',source_bundle_id:'bundle',suite_version_id:'suite',active_run_id:'latest'};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'});const errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url());if(u.origin!=='http://caseproof.test')return route.abort();
  if(u.pathname.startsWith('/api/')){
   if(route.request().method()!=='GET'){posts.push(u.pathname);return route.fulfill({status:405,body:'{}'});}
   let data;
   if(u.pathname==='/api/v1/workspace')data={actor:{tenant_id:'synthetic',actor_id:'analyst',roles:['ANALYST']},presets:[{create_body:{suite_version_id:'suite',pack_version_id:'synthetic'},case_inputs:[{case_id:'case',claim_days:30,case_context:{}}]}]};
   else if(u.pathname==='/api/v1/changes')data=[snapshot];
   else if(u.pathname.endsWith('/evaluation-runs/compare'))data=comparison;
   else if(u.pathname.endsWith('/evaluation-runs'))data={total_runs:2,limit:100,runs:[summary('new'),summary('old')]};
   else data={historical_integrity:'VALID',snapshot,latest_run:{...summary('latest'),completion:'INCOMPLETE',gate_summary:'BLOCK',case_results:[{case_id:'case',verdict:'INCONCLUSIVE',resolution_status:'INCONCLUSIVE'}]}};
   return route.fulfill({contentType:'application/json',body:JSON.stringify({data})});
  }
  const relative=u.pathname==='/'?'service/static/v1.html':'service'+u.pathname;
  const file=path.resolve(root,relative);if(!file.startsWith(root+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
  const type={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2'}[path.extname(file)];
  return route.fulfill({path:file,contentType:type});
 });
 try{
  await page.goto('http://caseproof.test/');await page.locator('#token').fill('synthetic-only');await page.locator('#login-form button[type=submit]').click();
  await page.locator('[data-change-id]').click();await page.locator('#load-run-history').click();await page.locator('#compare-runs').click();
  await page.locator('#comparison-rows tr').first().waitFor();assert.equal(await page.locator('#comparison-rows tr').count(),50);
  await page.locator('.comparison-case').first().focus();await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>document.activeElement.id),'comparison-case-detail');
  assert.match(await page.locator('#comparison-case-detail').textContent(),/synthetic-source/);
  await page.locator('#comparison-next').click();assert.match(await page.locator('#comparison-rows').textContent(),/case-0050/);
  await page.locator('#comparison-search').fill('case-0999');assert.equal(await page.locator('#comparison-rows tr').count(),1);
  assert.equal(await page.locator('#comparison-previous').isDisabled(),true);await page.locator('.comparison-case').click();
  const viewports=[];for(const width of [1440,390]){await page.setViewportSize({width,height:900});await page.locator('#comparison-case-detail').scrollIntoViewIfNeeded();
   const metrics=await page.evaluate(()=>({viewport:innerWidth,overflow:document.documentElement.scrollWidth-innerWidth,buttonHeight:document.querySelector('.comparison-case').getBoundingClientRect().height,focus:document.activeElement.id}));assert.equal(metrics.overflow,0);assert.ok(metrics.buttonHeight>=44);viewports.push(metrics);await page.screenshot({path:path.join(out,`case-review-${width}.png`),fullPage:true});}
  assert.equal(await page.locator('#submit-change').isDisabled(),true);assert.match(await page.locator('#run-comparison').textContent(),/CONTEXT_CHANGED.*INPUT_CHANGED/s);assert.deepEqual(posts,[]);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({scope:'actual Chromium UI with synthetic intercepted local API; not backend E2E',browser:browser.version(),viewports,errors,posts,status:'PASS'},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
