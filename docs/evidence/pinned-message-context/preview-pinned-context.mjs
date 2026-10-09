import {createRequire} from 'node:module';
import {readFile, writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const proof=JSON.parse(await readFile(root+'/pinned-context-native.json','utf8'));
const phase=process.argv[2];
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1280,height:850}});
page.setDefaultTimeout(30000);
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
try {
 const response=await page.request.post(`http://127.0.0.1:8006/task-runs/${proof.runId}/preview`,{data:{},timeout:90000});
 assert(response.ok(),await response.text());
 const preview=await response.json();
 assert.equal(preview.healthStatus,'healthy');
 await page.goto(preview.url,{waitUntil:'networkidle'});
 await page.getByRole('button',{name:proof.marker,exact:true}).waitFor();
 assert.deepEqual(errors,[]);
 await page.screenshot({path:root+`/pinned-context-preview-${phase}.png`});
 await page.goto('http://127.0.0.1:3000/?session='+proof.sessionId,{waitUntil:'domcontentloaded'});
 await page.locator('#message-'+proof.noteId).getByRole('button',{name:'取消置顶消息',exact:true}).waitFor();
 await writeFile(root+`/pinned-context-preview-${phase}.json`,JSON.stringify({phase,previewId:preview.id,healthStatus:preview.healthStatus,button:proof.marker,errors,checks:['actual Vite DOM displays label from pinned reference','pin still visible after reload']},null,2));
 console.log(JSON.stringify({phase,previewId:preview.id,health:preview.healthStatus}));
}finally{await browser.close();}
