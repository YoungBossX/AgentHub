import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-creation-20261009',api='http://127.0.0.1:8006';
const proof=JSON.parse(await readFile(root+'/native.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
const report={errors};
try{
 const directory=await (await page.request.get(api+`/workspaces/${proof.workspaceId}/agent-directory`)).json();
 const saved=directory.entries.find(e=>e.id===proof.profile.id);assert(saved);assert.equal(saved.systemPrompt,proof.profile.systemPrompt);assert.equal(saved.status,'available');assert.equal(saved.toolPolicy,'claude_file_edit');
 await page.goto('http://127.0.0.1:3000/settings/agents');
 await page.getByRole('button',{name:'编辑 '+saved.displayName,exact:true}).click();
 assert.equal(await page.getByLabel('自定义 System Prompt',{exact:false}).inputValue(),proof.profile.systemPrompt);
 await page.getByLabel('自定义名称',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:root+'/restart-profile.png'});
 const res=await page.request.post(api+`/task-runs/${proof.execution.runId}/preview`,{data:{},timeout:90000});assert(res.ok(),await res.text());const preview=await res.json();assert.equal(preview.healthStatus,'healthy');
 await page.goto('http://127.0.0.1:3000/?session='+proof.session.id);await page.getByRole('button',{name:/^成果/}).click();
 await page.getByRole('button',{name:/网页预览/}).filter({hasText:'ready · healthy'}).last().click();
 await page.frameLocator('iframe[title="Vite React 预览"]').getByRole('heading',{name:'Created Agent 731',exact:true}).waitFor();await page.screenshot({path:root+'/restart-preview.png'});
 assert.deepEqual(errors,[]);Object.assign(report,{passed:true,profileId:saved.id,profilePromptPreserved:true,previewId:preview.id,iframeHeading:'Created Agent 731'});console.log(JSON.stringify(report));
}catch(error){report.failure=String(error);throw error}finally{await writeFile(root+'/restart-browser.json',JSON.stringify(report,null,2));await browser.close()}
