import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const phase=process.argv[2]??'before-restart';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const results=[];
try{
 for(const mode of ['codex','claude']){
  const proof=JSON.parse(await readFile(root+`/attachment-${mode}-native.json`,'utf8'));
  const response=await page.request.post(`http://127.0.0.1:8006/task-runs/${proof.runId}/preview`,{data:{},timeout:90000});
  assert(response.ok(),await response.text());
  const preview=await response.json();assert.equal(preview.healthStatus,'healthy');
  await page.goto(preview.url,{waitUntil:'networkidle'});
  await page.getByRole('heading',{name:'Aurora Workshop 617',exact:true}).waitFor();
  if(mode==='codex')await page.getByRole('button',{name:'Cedar Beacon 842',exact:true}).waitFor();
  await page.screenshot({path:root+`/attachment-${mode}-preview-${phase}.png`});
  await page.goto('http://127.0.0.1:3000/?session='+proof.sessionId,{waitUntil:'domcontentloaded'});
  await page.locator('#message-'+proof.messageId).waitFor();
  await page.getByRole('button',{name:/^成果/}).click();
  await page.getByRole('button',{name:/网页预览/}).filter({hasText:'ready · healthy'}).last().click();
  const iframe=page.locator('iframe[title="Vite React 预览"]');
  await iframe.waitFor({state:'attached'});
  await page.frameLocator('iframe[title="Vite React 预览"]').getByRole('heading',{name:'Aurora Workshop 617',exact:true}).waitFor();
  results.push({mode,previewId:preview.id,health:preview.healthStatus,runId:proof.runId,checks:['actual Vite heading matches file','actual button matches image if Codex','workspace iframe loads actual result']});
 }
 assert.deepEqual(errors,[]);
 await writeFile(root+`/attachment-preview-${phase}.json`,JSON.stringify({phase,results,errors},null,2));
 console.log(JSON.stringify({phase,results}));
}finally{await browser.close()}
