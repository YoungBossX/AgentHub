import {createRequire} from 'node:module';import {readFile,writeFile} from 'node:fs/promises';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-edit-20261009',api='http://127.0.0.1:8006';
const proof=JSON.parse(await readFile(root+'/native.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(45000);
const result={errors:[]};page.on('pageerror',e=>result.errors.push(e.message));
try{
 const refused=await page.request.post(api+`/task-runs/${proof.first.run.id}/diff`);result.historicalDiffRefusal={status:refused.status(),body:await refused.json()};assert.equal(refused.status(),400);assert(result.historicalDiffRefusal.body.detail.includes('later user edits'));
 const response=await page.request.post(api+`/task-runs/${proof.second.run.id}/preview`,{data:{}});assert(response.ok(),await response.text());const preview=await response.json();assert.equal(preview.healthStatus,'healthy');result.preview=preview;
 await page.goto('http://127.0.0.1:3000/?session='+proof.session.id,{waitUntil:'domcontentloaded'});await page.getByRole('button',{name:/^成果/}).click();await page.getByRole('region',{name:'会话成果',exact:true}).getByRole('button').filter({hasText:'网页预览'}).filter({hasText:'ready · healthy'}).last().click();
 await page.frameLocator('iframe[title="Vite React 预览"]').getByRole('heading',{name:'Manual Edit User 732',exact:true}).waitFor();await page.frameLocator('iframe[title="Vite React 预览"]').getByText('Native Continuation 732',{exact:true}).waitFor();await page.getByTestId('user-revision-notice').waitFor();
 await page.getByText(/用户修改记录 · 最近/).click();const applied=page.locator('summary').filter({hasText:proof.operation.id.slice(0,8)});await applied.waitFor();assert((await applied.innerText()).includes('已应用'));
 await page.screenshot({path:root+'/restart-workbench.png',fullPage:true});assert.deepEqual(result.errors,[]);result.passed=true;console.log(JSON.stringify({passed:true,previewId:preview.id,operationId:proof.operation.id}));
}catch(error){result.failure=String(error);console.error(error);process.exitCode=1}
finally{await writeFile(root+'/restart-browser.json',JSON.stringify(result,null,2));await browser.close()}
