import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-edit-20261009',api='http://127.0.0.1:8006';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(45000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const report=process.argv.includes('--resume')?JSON.parse(await readFile(root+'/native.json','utf8')):{};
report.errors=errors;delete report.failure;const save=()=>writeFile(root+'/native.json',JSON.stringify(report,null,2));
const hash=v=>createHash('sha256').update(v).digest('hex');const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json()}
async function post(path,data){const r=await page.request.post(api+path,{data,timeout:180000});assert(r.ok(),await r.text());return r.json()}
async function send(content){
 const sent=page.waitForResponse(r=>r.url().endsWith(`/sessions/${report.session.id}/messages`)&&r.request().method()==='POST',{timeout:180000});
 await page.getByRole('textbox',{name:'消息',exact:true}).fill(content);await page.getByRole('button',{name:'发送',exact:true}).click();
 const r=await sent;assert(r.ok(),await r.text());return r.json();
}
async function waitRun(except){
 for(let i=0;i<300;i++){
  const tasks=await get(`/sessions/${report.session.id}/tasks`);
  const task=tasks.filter(t=>t.intentType==='frontend_change').at(-1);const run=task?.taskRuns.at(-1);
  if(run&&run.id!==except){
   if(['failed','interrupted','cancelled'].includes(run.state))throw new Error(JSON.stringify(run));
   if(run.state==='completed')return {task,run};
  }
  if(i%15===0)console.log(JSON.stringify({stage:'waiting-native',iteration:i,run:run?.id,state:run?.state}));
  await pause(2000);
 }
 throw new Error('Native run did not finish within the bounded wait');
}
async function selectDiff(){
 await page.getByRole('button',{name:/^成果/}).click();
 await page.getByRole('region',{name:'会话成果',exact:true}).getByRole('button').filter({hasText:'代码变更'}).last().click();
}
try{
 const ws=await get('/workspaces/demo');report.workspaceId=ws.id;
 if(!report.first)report.session=await post(`/workspaces/${ws.id}/sessions`,{title:'受限源码编辑 · 原生续接验证'});await save();
 await page.goto('http://127.0.0.1:3000/?session='+report.session.id,{waitUntil:'domcontentloaded'});
 if(!report.first)report.firstMessage=await send('@native-group-20261008 @created-front-731 请只创建一个 frontend_change 任务并执行：阅读 apps/demo/src/App.tsx，只把页面主标题改为 Manual Edit Baseline 732，保留其他代码和行为。');
 const first=report.first??await waitRun();assert.equal(first.run.adapterType,'claude_code');report.first=first;await save();
 const sourcePath=report.session.worktreePath+'/apps/demo/src/App.tsx';
 if(!report.operation){
 const original=await readFile(sourcePath,'utf8');assert(original.includes('Manual Edit Baseline 732'));
 report.firstDiffs=await get(`/task-runs/${first.run.id}/diffs`);report.firstDiffHash=hash(JSON.stringify(report.firstDiffs));
 await page.reload({waitUntil:'domcontentloaded'});await selectDiff();
 await page.getByRole('button',{name:'编辑完整源码 / 应用补丁',exact:true}).click();
 await page.getByRole('button',{name:'读取完整源码',exact:true}).click();
 await page.locator('.monaco-editor').first().waitFor();report.localMonaco=true;
 await page.getByRole('button',{name:'纯文本模式',exact:true}).click();
 const input=page.getByRole('textbox',{name:'完整源码',exact:true});
 assert.equal((await input.inputValue()).replaceAll('\r\n','\n'),original.replaceAll('\r\n','\n'));
 const edited=original.replace('Manual Edit Baseline 732','Manual Edit User 732');await input.fill(edited);
 await page.getByRole('button',{name:'检查并生成差异',exact:true}).click();
 const proposed=page.getByLabel('拟应用差异',{exact:true});await proposed.waitFor();
 assert((await proposed.innerText()).includes('+'));
 assert.equal(await readFile(sourcePath,'utf8'),original,'Preparation changed files');
 await page.screenshot({path:root+'/proposed-light.png',fullPage:true});
 const light=page.getByRole('button',{name:'切换到暗色模式',exact:true});if(await light.count())await light.click();
 await page.screenshot({path:root+'/proposed-dark.png',fullPage:true});
 for(const width of [390,320]){
  await page.setViewportSize({width,height:900});await proposed.scrollIntoViewIfNeeded();
  const controls=await page.getByRole('region',{name:'用户代码编辑',exact:true}).evaluate(el=>Array.from(el.querySelectorAll('button,select,textarea')).map(e=>({tag:e.tagName,label:e.textContent?.slice(0,32),x:e.getBoundingClientRect().x,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width})));
  assert(controls.every(c=>c.x>=-1&&c.right<=width+1),JSON.stringify(controls));report['controls'+width]=controls;
  await page.screenshot({path:root+`/proposed-${width}-dark.png`,fullPage:true});
 }
 await page.setViewportSize({width:1440,height:1000});
 const applying=page.waitForResponse(r=>/\/code-edits\/[^/]+\/apply$/.test(r.url())&&r.request().method()==='POST');
 await page.getByRole('button',{name:'应用以上差异',exact:true}).click();const applied=await applying;assert(applied.ok(),await applied.text());
 report.operation=await applied.json();assert.equal(report.operation.state,'applied');await save();
 const after=await readFile(sourcePath,'utf8');assert(after.includes('Manual Edit User 732'));report.appliedSourceSha256=hash(after);await writeFile(root+'/applied-source.txt',after);
 assert.equal(hash(JSON.stringify(await get(`/task-runs/${first.run.id}/diffs`))),report.firstDiffHash);
 report.preview=await post(`/task-runs/${first.run.id}/preview`,{});assert.equal(report.preview.healthStatus,'healthy');
 await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('button',{name:/^成果/}).click();
 await page.getByRole('region',{name:'会话成果',exact:true}).getByRole('button').filter({hasText:'网页预览'}).last().click();
 await page.frameLocator('iframe[title="Vite React 预览"]').getByRole('heading',{name:'Manual Edit User 732',exact:true}).waitFor();
 await page.getByTestId('user-revision-notice').waitFor();await page.screenshot({path:root+'/applied-preview.png',fullPage:true});
 const bad=await page.request.post(api+`/task-runs/${first.run.id}/diffs`);report.oldDiffRecollect={status:bad.status(),body:await bad.text()};
 }
 report.secondMessage=await send('@native-group-20261008 @created-front-731 请只创建一个 frontend_change 任务并执行：先阅读 apps/demo/src/App.tsx，保留当前主标题 Manual Edit User 732 和其他现有内容，只在主标题下新增一个段落，显示 Native Continuation 732。');
 const second=await waitRun(first.run.id);assert.equal(second.run.adapterType,'claude_code');report.second=second;await save();
 report.secondDiffs=await get(`/task-runs/${second.run.id}/diffs`);const diff=report.secondDiffs.at(-1);
 assert(diff.baseRef.startsWith('filesystem-snapshot:'),JSON.stringify(diff));
 assert(diff.patchText.includes('Native Continuation 732'));
 assert(!diff.patchText.split('\n').some(line=>line.startsWith('+')&&line.includes('Manual Edit User 732')),'Manual edit was credited as new Agent output');
 const finalSource=await readFile(sourcePath,'utf8');assert(finalSource.includes('Manual Edit User 732'));assert(finalSource.includes('Native Continuation 732'));
 report.finalSourceSha256=hash(finalSource);await writeFile(root+'/continued-source.txt',finalSource);
 report.continuedPreview=await post(`/task-runs/${second.run.id}/preview`,{});assert.equal(report.continuedPreview.healthStatus,'healthy');
 const previewPage=await browser.newPage();await previewPage.goto(report.continuedPreview.url);await previewPage.getByRole('heading',{name:'Manual Edit User 732',exact:true}).waitFor();await previewPage.getByText('Native Continuation 732',{exact:true}).waitFor();await previewPage.screenshot({path:root+'/continued-preview.png'});await previewPage.close();
 assert.equal(hash(JSON.stringify(await get(`/task-runs/${first.run.id}/diffs`))),report.firstDiffHash);
 assert.deepEqual(errors,[]);report.passed=true;console.log(JSON.stringify({passed:true,sessionId:report.session.id,operationId:report.operation.id,runId:second.run.id}));
}catch(error){report.failure=String(error);console.error(error);process.exitCode=1;await page.screenshot({path:root+'/failure.png',fullPage:true}).catch(()=>{})}
finally{await save();await browser.close()}
