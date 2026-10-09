import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);const {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-regeneration-20261009';const proof=JSON.parse(await readFile(root+'/network.json','utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:320,height:844}});
try{
 await page.goto('http://127.0.0.1:3000/?session='+proof.sourceSessionId);
 const bubble=page.locator('#message-'+proof.operationId);await bubble.waitFor();
 const result=await bubble.evaluate(article=>[article,...article.querySelectorAll('div,p,section')].map(el=>({tag:el.tagName,class:el.className,width:el.getBoundingClientRect().width,left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right,client:el.clientWidth,scroll:el.scrollWidth,text:el.textContent.slice(0,60)})).filter(x=>x.right>320||x.scroll>x.client+2));
 await writeFile(root+'/layout-overflow.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 await bubble.getByRole('link',{name:'查看原消息'}).scrollIntoViewIfNeeded();await page.screenshot({path:root+'/summary-actions-320.png'});
}finally{await browser.close()}
