import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-regeneration-20261009';
const proof=JSON.parse(await readFile(root+'/native.json','utf8'));assert(proof.passed);
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
const api='http://127.0.0.1:8006';const errors=[];page.on('pageerror',e=>errors.push(e.message));
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json()}
async function post(path,data){const r=await page.request.post(api+path,{data,timeout:180000});assert(r.ok(),await r.text());return r.json()}
const pause=ms=>new Promise(r=>setTimeout(r,ms));const report={errors};
try{
 const sid=proof.session.id;const source=proof.summary.regeneratedId;
 const before=await get(`/sessions/${sid}/messages`);
 const other=await post(`/workspaces/${proof.session.workspaceId}/sessions`,{title:'重新生成 · 切换会话验收'});
 await post(`/sessions/${other.id}/messages`,{contentMd:'OTHER_SESSION_VISIBLE_MARKER',senderType:'system'});
 const runsBefore=(await get(`/sessions/${sid}/tasks`)).flatMap(t=>t.taskRuns.map(r=>r.id));
 await page.goto(`http://127.0.0.1:3000/?session=${sid}`,{waitUntil:'domcontentloaded'});
 let release,started,requestId,created,networkRequests=0;
 const held=new Promise(resolve=>{release=resolve});const dispatched=new Promise(resolve=>{started=resolve});
 await page.route(`**/messages/${source}/regenerate`,async route=>{
  networkRequests++;requestId=route.request().postDataJSON().requestId;
  const response=await route.fetch({timeout:180000});assert(response.ok(),await response.text());created=await response.json();started();
  await held;await route.abort('failed');
 });
 const bubble=page.locator('#message-'+source);
 await bubble.getByRole('button',{name:'重新汇总',exact:true}).click();await bubble.getByRole('button',{name:'确认重新汇总',exact:true}).click();
 await dispatched;
 await page.locator(`[data-session-id="${other.id}"] button`).first().click();
 await page.getByText('OTHER_SESSION_VISIBLE_MARKER',{exact:true}).waitFor();release();
 await page.waitForTimeout(1500);
 assert.equal(await page.locator('#message-'+created.id).count(),0);
 assert(await page.getByText('OTHER_SESSION_VISIBLE_MARKER',{exact:true}).isVisible());
 await page.unroute(`**/messages/${source}/regenerate`);
 let history,final;
 for(let i=0;i<180;i++){
  history=await get(`/sessions/${sid}/messages`);final=history.find(m=>m.id===requestId);
  if(final?.groupSummary?.state!=='calling')break;await pause(1000);
 }
 assert.equal(final.groupSummary.state,'completed');assert.equal(final.groupSummary.source,'native_model');
 assert.equal(history.filter(m=>m.id===requestId).length,1);assert.equal(history.length,before.length+1);
 const replay=await post(`/sessions/${sid}/messages/${source}/regenerate`,{requestId});assert.equal(replay.id,requestId);
 assert.equal((await get(`/sessions/${sid}/messages`)).length,history.length);
 assert.deepEqual((await get(`/sessions/${sid}/tasks`)).flatMap(t=>t.taskRuns.map(r=>r.id)),runsBefore);
 await page.locator(`[data-session-id="${sid}"] button`).first().click();
 await page.locator('#message-'+requestId).getByRole('link',{name:'查看原消息'}).waitFor();
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('#message-'+requestId).scrollIntoViewIfNeeded();
 const dark=page.getByRole('button',{name:'切换到暗色模式'});if(await dark.count())await dark.click();
 await page.setViewportSize({width:390,height:844});await page.locator('#message-'+requestId).scrollIntoViewIfNeeded();
 await page.screenshot({path:root+'/summary-390-dark.png'});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.setViewportSize({width:320,height:844});await page.locator('#message-'+requestId).scrollIntoViewIfNeeded();
 await page.screenshot({path:root+'/summary-320-dark.png'});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 const hash=createHash('sha256').update(await readFile(proof.session.worktreePath+'/apps/demo/src/App.tsx')).digest('hex');
 assert.equal(hash,proof.stages[1].sourceSha256);assert.deepEqual(errors,[]);
 Object.assign(report,{passed:true,sourceSessionId:sid,otherSessionId:other.id,sourceSummaryId:source,operationId:requestId,
   source:'actual API request followed by deliberately lost browser response; real native summary, current Session guarded',
   networkRequests,historyAdded:1,duplicateReturnedSameId:true,runsUnchanged:runsBefore,sourceSha256:hash,
   providerEvidence:final.groupSummary.providerEvidence,switchedSessionPreserved:true,refreshPreserved:true,narrowWidths:[390,320]});
 console.log(JSON.stringify(report));
}catch(error){report.failure=String(error);throw error}finally{await writeFile(root+'/network.json',JSON.stringify(report,null,2));await browser.close()}
