// Run in an authenticated disposable browser session with at least two changes.
// Tests the actual page handlers, delays real responses, then disconnects.
async () => {
 const checks=[];
 if(!document.querySelector('#workspace')||document.querySelector('#workspace').classList.contains('hidden')||![...document.styleSheets].some(sheet=>sheet.href?.includes('tabler-1.7.3')))throw Error('Authenticated Tabler workspace absent: checks NOT RUN');
 const assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name);};
 const wait=async predicate=>{for(let n=0;n<150;n++){if(predicate())return;await new Promise(r=>setTimeout(r,20));}throw Error('DOM wait timed out');};
 const node=id=>document.getElementById(id);
 const unlabelled=[...document.querySelectorAll('input,select,textarea')].filter(el=>el.getClientRects().length&&!el.labels?.length&&!el.getAttribute('aria-label'));
 assert(unlabelled.length===0,'visible controls have accessible labels');
 assert(document.querySelectorAll('[aria-live]').length>=4,'status and error containers have live-region semantics');
 assert(!localStorage.length&&!sessionStorage.length,'tokens and recovery are absent from persistent browser storage');
 node('search').value='synthetic-nonexistent-search';node('search').dispatchEvent(new Event('input'));
 assert(node('list').querySelectorAll('.change').length===0&&node('list').textContent.includes('검색 결과'),'search empty state');
 node('search').value='';node('search').dispatchEvent(new Event('input'));
 node('statusfilter').value='REJECTED';node('statusfilter').dispatchEvent(new Event('change'));
 assert([...node('list').querySelectorAll('[data-state]')].every(el=>el.dataset.state==='REJECTED'),'status filter contains only selected state');
 node('statusfilter').value='ALL';node('statusfilter').dispatchEvent(new Event('change'));
 const items=[...node('list').querySelectorAll('.change')];
 assert(items.length>=2,'disposable fixture has at least two changes');
 const first=items[0].dataset.id,second=items[1].dataset.id,secondTitle=items[1].querySelector('strong').textContent;
 const original=window.fetch;let release;
 const selectedEvidence=id=>{try{return JSON.parse(node('evidence').textContent).content.change_id===id;}catch{return false;}};
 try {
  window.fetch=async(path,options)=>{const response=await original(path,options);if(path===`/api/changes/${first}`)await new Promise(resolve=>{release=resolve;});return response;};
  node('list').querySelectorAll('.change')[0].click();await wait(()=>release);
  node('list').querySelectorAll('.change')[1].click();await wait(()=>selectedEvidence(second));
  release();release=null;await new Promise(r=>setTimeout(r,80));
  assert(selectedEvidence(second)&&node('detail-heading').textContent===secondTitle,'late detail cannot overwrite newer selection');
  window.fetch=async(path,options)=>{const response=await original(path,options);if(path===`/api/changes/${first}/evidence`)await new Promise(resolve=>{release=resolve;});return response;};
  node('list').querySelectorAll('.change')[0].click();await wait(()=>release);
  node('list').querySelectorAll('.change')[1].click();await wait(()=>selectedEvidence(second));
  release();release=null;await new Promise(r=>setTimeout(r,80));
  assert(selectedEvidence(second)&&node('detail-heading').textContent===secondTitle,'late evidence cannot overwrite newer selection');
  window.fetch=async(path,options)=>String(path).endsWith('/evidence')?new Response(JSON.stringify({detail:{code:'FORBIDDEN',message:'Synthetic denied evidence request'}}),{status:403,headers:{'Content-Type':'application/json'}}):original(path,options);
  node('getevidence').click();await wait(()=>node('evidencemsg').textContent.includes('FORBIDDEN'));
  assert(node('evidence').textContent===''&&node('evidence-disclosure').classList.contains('hidden'),'evidence request failure clears previously displayed payload');
  window.fetch=async(path,options)=>{const response=await original(path,options);if(path==='/api/changes')await new Promise(resolve=>{release=resolve;});return response;};
  node('refresh').click();await wait(()=>release);node('switch').click();release();release=null;await new Promise(r=>setTimeout(r,100));
  assert(!node('login').classList.contains('hidden')&&node('workspace').classList.contains('hidden')&&node('list').textContent==='','disconnect invalidates pending list response');
  assert(document.activeElement===node('token'),'role switch focuses token input');
 } finally {window.fetch=original;if(release)release();}
 return {passed:checks.length,checks,userAgent:navigator.userAgent,viewport:{width:innerWidth,height:innerHeight},note:'403 was a controlled browser response; other reads used the temporary real server. No production data.'};
}
