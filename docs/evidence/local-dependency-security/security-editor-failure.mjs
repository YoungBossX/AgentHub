import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage();
let deny=true, blocked=0; const errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/_next/static/chunks/*_monaco-editor_esm_vs_base_common_observableInternal_*',route=>{
 if(deny){blocked++;return route.abort();}return route.continue();
});
try {
 await page.goto('http://127.0.0.1:3000/?session=c1b9feb0-10cc-48fe-9e23-0595b6d39c0d');
 await page.getByRole('button',{name:/^成果/}).click();
 await page.waitForTimeout(1000);
 console.log(JSON.stringify({phase:'before-diff',blocked,errors,body:(await page.locator('body').innerText()).slice(-2200)}));
 await page.getByRole('button',{name:/^代码变更/}).first().click();
 await page.getByRole('button',{name:'展开 Diff',exact:true}).click();
 await page.getByRole('button',{name:'并排对比',exact:true}).click();
 await page.getByText('对比编辑器加载失败，仍可查看上方代码补丁。',{exact:false}).waitFor();
 assert(blocked>0);assert((await page.getByLabel('代码补丁').innerText()).includes('Pinned Reference'));
 deny=false;
 await page.getByRole('button',{name:'重试加载',exact:true}).click();
 await page.locator('.monaco-diff-editor').waitFor({timeout:10000});
 assert.deepEqual(errors,[]);
 await writeFile('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/security-editor-failure.json',JSON.stringify({blocked,errors,checks:['local chunk unavailable retains patch','explicit retry loads editor after network recovers']},null,2));
 console.log(JSON.stringify({status:'passed',blocked,errors}));
}finally{await browser.close();}
