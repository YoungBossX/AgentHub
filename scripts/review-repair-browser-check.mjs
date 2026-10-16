// UI acceptance with intercepted API fixtures. Never dispatches real work.
import assert from "node:assert/strict"
import { mkdir, writeFile } from "node:fs/promises"
import { isAbsolute, relative, resolve } from "node:path"
import { chromium } from "playwright"

const output = process.env.AGENTHUB_REPAIR_UI_OUTPUT
assert.ok(output && isAbsolute(output), "Use an explicit external output directory")
const outside = relative(process.cwd(), resolve(output))
assert.ok(isAbsolute(outside) || outside.startsWith("../") || outside.startsWith("..\\"), "Keep screenshots outside the checkout")
const origin = "http://127.0.0.1:3000", api = "http://127.0.0.1:8000"
const workspace = await (await fetch(api + "/workspaces/demo")).json()
const sessions = await (await fetch(`${api}/workspaces/${workspace.id}/sessions?view=all`)).json()
assert.ok(Array.isArray(sessions) && sessions.length)
const sid = sessions[0].id, now = "2026-10-15T00:00:00Z"
const review = { id: "repair-ui-review", artifactId: "repair-ui-report", taskRunId: "repair-ui-run", artifactType: "review",
  reviewedDiffArtifactId: "repair-ui-diff", title: "Review Agent report", status: "warning", riskLevel: "low", summary: "受控 UI 验收：接口说明需要人工核验。",
  filesReviewed: ["apps/demo-api/app/main.py"], findings: [{ file: "apps/demo-api/app/main.py", message: "核对接口说明" }], suggestedChanges: [], adapterType: "scripted_mock" }
const task = { id: "repair-ui-task", sessionId: sid, createdByMessageId: null, title: "评审修复 UI 验收", intentType: "backend_change", status: "completed",
  priority: 0, planJson: { targetId: "demo-backend", assignedRole: "backend" }, dependsOnTaskIds: [], assignedAgentId: null, assignedAgentRole: "backend", createdAt: now, updatedAt: now,
  taskRuns: [{ id: "repair-ui-run", taskId: "repair-ui-task", sessionId: sid, agentId: "backend", adapterType: "scripted_mock", adapterRunId: null,
    state: "completed", startedAt: now, endedAt: now, worktreePath: "fixture", baseRef: null, headRef: null, errorCode: null, errorMessage: null, metricsJson: {}, createdAt: now, updatedAt: now }] }
const issue = { id: "finding:ui", message: "核对接口说明", file: "apps/demo-api/app/main.py", line: 55, autoVerifiable: false }
const state = { issues: [issue], history: [], canPrepare: true, reason: null, sourceFingerprint: "a".repeat(64) }
const selection = { reviewArtifactId: review.artifactId, issueIds: [issue.id], expectedFingerprint: "b".repeat(64) }
const draft = { contentMd: "@backend @qa 请修复评审指出的接口说明问题。", selection }
const withBudget = process.env.AGENTHUB_CONTEXT_BUDGET_UI === "1"
const budgetFixture = { schemaVersion: "agenthub.context_budget.v1", status: "rejected", textCharacters: 201234,
  textUtf8Bytes: 240000, managedBytes: 250000, imageCount: 0, imageBytes: 0, textSha256: "c".repeat(64), limits: { textCharacters: 200000, managedBytes: 50331648 },
  sources: [{ source: "projectRules", status: "included", sourceSerializedCharacters: 12000, omissionReason: null, upstreamSelection: {} },
    { source: "pinnedMessages", status: "metadata_only", sourceSerializedCharacters: 300, omissionReason: "source_selection_limit_or_integrity_policy", upstreamSelection: { omitted: 2 }, omissionReasons: { pinned_selection_limit: 2 } }] }
