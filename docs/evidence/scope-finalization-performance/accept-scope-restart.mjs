import assert from 'node:assert/strict';
import {spawn,execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {readFile,writeFile,mkdir,access} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';
const require=createRequire(import.meta.url),{chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='X:/Git_Clone/AgentHub',base='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007',output=base+'/scope-timing-restart',api='http://127.0.0.1:8007';
await mkdir(output,{recursive:true});await assert.rejects(access(output+'/stop'));
const previous=JSON.parse(await readFile(base+'/scope-timing-browser/acceptance.json','utf8')),database=base+'/scope-timing-browser/fresh.sqlite3';
const sha=value=>createHash('sha256').update(value).digest('hex');
function history(){return JSON.parse(execFileSync(root+'/.venv/Scripts/python.exe',['-c',"import sys,sqlite3,json,hashlib;from pathlib import Path;d=sqlite3.connect(Path(sys.argv[1]).as_uri()+'?mode=ro',uri=True);print(json.dumps({t:hashlib.sha256(json.dumps(d.execute('select * from '+t+' order by id').fetchall(),ensure_ascii=True,separators=(',',':')).encode()).hexdigest() for t in ['session','message','task','taskrun']}))",database],{encoding:'utf8',windowsHide:true}));}
const before=history();
const child=spawn(root+'/.venv/Scripts/python.exe',['-u',base+'/scope-timing-server.py',output],{cwd:root+'/apps/api',windowsHide:true,env:{...process.env,AGENTHUB_DATABASE_URL:'sqlite:///'+database,AGENTHUB_LLM_PLANNER_ENABLED:'false',AGENTHUB_LLM_PLANNER_PROVIDER:'disabled',CODEX_CLI_PATH:output+'/unavailable/codex.exe',PATH:'E:/Git/Git/bin;'+process.env.PATH},stdio:['ignore','pipe','pipe']});
let ended=false,log='',browser;child.stdout.on('data',b=>log+=b);child.stderr.on('data',b=>log+=b);const exited=new Promise(resolve=>child.on('close',code=>{ended=true;resolve(code)}));
async function until(fn,label){const start=Date.now();while(Date.now()-start<60000){if(ended)throw Error(log);if(await fn())return;await delay(150)}throw Error(label)}
async function get(base,path,payload){const r=await fetch(base+path,payload?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:{});assert(r.ok,r.status+' '+path);return r.json()}
try{
 await until(()=>log.includes('Application startup complete'),'API ready');const after=history();assert.deepEqual(after,before);
 const tasks=await get(api,'/sessions/'+previous.sessionId+'/tasks'),last=previous.runs.at(-1),run=tasks.find(t=>t.id===last.taskId).taskRuns.find(r=>r.id===last.runId);
 assert.equal(run.state,'completed');assert.equal(run.metricsJson.taskRunScopeGuard.status,'passed');assert.equal(run.metricsJson.completionValidation.status,'passed');
 const preview=await get(api,'/task-runs/'+last.runId+'/preview',{});await until(async()=> (await get(api,'/task-runs/'+last.runId+'/previews')).find(p=>p.id===preview.id)?.healthStatus==='healthy','restored Vite');
 browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(preview.url,{waitUntil:'domcontentloaded'});const button=page.locator('[data-agenthub-target="primary-action-button"]');await button.waitFor();assert.equal((await button.textContent()).trim(),'Timing second');assert.deepEqual(errors,[]);await page.screenshot({path:output+'/restored-preview.png'});
 const nativeId='ac5dccd4-55ed-4c4a-b0be-bd33ff94636d',nativeApi='http://127.0.0.1:8006';const native={session:await get(nativeApi,'/sessions/'+nativeId),messages:await get(nativeApi,'/sessions/'+nativeId+'/messages'),tasks:await get(nativeApi,'/sessions/'+nativeId+'/tasks')};const prior=JSON.parse(await readFile(base+'/copy-literal-verified/acceptance.json','utf8'));assert.equal(sha(JSON.stringify(native)),prior.existingSessionSha256);assert.equal(sha(await readFile(native.session.worktreePath+'/apps/demo/src/App.tsx')),prior.existingSourceSha256);
 await writeFile(output+'/acceptance.json',JSON.stringify({historyBefore:before,historyAfterStartup:after,sessionId:previous.sessionId,runId:run.id,previewId:preview.id,actualText:(await button.textContent()).trim(),errors,nativeSessionSha256:prior.existingSessionSha256,nativeSourceSha256:prior.existingSourceSha256,helperSha256:sha(await readFile(new URL(import.meta.url)))},null,2));console.log('Restart history hashes, durable completion, restored Vite DOM and existing native session verified');
}finally{if(browser)await browser.close();await writeFile(output+'/stop','stop\n');const code=await exited;await writeFile(output+'/server.txt',log);assert.equal(code,0,log)}
