import assert from "node:assert/strict"
import { mkdir, writeFile } from "node:fs/promises"
import { isAbsolute, relative, resolve } from "node:path"
import { chromium } from "playwright"

const origin = process.env.AGENTHUB_UI_ORIGIN ?? "http://127.0.0.1:3000"
const api = process.env.AGENTHUB_UI_API_ORIGIN ?? "http://127.0.0.1:18080"
const session = process.env.AGENTHUB_UI_SESSION_ID
const output = process.env.AGENTHUB_UI_OUTPUT
assert(session && output && isAbsolute(output), "Set a fixture Session and absolute external output directory")
const outside = relative(process.cwd(), resolve(output))
assert(isAbsolute(outside) || outside.startsWith("../") || outside.startsWith("..\\"), "Keep screenshots outside the checkout")
await mkdir(output, { recursive: true })
const results = [], errors = [], blockedMutations = []
const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chrome", headless: true, chromiumSandbox: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: "block", acceptDownloads: false })
  let rich = false, failRefresh = false, count = 40, append = ""
  const stamp = index => new Date(Date.UTC(2026, 9, 23, 5, 0, index)).toISOString()
  const message = index => ({ id: `reading-${String(index).padStart(4, "0")}`, sessionId: session, senderType: index >= 39 || index % 2 ? "orchestrator" : "user", senderId: null,
    contentMd: index === 39 ? `### 验证协作结果\n\n这是只读界面验收夹具，不代表真实模型执行结果。\n\n\`\`\`ts\nconst status = "核对成果"\n\`\`\`\n\n![界面图示](https://example.com/fixture.png)\n\n正文说明[^1]\n\n[^1]: 这是中文注释。${append}` : `第 ${index + 1} 条中文消息：先核对任务范围，再查看代码差异与预览证据。\n\n阅读历史时，新的输出应保留当前位置。`,
    messageKind: "chat", parentMessageId: null, streamState: "complete", createdAt: stamp(index), attachments: [], pinnedAt: null })
  const run = (id, taskId, state) => ({ id, taskId, sessionId: session, agentId: "fixture-agent", state, adapterType: "scripted_mock", adapterRunId: null,
    startedAt: stamp(10), endedAt: stamp(20), worktreePath: "fixture-only", baseRef: null, headRef: null, errorCode: state === "failed" ? "fixture_failure" : null,
    errorMessage: state === "failed" ? "夹具：当前重试未通过，请核对失败原因。" : null, metricsJson: {}, createdAt: stamp(10), updatedAt: stamp(20) })
  const task = (id, runs) => ({ id, sessionId: session, createdByMessageId: message(38).id, title: "登录页与表单反馈", intentType: "build_login_page", status: runs.at(-1).state,
    priority: 0, planJson: { targetId: "demo-frontend", summary: "只读 UI 夹具，不代表真实模型任务" }, dependsOnTaskIds: [], assignedAgentId: "fixture-agent", assignedAgentRole: "frontend", taskRuns: runs,
    integrationArtifacts: [], createdAt: stamp(1), updatedAt: stamp(20) })
  const tasks = [task("reading-a", [run("reading-old", "reading-a", "completed"), run("reading-retry", "reading-a", "failed")]), task("reading-b", [run("reading-current", "reading-b", "completed")])]
  const diff = id => ({ id: `diff-${id}`, artifactId: `artifact-${id}`, taskRunId: id, artifactType: "diff", title: id === "reading-old" ? "历史登录页变更" : "当前表单反馈变更", status: "ready", baseRef: "fixture-base", headRef: "fixture-head",
    patchText: "diff --git a/src/App.tsx b/src/App.tsx\n--- a/src/App.tsx\n+++ b/src/App.tsx\n@@ -1 +1 @@\n-<h1>登录</h1>\n+<h1>欢迎回来</h1>\n", changedFiles: ["src/App.tsx"], stats: { filesChanged: 1, additions: 1, deletions: 1, files: [{ path: "src/App.tsx", additions: 1, deletions: 1 }] } })
  const doc = { artifactId: "reading-doc", taskRunId: "reading-current", artifactType: "document", title: "中文交付说明", status: "ready", version: 3, rendererKind: "markdown", editable: true, contentHash: "fixture-hash", safeMeta: {}, createdAt: stamp(21), updatedAt: stamp(23),
    versions: [1, 3].map(version => ({ id: `reading-v${version}`, artifactId: "reading-doc", version, summary: `说明修订 ${version}`, contentMd: `# 交付说明\n\n版本 ${version}，仅用于 UI 验收。`, contentHash: "fixture-hash", editorSource: "user", createdAt: stamp(21 + version), parentVersionId: null, sourceTaskRunId: "reading-current", parentArtifactId: null, gitBaseRef: null, gitHeadRef: null, changedFiles: [] })) }
  const fulfill = (route, json, status = 200) => route.fulfill({ status, json, headers: { "access-control-allow-origin": origin } })
  await context.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url())
    if (![origin, api].includes(url.origin)) return route.abort()
    if (!["GET", "OPTIONS"].includes(request.method())) { blockedMutations.push(`${request.method()} ${url.pathname}`); return route.abort() }
    if (url.origin !== api) return route.continue()
    if (url.pathname === `/sessions/${session}/messages/page` && failRefresh) { failRefresh = false; return fulfill(route, { detail: "夹具：读取暂时不可用" }, 503) }
    if (!rich) return route.continue()
    if (url.pathname === `/sessions/${session}/tasks`) return fulfill(route, tasks)
    if (url.pathname === `/sessions/${session}/artifact-workbench`) return fulfill(route, { sessionId: session, artifacts: [doc] })
    if (url.pathname === `/sessions/${session}/messages/page`) {
      const older = url.searchParams.has("before"), messages = Array.from({ length: older ? 10 : count }, (_, i) => message(older ? i - 10 : i))
      return fulfill(route, { messages, pinnedMessages: [], pinnedTotal: 0, total: count + 10, hasOlder: !older, hasNewer: older,
        olderCursor: messages[0].id, newerCursor: messages.at(-1).id, latestMessageId: message(count - 1).id, previewCharacterLimit: 12000 })
    }
    const match = url.pathname.match(/^\/task-runs\/(reading-[^/]+)\/(diffs|previews|reviews|deployments)$/)
    if (match) return fulfill(route, match[2] === "diffs" && ["reading-old", "reading-current"].includes(match[1]) ? [diff(match[1])] : [])
    return route.continue()
  })
  const page = await context.newPage()
  page.on("pageerror", error => errors.push(error.message))
  page.on("console", message => {
    if (message.type() === "error" && /hydration|hydrated|Minified React error/i.test(message.text())) errors.push(message.text())
  })
  const composer = page.getByRole("textbox", { name: "消息", exact: true })
  const scroller = page.locator('[data-region="center-scroll"]')
  const layout = page.locator(".workbench-layout")
  const view = name => page.getByRole("navigation", { name: "工作台视图" }).getByRole("button", { name })
  async function ready() {
    await page.goto(`${origin}/?session=${encodeURIComponent(session)}`)
    await composer.waitFor()
    await page.getByRole("button", { name: "Copy message", exact: true }).first().waitFor()
  }
  async function refresh() {
    // Invoke the actual refresh handler without Playwright scrolling its
    // offscreen toolbar into view and changing the reader's position itself.
    await page.getByRole("button", { name: "刷新消息", exact: true }).evaluate(el => el.click())
    await page.waitForFunction(() => !document.querySelector('button[aria-label="刷新消息"]').disabled)
  }
  async function theme(value) {
    if (await page.locator("html").getAttribute("data-theme") !== value) await page.getByRole("button", { name: value === "dark" ? "切换到暗色模式" : "切换到亮色模式" }).click()
    await page.waitForFunction(() => !document.documentElement.hasAttribute("data-theme-changing"))
  }
  const position = () => scroller.evaluate(el => ({ top: el.scrollTop, max: el.scrollHeight - el.clientHeight }))
  const scrollTo = top => scroller.evaluate((el, value) => { el.scrollTop = value; el.dispatchEvent(new Event("scroll")) }, top)
  const bottom = () => page.waitForFunction(() => { const el = document.querySelector('[data-region="center-scroll"]'); return el.scrollHeight - el.clientHeight - el.scrollTop < 2 })
  await ready()
  assert((await layout.getAttribute("class")).includes("inspector-collapsed"))
  assert.equal(await page.locator(".workbench-inspector").isVisible(), false)
  assert.equal(await page.getByRole("button", { name: "消息记录", exact: true }).getAttribute("aria-expanded"), "false")
  assert.equal(await page.getByRole("button", { name: "阶段说明", exact: true }).getAttribute("aria-expanded"), "false")
  results.push({ check: "empty-inspector-and-routine-details-collapsed", passed: true })

  rich = true
  await ready()
  await view(/^成果/).click()
  const groups = page.getByRole("region", { name: /^任务成果/ })
  await groups.nth(1).waitFor()
  assert.equal(await groups.count(), 2)
  assert(await groups.nth(0).getByText(/当前运行尚无成果/).isVisible())
  assert.equal(await groups.nth(0).getByRole("button", { name: /代码变更/ }).count(), 0)
  await groups.nth(0).getByRole("button", { name: /历史成果/ }).click()
  await groups.nth(0).getByRole("button", { name: /代码变更/ }).click()
  await page.getByRole("button", { name: "关闭产物", exact: true }).waitFor()
  assert(await page.locator(".workbench-inspector").isVisible())
  const separator = page.getByRole("separator", { name: "调整成果面板宽度" })
  const width = Number(await separator.getAttribute("aria-valuenow"))
  await separator.focus(); await separator.press("ArrowLeft")
  assert.equal(Number(await separator.getAttribute("aria-valuenow")), width + 16)
  await page.getByRole("button", { name: "关闭产物", exact: true }).click()
  assert.equal(await page.locator(".workbench-inspector").isVisible(), false)
  await view("对话").click(); await refresh()
  assert.equal(await page.locator(".workbench-inspector").isVisible(), false)
  await view(/^成果/).click()
  await groups.nth(1).getByRole("button", { name: /文档产物/ }).click()
  assert(await page.locator(".workbench-inspector").isVisible())
  assert.equal(Number(await separator.getAttribute("aria-valuenow")), width + 16)
  await page.getByRole("button", { name: "关闭产物", exact: true }).click()
  await groups.nth(1).getByRole("button", { name: /文档版本/ }).click()
  await groups.nth(1).getByText(/v1 · 说明修订 1/).waitFor()
  await groups.nth(1).getByText(/v3 · 说明修订 3/).waitFor()
  results.push({ check: "task-run-identity-history-versions-manual-inspector-and-width", passed: true })
  for (const value of ["light", "dark"]) {
    await theme(value)
    await page.screenshot({ path: resolve(output, `desktop-results-${value}.png`) })
  }
  await view("对话").click()
  await bottom()
  await scrollTo(200)
  const before = (await position()).top
  count++
  await refresh()
  await page.getByRole("button", { name: /1 条新消息 · 跳至最新/ }).waitFor()
  assert(Math.abs((await position()).top - before) < 2, JSON.stringify({ before, after: await position(), stage: "append" }))
  append = "\n\n这是同一条消息追加的中文内容。"
  await refresh()
  await page.getByText("这是同一条消息追加的中文内容。", { exact: true }).waitFor()
  assert.equal(await page.getByRole("button", { name: /1 条新消息 · 跳至最新/ }).count(), 1)
  assert(Math.abs((await position()).top - before) < 2, JSON.stringify({ before, after: await position(), stage: "same-message" }))
  await page.setViewportSize({ width: 1280, height: 900 })
  assert(Math.abs((await position()).top - before) < 2, JSON.stringify({ before, after: await position(), stage: "resize" }))
  await page.getByRole("button", { name: /跳至最新/ }).click()
  await bottom()
  count++; await refresh()
  await page.locator(`#message-${message(count - 1).id}`).waitFor()
  await bottom()
  assert.equal(await page.getByRole("button", { name: /跳至最新/ }).count(), 0)
  results.push({ check: "upward-reading-counted-append-same-message-resize-bottom-follow", passed: true })

  await scrollTo(0)
  await page.getByRole("button", { name: "加载更早消息", exact: true }).click()
  await page.getByRole("button", { name: "回到最新消息", exact: true }).waitFor()
  await page.getByRole("button", { name: "回到最新消息", exact: true }).click()
  await bottom()
  // The progress/results footer is below the last message; no later smooth
  // scrollIntoView may pull the controller upward and disable following.
  await page.waitForTimeout(700)
  await bottom()
  count++; await refresh()
  await page.locator(`#message-${message(count - 1).id}`).waitFor()
  await bottom()
  await scrollTo(180)
  await view(/^执行过程/).click()
  await page.getByRole("heading", { name: /任务依赖图/ }).waitFor()
  const svgSizes = await page.locator('svg[aria-label="任务依赖关系图"] text').evaluateAll(nodes => nodes.map(el => Number(el.getAttribute("font-size"))))
  assert(svgSizes.every(size => size >= 12))
  await view("对话").click()
  assert(Math.abs((await position()).top - 180) < 2)
  results.push({ check: "historical-latest-footer-follow-and-view-reading-position", passed: true })

  failRefresh = true
  await refresh()
  await page.getByRole("alert").filter({ hasText: /无法加载会话消息/ }).waitFor()
  assert(await page.getByRole("button", { name: "刷新消息", exact: true }).isEnabled())
  results.push({ check: "manual-refresh-visible-error-and-recovery", passed: true })
  await refresh()
  await page.getByRole("alert").filter({ hasText: /无法加载会话消息/ }).waitFor({ state: "hidden" })

  await page.setViewportSize({ width: 1440, height: 1000 })
  for (const value of ["light", "dark"]) {
    await theme(value)
    await scrollTo(0)
    assert(await page.getByText("夹具：当前重试未通过，请核对失败原因。", { exact: true }).isVisible())
    const fonts = await page.evaluate(() => {
      const elements = [...document.querySelectorAll('[data-region="app-shell"] *')].filter(el => el.getClientRects().length && [...el.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()) && !el.closest("svg,.sr-only"))
      return { body: getComputedStyle(document.body).fontSize, weight: getComputedStyle(document.body).fontWeight,
        smallest: Math.min(...elements.map(el => parseFloat(getComputedStyle(el).fontSize))),
        small: elements.filter(el => parseFloat(getComputedStyle(el).fontSize) < 12).map(el => ({ tag: el.tagName, class: String(el.className), text: el.textContent.slice(0, 60), size: getComputedStyle(el).fontSize })),
        markdown: [...document.querySelectorAll('[class*="codeHeader"], [class*="imageButton"] span, .footnotes')].map(el => getComputedStyle(el).fontSize) }
    })
    assert.equal(fonts.body, "14px"); assert.equal(fonts.weight, value === "dark" ? "360" : "400")
    assert(fonts.smallest >= 12, JSON.stringify(fonts))
    assert(fonts.markdown.every(size => parseFloat(size) >= 12))
    const palette = await page.evaluate(() => {
      const css = getComputedStyle(document.documentElement)
      const value = key => css.getPropertyValue(`--${key}`).trim()
      return { foregrounds: ["text-muted", "muted-foreground"].map(value), backgrounds: ["background", "surface", "surface-muted", "surface-raised", "user-bubble", "primary-soft"].map(value) }
    })
    const supportingContrast = palette.foregrounds.flatMap(fg => palette.backgrounds.map(bg => {
      const a = luminance(fg), b = luminance(bg)
      return (Math.max(a, b) + .05) / (Math.min(a, b) + .05)
    }))
    assert(supportingContrast.every(ratio => ratio >= 4.5))
    await page.screenshot({ path: resolve(output, `desktop-conversation-${value}.png`) })
    results.push({ check: `${value}-typography-and-critical-reason`, fonts })
    results.push({ check: `${value}-supporting-text-contrast`, minimum: Math.min(...supportingContrast), palette })
  }
  for (const width of [1024, 390]) for (const value of ["light", "dark"]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await theme(value); await scrollTo(0)
    assert(await page.locator("html").evaluate(el => el.scrollWidth <= el.clientWidth))
    assert(await composer.isVisible())
    await page.screenshot({ path: resolve(output, `${width}-${value}.png`) })
    await page.getByRole("button", { name: "切换成果面板", exact: true }).click()
    assert(await page.locator(".workbench-inspector").isVisible())
    await page.getByRole("button", { name: "关闭产物", exact: true }).click()
    results.push({ check: `${width}-${value}-responsive-overlay`, passed: true })
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${origin}/settings/agents`)
  await page.getByRole("button", { name: "打开创建对话", exact: true }).click()
  await page.getByRole("textbox", { name: "描述你想创建的 Agent", exact: true }).fill("只读前端评审助手，使用中文输出。")
  function luminance(color) {
    const components = color.startsWith("#") ? color.slice(1).match(/../g).map(v => parseInt(v, 16)) : color.match(/[\d.]+/g).slice(0, 3).map(Number)
    const rgb = components.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
    return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
  }
  for (const value of ["light", "dark"]) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, value)
    for (const label of ["生成配置草稿", "保存自定义 Agent"]) {
      const button = page.getByRole("button", { name: label, exact: true })
      const colors = await button.evaluate(el => { const c = getComputedStyle(el); return { foreground: c.color, background: c.backgroundColor, opacity: c.opacity } })
      const a = luminance(colors.foreground), b = luminance(colors.background), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05)
      assert.equal(colors.opacity, "1"); assert(ratio >= 4.5)
      results.push({ check: `${value}-primary-contrast-${label}`, ratio, colors })
    }
    await page.getByRole("button", { name: "生成配置草稿", exact: true }).scrollIntoViewIfNeeded()
    await page.screenshot({ path: resolve(output, `agent-settings-${value}.png`) })
  }
  assert.deepEqual(blockedMutations, [])
  assert.deepEqual(errors, [])
  await writeFile(resolve(output, "result.json"), JSON.stringify({ evidence: "Actual Edge UI; isolated DB plus read-only response fixtures; no model runs, mutations or clipboard changes", browser: browser.version(), results, errors, blockedMutations }, null, 2))
  console.log(JSON.stringify({ checks: results.length, errors, blockedMutations, output }))
} catch (error) {
  await writeFile(resolve(output, "failure.json"), JSON.stringify({ error: String(error), results, errors, blockedMutations }, null, 2))
  throw error
} finally { await browser.close() }
