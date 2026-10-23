// Real workbench with 5,000-message API fixture and a controlled SSE event.
// No product SQLite writes, real Provider calls or target scripts.
import assert from "node:assert/strict"
import { mkdir, writeFile } from "node:fs/promises"
import { isAbsolute, relative, resolve } from "node:path"
import { chromium } from "playwright"

const output = process.env.AGENTHUB_HISTORY_UI_OUTPUT
assert.ok(output && isAbsolute(output))
const outside = relative(process.cwd(), resolve(output))
assert.ok(isAbsolute(outside) || outside.startsWith("../") || outside.startsWith("..\\"))
const origin = "http://127.0.0.1:3000", api = "http://127.0.0.1:8000"
const workspace = await (await fetch(api + "/workspaces/demo")).json()
const sessions = await (await fetch(`${api}/workspaces/${workspace.id}/sessions?view=all`)).json()
assert.ok(sessions.length)
const sid = sessions[0].id, id = number => `history-${String(number).padStart(6, "0")}`
const make = number => ({ id: id(number), sessionId: sid, senderType: "user", senderId: null, contentMd: `历史消息 ${number}\n` + "核对输入、过程和结果。\n".repeat(12),
  messageKind: "chat", parentMessageId: null, streamState: "complete", createdAt: "2026-10-15T00:00:00Z", pinnedAt: number < 40 ? "2026-10-15T00:00:00Z" : null })
