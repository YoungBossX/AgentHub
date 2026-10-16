// Real settings UI, controlled API fixture. All mutations stay in this browser.
import assert from "node:assert/strict"
import { mkdir, writeFile } from "node:fs/promises"
import { resolve, relative, isAbsolute } from "node:path"
import { chromium } from "playwright"

const output = process.env.AGENTHUB_USABILITY_UI_OUTPUT
assert.ok(output && isAbsolute(output))
const outside = relative(process.cwd(), resolve(output))
assert.ok(isAbsolute(outside) || outside.startsWith("../") || outside.startsWith("..\\"))
const origin = "http://127.0.0.1:3000", api = "http://127.0.0.1:8000"
const seed = { name: "ui-reference-demo", description: "参考文件编辑验收", markdown: "---\nname: ui-reference-demo\ndescription: 参考文件编辑验收\n---\n\n检查输入和错误提示。\n", references: {}, roles: ["frontend"], defaultAgents: [], enabled: true, revision: 3, source: "workspace" }
let browser
const results = []
try {
  await mkdir(output, { recursive: true })
  browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chrome", chromiumSandbox: true, headless: true, timeout: 30000 })
  for (const width of [1440, 390]) for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, serviceWorkers: "block", acceptDownloads: false })
    await context.addInitScript(theme => localStorage.setItem("agenthub.theme", theme), theme)
    let saved = structuredClone(seed), puts = 0, conflict = false
    const errors = []
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin === origin) return route.continue()
      if (url.origin !== api) return route.abort()
      const headers = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Headers": "content-type,x-agenthub-control", "Access-Control-Allow-Methods": "GET,PUT,OPTIONS" }
      if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers })
      if (/\/workspaces\/[^/]+\/skills$/.test(url.pathname)) {
        if (request.method() === "GET") return route.fulfill({ contentType: "application/json", headers, body: JSON.stringify([saved]) })
        assert.equal(request.method(), "PUT")
        assert.equal(request.headers()["x-agenthub-control"], "local-workspace")
        puts++
        if (conflict) return route.fulfill({ status: 409, contentType: "application/json", headers, body: JSON.stringify({ detail: "验收夹具：版本已变化，请重新载入并合并草稿。" }) })
        const body = request.postDataJSON()
        assert.equal(body.expectedRevision, 3)
        assert.deepEqual(body.references, { "references/checklist.md": "检查用户名、密码和错误提示。", "references/second.txt": "验证表单错误状态" })
        saved = { ...saved, ...body, revision: 4 }
        return route.fulfill({ contentType: "application/json", headers, body: JSON.stringify(saved) })
      }
      return request.method() === "GET" ? route.continue() : route.abort()
    })
    const page = await context.newPage()
    page.on("pageerror", error => errors.push(error.message))
    await page.goto(origin + "/settings/agents", { waitUntil: "domcontentloaded", timeout: 90000 })
    const library = page.getByRole("region", { name: "技能库" })
    await library.getByRole("button", { name: /ui-reference-demo/ }).click()
    await library.getByLabel("导入参考文件").setInputFiles({ name: "checklist.md", mimeType: "text/markdown", buffer: Buffer.from("检查用户名、密码和错误提示。") })
    await library.getByRole("textbox", { name: "参考路径 1" }).waitFor()
    assert.equal(await library.getByRole("textbox", { name: "参考内容 1" }).inputValue(), "检查用户名、密码和错误提示。")
    await library.getByRole("button", { name: "添加参考文件" }).click()
    await library.getByRole("textbox", { name: "参考路径 2" }).fill("references/second.txt")
    await library.getByRole("textbox", { name: "参考内容 2" }).fill("验证表单错误状态")
    await library.getByRole("textbox", { name: "参考路径 2" }).scrollIntoViewIfNeeded()
    assert.equal(await library.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true)
    assert.equal(await page.locator("html").getAttribute("data-theme"), theme)
    await page.screenshot({ path: resolve(output, `${width}-${theme}-references.png`) })
    assert.equal(puts, 0)
    await library.getByRole("button", { name: "保存技能", exact: true }).click()
    await library.getByText("技能已保存，新运行将使用新版本。").waitFor()
    assert.equal(puts, 1)
    await library.getByRole("button", { name: /ui-reference-demo/ }).click()
    assert.equal(await library.getByRole("textbox", { name: "参考路径 1" }).inputValue(), "references/checklist.md")
    await library.getByRole("textbox", { name: "参考内容 2" }).fill("发生冲突也要保留的草稿")
    conflict = true
    await library.getByRole("button", { name: "保存技能", exact: true }).click()
    await library.getByText(/验收夹具：版本已变化/).waitFor()
    assert.equal(await library.getByRole("textbox", { name: "参考内容 2" }).inputValue(), "发生冲突也要保留的草稿")
    assert.deepEqual(errors, [])
    results.push({ width, theme, strictUtf8Import: true, explicitPathContentSave: true, expectedRevision: 3, reloadReferences: true, conflictDraftRetained: true, layoutWithinViewport: true, errors })
    await context.close()
  }
  const report = { evidence: "Actual UI with intercepted API fixtures; no product database writes or model calls", browser: browser.version(), results }
  await writeFile(resolve(output, "result.json"), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
} finally { await browser?.close() }
