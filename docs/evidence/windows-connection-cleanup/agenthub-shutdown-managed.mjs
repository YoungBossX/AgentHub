import {spawn,spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {writeFile,readFile,mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
import net from 'node:net';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-shutdown-20261009/managed-'+Date.now();
const helper='C:/Users/XCC/AppData/Local/Temp/agenthub-shutdown-managed.py';
const python='X:/Git_Clone/AgentHub/.venv/Scripts/python.exe';
const oldroot='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const proof=JSON.parse(await readFile(oldroot+'/attachment-codex-native.json','utf8'));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const prepared=spawnSync(python,[helper,'prepare',root],{cwd:'X:/Git_Clone/AgentHub/apps/api',encoding:'utf8',windowsHide:true});
assert.equal(prepared.status,0,prepared.stderr);
const reports=[];
async function closed(port){return new Promise(resolve=>{const s=net.connect({host:'127.0.0.1',port});s.once('connect',()=>{s.destroy();resolve(false)});s.once('error',()=>resolve(true));s.setTimeout(1500,()=>{s.destroy();resolve(false)});});}
for(const mode of ['baseline','fixed']){
 let logs='';let exited=false;let exitCode;const child=spawn(python,['-u',helper,mode,root],{cwd:'X:/Git_Clone/AgentHub/apps/api',env:{...process.env,PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe'],windowsHide:true});
 child.stdout.on('data',b=>logs+=b);child.stderr.on('data',b=>logs+=b);
 const exit=new Promise(resolve=>child.on('exit',code=>{exited=true;exitCode=code;resolve()}));
 let browser;
 try{
  for(let i=0;i<200&&!logs.includes('[agenthub-ready:shutdown-acceptance]')&&!exited;i++)await pause(100);
  assert(!exited&&logs.includes('[agenthub-ready:shutdown-acceptance]'),logs);
  browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8011/health');
  const sse=await page.evaluate(async sid=>{
    const replay=await(await fetch(`/sessions/${sid}/events`)).text();
    const ids=[...replay.matchAll(/^id: (.+)$/gm)].map(m=>m[1]);if(!ids.length)throw Error('Missing persisted event IDs');
    const remaining=await(await fetch(`/sessions/${sid}/events`,{headers:{'Last-Event-ID':ids[0]}})).text();
    const resumed=[...remaining.matchAll(/^id: (.+)$/gm)].map(m=>m[1]);
    await new Promise((resolve,reject)=>{const stream=new EventSource(`/sessions/${sid}/events?stream=true`);stream.onopen=()=>{stream.close();resolve()};stream.onerror=()=>{stream.close();reject(Error('SSE failed'))};});
    return {replayed:ids.length,resumed:resumed.length,firstExcluded:!resumed.includes(ids[0])};
  },proof.sessionId);
  assert(sse.firstExcluded&&sse.replayed>0);
  const response=await page.request.post(`http://127.0.0.1:8011/task-runs/${proof.runId}/preview`,{data:{},timeout:90000});assert(response.ok(),await response.text());
  const preview=await response.json();assert.equal(preview.healthStatus,'healthy');
  await page.goto(preview.url);await page.getByRole('heading',{name:'Aurora Workshop 617',exact:true}).waitFor();await page.getByRole('button',{name:'Cedar Beacon 842',exact:true}).waitFor();
  await page.screenshot({path:root+'/'+mode+'-preview.png'});assert.deepEqual(errors,[]);
  await browser.close();browser=null;await pause(300);
  await writeFile(root+'/'+mode+'.trigger','inject the controlled cleanup fault');
  let fault;
  for(let i=0;i<100;i++){try{fault=JSON.parse(await readFile(root+'/'+mode+'-fault.json','utf8'));break}catch{await pause(50)}}
  assert(fault,'Missing controlled fault evidence');
  if(mode==='baseline'){assert.equal(fault.socketCloses,0);assert.equal(fault.after,fault.before+1)}
  else{assert.equal(fault.socketCloses,1);assert.equal(fault.after,fault.before);assert(fault.cleaned)}
  const start=Date.now();child.stdin.end('stop\n');await Promise.race([exit,pause(12000)]);assert(exited,'Managed API did not exit');
  const duration=Date.now()-start;assert.equal(exitCode,0,logs);assert(logs.includes('Application shutdown complete'),logs);
  assert(await closed(8011));assert(await closed(Number(new URL(preview.url).port)));
  if(mode==='baseline')assert(logs.includes('timeout graceful shutdown exceeded'),logs);
  else{assert(!logs.includes('timeout graceful shutdown exceeded'),logs);assert(logs.includes('Recovered Windows peer-reset'),logs)}
  reports.push({mode,shutdownMs:duration,exitCode,sse,fault,previewId:preview.id,previewPort:Number(new URL(preview.url).port),previewHealth:preview.healthStatus,apiAndPreviewPortsClosed:true,errors});
 }finally{
  if(browser)await browser.close();
  if(!exited){child.stdin.end('stop\n');await Promise.race([exit,pause(12000)]);if(!exited)throw Error('Owned managed API still running: '+child.pid)}
  await writeFile(root+'/'+mode+'.log',logs);
 }
}
await writeFile(root+'/report.json',JSON.stringify({reports,source:'controlled socket-shutdown injection through actual local-api entrypoint; real Edge SSE/preview, no new model inference'},null,2));
await writeFile('C:/Users/XCC/AppData/Local/Temp/agenthub-shutdown-20261009/managed-latest.json',JSON.stringify({root},null,2));
console.log(JSON.stringify({root,reports}));