const preview = row => ({ ...row, contentMd: Array.from(row.contentMd).slice(0, 12000).join(""), contentTruncated: Array.from(row.contentMd).length > 12000, contentCharacters: Array.from(row.contentMd).length })
let browser
const results = []
try {
  await mkdir(output, { recursive: true })
  browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chrome", headless: true, chromiumSandbox: true, timeout: 30000 })
  for (const width of [1440, 390]) for (const theme of ["light", "dark"]) {
    const data = Array.from({ length: 5000 }, (_, number) => make(number))
    data[4980].contentMd = "完整片段😀".repeat(8000)
    const pages = [], segments = [], errors = []
    const context = await browser.newContext({ viewport: { width, height: 1000 }, serviceWorkers: "block", acceptDownloads: false })
    await context.addInitScript(theme => {
      localStorage.setItem("agenthub.theme", theme)
      window.__historySources = []
      window.EventSource = class {
        constructor(url) { this.url = url; window.__historySources.push(this) }
        close() { this.closed = true }
      }
    }, theme)
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin === origin) return route.continue()
      if (url.origin !== api) return route.abort()
      const headers = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Headers": "content-type,x-agenthub-control", "Access-Control-Allow-Methods": "GET,OPTIONS" }
      const json = body => route.fulfill({ contentType: "application/json", headers, body: JSON.stringify(body) })
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers })
      if (request.method() !== "GET") return route.abort()
      if (url.pathname === `/sessions/${sid}/messages/page`) {
        const limit = Number(url.searchParams.get("limit") ?? 80)
        assert.ok(limit >= 1 && limit <= 200)
        const cursor = url.searchParams.get("before") ?? url.searchParams.get("after") ?? url.searchParams.get("around")
        const anchor = cursor ? data.findIndex(row => row.id === cursor) : -1
        assert.ok(!cursor || anchor >= 0)
        let start = Math.max(0, data.length - limit), end = data.length
        if (url.searchParams.has("before")) { end = anchor; start = Math.max(0, end - limit) }
        if (url.searchParams.has("after")) { start = anchor + 1; end = Math.min(data.length, start + limit) }
        if (url.searchParams.has("around")) { start = Math.max(0, anchor - Math.floor(limit / 2)); end = Math.min(data.length, start + limit) }
        const messages = data.slice(start, end).map(preview), pinned = data.filter(row => row.pinnedAt).reverse()
        pages.push({ limit, before: url.searchParams.get("before"), after: url.searchParams.get("after"), around: url.searchParams.get("around"), returned: messages.length })
        return json({ messages, pinnedMessages: pinned.slice(0, 16).map(preview), pinnedTotal: pinned.length, total: data.length,
          hasOlder: start > 0, hasNewer: end < data.length, olderCursor: messages[0]?.id ?? null, newerCursor: messages.at(-1)?.id ?? null,
          latestMessageId: data.at(-1).id, previewCharacterLimit: 12000 })
      }
      if (url.pathname.startsWith(`/sessions/${sid}/messages/`) && url.pathname.endsWith("/content")) {
        const mid = url.pathname.split("/").at(-2), row = data.find(row => row.id === mid)
        assert.ok(row)
        const offset = Number(url.searchParams.get("offset") ?? 0), limit = Number(url.searchParams.get("limit") ?? 12000), body = Array.from(row.contentMd)
        assert.ok(offset >= 0 && limit <= 12000)
        const text = body.slice(offset, offset + limit).join("")
        segments.push({ offset, characters: Array.from(text).length })
        return json({ messageId: mid, text, offset, totalCharacters: body.length, nextOffset: offset + limit < body.length ? offset + limit : null,
          previousOffset: offset ? Math.max(0, offset - limit) : null, unit: "Unicode code points" })
      }
      if (url.pathname === `/sessions/${sid}/tasks`) return json([])
      if (url.pathname === `/sessions/${sid}/artifact-workbench`) return json({ sessionId: sid, artifacts: [] })
      if (url.pathname.endsWith("/code-edits")) return json([])
      if (url.pathname === `/sessions/${sid}/messages`) throw new Error("Workbench requested unbounded legacy history")
      return route.continue()
    })
    const page = await context.newPage()
    page.on("pageerror", error => errors.push(error.message))
    const start = performance.now()
    await page.goto(`${origin}/?session=${sid}`, { waitUntil: "domcontentloaded", timeout: 90000 })
    const messages = page.locator('article[id^="message-history-"]')
    await page.waitForFunction(() => document.querySelectorAll('article[id^="message-history-"]').length === 80)
    const initialReadyMs = Math.round(performance.now() - start)
    assert.equal(pages[0].returned, 80)
    const long = page.locator(`#message-${id(4980)}`)
    await long.getByText(/查看全文（分段）/).click()
    await long.getByRole("button", { name: "下一段", exact: true }).waitFor()
    await long.getByRole("button", { name: "下一段", exact: true }).click()
    await page.waitForFunction(() => [...document.querySelectorAll('article[id^="message-history-"] details pre')].some(pre => pre.previousElementSibling?.textContent?.includes("12001")))
    assert.ok(segments.length >= 2 && segments.every(row => row.characters <= 12000))
    for (let index = 0; index < 4; index++) {
      const old = await messages.first().getAttribute("id")
      await page.getByRole("button", { name: "加载更早消息", exact: true }).click()
      await page.waitForFunction(old => document.querySelector('article[id^="message-history-"]')?.id !== old, old)
      assert.ok(await messages.count() <= 200)
    }
    assert.equal(await messages.count(), 200)
    const before = await messages.evaluateAll(rows => rows.map(row => row.id))
    data.push({ ...make(5000), contentMd: "新到达消息：历史窗口保持原位置" })
    await page.evaluate(() => {
      const source = window.__historySources.at(-1)
      source.onmessage(new MessageEvent("message", { data: JSON.stringify({ id: "fixture-sse", taskRunId: "fixture-run", eventType: "task.state", payload: { state: "completed" }, createdAt: "2026-10-15T00:00:01Z", cursor: "fixture-cursor" }) }))
    })
    await page.waitForFunction(latest => document.querySelector("[data-history-latest]")?.getAttribute("data-history-latest") === latest, id(5000))
    assert.deepEqual(await messages.evaluateAll(rows => rows.map(row => row.id)), before)
    const pins = page.getByLabel("关键消息")
    await pins.getByRole("button", { name: /置顶消息/ }).click()
    assert.equal(await pins.getByRole("button").count(), 16)
    await pins.getByRole("button").first().click()
    await page.locator(`#message-${id(39)}`).waitFor()
    assert.ok(await messages.count() <= 200)
    await page.getByRole("button", { name: "回到最新消息", exact: true }).click()
    await page.locator(`#message-${id(5000)}`).waitFor()
    await page.waitForFunction(mid => {
      const box = document.getElementById(`message-${mid}`)?.getBoundingClientRect()
      const input = document.querySelector("textarea[aria-label='消息']")?.getBoundingClientRect()
      return box && input && box.top >= 140 && box.bottom <= input.top
    }, id(5000), { timeout: 5000 }).catch(async error => {
      await page.screenshot({ path: resolve(output, `${width}-${theme}-viewport-failure.png`) })
      const geometry = await page.evaluate(mid => ({ message: document.getElementById(`message-${mid}`)?.getBoundingClientRect().toJSON(), input: document.querySelector("textarea[aria-label='消息']")?.getBoundingClientRect().toJSON() }), id(5000))
      await writeFile(resolve(output, `${width}-${theme}-viewport-failure.json`), JSON.stringify(geometry, null, 2))
      throw error
    })
    assert.equal(await messages.count(), 80)
    const nav = page.getByLabel("消息历史导航")
    assert.equal(await nav.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true)
    assert.equal(await page.locator("html").getAttribute("data-theme"), theme)
    await page.screenshot({ path: resolve(output, `${width}-${theme}-history.png`) })
    assert.deepEqual(errors, [])
    results.push({ width, theme, fixtureMessages: 5000, initialRendered: 80, maxRendered: 200, sourcePinCount: 40, renderedPinEntries: 16,
      longSegments: segments, historyStableDuringControlledSse: true, outsideWindowPinLocated: true, latestRestored: true,
      initialReadyMsIncludingDevNavigation: initialReadyMs, apiPages: pages.length, largestPage: Math.max(...pages.map(row => row.returned)), errors })
    await context.close()
  }
  const report = { evidence: "Real Next UI, 5,000-row intercepted API fixture and controlled EventSource event; no product writes; dev timing is illustrative only", browser: browser.version(), results }
  await writeFile(resolve(output, "result.json"), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
} finally { await browser?.close() }
