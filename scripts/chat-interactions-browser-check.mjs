// Actual components + production CSS in an offline browser fixture. No server/model/OS-IME claims.
import assert from "node:assert/strict"
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises"
import { isAbsolute, relative, resolve } from "node:path"
import { createRequire } from "node:module"
import { pathToFileURL } from "node:url"
import { chromium } from "playwright"

const output = process.env.AGENTHUB_UI_OUTPUT
assert(output && isAbsolute(output))
const outside = relative(process.cwd(), resolve(output))
assert(isAbsolute(outside) || outside.startsWith("../") || outside.startsWith("..\\"))
await mkdir(output, { recursive: true })
const results = [], errors = [], mutations = []
const filename = "项目资料/中文协作需求与多角色执行结果验收记录及版本说明文件.d.ts"
let count = 35
const source = resolve("apps/web/src").replaceAll("\\", "/")
const requireWeb = createRequire(resolve("apps/web/package.json"))
const requireDemo = createRequire(resolve("apps/demo/package.json"))
const { build } = await import(pathToFileURL(requireDemo.resolve("vite")).href)
const { default: react } = await import(pathToFileURL(requireDemo.resolve("@vitejs/plugin-react")).href)
const fixture = resolve(output, "offline")
await mkdir(fixture, { recursive: true })
await writeFile(resolve(fixture, "fixture.tsx"), `
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { WorkbenchLayout } from "${source}/components/workbench-layout";
import { MessageComposer } from "${source}/components/message-composer";
import { WorkspaceHeader } from "${source}/components/workspace-shell-header";
import { ConversationScroll } from "${source}/components/conversation-scroll";
import { MessageAttachments } from "${source}/components/message-attachments";
import { useInspectorState } from "${source}/components/use-inspector-state";
import { useWorkbenchViewport } from "${source}/components/use-workbench-viewport";
function Fixture() {
  const viewport = useWorkbenchViewport();
  const [epoch,setEpoch] = useState(0);
  React.useEffect(()=>{window.__uiSwitchSession=()=>setEpoch(n=>n+1);return()=>{delete window.__uiSwitchSession}},[]);
  const [count,setCount] = useState(35), [draft,setDraft] = useState("中文输入与协作界面验收");
  const inspector = useInspectorState("fixture",false);
  const messages = Array.from({length:count},(_,i)=>({id:"interaction-"+i,contentMd:"第 "+(i+1)+" 条中文阅读验收消息"}));
  return <section key={epoch} ref={viewport} className="workspace-viewport h-dvh flex flex-col" data-region="app-shell">
    <WorkbenchLayout className={"workbench-layout h-full min-h-0 "+(inspector.collapsed?"inspector-collapsed":"")}
      inspectorCollapsed={inspector.collapsed} inspectorExpanded={false} onCollapseInspector={inspector.close}>
      <div className="workbench-sidebar"><aside style={{padding:16}}>协作 Agent<br/>前端 · 后端 · QA<br/><button aria-label="追加验收消息" onClick={()=>setCount(n=>n+1)}>追加验收消息</button></aside></div>
      <main className="workbench-main flex min-h-0 min-w-0 flex-col overflow-hidden bg-white">
        <WorkspaceHeader conversationMode="group" onModeChange={()=>{}} selectedSessionTitle="离线组件交互验收夹具" taskCount={count} stages={[]} view="conversation" onViewChange={()=>{}} artifactCount={1} onToggleSidebar={()=>{}} onToggleInspector={inspector.toggleDesktop}/>
        <ConversationScroll sessionId="fixture" active loading={false} historical={false} messages={messages}>
          {messages.map((message,i)=><article id={"message-"+message.id} key={message.id} style={{padding:16,marginBottom:12,background:"var(--surface-muted)",borderRadius:12}}>
            <p>{message.contentMd}</p><p>这里验证阅读位置、滚动意图和文件展示，不代表真实模型任务。</p>
            {i===34?<MessageAttachments backendUrl="" items={[{id:"ui-file",sessionId:"fixture",filename:${JSON.stringify(filename)},kind:"text",byteSize:20,extractionStatus:"ready",sha256:"fixture"}]} />:null}
          </article>)}
        </ConversationScroll>
        <div className="composer-dock shrink-0 px-5 pb-4 pt-2"><MessageComposer contextItems={[{id:"fixture-note",kind:"note",title:"上下文操作验收",summary:"验证容器层次与无边框操作按钮"}]} draft={draft} isPending={false} onAttach={()=>{}}
          onClearContext={()=>{}} onDraftChange={setDraft} onMoveContextItem={()=>{}} onRemoveContextItem={()=>{}}
          onSubmit={event=>{event.preventDefault();window.__uiSubmits=(window.__uiSubmits??0)+1;}} /></div>
      </main>
      <div className="workbench-inspector flex min-h-0 min-w-0 flex-col"><aside style={{height:"100%",padding:16}}>
        <button aria-label="关闭产物" onClick={inspector.close}>关闭预览</button>
        <iframe title="拖拽输入隔离验收" style={{width:"100%",height:"80%",border:0}} srcDoc="<p>预览 iframe 验收夹具</p>" />
      </aside></div>
    </WorkbenchLayout></section>;
}
createRoot(document.getElementById("root")).render(<Fixture/>);
`)
await build({ configFile: false, root: fixture, cacheDir: resolve(fixture, "cache"), plugins: [react()], define: { "process.env.NODE_ENV": JSON.stringify("production") },
  resolve: { alias: [ {find:"@",replacement:source}, ...["react", "react/jsx-runtime", "react-dom/client"].map(name=>({find:new RegExp("^"+name+"$"),replacement:requireWeb.resolve(name)})) ] },
  build: { outDir: resolve(fixture,"bundle"), emptyOutDir: false, minify: false, lib: {entry:resolve(fixture,"fixture.tsx"),name:"AgentHubFixture",formats:["iife"],fileName:()=>"fixture.js"} } })
