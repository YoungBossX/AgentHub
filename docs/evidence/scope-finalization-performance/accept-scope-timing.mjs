import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
const repo='X:/Git_Clone/AgentHub', base='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const tag=process.argv[2], output=base+'/scope-timing-'+tag, api='http://127.0.0.1:8007';
await mkdir(output,{recursive:true}); await assert.rejects(access(output+'/fresh.sqlite3'));
const child=spawn(repo+'/.venv/Scripts/python.exe',['-u',base+'/scope-timing-server.py',output],{cwd:repo+'/apps/api',windowsHide:true,env:{...process.env,AGENTHUB_DATABASE_URL:'sqlite:///'+output+'/fresh.sqlite3',AGENTHUB_LLM_PLANNER_ENABLED:'false',AGENTHUB_LLM_PLANNER_PROVIDER:'disabled',CODEX_CLI_PATH:output+'/unavailable/codex.exe',PATH:'E:/Git/Git/bin;'+process.env.PATH},stdio:['ignore','pipe','pipe']});
let log='',ended=false; child.stdout.on('data',b=>log+=b);child.stderr.on('data',b=>log+=b);const exited=new Promise(resolve=>child.on('close',code=>{ended=true;resolve(code)}));
const sha=x=>createHash('sha256').update(x).digest('hex');
async function json(path,payload){const r=await fetch(api+path,payload?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:{});assert(r.ok, r.status+': '+await(r.ok?Promise.resolve(''):r.text()));return r.json()}
async function until(fn,label,limit=180000){const start=Date.now();while(Date.now()-start<limit){if(ended)throw Error(log);if(await fn())return;await delay(200)}throw Error('observation timeout: '+label)}
async function terminal(sessionId,taskId,id){let run;await until(async()=>{const tasks=await json('/sessions/'+sessionId+'/tasks');run=tasks.find(t=>t.id===taskId)?.taskRuns.find(r=>r.id===id);return run&&['failed','completed','interrupted'].includes(run.state)},id);return run}
const proof={tag,runs:[],health:[],boundaries:['Fresh SQLite; API routes; explicit ScriptedMock fallback; deliberately simulated Codex failure; no model invocation','Timing instrumentation wraps unchanged snapshot function and records counts, not content or control keys']};
try {
 await until(()=>log.includes('Application startup complete'),'API readiness',30000);
 const workspace=await json('/workspaces/demo'), session=await json('/workspaces/'+workspace.id+'/sessions',{title:'Scope timing '+tag});proof.sessionId=session.id;
 for(const value of ['Timing first','Timing second']){
  await json('/sessions/'+session.id+'/messages',{contentMd:'@frontend for the demo app, change the button text to '+value});
  const tasks=await json('/sessions/'+session.id+'/tasks'),task=tasks.at(-1);assert.equal(task.intentType,'frontend_change');
  let failed=task.taskRuns.at(-1);if(!failed)failed=await json('/tasks/'+task.id+'/runs/force-codex-failure',{});failed=await terminal(session.id,task.id,failed.id);assert.equal(failed.state,'failed');
  const started=Date.now(), retry=await json('/task-runs/'+failed.id+'/retry-with-fallback',{});
  let finished=false; const healthLoop=(async()=>{while(!finished){const t=performance.now();const health=await json('/health');proof.health.push({milliseconds:performance.now()-t,status:health.status});await delay(500)}})();
  let run;try{run=await terminal(session.id,task.id,retry.id)}finally{finished=true;await healthLoop}
  assert.equal(run.state,'completed',JSON.stringify(run));assert.equal(run.adapterType,'scripted_mock');assert.equal(run.metricsJson.taskRunScopeGuard.status,'passed');assert.equal(run.metricsJson.completionValidation.status,'passed');
  const diffs=await json('/task-runs/'+run.id+'/diffs');assert.equal(diffs.length,1);assert(diffs[0].patchText.includes(value));
  proof.runs.push({runId:run.id,taskId:task.id,seconds:(Date.now()-started)/1000,expected:value,completion:run.metricsJson.completionValidation,diffId:diffs[0].id});
 }
 proof.snapshots=(await readFile(output+'/snapshots.jsonl','utf8')).trim().split('\n').map(x=>JSON.parse(x));proof.sources=JSON.parse(await readFile(output+'/executed-source.json','utf8'));proof.helperSha256=sha(await readFile(new URL(import.meta.url)));
 await writeFile(output+'/acceptance.json',JSON.stringify(proof,null,2));console.log(JSON.stringify({tag,runs:proof.runs.map(r=>({id:r.runId,seconds:r.seconds})),snapshots:proof.snapshots.map(s=>({seconds:s.seconds,entries:s.entries})),maxHealthMs:Math.max(...proof.health.map(x=>x.milliseconds))}));
}finally{await writeFile(output+'/stop','stop\n');const code=await exited;await writeFile(output+'/server.txt',log);assert.equal(code,0,log)}