let browser
const results = []
try {
  await mkdir(output, { recursive: true })
  browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chrome", chromiumSandbox: true, headless: true, timeout: 30000 })
  for (const width of [1440, 390]) for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, serviceWorkers: "block", acceptDownloads: false })
    let prepares = 0, sends = 0
    const messages = [], errors = []
    if (withBudget) messages.push({ id: "budget-rejection-ui", sessionId: sid, senderType: "orchestrator", senderId: null, contentMd: "受控 UI 验收：最终上下文超限，尚未调用模型。", messageKind: "chat", parentMessageId: null, streamState: "complete", createdAt: now, contextBudget: budgetFixture })
    await context.addInitScript(theme => localStorage.setItem("agenthub.theme", theme), theme)
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin === origin) return route.continue()
      if (url.origin !== api) return route.abort()
      const headers = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Headers": "content-type,x-agenthub-control", "Access-Control-Allow-Methods": "GET,POST,OPTIONS" }
      const json = body => route.fulfill({ contentType: "application/json", headers, body: JSON.stringify(body) })
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers })
      if (url.pathname.endsWith("/repair/prepare")) {
        prepares++; assert.deepEqual(request.postDataJSON(), { issueIds: [issue.id] }); return json(draft)
      }
      if (url.pathname === `/sessions/${sid}/messages` && request.method() === "POST") {
        sends++; const body = request.postDataJSON(); assert.deepEqual(body.context.reviewRepair, selection)
        assert.ok(body.contentMd.includes("补充：保留原有接口"))
        const message = { id: `ui-message-${sends}`, sessionId: sid, senderType: "user", senderId: null, contentMd: body.contentMd, messageKind: "chat", parentMessageId: null, streamState: "complete", createdAt: now }
        messages.push(message); return json(message)
      }
      if (request.method() !== "GET") return route.abort()
      if (url.pathname === `/sessions/${sid}/messages/page`) return json({ messages, pinnedMessages: [], pinnedTotal: 0, total: messages.length,
        hasOlder: false, hasNewer: false, olderCursor: messages[0]?.id ?? null, newerCursor: messages.at(-1)?.id ?? null,
        latestMessageId: messages.at(-1)?.id ?? null, previewCharacterLimit: 12000 })
      if (url.pathname === `/sessions/${sid}/messages`) return json(messages)
      if (url.pathname === `/sessions/${sid}/tasks`) return json([task])
      if (url.pathname === `/sessions/${sid}/artifacts`) return json({ sessionId: sid, artifacts: [] })
      if (url.pathname.endsWith("/repair")) return json(state)
      if (url.pathname === "/task-runs/repair-ui-run/reviews") return json([review])
      if (/^\/task-runs\/repair-ui-run\/(diffs|previews|deployments)$/.test(url.pathname)) return json([])
      if (url.pathname.endsWith("/code-edits")) return json([])
      if (url.pathname.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", headers, body: ": fixture\n\n" })
      return route.continue() // Existing read-only settings/health endpoints.
    })
    const page = await context.newPage()
    page.on("pageerror", error => errors.push(error.message))
    await page.goto(`${origin}/?session=${sid}`, { waitUntil: "domcontentloaded", timeout: 90000 })
    const guidance = page.getByRole("region", { name: "当前阶段与下一步" })
    await guidance.getByText(/执行已结束，待核对结果/).waitFor()
    await guidance.getByText(/执行完成不等于功能验收通过/).waitFor()
    assert.equal(await guidance.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true)
    await guidance.getByRole("button", { name: "查看结果与证据" }).click()
    assert.equal(await page.getByRole("button", { name: /^成果/ }).getAttribute("aria-pressed"), "true")
    if (withBudget) {
      const evidence = page.getByLabel("最终上下文预算")
      await evidence.locator("summary").click()
      await evidence.getByText(/字符不是模型 Token/).waitFor()
      await evidence.getByText(/置顶选择限额 2/).waitFor()
      assert.equal(await evidence.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true)
      await page.screenshot({ path: resolve(output, `${width}-${theme}-budget.png`) })
    }
    await page.getByRole("button", { name: /执行过程/ }).click()
    if (width < 1200) await page.getByRole("button", { name: "切换成果面板" }).click()
    await page.getByRole("button", { name: /^评审\s*1$/ }).click()
    const control = page.getByRole("region", { name: "评审修复" })
    await control.getByRole("checkbox").check()
    const box = await control.boundingBox()
    assert.ok(box && box.x >= 0 && box.x + box.width <= width + 1, "Repair panel exceeds viewport")
    assert.equal(await control.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true)
    assert.equal(await page.locator("html").getAttribute("data-theme"), theme)
    await page.screenshot({ path: resolve(output, `${width}-${theme}.png`) })
    await control.getByRole("button", { name: /准备修复草稿/ }).click()
    const editor = page.getByRole("textbox", { name: "消息", exact: true })
    await editor.waitFor()
    assert.equal(await editor.inputValue(), draft.contentMd)
    assert.equal(prepares, 1); assert.equal(sends, 0)
    await editor.fill(draft.contentMd + "\n补充：保留原有接口")
    await page.getByRole("button", { name: "发送" , exact: true }).click()
    await page.getByText(/修复草稿 · 评审/).waitFor({ state: "hidden" })
    assert.equal(sends, 1)
    assert.deepEqual(errors, [])
    results.push({ width, theme, stateGroundedGuidance: true, resultActionNavigation: true, prepareWithoutSend: true, explicitEditedSend: true, layoutWithinViewport: true, ...(withBudget ? { budgetFoldAndOmissionReasons: true } : {}), errors })
    await context.close()
  }
  const report = { evidence: "UI fixtures; all browser mutations intercepted; no real Provider or product data writes", browser: browser.version(), results }
  await writeFile(resolve(output, "result.json"), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
} finally { await browser?.close() }
