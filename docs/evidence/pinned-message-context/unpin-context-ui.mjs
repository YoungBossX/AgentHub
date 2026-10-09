import {createRequire} from 'node:module';
import {readFile, writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const proof=JSON.parse(await readFile(root+'/pinned-context-native.json','utf8'));
const phase=process.argv[2];
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
page.setDefaultTimeout(30000);
try {
 await page.goto('http://127.0.0.1:3000/?session='+proof.sessionId,{waitUntil:'domcontentloaded'});
 const card=page.locator('#message-'+proof.noteId);
 const shouldPin=phase==='repin';
 await card.getByRole('button',{name:shouldPin?'置顶消息':'取消置顶消息',exact:true}).click();
 await card.getByRole('button',{name:shouldPin?'取消置顶消息':'置顶消息',exact:true}).waitFor();
 const response=await page.request.get(`http://127.0.0.1:8006/sessions/${proof.sessionId}/messages`);
 const selected=(await response.json()).find(item=>item.id===proof.noteId);
 assert.equal(!!selected.pinnedAt,shouldPin);
 await page.screenshot({path:root+`/pinned-context-${phase}.png`});
 await writeFile(root+`/pinned-context-${phase}.json`,JSON.stringify({phase,noteId:proof.noteId,pinnedAt:selected.pinnedAt,method:'actual browser pin control'},null,2));
 console.log(phase+' verified');
}finally{await browser.close();}
