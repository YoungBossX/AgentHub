import {createRequire} from 'node:module';
import {writeFile, readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const api='http://127.0.0.1:8006';
const marker='Pinned Reference 20261008';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
page.setDefaultTimeout(30000);
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json();}
async function post(path,data){const r=await page.request.post(api+path,{data,timeout:120000});assert(r.ok(),`${r.status()}: ${await r.text()}`);return r.json();}
try {
 const workspace=await get('/workspaces/demo');
 const resumed=process.argv[2]==='resume' ? JSON.parse(await readFile(root+'/pinned-context-session.json','utf8')) : null;
 const session=resumed ? await get(`/sessions/${resumed.sessionId}`) : await post(`/workspaces/${workspace.id}/sessions`,{title:'置顶上下文原生验收'});
 const note=resumed ? {id:resumed.noteId} : await post(`/sessions/${session.id}/messages`,{senderType:'agent',contentMd:`产品约定：演示应用主按钮的最终文案必须为 ${marker}。只修改按钮文字。`});
 if(!resumed)for(let i=0;i<10;i++)await post(`/sessions/${session.id}/messages`,{senderType:'agent',contentMd:`补充记录 ${i+1}：此条没有新增需求。`});
 await page.goto(`http://127.0.0.1:3000/?session=${session.id}`,{waitUntil:'domcontentloaded'});
 await page.getByRole('heading',{name:session.title,exact:true}).waitFor();
 const noteCard=page.locator(`#message-${note.id}`);
 if(!resumed)await noteCard.getByRole('button',{name:'置顶消息',exact:true}).click();
 await noteCard.getByRole('button',{name:'取消置顶消息',exact:true}).waitFor();
 assert((await get(`/sessions/${session.id}/messages`)).find(m=>m.id===note.id).pinnedAt);
 await page.screenshot({path:root+'/pinned-context-ui.png'});
 const request='@native-group-20261008 @claude-code-20261008 请根据当前会话的置顶产品约定，把演示应用 apps/demo/src/App.tsx 中主按钮文案修改为约定里的原文。只改这一处文本，保留页面和逻辑。在计划验收标准中写出该文案，然后执行。' + (resumed ? '本组只选了一个执行角色 frontend，因此只生成一个 frontend_change 任务，不添加 QA、评审或单独的规划任务。' : '');
 assert(!request.includes(marker));
 await writeFile(root+'/pinned-context-session.json',JSON.stringify({sessionId:session.id,workspaceId:workspace.id,noteId:note.id,worktreePath:session.worktreePath,marker,request},null,2));
 await post(`/sessions/${session.id}/messages`,{contentMd:request,context:{autoStart:false}});
 let tasks=await get(`/sessions/${session.id}/tasks`);
 await writeFile(root+'/pinned-context-plan.json',JSON.stringify(tasks,null,2));
 assert.equal(tasks.length,1);
 assert.equal(tasks[0].planJson.plannerEvidence.plannerSource,'real_llm');
 assert(JSON.stringify(tasks[0].planJson).includes(marker),'Planner did not resolve pinned reference');
 console.log(JSON.stringify({phase:'actual-planner-used-pin',sessionId:session.id,taskId:tasks[0].id}));
 if(tasks[0].taskRuns.length===0)await post(`/tasks/${tasks[0].id}/runs`,{});
 for(let i=0;i<360;i++){
  tasks=await get(`/sessions/${session.id}/tasks`);
  const run=tasks[0].taskRuns.at(-1);
  if(run&&['completed','failed','interrupted'].includes(run.state))break;
  await page.waitForTimeout(1000);
 }
 const run=tasks[0].taskRuns.at(-1);
 await writeFile(root+'/pinned-context-runs.json',JSON.stringify(tasks,null,2));
 assert.equal(run.state,'completed',JSON.stringify({code:run.errorCode,message:run.errorMessage}));
 assert.equal(run.adapterType,'claude_code');
 const app=await readFile(session.worktreePath+'/apps/demo/src/App.tsx');
 assert(app.includes(Buffer.from(marker)));
 const diffs=await get(`/task-runs/${run.id}/diffs`);
 assert(diffs.some(d=>d.patchText.includes(marker)));
 await page.reload({waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:/^执行过程/}).click();
 await page.getByRole('heading',{name:tasks[0].title,exact:true}).waitFor();
 await page.screenshot({path:root+'/pinned-context-completed.png'});
 await writeFile(root+'/pinned-context-native.json',JSON.stringify({sessionId:session.id,noteId:note.id,taskId:tasks[0].id,runId:run.id,adapter:run.adapterType,marker,appSha256:createHash('sha256').update(app).digest('hex'),plannerEvidence:tasks[0].planJson.plannerEvidence,diffIds:diffs.map(d=>d.id),checks:['old assistant reference pinned through actual UI','ten newer messages before current request','current user request omits literal label','real planner resolved literal label','real Claude coding completed with matching source and Diff']},null,2));
 console.log(JSON.stringify({phase:'actual-coding-used-pin',runId:run.id}));
}finally{await browser.close();}
