import {createRequire} from 'node:module';import {readFile,writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),{chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009',api='http://127.0.0.1:8006';
const load=async name=>JSON.parse(await readFile(root+'/'+name+'.json','utf8'));
const native=await load('native'),selection=await load('selection-runtime'),codex=await load('codex-followup'),recovery=await load('recovery');
assert(native.passed&&selection.passed&&codex.passed&&recovery.passed);
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),report={errors:[],cases:[]};page.setDefaultTimeout(45000);page.on('pageerror',error=>report.errors.push(error.message));
async function req(path,data){const response=data===undefined?await page.request.get(api+path):await page.request.post(api+path,{data,timeout:90000});assert(response.ok(),await response.text());return response.json()}
try{
 const cases=[{key:'codex',session:native.sessions.codex,run:codex.run,heading:'Final Codex 735'},
 {key:'claude',session:native.sessions.claude,run:selection.run,heading:'Selected Context 735'},
 {key:'fallback',session:recovery.session,run:recovery.recovered}];
 for(const row of cases){
  const tasks=await req(`/sessions/${row.session.id}/tasks`);row.taskTitle=tasks.find(task=>task.taskRuns.some(run=>run.id===row.run.id)).title;
  row.preview=await req(`/task-runs/${row.run.id}/preview`,{});assert.equal(row.preview.healthStatus,'healthy');
  await page.goto('http://127.0.0.1:3000/?session='+row.session.id,{waitUntil:'domcontentloaded'});
  const light=page.getByRole('button',{name:'切换到亮色模式',exact:true});if(await light.count())await light.click();
  await page.getByRole('button',{name:/^成果/}).click();
  await page.getByRole('region',{name:'会话成果',exact:true}).getByRole('button').filter({hasText:'网页预览'}).filter({hasText:row.taskTitle}).last().click();
  const frame=page.frameLocator('iframe[title="Vite React 预览"]');
  if(row.heading)await frame.getByRole('heading',{name:row.heading,exact:true}).waitFor();else await frame.locator('input[type="email"]').waitFor();
  await page.getByRole('button',{name:new RegExp('^'+row.session.title.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))}).first().click();
  if(row.heading)await frame.getByRole('heading',{name:row.heading,exact:true}).waitFor();else await frame.locator('input[type="password"]').waitFor();
  row.reselectPreservesPreview=true;
  await page.screenshot({path:root+`/final-${row.key}-preview.png`});
  if(row.key==='fallback'){row.deployment=await req(`/previews/${row.preview.id}/deploy`,{providerId:'mock',environment:'preview'});assert.equal(row.deployment.provider,'mock');assert.equal(row.deployment.status,'ready')}
  report.cases.push({key:row.key,sessionId:row.session.id,runId:row.run.id,preview:row.preview,deployment:row.deployment,reselectPreservesPreview:true});
 }
 assert.deepEqual(report.errors,[]);report.passed=true;console.log(JSON.stringify({passed:true,cases:report.cases.map(row=>row.key)}));
}catch(error){report.failure=String(error);console.error(error);process.exitCode=1;await page.screenshot({path:root+'/final-browser-failure.png'}).catch(()=>{})}
finally{await writeFile(root+'/final-browser.json',JSON.stringify(report,null,2));await browser.close()}