const cssDirectory = resolve("apps/web/.next/static/chunks")
let css = ""
const cssLinks = []
await mkdir(resolve(fixture,"styles"), { recursive: true })
for (const file of await readdir(cssDirectory)) if (file.endsWith(".css")) {
  const candidate = await readFile(resolve(cssDirectory,file),"utf8")
  if (candidate.includes("--control-radius")) css += candidate
  // Next splits preflight/theme/utilities across chunks. Keep every original
  // stylesheet and relative import; copying only globals gives native borders.
  await writeFile(resolve(fixture,"styles",file),candidate)
  cssLinks.push(`<link rel="stylesheet" href="./styles/${file}">`)
}
assert(css.includes(".composer-surface"), "Build the current web app before browser checks")
await writeFile(resolve(fixture,"index.html"), `<!doctype html><html data-theme="light"><meta charset="utf-8">${cssLinks.join("")}<style>#root{height:100vh;display:flex;flex-direction:column}.workbench-layout{flex:1;height:auto}</style><body><div id="root"></div><script src="./bundle/fixture.js"></script></body></html>`)
const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chrome", headless: true, chromiumSandbox: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, hasTouch: true, serviceWorkers: "block", acceptDownloads: false })
  await context.route("**/*", route => {
    const request = route.request(), url = new URL(request.url())
    if (!request.url().startsWith(pathToFileURL(fixture).href) && url.protocol !== "about:") return route.abort()
    if (request.method() !== "GET") { mutations.push(`${request.method()} ${url.pathname}`); return route.abort() }
    return route.continue()
  })
  const page = await context.newPage()
  page.on("pageerror", error => errors.push(error.message))
  await page.goto(pathToFileURL(resolve(fixture,"index.html")).href)
  const composer = page.getByRole("textbox", { name: "消息", exact: true })
  const scroller = page.locator('[data-region="center-scroll"]')
  const layout = page.locator(".workbench-layout")
  await composer.waitFor()
  await page.locator(`#message-interaction-${count - 1}`).waitFor()
  const measure = () => scroller.evaluate(el => ({ top: el.scrollTop, distance: el.scrollHeight - el.clientHeight - el.scrollTop }))
  const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  const refresh = async () => {
    await page.getByRole("button", { name: "追加验收消息", exact: true }).evaluate(el => el.click())
    await page.locator(`#message-interaction-${count - 1}`).waitFor()
    await settle()
  }
  const scrollDistance = async distance => {
    await scroller.evaluate((el, distance) => { el.scrollTop = el.scrollHeight - el.clientHeight - distance; el.dispatchEvent(new Event("scroll")) }, distance)
    await settle()
  }

  await composer.fill("短需求")
  const inputHeight = () => composer.evaluate(el => el.getBoundingClientRect().height)
  const shortHeight = await inputHeight()
  await composer.fill("请核对中文任务拆解、文件修改范围与执行结果。\n".repeat(24))
  const longInput = await composer.evaluate(el => ({ height: el.clientHeight, content: el.scrollHeight, overflow: getComputedStyle(el).overflowY }))
  assert(longInput.height > shortHeight && longInput.height <= 240)
  assert(longInput.content > longInput.height && longInput.overflow === "auto")
  await composer.fill("")
  assert.equal(await inputHeight(), shortHeight)
  await composer.fill("这是用于验收输入框自适应宽度的中文需求，请保持选区与文字完整。".repeat(3))
  const wideHeight = await inputHeight()
  await composer.evaluate(el => el.setSelectionRange(2, 6))
  await page.setViewportSize({width:390,height:844}); await settle()
  assert(await inputHeight() > wideHeight)
  assert.deepEqual(await composer.evaluate(el=>[el.selectionStart,el.selectionEnd]),[2,6])
  for (const name of ["添加附件", "发送"]) {
    const box = await page.getByRole("button",{name,exact:true}).boundingBox()
    assert(box.width >= 44 && box.height >= 44)
  }
  results.push({check:"adaptive-input-grow-clear-width-selection-and-touch-targets",passed:true})
  await page.setViewportSize({width:1440,height:1000}); await settle()

  await composer.fill("中文输入法边界验收")
  await composer.evaluate(el => {
    window.__uiSubmits = 0
    el.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true }))
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }))
    el.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }))
    el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }))
  })
  assert.equal(await page.evaluate(() => window.__uiSubmits), 0)
  await page.waitForTimeout(520)
  await composer.dispatchEvent("keydown", { key: "Enter", keyCode: 229 })
  await composer.dispatchEvent("keydown", { key: "Enter", isComposing: true })
  assert.equal(await page.evaluate(() => window.__uiSubmits), 0)
  await composer.press("Enter")
  assert.equal(await page.evaluate(() => window.__uiSubmits), 1)
  await composer.press("Shift+Enter")
  assert.equal(await page.evaluate(() => window.__uiSubmits), 1)
  results.push({ check: "ime-events-229-and-500ms-submission-guard", passed: true })

  await scrollDistance(41)
  const held = (await measure()).top
  count++; await refresh()
  assert(Math.abs((await measure()).top - held) < 2)
  await scrollDistance(40)
  count++; await refresh()
  assert((await measure()).distance < 2)
  await scroller.hover(); await page.mouse.wheel(0, -20)
  await page.waitForFunction(() => { const el = document.querySelector('[data-region="center-scroll"]'); return el.scrollHeight - el.clientHeight - el.scrollTop > 2 })
  await settle()
  const manuallyHeld = (await measure()).top
  count++; await refresh()
  assert(Math.abs((await measure()).top - manuallyHeld) < 2)
  await scrollDistance(120)
  assert.equal(await page.getByRole("button", { name: /跳至最新/ }).count(), 0)
  await scrollDistance(121)
  await page.getByRole("button", { name: /跳至最新/ }).click()
  assert((await measure()).distance < 2)
  results.push({ check: "40-41px-follow-manual-wheel-pause-and-120-121px-jump", passed: true })

  await page.getByRole("button", { name: "切换成果面板", exact: true }).click()
  const separator = page.getByRole("separator", { name: "调整成果面板宽度" })
  await separator.waitFor()
  const oldWidth = Number(await separator.getAttribute("aria-valuenow"))
  const box = await separator.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + 80); await page.mouse.down()
  await page.mouse.move(box.x - 60, box.y + 80)
  assert(Number(await separator.getAttribute("aria-valuenow")) > oldWidth)
  const shield = await page.locator(".workbench-drag-shield").evaluate(el => {
    const css = getComputedStyle(el), rect = el.getBoundingClientRect()
    return { background: css.backgroundColor, target: document.elementFromPoint(rect.right - 20, rect.top + 160) === el }
  })
  assert.equal(shield.background, "rgba(0, 0, 0, 0)"); assert(shield.target)
  await page.keyboard.press("Escape"); await page.mouse.up()
  assert.equal(Number(await separator.getAttribute("aria-valuenow")), oldWidth)
  assert.equal(await page.locator(".workbench-drag-shield").count(), 0)
  await separator.dblclick()
  const sizes = await layout.evaluate(el => ({ columns: getComputedStyle(el).gridTemplateColumns.split(" ").map(parseFloat), width: el.clientWidth }))
  assert(Math.abs(sizes.columns[1] - sizes.columns[2]) <= 1)
  results.push({ check: "transparent-shield-hit-testing-escape-and-50-50-reset", sizes, passed: true })
  const resetBox = await separator.boundingBox()
  await page.mouse.move(resetBox.x + resetBox.width / 2, resetBox.y + 80); await page.mouse.down()
  await page.mouse.move(sizes.columns[0] + (sizes.width - sizes.columns[0]) * .85, resetBox.y + 80)
  await page.mouse.up()
  assert((await layout.getAttribute("class")).includes("inspector-collapsed"))
  await page.getByRole("button", { name: "切换成果面板", exact: true }).click()
  assert(await separator.isVisible())
  assert(Number(await separator.getAttribute("aria-valuenow")) >= 280)
  results.push({ check: "over-82-percent-collapse-and-reopen", passed: true })

  for (const width of [1440, 1024, 390]) for (const theme of ["light", "dark"]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await page.evaluate(theme=>{document.documentElement.dataset.theme=theme},theme)
    if (width < 1200 && await page.locator(".workbench-inspector").isVisible()) await page.getByRole("button", { name: "关闭产物", exact: true }).click()
    await scrollDistance(0); await composer.focus()
    const geometry = await composer.evaluate(el => {
      const surface = el.form, css = getComputedStyle(surface), button = surface.querySelector('button[type="submit"]'), child = getComputedStyle(button)
      const input = getComputedStyle(el)
      return { radius: parseFloat(css.borderRadius), padding: parseFloat(css.padding), inner: parseFloat(child.borderRadius), border: css.borderWidth, shadow: css.boxShadow, buttonBorder: child.borderWidth, textareaBorder: input.borderWidth, textareaShadow: input.boxShadow, textareaOutline: input.outlineStyle }
    })
    assert.equal(geometry.radius, geometry.inner + geometry.padding)
    assert.equal(geometry.border, "0px"); assert.equal(geometry.buttonBorder, "0px"); assert(geometry.shadow.includes("inset"))
    assert.equal(geometry.textareaBorder,"0px"); assert.equal(geometry.textareaShadow,"none"); assert.equal(geometry.textareaOutline,"none")
    const action = page.getByRole("button", {name:"移除上下文 上下文操作验收",exact:true})
    await page.mouse.move(0,0)
    const before = await action.evaluate(el=>({background:getComputedStyle(el).backgroundColor,width:el.offsetWidth,border:getComputedStyle(el).borderWidth}))
    await action.hover(); await page.waitForTimeout(180)
    const after = await action.evaluate(el=>({background:getComputedStyle(el).backgroundColor,width:el.offsetWidth,border:getComputedStyle(el).borderWidth}))
    assert.notEqual(before.background,after.background); assert.equal(before.width,after.width); assert.equal(after.border,"0px")
    const label = page.getByTitle(filename, { exact: true }).last()
    await label.scrollIntoViewIfNeeded()
    const filenameGeometry = await label.evaluate(el => {
      const prefix = el.querySelector(".filename-prefix"), suffix = el.querySelector(".filename-suffix"), css = getComputedStyle(prefix)
      return { prefixClips: prefix.scrollWidth > prefix.clientWidth, ellipsis: css.textOverflow, suffix: suffix.textContent, suffixFits: suffix.scrollWidth <= suffix.clientWidth + 1, title: el.title }
    })
    assert.equal(filenameGeometry.ellipsis, "ellipsis"); assert(filenameGeometry.suffix.endsWith(".d.ts")); assert(filenameGeometry.suffixFits)
    if (width === 390) assert(filenameGeometry.prefixClips)
    await scrollDistance(121)
    const jump = page.getByRole("button", {name:/跳至最新/})
    await jump.hover(); await page.waitForTimeout(180)
    const contrast = await jump.evaluate(el=>{
      const css=getComputedStyle(el)
      function luminance(color) {
        const values=color.match(/[\d.]+/g).slice(0,3).map(Number)
        const rgb=values.map(value=>color.startsWith("color(srgb")?value:value/255).map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4)
        return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]
      }
      const a=luminance(css.color), b=luminance(css.backgroundColor)
      return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)
    })
    assert(contrast>=4.5,`Jump action hover contrast ${contrast}`)
    assert(await page.locator("html").evaluate(el => el.scrollWidth <= el.clientWidth))
    await page.screenshot({ path: resolve(output, `${width}-${theme}.png`) })
    results.push({ check: `${width}-${theme}-radius-inset-filename-and-overflow`, geometry, filenameGeometry, jumpHoverContrast:contrast, passed: true })
  }
  await page.emulateMedia({forcedColors:"active"})
  const action = page.getByRole("button", {name:"移除上下文 上下文操作验收",exact:true})
  await action.focus()
  await page.keyboard.press("Tab"); await page.keyboard.press("Shift+Tab")
  assert(await action.evaluate(el=>el.matches(":focus-visible")))
  assert.notEqual(await action.evaluate(el=>getComputedStyle(el).outlineStyle),"none")
  await page.emulateMedia({forcedColors:"none"})
  results.push({check:"forced-colors-keyboard-focus",passed:true})

  const keyboardPage = await context.newPage()
  keyboardPage.on("pageerror", error => errors.push(error.message))
  await keyboardPage.setViewportSize({width:390,height:844})
  await keyboardPage.addInitScript(() => {
    class SimulatedViewport extends EventTarget {
      height = 844; offsetTop = 0; scale = 1
    }
    window.__simulatedViewport = new SimulatedViewport()
    Object.defineProperty(window,"visualViewport",{configurable:true,value:window.__simulatedViewport})
  })
  await keyboardPage.goto(pathToFileURL(resolve(fixture,"index.html")).href)
  await keyboardPage.getByRole("textbox",{name:"消息",exact:true}).fill("长需求\n".repeat(24))
  for (const theme of ["light","dark"]) {
    await keyboardPage.evaluate(theme=>{
      document.documentElement.dataset.theme=theme
      Object.assign(window.__simulatedViewport,{height:360,offsetTop:24})
      window.__simulatedViewport.dispatchEvent(new Event("resize"))
    },theme)
    await keyboardPage.getByRole("button",{name:"上下文与附件",exact:true}).waitFor()
    await keyboardPage.waitForTimeout(280)
    await keyboardPage.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))
    const shell = await keyboardPage.locator('[data-region="app-shell"]').boundingBox()
    const send = await keyboardPage.getByRole("button",{name:"发送",exact:true}).boundingBox()
    assert.equal(Math.round(shell.height),360); assert.equal(Math.round(shell.y),24)
    assert(send.y>=shell.y && send.y+send.height<=shell.y+shell.height,`Send must stay in simulated viewport: ${JSON.stringify({shell,send})}`)
    const input = await keyboardPage.getByRole("textbox",{name:"消息",exact:true}).evaluate(el=>({height:el.clientHeight,content:el.scrollHeight}))
    assert(input.content>input.height)
    assert(await keyboardPage.locator("html").evaluate(el=>el.scrollWidth<=el.clientWidth))
    await keyboardPage.screenshot({path:resolve(output,`390-${theme}-simulated-keyboard.png`)})
    results.push({check:`simulated-keyboard-${theme}-bounded-input-and-visible-send`,passed:true})
  }
  const referenceToggle=keyboardPage.getByRole("button",{name:"上下文与附件",exact:true})
  await referenceToggle.tap()
  await keyboardPage.waitForTimeout(280)
  const removeReference=keyboardPage.getByRole("button",{name:"移除上下文 上下文操作验收",exact:true})
  await removeReference.scrollIntoViewIfNeeded()
  assert(await referenceToggle.evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}),"Message scroller must not intercept reference controls")
  const referenceBox=await removeReference.boundingBox()
  const visibleShell=await keyboardPage.locator('[data-region="app-shell"]').boundingBox()
  assert(referenceBox.y>=visibleShell.y && referenceBox.y+referenceBox.height<=visibleShell.y+visibleShell.height)
  await referenceToggle.tap()
  await keyboardPage.waitForTimeout(280)
  await keyboardPage.evaluate(()=>{
    window.__oldShell=document.querySelector('[data-region="app-shell"]')
    window.__uiSwitchSession()
  })
  await keyboardPage.waitForFunction(()=>window.__oldShell!==document.querySelector('[data-region="app-shell"]'))
  await keyboardPage.evaluate(()=>{
    Object.assign(window.__simulatedViewport,{height:320,offsetTop:18})
    window.__simulatedViewport.dispatchEvent(new Event("resize"))
  })
  await keyboardPage.waitForFunction(()=>document.querySelector('[data-region="app-shell"]').style.getPropertyValue("--workspace-viewport-height")==="320px")
  assert.equal(await keyboardPage.evaluate(()=>window.__oldShell.style.getPropertyValue("--workspace-viewport-height")),"")
  const switchedShell=await keyboardPage.locator('[data-region="app-shell"]').boundingBox()
  const switchedSend=await keyboardPage.getByRole("button",{name:"发送",exact:true}).boundingBox()
  assert(switchedSend.y>=switchedShell.y && switchedSend.y+switchedSend.height<=switchedShell.y+switchedShell.height)
  results.push({check:"short-viewport-reference-access-and-session-node-rebinding",passed:true})
  await keyboardPage.evaluate(()=>{
    window.__simulatedViewport.scale=2
    window.__simulatedViewport.dispatchEvent(new Event("resize"))
  })
  assert.equal(await keyboardPage.locator('[data-region="app-shell"]').evaluate(el=>el.style.getPropertyValue("--workspace-viewport-height")),"")
  await keyboardPage.close()
  results.push({check:"simulated-pinch-zoom-preserves-browser-control",passed:true})
  assert.deepEqual(errors, []); assert.deepEqual(mutations, [])
  await writeFile(resolve(output, "result.json"), JSON.stringify({ evidence: "Actual components and production CSS, offline Edge fixture; no server, model tasks, full-workbench or OS IME candidate-window claim", results, errors, mutations }, null, 2))
  console.log(JSON.stringify({ checks: results.length, errors, mutations }))
} catch (error) {
  await writeFile(resolve(output, "failure.json"), JSON.stringify({ error: String(error), results, errors, mutations }, null, 2))
  throw error
} finally { await browser.close() }
