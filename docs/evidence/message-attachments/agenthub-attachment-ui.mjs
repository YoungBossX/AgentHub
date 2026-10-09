import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const proof=JSON.parse(await readFile(root+'/attachment-codex-native.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050}});
page.setDefaultTimeout(30000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const checks=[];
try {
 await page.goto('http://127.0.0.1:3000/?session='+proof.sessionId);
 await page.getByRole('img',{name:'attachment-reference.png',exact:true}).waitFor();
 for(const width of [1440,390,320]){
  await page.setViewportSize({width,height:1000});
  for(const theme of ['light','dark']){
   const button=page.getByRole('button',{name:theme==='light'?'切换到亮色模式':'切换到暗色模式',exact:true});
   if(await button.count())await button.click();
   await page.waitForFunction(t=>document.documentElement.dataset.theme===t,theme);
   const result=await page.locator('#message-'+proof.messageId).evaluate(article=>{
    const bubble=article.lastElementChild;const image=article.querySelector('img');const box=article.getBoundingClientRect();
    return {article:article.clientWidth,scroll:article.scrollWidth,bubble:bubble.clientWidth,bubbleScroll:bubble.scrollWidth,imageWidth:image.getBoundingClientRect().width,imageReady:image.complete&&image.naturalWidth>0,viewport:innerWidth,right:box.right};
   });
   assert(result.scroll<=result.article+1,JSON.stringify(result));assert(result.bubbleScroll<=result.bubble+1,JSON.stringify(result));assert(result.imageReady);
   await page.screenshot({path:root+`/attachment-ui-${width}-${theme}.png`});
   checks.push({width,theme,...result});
  }
 }
 await page.setViewportSize({width:1440,height:1050});
 // File errors remain visible, block sending, and can be removed without a reload.
 await page.getByLabel('选择附件',{exact:true}).setInputFiles({name:'unsafe.svg',mimeType:'image/svg+xml',buffer:Buffer.from('<svg/>')});
 await page.getByRole('alert').filter({hasText:'不支持此格式'}).waitFor();
 await page.getByRole('textbox').fill('附件失败时不能误发送');
 assert(await page.getByRole('button',{name:'发送',exact:true}).isDisabled());
 await page.getByRole('button',{name:'移除附件 unsafe.svg',exact:true}).click();
 await page.getByRole('textbox').fill('');
 await page.getByLabel('选择附件',{exact:true}).setInputFiles(root+'/attachment-reference.txt');
 await page.getByRole('list',{name:'待发送附件'}).getByText(/文字已提取/).waitFor();
 const removed=page.waitForResponse(r=>r.request().method()==='DELETE'&&r.url().includes('/attachments/'));
 await page.getByRole('button',{name:'移除附件 attachment-reference.txt',exact:true}).click();
 assert.equal((await removed).status(),204);
 await page.getByRole('list',{name:'待发送附件'}).waitFor({state:'hidden'});
 await page.reload();await page.getByRole('img',{name:'attachment-reference.png',exact:true}).waitFor();
 assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
 assert.deepEqual(errors,[]);
 await writeFile(root+'/attachment-ui.json',JSON.stringify({checks,errors,extra:['invalid format remains visible and blocks send','remove failed draft recovers composer','real upload and DELETE remove pending bytes','sent attachment and dark theme survive reload']},null,2));
 console.log(JSON.stringify({checks:checks.length,errors}));
}finally{await browser.close()}
