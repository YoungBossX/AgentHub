import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root = 'X:/Git_Clone/AgentHub';
const mode = process.argv[2] || 'reproduction';
const output = 'C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/copy-literal-' + (process.argv[3] || mode);
await mkdir(output, { recursive: true });
const pnpm = 'E:/NodeJs/node_global/node_modules/pnpm/bin/pnpm.cjs';
const api = 'http://127.0.0.1:8007', web = 'http://127.0.0.1:3001';
const env = { ...process.env, AGENTHUB_DATABASE_URL: 'sqlite:///' + output + '/fresh.sqlite3',
  AGENTHUB_LLM_PLANNER_ENABLED: 'false', AGENTHUB_LLM_PLANNER_PROVIDER: 'disabled', CODEX_CLI_PATH: output + '/unavailable/codex.exe' };
const proof = { mode, cases: [], checks: [], routes: [], boundaries: [
  'Fresh isolated SQLite; deterministic planner; no model invocation',
  'Direct/Orchestrator initial failures deliberately simulated; automatic group and follow-up CLI deliberately unavailable',
  'All recovered writes are explicitly ScriptedMock; independent group review is scripted',
] };
const services = [];
let browser, page;
const sha = value => createHash('sha256').update(typeof value === 'string' || Buffer.isBuffer(value) ? value : JSON.stringify(value)).digest('hex');
proof.executedSourceSha256=Object.fromEntries(await Promise.all(['apps/api/app/scripted_mock.py','apps/api/app/planning.py','apps/api/app/planning_intents.py','apps/api/app/planning_tasks.py','apps/api/app/group_planning.py'].map(async name=>[name,sha(await readFile(root+'/'+name))])));
proof.acceptanceScriptSha256=sha(await readFile(new URL(import.meta.url)));
function frozenRun(run) { const {sessionQueue,targetLock,previewDeployJobs,...stored}=run;return stored; }
async function json(url, options) { const response = await fetch(url, options); assert(response.ok, `${response.status}: ${new URL(url).pathname} ${await (response.ok ? Promise.resolve('') : response.text())}`); return response.json(); }
const post = (url, payload={}) => json(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
async function until(fn, label, limit=60000) { const began=Date.now(); while(Date.now()-began<limit) { if(await fn()) return; await delay(150); } throw new Error('Timed out: '+label); }
function start(label) {
  const child = spawn(process.execPath, [pnpm, 'dev:local', '--api-port','8007','--web-port','3001'], { cwd: root, env, windowsHide:true, stdio:['pipe','pipe','pipe'] });
  const record = { child, label, log:'', ended:false };
  child.stdout.on('data', b=>record.log+=b); child.stderr.on('data', b=>record.log+=b); child.stdin.on('error',()=>{});
  record.exit = new Promise(resolve=>child.on('close',code=>{record.ended=true; record.code=code; resolve(code);})); services.push(record); return record;
}
async function ready(service) { await until(()=>{if(service.ended) throw new Error(service.log);return service.log.includes('[local] Ready:');},service.label); }
async function stop(service) { if(!service.ended) service.child.stdin.end('stop\n'); await until(()=>service.ended,service.label+' exit',25000); assert.equal(service.code,0,service.log); await writeFile(output+'/'+service.label+'.txt',service.log); }
async function metadata(base,id) { return { session:await json(base+'/sessions/'+id), messages:await json(base+'/sessions/'+id+'/messages'), tasks:await json(base+'/sessions/'+id+'/tasks') }; }
async function sourcePath(session) { const nested=session.worktreePath+'/apps/demo/src/App.tsx'; try { await access(nested); return nested; } catch { return session.worktreePath+'/src/App.tsx'; } }
async function visible(locator,last=false) { await until(async()=>{ const all=await locator.all(); const visible=[]; for(const item of all) if(await item.isVisible()) visible.push(item); return visible.length; },'visible '+String(locator)); const all=await locator.all();const matches=[];for(const item of all) if(await item.isVisible()) matches.push(item);return matches[last?matches.length-1:0]; }
async function send(content) { await page.locator('textarea').fill(content); const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().startsWith(api)&&r.url().endsWith('/messages')); await page.getByRole('button',{name:'发送',exact:true}).click(); const r=await response;assert.equal(r.status(),201);return r.json(); }
async function terminal(id,taskId,runId) { let run;await until(async()=>{const tasks=await json(api+'/sessions/'+id+'/tasks');run=tasks.find(t=>t.id===taskId)?.taskRuns.find(r=>!runId||r.id===runId);return run&&['completed','failed','interrupted'].includes(run.state);},'terminal run',180000);return run; }
async function fallback(id,task,initial) {
  const failed=await terminal(id,task.id,initial?.id);assert.equal(failed.state,'failed');
  assert.equal(failed.adapterType,'codex');
  await page.getByRole('button',{name:/^执行过程/}).click();
  const taskCard=page.locator('article').filter({has:page.getByRole('heading',{name:task.title,exact:true})});
  const button=await visible(taskCard.getByRole('button',{name:'使用兜底重试',exact:true}));
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===api+'/task-runs/'+failed.id+'/retry-with-fallback');await button.click();
  const r=await response;assert.equal(r.status(),201);const retry=await r.json();const recovered=await terminal(id,task.id,retry.id);
  return {failed,recovered};
}
async function preview(id,run,label) {
  await page.getByRole('button',{name:/^执行过程/}).click();
  const task=(await json(api+'/sessions/'+id+'/tasks')).find(t=>t.taskRuns.some(r=>r.id===run.id));
  const taskCard=page.locator('article').filter({has:page.getByRole('heading',{name:task.title,exact:true})});
  const button=await visible(taskCard.getByRole('button',{name:'启动预览',exact:true}));
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===api+'/task-runs/'+run.id+'/preview');
  await button.click();const r=await response;assert.equal(r.status(),201);const p=await r.json();
  await until(async()=> (await json(api+'/task-runs/'+run.id+'/previews')).find(x=>x.id===p.id)?.healthStatus==='healthy','healthy preview');
  await until(async()=>await page.locator('iframe[title="Vite React 预览"]').getAttribute('src')===p.url,'selected matching Preview iframe');
  const frame=page.frameLocator('iframe[title="Vite React 预览"]');
  if(mode!=='reproduction' || label==='Continue') { await frame.locator('input[type=email]').waitFor();await frame.locator('input[type=password]').waitFor();await frame.getByRole('button',{name:label,exact:true}).waitFor(); }
  await page.screenshot({path:output+'/'+id+'-'+p.id+'.png'});
  return p;
}

