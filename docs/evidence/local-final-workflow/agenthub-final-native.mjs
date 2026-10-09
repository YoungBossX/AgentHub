import {writeFile,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009', api='http://127.0.0.1:8006';
const report={startedAt:new Date().toISOString(),requests:[],observations:[]};
const save=()=>writeFile(root+'/native.json',JSON.stringify(report,null,2));
async function request(path,data){const r=await fetch(api+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(240000)});const body=await r.json();assert(r.ok,JSON.stringify({path,status:r.status,body}));return body}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 const workspace=await request('/workspaces/demo');report.workspaceId=workspace.id;
 const codex=await request(`/workspaces/${workspace.id}/sessions`,{title:'本地终验 · Codex 734'});
 const claude=await request(`/workspaces/${workspace.id}/sessions`,{title:'本地终验 · Claude 协作 734'});
 report.sessions={codex,claude};assert.notEqual(codex.worktreePath,claude.worktreePath);await save();
 const prompts={codex:'@native-group-20261008 @attachment-codex-20261009 请只创建一个 frontend_change 任务并执行：阅读 apps/demo/src/App.tsx，只把页面主标题改为 Final Codex 734，保留其他代码和行为。',claude:'@native-group-20261008 @created-front-731 @claude-review-20261008 请在 demo-frontend 协作：编码师阅读 apps/demo/src/App.tsx，只把页面主标题改为 Final Claude 734，保留其他代码和行为；评审师在编码完成后只读评审本次改动，最后由协调器汇总实际结果。'};
 await Promise.all(Object.entries(report.sessions).map(async([key,session])=>{
  const startedAt=new Date().toISOString();
  try {const message=await request(`/sessions/${session.id}/messages`,{contentMd:prompts[key]});report.requests.push({key,startedAt,finishedAt:new Date().toISOString(),message});}
  catch(error){report.requests.push({key,startedAt,error:String(error)});throw error}
  finally{await save()}
 }));
 for(let index=0;index<360;index++){
  const current=await Promise.all(Object.entries(report.sessions).map(async([key,session])=>({key,tasks:await request(`/sessions/${session.id}/tasks`),messages:await request(`/sessions/${session.id}/messages`)})));
  report.current=current;
  if(index%15===0){const state=current.map(row=>({key:row.key,tasks:row.tasks.map(task=>({id:task.id,state:task.state,runs:task.taskRuns.map(run=>({id:run.id,adapter:run.adapterType,state:run.state}))}))}));console.log(JSON.stringify(state));report.observations.push({at:new Date().toISOString(),state});await save()}
  const runs=current.flatMap(row=>row.tasks.flatMap(task=>task.taskRuns));
  assert(!runs.some(run=>['failed','interrupted','cancelled'].includes(run.state)),JSON.stringify(runs));
  const summary=current.find(row=>row.key==='claude').messages.find(message=>message.groupSummary?.state==='completed');
  if(runs.filter(run=>run.adapterType==='codex').some(run=>run.state==='completed')&&runs.filter(run=>run.adapterType==='claude_code').length>=2&&runs.every(run=>run.state==='completed')&&summary){report.summary=summary;break}
  assert(index<359,'Native completion/summary timeout');await pause(2000);
 }
 report.artifacts={};
 for(const {key,tasks} of report.current){const run=tasks.flatMap(task=>task.taskRuns).find(run=>run.adapterType===(key==='codex'?'codex':'claude_code')&&run.state==='completed');
  const diffs=await request(`/task-runs/${run.id}/diffs`);const source=await readFile(report.sessions[key].worktreePath+'/apps/demo/src/App.tsx','utf8');assert(source.includes(key==='codex'?'Final Codex 734':'Final Claude 734'));assert(diffs.some(diff=>diff.patchText.includes(key==='codex'?'Final Codex 734':'Final Claude 734')));
  const preview=await request(`/task-runs/${run.id}/preview`,{});assert.equal(preview.healthStatus,'healthy');report.artifacts[key]={runId:run.id,diffs,preview};await writeFile(root+`/${key}-source.txt`,source);
 }
 report.passed=true;console.log(JSON.stringify({passed:true,sessions:report.sessions}));
}catch(error){report.failure=String(error);console.error(error);process.exitCode=1}
finally{report.finishedAt=new Date().toISOString();await save()}
