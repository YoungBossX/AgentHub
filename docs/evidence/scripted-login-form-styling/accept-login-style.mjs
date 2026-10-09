import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root = 'X:/Git_Clone/AgentHub';
const output = 'C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/login-style-' + (process.argv[2] || 'first');
await mkdir(output, { recursive: true });
const pnpm = 'E:/NodeJs/node_global/node_modules/pnpm/bin/pnpm.cjs';
const api = 'http://127.0.0.1:8007', web = 'http://127.0.0.1:3001';
const env = { ...process.env, AGENTHUB_DATABASE_URL: 'sqlite:///' + output + '/fresh.sqlite3',
  AGENTHUB_LLM_PLANNER_ENABLED: 'false', AGENTHUB_LLM_PLANNER_PROVIDER: 'disabled', CODEX_CLI_PATH: output + '/unavailable/codex.exe' };
const proof = { checks: [], routes: [], boundaries: [
  'Fresh isolated SQLite; deterministic planner; no model invocation',
  'Direct/Orchestrator initial failures deliberately simulated; automatic group and follow-up CLI deliberately unavailable',
  'All recovered writes are explicitly ScriptedMock; independent group review is scripted',
] };
proof.formMeasurements = [];
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
async function terminal(id,taskId,runId) { let run;await until(async()=>{const tasks=await json(api+'/sessions/'+id+'/tasks');run=tasks.find(t=>t.id===taskId)?.taskRuns.find(r=>!runId||r.id===runId);return run&&['completed','failed','interrupted'].includes(run.state);},'terminal run');return run; }
async function fallback(id,task,initial) {
  const failed=await terminal(id,task.id,initial?.id);assert.equal(failed.state,'failed');
  assert.equal(failed.adapterType,'codex');
  await page.getByRole('button',{name:/^执行过程/}).click();
  const button=await visible(page.getByRole('button',{name:'使用兜底重试',exact:true}));
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
  await frame.locator('input[type=email]').waitFor();await frame.locator('input[type=password]').waitFor();
  await frame.getByRole('button',{name:label,exact:true}).waitFor();
  await page.screenshot({path:output+'/'+id+'-'+label.replaceAll(' ','-')+'.png'});
  return p;
}
async function measureForm(surface, route, stage, width) {
  const email=surface.getByLabel('Email address',{exact:true});
  const password=surface.getByLabel('Password',{exact:true});
  assert.equal(await email.getAttribute('name'),'email');
  assert.equal(await email.getAttribute('autocomplete'),'username');
  assert.equal(await password.getAttribute('name'),'password');
  assert.equal(await password.getAttribute('autocomplete'),'current-password');
  const measurement=await surface.locator('html').evaluate(html=>{
    const form=html.querySelector('.login-form'),style=getComputedStyle(form);
    const fields=[...form.querySelectorAll('input')].map(input=>{
      const css=getComputedStyle(input),box=input.getBoundingClientRect(),label=input.parentElement.getBoundingClientRect();
      return {fontSize:css.fontSize,boxSizing:css.boxSizing,borderRadius:css.borderRadius,
        borderWidth:css.borderTopWidth,minHeight:css.minHeight,width:box.width,height:box.height,
        left:box.left,right:box.right,labelWidth:label.width};
    });
    return {viewport:html.clientWidth,scrollWidth:html.scrollWidth,bodyScrollWidth:html.querySelector('body').scrollWidth,
      display:style.display,gap:style.gap,labelGap:getComputedStyle(form.querySelector('label')).gap,fields};
  });
  assert.equal(measurement.display,'grid');assert.equal(measurement.gap,'20px');assert.equal(measurement.labelGap,'8px');
  assert(measurement.viewport>=320,'demo scaffold minimum viewport');
  assert(measurement.scrollWidth<=measurement.viewport && measurement.bodyScrollWidth<=measurement.viewport,JSON.stringify(measurement));
  for(const field of measurement.fields) {
    assert.equal(field.fontSize,'16px');assert.equal(field.boxSizing,'border-box');
    assert.equal(field.borderRadius,'6px');assert.equal(field.borderWidth,'1px');assert(field.height>=48);
    assert(Math.abs(field.width-field.labelWidth)<1);assert(field.left>=0 && field.right<=measurement.viewport);
  }
  proof.formMeasurements.push({route,stage,width,...measurement});return measurement;
}
async function acceptStyledPreview(p,route,label,stage,widths=[1440,390,320]) {
  // Inspect the actual matching iframe first, then the same healthy Vite URL at exact viewport sizes.
  await measureForm(page.frameLocator('iframe[title="Vite React 预览"]'),route,stage+' iframe',null);
  const actual=await browser.newPage({viewport:{width:widths[0],height:900}});
  actual.on('pageerror',e=>proof.formBrowserErrors=(proof.formBrowserErrors||[]).concat(e.message));
  try {
    await actual.goto(p.url,{waitUntil:'domcontentloaded'});await actual.getByRole('button',{name:label,exact:true}).waitFor();
    const email=actual.getByLabel('Email address',{exact:true}),password=actual.getByLabel('Password',{exact:true});
    await actual.keyboard.press('Tab');assert(await email.evaluate(el=>el===document.activeElement && el.matches(':focus-visible')));
    const focus=await email.evaluate(el=>{const s=getComputedStyle(el);return {outlineWidth:s.outlineWidth,outlineStyle:s.outlineStyle,outlineColor:s.outlineColor,outlineOffset:s.outlineOffset};});
    assert.deepEqual(focus,{outlineWidth:'2px',outlineStyle:'solid',outlineColor:'rgb(37, 99, 235)',outlineOffset:'2px'});
    await email.fill('demo@example.com');await actual.keyboard.press('Tab');assert(await password.evaluate(el=>el===document.activeElement));
    await password.fill('DemoPassword');
    for(const width of widths) {
      await actual.setViewportSize({width,height:844});await measureForm(actual,route,stage,width);
      await email.scrollIntoViewIfNeeded();await actual.screenshot({path:output+'/'+route+'-'+stage+'-'+width+'.png',fullPage:true});
    }
    await email.hover();await until(async()=>await email.evaluate(el=>getComputedStyle(el).borderTopColor)==='rgb(147, 168, 196)','hover border after transition',3000);
    proof.checks.push(route+' '+stage+': real computed form spacing, label/font/full-width fields, keyboard focus/autocomplete and '+widths.join('/')+'px without overflow');
  } finally { await actual.close(); }
}
const existingId='ac5dccd4-55ed-4c4a-b0be-bd33ff94636d';
const existing=await metadata('http://127.0.0.1:8006',existingId);
const existingFile=await sourcePath(existing.session), existingSource=sha(await readFile(existingFile));
try {
  await assert.rejects(access(output+'/fresh.sqlite3'));
  const service=start('first-start');await ready(service);
  browser=await chromium.launch({channel:'msedge',headless:true});
  page=await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const [route,mentions] of [['direct','@frontend'],['group','@frontend @qa'],['orchestrator','@orchestrator']]) {
    await page.goto(web,{waitUntil:'domcontentloaded'});
    const created=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().startsWith(api)&&r.url().endsWith('/sessions'));
    await page.getByRole('button',{name:'新建会话',exact:true}).click();assert.equal((await created).status(),201);
    await until(()=>new URL(page.url()).searchParams.get('session'),'created session');const id=new URL(page.url()).searchParams.get('session');
    const session=await json(api+'/sessions/'+id),file=await sourcePath(session),baseline=await readFile(file);
    const message=await send(mentions+(route==='orchestrator'?' 为演示应用创建登录页':' build a login page for the demo app')+(route==='direct'?'; please run project checks':''));
    let tasks=await json(api+'/sessions/'+id+'/tasks');const writer=tasks.find(t=>t.createdByMessageId===message.id&&t.intentType==='frontend_change');
    assert.equal(writer.planJson.target,'login_page');assert.equal(writer.planJson.targetId,'demo-frontend');
    if(route==='orchestrator') assert.equal(tasks.length,3);
    const initial=route==='group'?null:await post(api+'/tasks/'+writer.id+'/runs/force-codex-failure');
    await terminal(id,writer.id,initial?.id);assert.equal(sha(await readFile(file)),sha(baseline));
    const {failed,recovered}=await fallback(id,writer,initial);assert.equal(recovered.state,'completed',JSON.stringify(recovered));assert.equal(recovered.adapterType,'scripted_mock');
    const failureHash=sha(frozenRun(failed)),diffs=await json(api+'/task-runs/'+recovered.id+'/diffs');assert(diffs.some(d=>d.patchText.includes('type="password"')&&d.patchText.includes('.login-form input:focus-visible')));
    assert.deepEqual([...diffs[0].changedFiles].sort(),['apps/demo/src/App.tsx','apps/demo/src/styles.css']);
    const login=await readFile(file,'utf8'),stylesHash=sha(await readFile(file.replace('App.tsx','styles.css')));assert(login.includes('<form className="login-form"')&&login.includes('type="email"'));
    assert.equal((await readFile(file.replace('App.tsx','styles.css'),'utf8')).split('/* AgentHub scripted login form: start */').length,2);
    assert.equal(recovered.metricsJson.taskRunScopeGuard.status,'passed');assert.equal(recovered.metricsJson.completionValidation.status,'passed');
    if(route==='group') { await until(async()=>{tasks=await json(api+'/sessions/'+id+'/tasks');return tasks.find(t=>t.intentType==='qa_review')?.status==='completed';},'independent group review');const review=tasks.find(t=>t.intentType==='qa_review');assert(review.taskRuns.some(r=>r.state==='completed'&&r.adapterType==='scripted_mock')); }
    const firstPreview=await preview(id,recovered,'Continue');
    await acceptStyledPreview(firstPreview,route,'Continue','login');
    const label='Login '+route+' Verified';const followupMessage=await send(mentions+' for demo app change button text to '+label);
    tasks=await json(api+'/sessions/'+id+'/tasks');const followup=tasks.find(t=>t.createdByMessageId===followupMessage.id&&t.intentType==='frontend_change');
    assert.equal(followup.planJson.target,'primary_action_button_text');assert.equal(followup.planJson.targetText,label);
    const followupInitial=followup.taskRuns.length?null:await post(api+'/tasks/'+followup.id+'/runs/force-codex-failure');
    const changed=await fallback(id,followup,followupInitial);assert.equal(changed.recovered.state,'completed',JSON.stringify(changed.recovered));
    assert.equal(await readFile(file,'utf8'),login.replace(/            Continue(\r?\n)/,'            '+label+'$1'));
    assert.equal(sha(await readFile(file.replace('App.tsx','styles.css'))),stylesHash);
    const changedDiffs=await json(api+'/task-runs/'+changed.recovered.id+'/diffs');assert(changedDiffs.some(d=>d.patchText.includes('+            '+label)));
    const finalPreview=await preview(id,changed.recovered,label);
    await acceptStyledPreview(finalPreview,route,label,'copy',[390]);
    tasks=await json(api+'/sessions/'+id+'/tasks');const oldFailed=tasks.find(t=>t.id===writer.id).taskRuns.find(r=>r.id===failed.id);assert.equal(sha(frozenRun(oldFailed)),failureHash);
    const liveDiagnosticsChanged=Object.keys(failed).filter(key=>sha(failed[key])!==sha(oldFailed[key]));assert(liveDiagnosticsChanged.every(key=>['sessionQueue','targetLock','previewDeployJobs'].includes(key)));
    if(route==='group') await until(async()=> (await json(api+'/sessions/'+id+'/tasks')).filter(t=>t.intentType==='qa_review').every(t=>t.status==='completed'),'followup independent review');
    proof.routes.push({route,sessionId:id,loginTaskId:writer.id,failedRunId:failed.id,errorCode:failed.errorCode,scriptedRunId:recovered.id,
      followupTaskId:followup.id,followupRunId:changed.recovered.id,firstPreviewId:firstPreview.id,finalPreviewId:finalPreview.id,
      diffIds:diffs.map(d=>d.id),followupDiffIds:changedDiffs.map(d=>d.id),sourceSha256:sha(await readFile(file)),stylesSha256:stylesHash,failedHistorySha256:failureHash,liveDiagnosticsChanged});
    proof.checks.push(route+': UI message -> failed Codex -> UI explicit ScriptedMock recovery -> matching real login Diff/healthy iframe; same-Session button-only change');
    console.log('PASS '+route);
  }
  // A compound authentication request must retain generic semantics and refuse fallback without writes.
  const workspace=await json(api+'/workspaces/demo');proof.negative=[];
  for (const mentions of ['@frontend','@frontend @qa','@orchestrator']) {
  const negative=await post(api+'/workspaces/'+workspace.id+'/sessions',{title:'Unsupported login integration '+mentions});
  const negativeFile=await sourcePath(negative),negativeBefore=sha(await readFile(negativeFile));
  await post(api+'/sessions/'+negative.id+'/messages',{contentMd:mentions+' build a login page for the demo app with OAuth',context:{groupExecution:'manual'}});
  let negativeTasks=await json(api+'/sessions/'+negative.id+'/tasks');assert.equal(negativeTasks[0].planJson.target,'demo_frontend_request');
  const nf=await post(api+'/tasks/'+negativeTasks[0].id+'/runs/force-codex-failure');await terminal(negative.id,negativeTasks[0].id,nf.id);
  const nr=await post(api+'/task-runs/'+nf.id+'/retry-with-fallback');const rejected=await terminal(negative.id,negativeTasks[0].id,nr.id);
  assert.equal(rejected.state,'failed');assert.equal(rejected.errorCode,'SCRIPTED_MOCK_MUTATION_FAILED');assert.equal(sha(await readFile(negativeFile)),negativeBefore);
  assert.deepEqual(await json(api+'/task-runs/'+nr.id+'/diffs'),[]);
  proof.negative.push({mentions,sessionId:negative.id,failedFallbackId:nr.id,errorCode:rejected.errorCode,sourceSha256:negativeBefore});
  }
  proof.checks.push('All three routes reject unsupported OAuth compound fallback without source changes or Diff');
  await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('button',{name:/^执行过程/}).click();
  await page.getByRole('button',{name:'切换到暗色模式',exact:true}).click();
  await page.screenshot({path:output+'/dark-history.png'});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:output+'/narrow-history.png'});
  const before=await Promise.all(proof.routes.map(r=>metadata(api,r.sessionId))),historyHash=sha(before);
  await page.close();page=null;await stop(service);
  const restarted=start('restart');await ready(restarted);
  const after=await Promise.all(proof.routes.map(r=>metadata(api,r.sessionId)));assert.equal(sha(after),historyHash);
  page=await browser.newPage({viewport:{width:1440,height:900}});const route=proof.routes.find(r=>r.route==='group');
  await page.goto(web+'/?session='+route.sessionId,{waitUntil:'domcontentloaded'});await page.getByRole('button',{name:/^执行过程/}).click();
  await visible(page.getByText('兜底已恢复',{exact:true}));
  const fresh=await post(api+'/task-runs/'+route.followupRunId+'/preview');await until(async()=> (await json(api+'/task-runs/'+route.followupRunId+'/previews')).find(p=>p.id===fresh.id)?.healthStatus==='healthy','explicit restart preview');
  const standalone=await browser.newPage();await standalone.goto(fresh.url,{waitUntil:'domcontentloaded'});await standalone.getByRole('button',{name:'Login group Verified',exact:true}).waitFor();await standalone.locator('input[type=password]').waitFor();await measureForm(standalone,'group','restart',null);await standalone.setViewportSize({width:320,height:844});await measureForm(standalone,'group','restart',320);await standalone.screenshot({path:output+'/restored-login-preview.png',fullPage:true});
  const recoveredSession=await json(api+'/sessions/'+route.sessionId),recoveredFile=await sourcePath(recoveredSession);assert.equal(sha(await readFile(recoveredFile.replace('App.tsx','styles.css'))),route.stylesSha256);await standalone.close();proof.recoveredPreviewId=fresh.id;
  await page.screenshot({path:output+'/restored-group-history.png'});proof.historySha256Before=historyHash;proof.historySha256After=sha(after);
  proof.checks.push('API/Web restart preserves all three full Session/Message/TaskRun histories; explicit real Preview recovery matches group source');
  proof.browserErrors=errors;assert.deepEqual(errors,[]);assert.deepEqual(proof.formBrowserErrors||[],[]);
  assert.equal(sha(await metadata('http://127.0.0.1:8006',existingId)),sha(existing));assert.equal(sha(await readFile(existingFile)),existingSource);
  proof.existingSessionSha256=sha(existing);proof.existingSourceSha256=existingSource;proof.checks.push('Separate existing API8006, accepted history and native-written source unchanged');
  await stop(restarted);for(const [name,hash] of Object.entries(proof.executedSourceSha256)) assert.equal(sha(await readFile(root+'/'+name)),hash);assert.equal(sha(await readFile(new URL(import.meta.url))),proof.acceptanceScriptSha256);await writeFile(output+'/acceptance.json',JSON.stringify(proof,null,2));console.log(JSON.stringify({passed:proof.checks.length,routes:proof.routes.map(r=>r.route)}));
} catch(error) {
  if(page) { await page.screenshot({path:output+'/browser-error.png'}).catch(()=>{});console.log((await page.locator('body').innerText()).slice(0,4200)); }
  throw error;
} finally {
  if(browser) await browser.close();for(const service of services) if(!service.ended) await stop(service);for(const service of services) await writeFile(output+'/'+service.label+'.txt',service.log);
}