const existingId='ac5dccd4-55ed-4c4a-b0be-bd33ff94636d';
const existing=await metadata('http://127.0.0.1:8006',existingId);
const existingFile=await sourcePath(existing.session),existingSource=sha(await readFile(existingFile));
const historyCases=[];
async function task(id,mentions,text,target='button',initialLogin=false) {
  const message=await send(mentions+(initialLogin?' build a login page for the demo app':' for demo app change '+target+' text to "'+text+'"'));
  const tasks=await json(api+'/sessions/'+id+'/tasks');const writer=tasks.find(t=>t.createdByMessageId===message.id&&t.intentType==='frontend_change');
  assert(writer);assert.equal(writer.planJson.target,initialLogin?'login_page':target==='button'?'primary_action_button_text':'demo_heading_text');
  if(!initialLogin) assert.equal(writer.planJson.targetText,text);
  const initial=writer.taskRuns.length?null:await post(api+'/tasks/'+writer.id+'/runs/force-codex-failure');
  const result=await fallback(id,writer,initial);assert.equal(result.recovered.state,'completed',JSON.stringify(result.recovered));
  assert.equal(result.recovered.adapterType,'scripted_mock');assert.equal(result.recovered.metricsJson.taskRunScopeGuard.status,'passed');
  assert.equal(result.recovered.metricsJson.completionValidation.status,'passed');
  assert.equal(result.recovered.metricsJson.completionValidation.functionalAcceptance,'not_evaluated');
  return {writer,...result};
}
async function inspect(p,target,expected,route,runId) {
  const actual=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  actual.on('pageerror',e=>errors.push(e.message));
  try {
    await actual.goto(p.url,{waitUntil:'domcontentloaded'});
    if(mode==='reproduction' && expected==='{agenthubCopyProbe}') {
      await until(()=>errors.some(e=>e.includes('agenthubCopyProbe')),'actual pre-fix undefined JSX expression');
      proof.cases.push({route,runId,target,expected,errors,rendered:false,healthStatus:'healthy',completionFunctionalAcceptance:'not_evaluated'});
      await actual.screenshot({path:output+'/'+route+'-'+target+'-broken.png'});return;
    }
    const element=actual.locator(target==='button'?'[data-agenthub-target="primary-action-button"]':'#demo-heading');
    await element.waitFor();
    const text=await element.textContent(),children=await element.locator('*').count();
    const normalized=target==='button'?text.trim():text;
    if(mode==='reproduction' && expected.includes('<strong>')) {assert.notEqual(normalized,expected);assert.equal(children,1);}
    else {assert.equal(normalized,expected);assert.equal(children,0);assert.deepEqual(errors,[]);}
    proof.cases.push({route,runId,target,expected,actualText:normalized,childElements:children,errors,rendered:true,healthStatus:'healthy'});
    if(mode!=='reproduction') {
      await actual.setViewportSize({width:390,height:844});assert.equal((await element.textContent()).trim(),expected);
      assert.equal(await actual.getByLabel('Email address',{exact:true}).count(),1);
      assert.equal(await actual.getByLabel('Password',{exact:true}).count(),1);
    }
    await actual.screenshot({path:output+'/'+route+'-'+target+'-'+proof.cases.length+'.png',fullPage:true});
  } finally {await actual.close();}
}
try {
  await assert.rejects(access(output+'/fresh.sqlite3'));
  const service=start('first-start');await ready(service);
  browser=await chromium.launch({channel:'msedge',headless:true});page=await browser.newPage({viewport:{width:1440,height:900}});
  const routes=mode==='reproduction'?[['direct','@frontend']]:[['direct','@frontend'],['group','@frontend @qa'],['orchestrator','@orchestrator']];
  for(const [route,mentions] of routes) {
    await page.goto(web,{waitUntil:'domcontentloaded'});const created=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().startsWith(api)&&r.url().endsWith('/sessions'));
    await page.getByRole('button',{name:'新建会话',exact:true}).click();assert.equal((await created).status(),201);
    await until(()=>new URL(page.url()).searchParams.get('session'),'new copy Session');const id=new URL(page.url()).searchParams.get('session');
    const session=await json(api+'/sessions/'+id),file=await sourcePath(session);
    const login=await task(id,mentions,'Continue','button',true);await preview(id,login.recovered,'Continue');
    const cssHash=sha(await readFile(file.replace('App.tsx','styles.css')));
    const values=mode==='reproduction'?
      [['button','{agenthubCopyProbe}'],['button','Plain after expression'],['heading','A &amp; B <strong>text</strong>']]:
      [['button','登入 </button><b>{name}</b> &amp; \\1 $&'],['button','Plain after literal'],
       ['heading','标题 </h1><b>{x}</b> &lt; \\g<1> $&'],['heading','Plain heading after literal']];
    const runs=[];
    for(const [target,value] of values) {
      const before=await readFile(file);const changed=await task(id,mentions,value,target);assert.notEqual(sha(await readFile(file)),sha(before));
      assert.equal(sha(await readFile(file.replace('App.tsx','styles.css'))),cssHash);
      const buttonText=target==='button'?value:(mode==='reproduction'?'Plain after expression':'Plain after literal');
      const p=await preview(id,changed.recovered,buttonText);await inspect(p,target,value,route,changed.recovered.id);
      const diffs=await json(api+'/task-runs/'+changed.recovered.id+'/diffs');assert.equal(diffs.length,1);
      runs.push({target,value,taskId:changed.writer.id,failedRunId:changed.failed.id,scriptedRunId:changed.recovered.id,diffId:diffs[0].id,previewId:p.id});
    }
    if(route==='group') await until(async()=> (await json(api+'/sessions/'+id+'/tasks')).filter(t=>t.intentType==='qa_review').every(t=>t.status==='completed'),'all independent scripted QA');
    proof.routes.push({route,sessionId:id,loginRunId:login.recovered.id,runs,stylesSha256:cssHash,sourceSha256:sha(await readFile(file))});
    historyCases.push(id);proof.checks.push(route+': actual bound copy events/Diff/Preview; unchanged styles; structured task target text preserved');console.log('PASS '+route+' '+mode);
  }
  const before=await Promise.all(historyCases.map(id=>metadata(api,id))),historyHash=sha(before);
  await page.close();page=null;await stop(service);
  const restarted=start('restart');await ready(restarted);const after=await Promise.all(historyCases.map(id=>metadata(api,id)));assert.equal(sha(after),historyHash);
  if(mode!=='reproduction') {
    const route=proof.routes.find(r=>r.route==='group'),run=route.runs.at(-1);const fresh=await post(api+'/task-runs/'+run.scriptedRunId+'/preview');
    await until(async()=> (await json(api+'/task-runs/'+run.scriptedRunId+'/previews')).find(p=>p.id===fresh.id)?.healthStatus==='healthy','explicit final Preview restore');
    await inspect(fresh,'heading','Plain heading after literal','group-restored',run.scriptedRunId);
  }
  proof.historySha256Before=historyHash;proof.historySha256After=sha(after);
  assert.equal(sha(await metadata('http://127.0.0.1:8006',existingId)),sha(existing));assert.equal(sha(await readFile(existingFile)),existingSource);
  proof.existingSessionSha256=sha(existing);proof.existingSourceSha256=existingSource;
  await stop(restarted);for(const [name,hash] of Object.entries(proof.executedSourceSha256)) assert.equal(sha(await readFile(root+'/'+name)),hash);
  assert.equal(sha(await readFile(new URL(import.meta.url))),proof.acceptanceScriptSha256);
  await writeFile(output+'/acceptance.json',JSON.stringify(proof,null,2));console.log(JSON.stringify({mode,cases:proof.cases.length,routes:proof.routes.length}));
} catch(error) {
  if(page) {await page.screenshot({path:output+'/browser-error.png'}).catch(()=>{});console.log((await page.locator('body').innerText()).slice(0,1800));}throw error;
} finally {
  if(browser) await browser.close();for(const service of services) if(!service.ended) await stop(service);for(const service of services) await writeFile(output+'/'+service.label+'.txt',service.log);
}
