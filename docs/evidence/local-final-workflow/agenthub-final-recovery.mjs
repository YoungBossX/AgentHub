import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009', api='http://127.0.0.1:8006',report={};
const save=()=>writeFile(root+'/recovery.json',JSON.stringify(report,null,2));
async function req(path,data){const r=await fetch(api+path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(120000)});const body=await r.json();assert(r.ok,JSON.stringify({path,status:r.status,body}));return body}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitRun(id,state){for(let i=0;i<240;i++){const tasks=await req(`/sessions/${report.session.id}/tasks`),run=tasks.flatMap(t=>t.taskRuns).find(r=>r.id===id);if(run?.state===state)return run;if(['failed','interrupted','completed'].includes(run?.state))throw Error(JSON.stringify(run));if(i%30===0)console.log(JSON.stringify({waiting:id,state:run?.state}));await pause(1000)}throw Error('Timed out')}
try{
 const ws=await req('/workspaces/demo');report.session=await req(`/workspaces/${ws.id}/sessions`,{title:'本地终验 · 故障与中断恢复 734'});await save();
 report.message=await req(`/sessions/${report.session.id}/messages`,{contentMd:'@orchestrator build a login page for the demo app'});
 const tasks=await req(`/sessions/${report.session.id}/tasks`),coding=tasks.find(t=>t.intentType==='frontend_change');assert(coding);assert.equal(coding.taskRuns.length,0,'Unexpected auto-start; do not duplicate work');report.taskId=coding.id;
 const forced=await req(`/tasks/${coding.id}/runs/force-codex-failure`,{});report.forced=await waitRun(forced.id,'failed');assert.equal(report.forced.errorCode,'CODEX_DEMO_FORCED_FAILURE');await save();
 const fallback=await req(`/task-runs/${forced.id}/retry-with-fallback`,{});report.beforeInterrupt=fallback;report.interrupted=await req(`/task-runs/${fallback.id}/interrupt`,{});assert.equal(report.interrupted.state,'interrupted');await save();
 const retry=await req(`/task-runs/${fallback.id}/retry`,{});report.recovered=await waitRun(retry.id,'completed');assert.equal(report.recovered.adapterType,'scripted_mock');
 report.diffs=await req(`/task-runs/${retry.id}/diffs`);assert(report.diffs.some(diff=>diff.patchText.includes('type="email"')&&diff.patchText.includes('type="password"')));
 report.preview=await req(`/task-runs/${retry.id}/preview`,{});assert.equal(report.preview.healthStatus,'healthy');
 report.passed=true;console.log(JSON.stringify({passed:true,sessionId:report.session.id,runId:retry.id}));
}catch(error){report.failure=String(error);console.error(error);process.exitCode=1}finally{await save()}
