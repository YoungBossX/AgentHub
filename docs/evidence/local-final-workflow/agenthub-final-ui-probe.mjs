import {createRequire} from 'node:module';import {mkdir,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out='C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009';await mkdir(out,{recursive:true});
const phase=process.argv[2]??'after';
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const result={errors,measurements:[]};
try{
 await page.goto('http://127.0.0.1:3000/?session=61107635-b6c9-49e8-99b8-42ad57e7f68e',{waitUntil:'domcontentloaded'});
 for(const theme of ['light','dark']){
  const button=page.getByRole('button',{name:theme==='light'?'切换到亮色模式':'切换到暗色模式',exact:true});if(await button.count())await button.click();
  for(const width of [1440,1024,768,390,320]){
   await page.setViewportSize({width,height:900});await page.getByRole('textbox',{name:'消息',exact:true}).fill('本地终验草稿，仅测量，不发送。');
   const data=await page.locator('[data-region="composer"]').evaluate(form=>({form:{x:form.getBoundingClientRect().x,right:form.getBoundingClientRect().right,width:form.getBoundingClientRect().width},controls:Array.from(form.querySelectorAll('button,textarea')).map(e=>{const r=e.getBoundingClientRect();const top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {tag:e.tagName,label:e.getAttribute('aria-label')||e.textContent,x:r.x,right:r.right,y:r.y,bottom:r.bottom,width:r.width,height:r.height,hit:!!top&&(top===e||e.contains(top))}})}));
   result.measurements.push({theme,width,...data});await page.screenshot({path:out+`/composer-${width}-${theme}-${phase}.png`});
  }
 }
 console.log(JSON.stringify(result));
}finally{await writeFile(out+`/composer-${phase}.json`,JSON.stringify(result,null,2));await browser.close()}
