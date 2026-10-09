import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url), {chromium}=require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009', api='http://127.0.0.1:8006';
const native=JSON.parse(await readFile(root+'/native.json','utf8'));assert(native.passed,'Native baseline must finish first');
const session=native.sessions.claude, sourcePath=session.worktreePath+'/apps/demo/src/App.tsx';
const report={errors:[],measurements:[],sessionId:session.id};
const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(45000);page.on('pageerror',error=>report.errors.push(error.message));
async function get(path){const r=await page.request.get(api+path);assert(r.ok(),await r.text());return r.json()}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 await page.goto('http://127.0.0.1:3000/?session='+session.id,{waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:/^成果/}).click();
 await page.getByRole('region',{name:'会话成果',exact:true}).getByRole('button').filter({hasText:'代码变更'}).first().click();
 await page.getByRole('button',{name:'编辑完整源码 / 应用补丁',exact:true}).click();await page.getByRole('button',{name:'读取完整源码',exact:true}).click();
 await page.locator('.monaco-editor').first().waitFor();await page.getByRole('button',{name:'纯文本模式',exact:true}).click();
 const original=await readFile(sourcePath,'utf8');const edited=original.replace(/(<h1\b[^>]*>)[^<]*(<\/h1>)/,'$1Selected Context 735$2');assert.notEqual(edited,original);
 const source=page.getByRole('textbox',{name:'完整源码',exact:true});await source.fill(edited);await page.getByRole('button',{name:'代码编辑器',exact:true}).click();
 const editor=page.locator('.monaco-editor textarea').first();await editor.waitFor();await page.locator(".monaco-editor .view-lines").first().click();
 const lines=edited.replaceAll('\r\n','\n').split('\n'), index=lines.findIndex(line=>line.includes('Selected Context 735'));assert(index>=0);
 await page.keyboard.press('Control+Home');for(let i=0;i<19;i++)await page.keyboard.press('Shift+ArrowRight');
 console.log(JSON.stringify({stage:'native-selection',enabled:await page.getByRole('button',{name:'引用选中代码',exact:true}).isEnabled()}));
 await page.getByRole('button',{name:'引用选中代码',exact:true}).click();
 await page.getByText('待发送上下文',{exact:true}).waitFor();assert.equal(await readFile(sourcePath,'utf8'),original,'Quoting applied a draft');
 report.nativeEditorSelection=edited.slice(0,19);report.draftNotApplied=true;
 await page.getByLabel('选择附件',{exact:true}).setInputFiles({name:'final-reference-734.txt',mimeType:'text/plain',buffer:Buffer.from('Keep all content other than the requested heading unchanged. Final reference 734.')});
 await page.getByText(/文字已提取/).first().waitFor();
 const composer=page.getByRole('textbox',{name:'消息',exact:true});await composer.fill('中文输入检查');
 const postCount=[];page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith(`/sessions/${session.id}/messages`))postCount.push(r.postDataJSON())});
 await composer.dispatchEvent('keydown',{key:'Enter',code:'Enter',isComposing:true,bubbles:true});await page.waitForTimeout(150);assert.equal(postCount.length,0);report.compositionEnterNotSent=true;
 await composer.press('Shift+Enter');assert((await composer.inputValue()).includes('\n'));assert.equal(postCount.length,0);report.shiftEnterNewline=true;
 for(const theme of ['light','dark']){
  const toggle=page.getByRole('button',{name:theme==='light'?'切换到亮色模式':'切换到暗色模式',exact:true});if(await toggle.count())await toggle.click();
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:1000});
   const controls=await page.locator('[data-region="composer"]').evaluate(form=>Array.from(form.querySelectorAll('button,textarea')).map(e=>{const b=e.getBoundingClientRect(),hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return {label:e.getAttribute('aria-label')||e.textContent,x:b.x,right:b.right,width:b.width,hit:!!hit&&(hit===e||e.contains(hit))}}));
   assert(controls.every(c=>c.x>=0&&c.right<=width&&c.hit),JSON.stringify(controls));report.measurements.push({theme,width,controls});await page.screenshot({path:root+`/selection-context-${width}-${theme}.png`});
  }
 }
 // Changing Sessions cannot carry selected code or attachments to another conversation.
 await page.setViewportSize({width:1440,height:1000});await page.getByRole('button',{name:/本地终验 · Codex 734/}).first().click();
 await page.waitForURL(url=>url.searchParams.get('session')===native.sessions.codex.id);
 assert.equal(await page.getByText('待发送上下文',{exact:true}).count(),0);report.sessionIsolation=true;
 await page.getByRole('button',{name:/本地终验 · Claude 协作 734/}).first().click();
 await page.waitForURL(url=>url.searchParams.get('session')===session.id);
 // Context is intentionally cleared on session change; quote again from the retained editor draft.
 await page.getByRole('button',{name:/^成果/}).click();await page.getByRole('region',{name:'会话成果',exact:true}).getByRole('button').filter({hasText:'代码变更'}).first().click();
 await page.getByRole('button',{name:'编辑完整源码 / 应用补丁',exact:true}).click();await page.locator('.monaco-editor').first().waitFor();await page.getByRole('button',{name:'纯文本模式',exact:true}).click();
 const text=page.getByRole('textbox',{name:'完整源码',exact:true});assert((await text.inputValue()).includes('Selected Context 735'));
 await text.evaluate(el=>{const start=el.value.indexOf('Selected Context 735');el.focus();el.setSelectionRange(start,start+'Selected Context 735'.length);el.dispatchEvent(new Event('select',{bubbles:true}))});
 await text.press('Shift+ArrowRight');await text.press('Shift+ArrowLeft');
 await page.getByRole('button',{name:'引用选中代码',exact:true}).click();
 await page.setViewportSize({width:320,height:1000});
 const prompt='@native-group-20261008 @created-front-731 请只创建一个 frontend_change 并执行：将 apps/demo/src/App.tsx 中现有主标题替换为我引用的编辑器草稿片段文字，其他内容不变。参考附件的保留要求。';
 await composer.fill(prompt);const sent=page.waitForResponse(r=>r.url().endsWith(`/sessions/${session.id}/messages`)&&r.request().method()==='POST',{timeout:240000});await composer.press('Enter');const response=await sent;assert(response.ok(),await response.text());report.message=await response.json();report.sentContext=postCount.at(-1);assert.equal(report.sentContext.context.contextItems[0].selectedText,'Selected Context 735');assert.equal(report.sentContext.attachmentIds.length,1);
 for(let i=0;i<240;i++){
  const tasks=await get(`/sessions/${session.id}/tasks`),task=tasks.find(task=>task.createdByMessageId===report.message.id),run=task?.taskRuns.at(-1);
  if(i%15===0)console.log(JSON.stringify({iteration:i,state:run?.state}));
  if(run?.state==='completed'){report.run=run;break}assert(!['failed','interrupted','cancelled'].includes(run?.state),JSON.stringify(run));assert(i<239,'Continuation timeout');await pause(2000);
 }
 const final=await readFile(sourcePath,'utf8');assert(final.includes('Selected Context 735'));report.diffs=await get(`/task-runs/${report.run.id}/diffs`);assert(report.diffs.some(diff=>diff.patchText.includes('Selected Context 735')));
 const previewResponse=await page.request.post(api+`/task-runs/${report.run.id}/preview`);assert(previewResponse.ok(),await previewResponse.text());report.preview=await previewResponse.json();assert.equal(report.preview.healthStatus,'healthy');
 const preview=await browser.newPage();await preview.goto(report.preview.url);await preview.getByRole('heading',{name:'Selected Context 735',exact:true}).waitFor();await preview.screenshot({path:root+'/selection-native-preview.png'});await preview.close();
 assert.deepEqual(report.errors,[]);report.passed=true;console.log(JSON.stringify({passed:true,runId:report.run.id}));
}catch(error){report.failure=String(error);console.error(error);process.exitCode=1;await page.screenshot({path:root+'/selection-failure.png'}).catch(()=>{})}
finally{await writeFile(root+'/selection-runtime.json',JSON.stringify(report,null,2));await browser.close()}
