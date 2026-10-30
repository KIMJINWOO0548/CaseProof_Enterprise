// Browser-side scenario for an owned, disposable SQLite instance.
// Pass privately held seed credentials; the returned report never includes them.
async credentials => {
 const q=selector=>document.querySelector(selector),checks=[],requests=[];
 const wait=async predicate=>{for(let n=0;n<250;n++){if(predicate())return;await new Promise(r=>setTimeout(r,20));}throw Error('workflow UI wait timed out');};
 const assert=(condition,name)=>{if(!condition)throw Error(name);checks.push(name);};
 const login=async user=>{if(!q('#workspace').classList.contains('hidden')){await wait(()=>!q('#switch').disabled);q('#switch').click();}q('#token').value=credentials[user];q('#loginform').requestSubmit();await wait(()=>!q('#workspace').classList.contains('hidden'));};
 const title='문서 기한의 적용시점 검토 '+Date.now().toString().slice(-6);
 const open=async()=>{const item=[...document.querySelectorAll('#list .change')].find(button=>button.querySelector('strong').textContent===title);if(!item)throw Error('created request missing');item.click();await wait(()=>q('#detail-heading')?.textContent===title);};
 await login('aurora-analyst');
 assert(q('#scope').checkValidity(),'new request has valid initial scope');
 q('#newchange').click();q('#new-title-input').value=title;
 q('#scope').value=[...q('#scope').options].find(option=>option.text.includes('DOCUMENT_WINDOW_DAYS')).value;
 q('#newform').requestSubmit();await wait(()=>q('#evalform')&&q('#detail-heading')?.textContent===title);
 assert(!q('#newdialog').open&&q('#submitbtn').disabled,'created draft blocks premature submission');
 for(const [index,claim,date] of [[1,30,'2026-06-30'],[2,20,'2026-07-01']]){
  q('#claim-days').value=String(claim);q('#basis-date').value=date;q('#evalform').requestSubmit();await wait(()=>document.querySelectorAll('.result.pass').length===index&&!q('#switch').disabled);
 }
 assert(!q('#submitbtn').disabled,'two distinct rules permit review request');
 q('#submitbtn').click();await wait(()=>q('#detail [data-state=PENDING_DOMAIN_REVIEW]'));
 await login('aurora-reviewer');await open();await wait(()=>q('#domainapprove'));
 assert(q('#newchange').disabled&&!q('#evalform'),'reviewer cannot create or evaluate');
 q('#domainapprove').click();assert(q('#decisiondialog').open&&document.activeElement===q('#decision-reason'),'Tabler-styled native decision dialog focuses reason');
 q('#decision-reason').value='   근거검토중   ';q('#decisionform').requestSubmit();
 assert(q('#decisionmsg').textContent.includes('8–500')&&q('#decisiondialog').open,'trimmed short reason rejected');
 q('#decision-reason').value='상반기와 하반기 규정의 적용 시점 및 검증 근거를 확인했습니다.';
 q('#decisionform').requestSubmit();await wait(()=>q('#detail [data-state=PENDING_RELEASE]'));
 await login('aurora-approver');await open();await wait(()=>q('#releaseapprove'));
 const original=window.fetch;let dropped=false;
 window.fetch=async(path,options={})=>{const response=await original(path,options);if(String(path).endsWith('/release-decision')&&options.method==='POST'){requests.push({path:String(path),body:options.body,key:options.headers['Idempotency-Key'],status:response.status});if(!dropped&&response.ok){dropped=true;throw new TypeError('Synthetic committed response loss');}}return response;};
 try{
  q('#releaseapprove').click();assert(q('#decision-warning').textContent.includes('실제 배포'),'demo-only approval clearly described');
  q('#decision-reason').value='현업 검토와 합성 규정 검증 및 감사 근거의 일치를 확인했습니다.';
  q('#decisionform').requestSubmit();await wait(()=>!q('#recovery').classList.contains('hidden')&&!q('#switch').disabled);
  await login('aurora-analyst');assert(q('#recovery').classList.contains('hidden'),'another actor cannot see pending recovery');
  await login('aurora-approver');assert(!q('#recovery').classList.contains('hidden'),'original actor retains recovery across role switching');
  q('#retryrequest').click();await wait(()=>q('#recovery').classList.contains('hidden')&&!q('#switch').disabled);await open();
  await wait(()=>{try{return JSON.parse(q('#evidence').textContent).matches_approval===true;}catch{return false;}});
  assert(requests.length===2&&requests[0].key===requests[1].key&&requests[0].body===requests[1].body,'exact request key/body/revision recovered after committed response loss');
  const evidence=JSON.parse(q('#evidence').textContent);
  assert(evidence.record_integrity_verified&&evidence.audit_chain_verified&&evidence.matches_approval&&!evidence.real_release,'three-person approval and evidence agree');
  assert(!q('#detail [data-mutation]'),'terminal change offers no mutation');
  return {title,passed:checks.length,checks,requests,change_id:evidence.content.change_id,revision:6,userAgent:navigator.userAgent,tablerLoaded:[...document.styleSheets].some(sheet=>sheet.href?.includes('tabler-1.7.3')),externalResources:performance.getEntriesByType('resource').filter(resource=>new URL(resource.name).origin!==location.origin).map(resource=>resource.name)};
 }finally{window.fetch=original;}
}
