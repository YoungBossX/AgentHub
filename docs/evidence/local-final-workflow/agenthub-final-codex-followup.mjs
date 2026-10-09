import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009',api='http://127.0.0.1:8006';
const baseline=JSON.parse(await readFile(root+'/native.json','utf8')),session=baseline.sessions.codex,report={sessionId:session.id};
async function req(path,data){const r=await fetch(api+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(240000)});const body=await r.json();assert(r.ok,JSON.stringify({path,status:r.status,body}));return body}
try{
 report.message=await req(`/sessions/${session.id}/messages`,{contentMd:'@native-group-20261008 @attachment-codex-20261009 请只创建一个 frontend_change 并执行：阅读当前 apps/demo/src/App.tsx，仅将主标题从 Final Codex 734 改为 Final Codex 735，其他内容和行为保持不变。'});
 for(let i=0;i<300;i++){
  const tasks=await req(`/sessions/${session.id}/tasks`),task=tasks.find(task=>task.createdByMessageId===report.message.id),run=task?.taskRuns.at(-1);
  if(i%20===0)console.log(JSON.stringify({i,state:run?.state}));
  assert(!['failed','interrupted','cancelled'].includes(run?.state),JSON.stringify(run));
  if(run?.state==='completed'){report.run=run;break}assert(i<299,'Timed out');await new Promise(resolve=>setTimeout(resolve,2000));
 }
 assert.equal(report.run.adapterType,'codex');report.diffs=await req(`/task-runs/${report.run.id}/diffs`);assert(report.diffs.some(diff=>diff.patchText.includes('Final Codex 735')));
 assert((await readFile(session.worktreePath+'/apps/demo/src/App.tsx','utf8')).includes('Final Codex 735'));
 report.passed=true;console.log(JSON.stringify({passed:true,runId:report.run.id}));
}catch(error){report.failure=String(error);console.error(error);process.exitCode=1}
finally{await writeFile(root+'/codex-followup.json',JSON.stringify(report,null,2))}
