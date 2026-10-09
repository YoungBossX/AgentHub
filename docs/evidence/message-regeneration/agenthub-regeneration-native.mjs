import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash,randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-regeneration-20261009';
const api='http://127.0.0.1:8006';
const prefix='Regeneration Atlas 928';
const request='@native-group-20261008 @claude-code-20261008 请读取文本附件给出的标题前缀。每次处理本请求时，先读取 apps/demo/src/App.tsx 中当前主标题：若它已是附件前缀加空格加一个整数，则将整数加 1；否则从 1 开始。将主标题设为这个前缀和新序号，只改标题文字，保留其他文字、样式和行为。本组只选了 frontend，请只创建一个 frontend_change 任务并执行；验收标准要求先读取当前标题再计算序号，不要固定序号。';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(30000);
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const report={request,errors,stages:[]};
const save=()=>writeFile(root+'/native.json',JSON.stringify(report,null,2));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const hash=value=>createHash('sha256').update(value).digest('hex');
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json()}
async function post(path,data){const r=await page.request.post(api+path,{data,timeout:180000});assert(r.ok(),await r.text());return r.json()}
try{
 const workspace=await get('/workspaces/demo');
 const session=await post(`/workspaces/${workspace.id}/sessions`,{title:'消息重新生成 · 原生执行验收'});report.session=session;await save();
 const file=root+'/regeneration-reference.txt';await writeFile(file,'标题前缀：'+prefix+'\n本附件只提供前缀；序号应根据当前源文件计算。\n');
 await page.goto(`http://127.0.0.1:3000/?session=${session.id}`,{waitUntil:'domcontentloaded'});
 await page.getByLabel('选择附件',{exact:true}).setInputFiles(file);
 await page.getByText(/文字已提取/).waitFor();
 await page.getByRole('textbox').fill(request);
 const sent=page.waitForResponse(r=>r.url().endsWith(`/sessions/${session.id}/messages`)&&r.request().method()==='POST',{timeout:240000});
 await page.getByRole('button',{name:'发送',exact:true}).click();
 const first=await sent;assert(first.ok(),await first.text());const firstRequest=await first.json();report.originalMessage=firstRequest;await save();
 assert(!request.includes(prefix));
 async function completed(requestId,number){
  let tasks;
  for(let i=0;i<360;i++){
   tasks=(await get(`/sessions/${session.id}/tasks`)).filter(t=>t.createdByMessageId===requestId);
   if(tasks.length&&tasks.every(t=>t.taskRuns.length&&['completed','failed','interrupted'].includes(t.taskRuns.at(-1).state)))break;
   await pause(1000);
  }
  // Older public Task response names are checked explicitly, never guessed.
  if(!tasks?.length){await writeFile(root+'/tasks-debug.json',JSON.stringify(await get(`/sessions/${session.id}/tasks`),null,2));throw Error('No tasks bound to request '+requestId)}
  assert.equal(tasks.length,1);const task=tasks[0],run=task.taskRuns.at(-1);
  assert.equal(run.state,'completed',JSON.stringify({state:run.state,error:run.errorCode}));assert.equal(run.adapterType,'claude_code');
  assert.equal(task.planJson.plannerEvidence.plannerSource,'real_llm');
  const source=await readFile(session.worktreePath+'/apps/demo/src/App.tsx','utf8');
  assert(source.includes(prefix+' '+number),source);
  const diffs=await get(`/task-runs/${run.id}/diffs`);assert(diffs.some(d=>d.patchText.includes(prefix+' '+number)));
  const preview=await post(`/task-runs/${run.id}/preview`,{});assert.equal(preview.healthStatus,'healthy');
  const previewPage=await browser.newPage();await previewPage.goto(preview.url);
  await previewPage.getByRole('heading',{name:prefix+' '+number,exact:true}).waitFor();
  await previewPage.screenshot({path:root+`/native-preview-${number}.png`});await previewPage.close();
  const evidence={number,requestId,taskId:task.id,runId:run.id,adapter:run.adapterType,sourceSha256:hash(source),diffs:diffs.map(d=>({id:d.id,patchSha256:hash(d.patchText)})),previewId:preview.id,
    plannerEvidence:Object.fromEntries(['providerId','plannerSource','status','outputSha256'].map(k=>[k,task.planJson.plannerEvidence[k]]))};
  report.stages.push(evidence);await writeFile(root+`/native-source-${number}.txt`,source);await save();
  console.log(JSON.stringify({stage:'completed',...evidence}));
 }
 await completed(firstRequest.id,1);
 let messages=await get(`/sessions/${session.id}/messages`);
 const plan=messages.find(m=>m.parentMessageId===firstRequest.id&&m.messageKind==='plan');assert(plan?.regenerationAction?.available);
 report.originalPlan=plan;await save();
 await page.reload({waitUntil:'domcontentloaded'});
 const bubble=page.locator('#message-'+plan.id);
 await bubble.getByRole('button',{name:'重新生成',exact:true}).click();
 await page.screenshot({path:root+'/confirm-light.png'});
 assert((await bubble.textContent()).includes('当前代码'));
 const regenerated=page.waitForResponse(r=>r.url().endsWith(`/messages/${plan.id}/regenerate`)&&r.request().method()==='POST',{timeout:240000});
 await bubble.getByRole('button',{name:'确认重新生成',exact:true}).click();
 const answer=await regenerated;assert(answer.ok(),await answer.text());const next=await answer.json();report.regeneratedMessage=next;await save();
 assert.equal(next.contentMd,firstRequest.contentMd);assert.equal(next.attachments[0].id,firstRequest.attachments[0].id);
 assert.equal(next.regeneration.sourceMessageId,plan.id);assert.equal(next.regeneration.state,'submitted');
 await completed(next.id,2);
 // Regenerate only the group's completed summary, never rerun the coding task.
 let summary;
 for(let i=0;i<150;i++){
  messages=await get(`/sessions/${session.id}/messages`);
  summary=messages.find(m=>m.parentMessageId===next.id&&m.messageKind==='group_summary'&&m.groupSummary?.current&&m.groupSummary?.state==='completed');
  if(summary)break;await pause(1000);
 }
 assert(summary,JSON.stringify(messages.map(m=>({kind:m.messageKind,state:m.groupSummary?.state}))));
 const runsBefore=(await get(`/sessions/${session.id}/tasks`)).flatMap(t=>t.taskRuns.map(r=>r.id));
 await page.reload({waitUntil:'domcontentloaded'});
 const summaryBubble=page.locator('#message-'+summary.id);
 await summaryBubble.getByRole('button',{name:'重新汇总',exact:true}).click();
 const again=page.waitForResponse(r=>r.url().endsWith(`/messages/${summary.id}/regenerate`)&&r.request().method()==='POST',{timeout:180000});
 await summaryBubble.getByRole('button',{name:'确认重新汇总',exact:true}).click();
 const receipt=await again;assert(receipt.ok(),await receipt.text());const renewed=await receipt.json();
 let final;
 for(let i=0;i<150;i++){
  messages=await get(`/sessions/${session.id}/messages`);final=messages.find(m=>m.id===renewed.id);
  if(final?.groupSummary?.state!=='calling')break;await pause(1000);
 }
 assert.equal(final.groupSummary.state,'completed');assert.equal(final.groupSummary.source,'native_model');
 assert.deepEqual((await get(`/sessions/${session.id}/tasks`)).flatMap(t=>t.taskRuns.map(r=>r.id)),runsBefore);
 assert.equal(final.groupSummary.evidence.inputFingerprint,summary.groupSummary.evidence.inputFingerprint);
 assert.equal(hash(await readFile(session.worktreePath+'/apps/demo/src/App.tsx')),report.stages[1].sourceSha256);
 report.summary={originalId:summary.id,regeneratedId:final.id,source:final.groupSummary.source,outputSha256:final.groupSummary.providerEvidence.outputSha256,inputFingerprint:final.groupSummary.evidence.inputFingerprint,runsUnchanged:runsBefore};
 assert.equal(messages.find(m=>m.id===plan.id).contentMd,plan.contentMd);
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('#message-'+final.id).getByRole('link',{name:'查看原消息'}).waitFor();
 await page.locator('#message-'+final.id).scrollIntoViewIfNeeded();await page.screenshot({path:root+'/history-light.png'});
 await page.getByRole('button',{name:'切换到暗色模式'}).click();await pause(100);await page.screenshot({path:root+'/history-dark.png'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:root+'/history-390-dark.png'});
 assert.deepEqual(errors,[]);report.passed=true;await save();
 console.log(JSON.stringify({passed:true,sessionId:session.id,summary:report.summary}));
}catch(error){report.failure=String(error);await save();throw error}finally{await browser.close()}
