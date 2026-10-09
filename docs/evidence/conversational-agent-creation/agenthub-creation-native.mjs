import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-creation-20261009',api='http://127.0.0.1:8006';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(30000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const report={errors,generations:[]};const save=()=>writeFile(root+'/native.json',JSON.stringify(report,null,2));
const hash=v=>createHash('sha256').update(v).digest('hex');const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json()}
async function post(path,data){const r=await page.request.post(api+path,{data,timeout:180000});assert(r.ok(),await r.text());return r.json()}
const roleKeys=['agentProfileId','providerId','adapterType','mode','enabled','fallbackPolicy','providerPresetId','protocol','model','baseUrl','timeoutSeconds','apiKeyEnv','systemPrompt'];
const strip=roles=>Object.fromEntries(Object.entries(roles).map(([role,value])=>[role,Object.fromEntries(roleKeys.map(k=>[k,value[k]??null]))]));
let originalRoles=null,workspace;
try{
 workspace=await get('/workspaces/demo');report.workspaceId=workspace.id;
 const beforeDirectory=await get(`/workspaces/${workspace.id}/agent-directory`);report.beforeProfileIds=beforeDirectory.entries.map(e=>e.id);
 const runtime=await get(`/workspaces/${workspace.id}/runtime-config`);originalRoles=strip(runtime.roles);
 await page.goto('http://127.0.0.1:3000/settings/agents#create-agent',{waitUntil:'domcontentloaded'});
 const builder=page.locator('#create-agent');await builder.getByRole('button',{name:'打开创建对话'}).click();
 const request='创建一个前端助手，名称“对话生成的界面助手”，@ 别名 created-front-731。使用 Claude Code 的受限文件编辑工具，只负责已注册 demo-frontend。System Prompt 约定：先阅读现有代码，只完成用户指定修改，保留其他行为；当用户要求修改主标题但没指定标题文案时，必须使用 Created Agent 731。用中文解释结果。不要保存或执行任务，先给出可编辑草稿。';
 await builder.getByLabel('描述你想创建的 Agent',{exact:true}).fill(request);
 const disabled=page.waitForResponse(r=>r.url().endsWith('/agent-creation')&&r.request().method()==='POST');
 await builder.getByRole('button',{name:'生成配置草稿'}).click();const blocked=await disabled;
 assert.equal(blocked.status(),409);await builder.getByRole('alert').waitFor();
 report.disabledProvider={status:blocked.status(),detail:await blocked.json()};
 const coordinator=beforeDirectory.entries.find(e=>e.role==='orchestrator'&&e.entryType==='built_in');assert(coordinator);
 const configResponse=await page.request.put(api+`/workspaces/${workspace.id}/runtime-config`,{data:{roles:{...originalRoles,planner:{...originalRoles.planner,enabled:true,providerId:'claude-cli-planner',adapterType:'claude_cli',agentProfileId:coordinator.id,mode:'read_only',timeoutSeconds:90}}}});
 assert(configResponse.ok(),await configResponse.text());
 async function generate(button){
  const pending=page.waitForResponse(r=>r.url().endsWith('/agent-creation')&&r.request().method()==='POST',{timeout:180000});
  await builder.getByRole('button',{name:button,exact:true}).click();const response=await pending;
  const value=await response.json();report.generations.push({status:response.status(),...value});await save();assert(response.ok(),JSON.stringify(value));
  assert.equal(value.kind,'draft');assert.equal(value.provenance.plannerSource,'real_llm');assert(value.draft.systemPrompt.includes('Created Agent 731'));
  await builder.getByRole('heading',{name:'检查生成的 Agent 配置'}).waitFor();return value;
 }
 const first=await generate('生成配置草稿');assert.equal(first.draft.toolPolicy,'claude_file_edit');assert.equal(first.draft.enabled,false);
 assert.deepEqual((await get(`/workspaces/${workspace.id}/agent-directory`)).entries.map(e=>e.id),report.beforeProfileIds);
 await builder.getByLabel('职责说明',{exact:true}).fill('手工编辑保留 MANUAL_DESCRIPTION_731');
 await builder.getByLabel('补充或调整 Agent 要求',{exact:true}).fill('在系统提示词中补充：完成后说明修改范围和验证局限。保留刚才的主标题默认文案、名称、别名，以及我手工编辑的职责说明 MANUAL_DESCRIPTION_731。');
 const second=await generate('发送调整要求');assert(second.draft.description.includes('MANUAL_DESCRIPTION_731'));assert.equal(second.draft.mentionAlias,'created-front-731');
 await builder.getByLabel('自定义名称',{exact:true}).fill('对话界面助手 · 手工确认');
 await page.screenshot({path:root+'/draft-light.png'});
 await page.reload({waitUntil:'domcontentloaded'});await builder.getByRole('button',{name:'打开创建对话'}).click();
 assert.equal(await builder.getByLabel('自定义名称',{exact:true}).inputValue(),'对话界面助手 · 手工确认');
 assert((await builder.getByLabel('自定义 System Prompt',{exact:false}).inputValue()).includes('Created Agent 731'));
 report.refreshRestored=true;
 await page.goto('http://127.0.0.1:3000/',{waitUntil:'domcontentloaded'});await page.getByRole('button',{name:'切换到暗色模式'}).click();
 await page.goto('http://127.0.0.1:3000/settings/agents#create-agent',{waitUntil:'domcontentloaded'});await builder.getByRole('button',{name:'打开创建对话'}).click();
 for(const width of [390,320]){
  await page.setViewportSize({width,height:900});
  await builder.getByLabel('自定义名称',{exact:true}).scrollIntoViewIfNeeded();
  const overflow=await builder.evaluate(el=>[el,...el.querySelectorAll('form,fieldset,input,textarea,select')].filter(e=>e.clientWidth&&e.scrollWidth>e.clientWidth+2&&!['INPUT','TEXTAREA','SELECT'].includes(e.tagName)).map(e=>({tag:e.tagName,client:e.clientWidth,scroll:e.scrollWidth})));
  assert.deepEqual(overflow,[],JSON.stringify(overflow));await page.screenshot({path:root+`/draft-${width}-dark.png`});
 }
 await page.setViewportSize({width:1440,height:1000});await builder.getByLabel('启用自定义 Agent',{exact:true}).check();
 const saved=page.waitForResponse(r=>r.url().endsWith('/custom-agents')&&r.request().method()==='POST');
 await builder.getByRole('button',{name:'保存自定义 Agent',exact:true}).click();const response=await saved;assert(response.ok(),await response.text());const profile=await response.json();
 assert.equal(profile.status,'available');report.profile=profile;await save();await builder.getByText(/已保存 @created-front-731/).waitFor();
 await page.screenshot({path:root+'/saved-dark.png'});
 const restore=await page.request.put(api+`/workspaces/${workspace.id}/runtime-config`,{data:{roles:originalRoles}});assert(restore.ok(),await restore.text());originalRoles=null;report.runtimeRestored=true;
 const session=await post(`/workspaces/${workspace.id}/sessions`,{title:'对话创建 Agent · 真实执行'});report.session=session;await save();
 const taskRequest='@native-group-20261008 @created-front-731 请先阅读 apps/demo/src/App.tsx，只修改页面主标题，使用该前端 Agent 系统约定的默认标题文案，保留其他代码和行为。只创建一个 frontend_change 任务并执行。';
 assert(!taskRequest.includes('Created Agent 731'));
 await page.goto('http://127.0.0.1:3000/?session='+session.id,{waitUntil:'domcontentloaded'});
 await page.getByRole('textbox').fill(taskRequest);
 const sent=page.waitForResponse(r=>r.url().endsWith(`/sessions/${session.id}/messages`)&&r.request().method()==='POST',{timeout:180000});
 await page.getByRole('button',{name:'发送',exact:true}).click();const messageResponse=await sent;assert(messageResponse.ok(),await messageResponse.text());report.message=await messageResponse.json();await save();
 let tasks,run;
 for(let i=0;i<360;i++){
  tasks=await get(`/sessions/${session.id}/tasks`);run=tasks[0]?.taskRuns?.at(-1);
  if(run&&['completed','failed','interrupted'].includes(run.state))break;await pause(1000);
 }
 assert.equal(tasks.length,1);assert.equal(run?.state,'completed',JSON.stringify(run));assert.equal(run.adapterType,'claude_code');
 assert.equal(run.metricsJson.agentSelection.customProfile.id,profile.id);
 assert.equal(run.metricsJson.agentInstruction.profileId,profile.id);
 const source=await readFile(session.worktreePath+'/apps/demo/src/App.tsx','utf8');assert(source.includes('Created Agent 731'));
 const diffs=await get(`/task-runs/${run.id}/diffs`);assert(diffs.some(d=>d.patchText.includes('Created Agent 731')));
 const preview=await post(`/task-runs/${run.id}/preview`,{});assert.equal(preview.healthStatus,'healthy');
 const previewPage=await browser.newPage();await previewPage.goto(preview.url);await previewPage.getByRole('heading',{name:'Created Agent 731',exact:true}).waitFor();await previewPage.screenshot({path:root+'/native-preview.png'});await previewPage.close();
 report.execution={taskId:tasks[0].id,runId:run.id,adapter:run.adapterType,instruction:run.metricsJson.agentInstruction,selection:run.metricsJson.agentSelection.customProfile,sourceSha256:hash(source),diffs:diffs.map(d=>({id:d.id,sha256:hash(d.patchText)})),previewId:preview.id,heading:'Created Agent 731'};
 await writeFile(root+'/native-source.txt',source);await save();
 await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('button',{name:/^成果/}).click();await page.getByRole('button',{name:/网页预览/}).filter({hasText:'ready · healthy'}).last().click();
 await page.frameLocator('iframe[title="Vite React 预览"]').getByRole('heading',{name:'Created Agent 731',exact:true}).waitFor();await page.screenshot({path:root+'/workbench-preview.png'});
 assert.deepEqual(errors,[]);report.passed=true;console.log(JSON.stringify({passed:true,profileId:profile.id,runId:run.id,sourceSha256:report.execution.sourceSha256}));
}catch(error){report.failure=String(error);console.error(String(error));process.exitCode=1}
finally{
 if(originalRoles&&workspace){const r=await page.request.put(api+`/workspaces/${workspace.id}/runtime-config`,{data:{roles:originalRoles}});report.runtimeRestored=r.ok();if(!r.ok())process.exitCode=1}
 await save();await browser.close();
}
