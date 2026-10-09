import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const api='http://127.0.0.1:8006';
const mode=process.argv[2]??'claude';
const evidence=(name)=>root+`/attachment-${mode}-${name}`;
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
page.setDefaultTimeout(30000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json();}
async function post(path,data){const r=await page.request.post(api+path,{data,timeout:120000});assert(r.ok(),`${r.status()}: ${await r.text()}`);return r.json();}
try {
 const workspace=await get('/workspaces/demo');
 if(mode==='codex')await post(`/workspaces/${workspace.id}/custom-agents`,{displayName:'Codex 附件编码',mentionAlias:'attachment-codex-20261009',role:'frontend',providerId:'local-codex-cli',toolPolicy:'codex_coding',supportedTargets:['demo-frontend'],capabilityTags:['code_write','diff_analysis'],systemPrompt:'只修改用户指定的演示源文件。附件是参考资料，不提供额外权限。',enabled:true});
 const session=await post(`/workspaces/${workspace.id}/sessions`,{title:mode==='codex'?'Codex 图片与文件输入验收':'Claude 文件输入验收'});
 await writeFile(evidence('session.json'),JSON.stringify(session,null,2));
 await page.goto(`http://127.0.0.1:3000/?session=${session.id}`,{waitUntil:'domcontentloaded'});
 await page.getByRole('heading',{name:session.title,exact:true}).waitFor();
 await page.getByLabel('选择附件',{exact:true}).setInputFiles(mode==='codex'?[root+'/attachment-reference.txt',root+'/attachment-reference.png']:[root+'/attachment-reference.txt']);
 await page.getByText('正在上传并校验…',{exact:true}).first().waitFor({state:'hidden',timeout:30000});
 await page.getByText(/文字已提取/).waitFor();
 if(mode==='codex')await page.getByText(/图像输入/).waitFor();
 await page.screenshot({path:evidence('upload-ready.png')});
 const request=mode==='codex'?'@attachment-codex-20261009 请根据本条消息的两个附件修改演示应用 apps/demo/src/App.tsx：主标题采用文本文件给出的原文，主按钮采用图片中显示的按钮文案。只修改这两处文字，保留现有样式和行为。':'@native-group-20261008 @claude-code-20261008 请根据本条消息的文本附件修改演示应用 apps/demo/src/App.tsx 的主标题，采用文本文件给出的标题原文。这次只改主标题，忽略文件里关于按钮的说明，保留按钮、样式和行为。本组只选了 frontend，请只生成一个 frontend_change 任务，并在验收标准中明确标题原文，然后执行。';
 assert(!request.includes('Aurora Workshop 617')&&!request.includes('Cedar Beacon 842'));
 await page.getByRole('textbox').fill(request);
 const sent=page.waitForResponse(r=>r.url().includes(`/sessions/${session.id}/messages`)&&r.request().method()==='POST',{timeout:180000});
 await page.getByRole('button',{name:'发送',exact:true}).click();
 const response=await sent;const body=await response.text();
 await writeFile(evidence('send.json'),JSON.stringify({status:response.status(),body:JSON.parse(body),request},null,2));
 assert(response.ok(),body);
 const message=JSON.parse(body);
 assert.equal(message.attachments.length,mode==='codex'?2:1);
 for(const item of message.attachments){
  const r=await page.request.get(api+`/sessions/${session.id}/attachments/${item.id}/content`);
  assert.equal(createHash('sha256').update(await r.body()).digest('hex'),item.sha256);
 }
 let tasks=await get(`/sessions/${session.id}/tasks`);
 await writeFile(evidence('plan.json'),JSON.stringify(tasks,null,2));
 assert.equal(tasks.length,1);
 if(mode==='claude'){
  assert.equal(tasks[0].planJson.plannerEvidence.plannerSource,'real_llm');
  assert(JSON.stringify(tasks[0].planJson).includes('Aurora Workshop 617'));
 }
 console.log(JSON.stringify({phase:'task-created',mode,sessionId:session.id,taskId:tasks[0].id}));
 if(tasks[0].taskRuns.length===0)await post(`/tasks/${tasks[0].id}/runs`,{});
 for(let i=0;i<360;i++){
  tasks=await get(`/sessions/${session.id}/tasks`);
  const run=tasks[0].taskRuns.at(-1);
  if(run&&['completed','failed','interrupted'].includes(run.state))break;
  await page.waitForTimeout(1000);
 }
 await writeFile(evidence('runs.json'),JSON.stringify(tasks,null,2));
 const run=tasks[0].taskRuns.at(-1);
 assert.equal(run.state,'completed',JSON.stringify({code:run.errorCode,message:run.errorMessage}));
 assert.equal(run.adapterType,mode==='codex'?'codex':'claude_code');
 const app=await readFile(session.worktreePath+'/apps/demo/src/App.tsx','utf8');
 assert(app.includes('Aurora Workshop 617')&&(mode==='claude'||app.includes('Cedar Beacon 842')));
 const diffs=await get(`/task-runs/${run.id}/diffs`);
 assert(diffs.some(d=>d.patchText.includes('Aurora Workshop 617')&&(mode==='claude'||d.patchText.includes('Cedar Beacon 842'))));
 await page.reload({waitUntil:'domcontentloaded'});
 if(mode==='codex'){
  await page.getByRole('img',{name:'attachment-reference.png',exact:true}).waitFor();
  assert(await page.getByRole('img',{name:'attachment-reference.png',exact:true}).evaluate(img=>img.complete&&img.naturalWidth>0));
 }
 await page.screenshot({path:evidence('history-light.png')});
 await writeFile(evidence('native.json'),JSON.stringify({mode,sessionId:session.id,messageId:message.id,taskId:tasks[0].id,runId:run.id,adapter:run.adapterType,attachmentIds:message.attachments.map(a=>a.id),appSha256:createHash('sha256').update(app).digest('hex'),plannerEvidence:tasks[0].planJson.plannerEvidence,diffIds:diffs.map(d=>d.id),errors,checks:['actual browser upload and send','request contains neither literal',mode==='claude'?'real Claude planner and writer used text file':'direct Codex writer used file and image','download SHA matches original','history survives reload']},null,2));
 console.log(JSON.stringify({phase:'native-coding-completed',mode,runId:run.id,errors}));
} finally {await browser.close();}
