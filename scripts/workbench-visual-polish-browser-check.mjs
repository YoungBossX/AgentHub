import assert from "node:assert/strict"
import { mkdir, writeFile } from "node:fs/promises"
import { isAbsolute, relative, resolve } from "node:path"
import { chromium } from "playwright"

const origin = process.env.AGENTHUB_UI_ORIGIN ?? "http://127.0.0.1:3000"
const api = process.env.AGENTHUB_UI_API_ORIGIN ?? "http://127.0.0.1:8000"
const session = process.env.AGENTHUB_UI_SESSION_ID
const output = process.env.AGENTHUB_UI_OUTPUT
assert(session && output, "Set AGENTHUB_UI_SESSION_ID and a new external AGENTHUB_UI_OUTPUT directory")
assert(isAbsolute(output), "Use an absolute external output directory")
const outside = relative(process.cwd(), resolve(output))
assert(isAbsolute(outside) || outside.startsWith("../") || outside.startsWith("..\\"), "Keep screenshots outside the checkout")
await mkdir(output, { recursive: true })
const results = []
const errors = []
const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : "chrome", headless: true, chromiumSandbox: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: "block", acceptDownloads: false })
  // Exercise presentation without changing the operator's OS clipboard.
  await context.addInitScript(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } }))
  let appendedFixtureText = ""
  await context.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url())
    if (![origin, api].includes(url.origin) || !["GET", "OPTIONS"].includes(request.method())) return route.abort()
    if (url.origin === api && url.pathname === `/sessions/${session}/messages/page` && appendedFixtureText) {
      const response = await route.fetch(), data = await response.json()
      const message = [...data.messages].reverse().find(row => row.senderType === "orchestrator" && row.messageKind === "chat")
      assert(message, "Use a fixture session with an ordinary orchestrator message")
      message.contentMd += appendedFixtureText
      return route.fulfill({ response, json: data })
    }
    return route.continue()
  })
  const page = await context.newPage()
  page.on("pageerror", error => errors.push(error.message))
  await page.goto(`${origin}/?session=${encodeURIComponent(session)}`, { waitUntil: "domcontentloaded" })
  const composer = page.getByRole("textbox", { name: "消息", exact: true })
  await composer.waitFor()
  await page.getByRole("button", { name: "Copy message", exact: true }).first().waitFor()

  for (const theme of ["light", "dark"]) {
    const current = await page.locator("html").getAttribute("data-theme")
    if (current !== theme) await page.getByRole("button", { name: theme === "dark" ? "切换到暗色模式" : "切换到亮色模式" }).click()
    await page.waitForFunction(() => !document.documentElement.hasAttribute("data-theme-changing"))
    const palette = await page.locator("body").evaluate(el => {
      const css = getComputedStyle(el), root = getComputedStyle(document.documentElement)
      return { background: css.backgroundColor, weight: css.fontWeight, numbers: css.fontVariantNumeric,
        headingWeight: getComputedStyle(document.querySelector('[data-region="top-header"] h2')).fontWeight,
        wrap: getComputedStyle(document.querySelector("p")).textWrapStyle,
        iconAlignment: parseFloat(getComputedStyle(document.querySelector("svg.lucide")).verticalAlign) / parseFloat(getComputedStyle(document.querySelector("svg.lucide")).fontSize),
        surface: root.getPropertyValue("--surface").trim(), muted: root.getPropertyValue("--surface-muted").trim() }
    })
    assert.equal(palette.background, theme === "light" ? "rgb(245, 245, 243)" : "rgb(11, 11, 10)")
    assert.equal(palette.weight, theme === "light" ? "400" : "360")
    assert.equal(palette.numbers, "tabular-nums")
    assert.equal(palette.headingWeight, theme === "light" ? "600" : "560")
    assert.equal(palette.wrap, "pretty")
    assert.equal(palette.iconAlignment, -.125)
    await composer.focus()
    await page.waitForFunction(() => getComputedStyle(document.querySelector('[data-region="composer"]')).boxShadow.includes("0px 0px 0px 4px"))
    const focus = await page.locator('[data-region="composer"]').evaluate(el => {
      const css = getComputedStyle(el), input = getComputedStyle(el.querySelector("textarea"))
      return { shadow: css.boxShadow, outline: input.outlineStyle, border: css.borderWidth }
    })
    assert.equal(focus.outline, "none")
    assert.equal(focus.border, "0px")
    assert(focus.shadow.includes("4px"), "Composer must have a visible outer focus ring")
    await composer.blur()
    await page.waitForFunction(() => getComputedStyle(document.querySelector('[data-region="composer"]')).boxShadow.endsWith(" 0px"))
    await page.screenshot({ path: resolve(output, `desktop-${theme}.png`) })
    results.push({ check: `desktop-${theme}`, palette, focus })
  }

  const skill = page.getByRole("button", { name: /本次技能/ })
  await skill.focus()
  await skill.press("Enter")
  assert.equal(await skill.getAttribute("aria-expanded"), "true")
  const panel = page.locator(`[id="${await skill.getAttribute("aria-controls")}"]`)
  assert.equal(await panel.getAttribute("inert"), null)
  await skill.press("Space")
  assert.equal(await skill.getAttribute("aria-expanded"), "false")
  assert.equal(await panel.getAttribute("inert"), "")
  results.push({ check: "disclosure-keyboard-inert", passed: true })

  const copy = page.getByRole("button", { name: "Copy message", exact: true }).first()
  await copy.click()
  assert.equal(await copy.getAttribute("data-copied"), "true")
  await page.waitForFunction(() => document.querySelector('.copy-button[data-copied="true"]') === null, undefined, { timeout: 4000 })
  results.push({ check: "copy-feedback-expires", clipboard: "stubbed to preserve OS clipboard", passed: true })

  await page.evaluate(() => {
    document.documentElement.dataset.revealStarts = "0"
    document.addEventListener("animationstart", event => {
      if (event.animationName === "stream-reveal") document.documentElement.dataset.revealStarts = String(Number(document.documentElement.dataset.revealStarts) + 1)
    })
  })
  appendedFixtureText = "\n\n甲"
  await page.getByRole("button", { name: "刷新消息", exact: true }).click()
  await page.waitForFunction(() => Number(document.documentElement.dataset.revealStarts) >= 1)
  appendedFixtureText += "乙"
  await page.getByRole("button", { name: "刷新消息", exact: true }).click()
  await page.waitForFunction(() => Number(document.documentElement.dataset.revealStarts) >= 2)
  const reveal = await page.locator(".stream-reveal-char").evaluateAll(elements => elements.map(el => ({ text: el.textContent, duration: getComputedStyle(el).animationDuration })))
  assert.deepEqual(reveal, [{ text: "乙", duration: "0.09s" }])
  appendedFixtureText = ""
  await page.getByRole("button", { name: "刷新消息", exact: true }).click()
  results.push({ check: "consecutive-prose-append-animation", evidence: "intercepted read response only; no database writes", passed: true })

  await page.emulateMedia({ forcedColors: "active" })
  const markdownLink = page.locator('[class*="markdown"] a').first()
  await markdownLink.focus()
  await page.keyboard.press("Tab")
  await page.keyboard.press("Shift+Tab")
  assert.notEqual(await markdownLink.evaluate(el => getComputedStyle(el).outlineStyle), "none")
  await page.emulateMedia({ forcedColors: "none" })
  results.push({ check: "forced-colors-markdown-focus", passed: true })

  const separator = page.getByRole("separator", { name: "调整会话侧栏宽度" })
  const start = Number(await separator.getAttribute("aria-valuenow"))
  const box = await separator.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + 60)
  await page.mouse.down()
  await page.mouse.move(box.x + 75, box.y + 60)
  assert(Number(await separator.getAttribute("aria-valuenow")) > start)
  await page.keyboard.press("Escape")
  await page.mouse.up()
  assert.equal(Number(await separator.getAttribute("aria-valuenow")), start)
  assert.equal(await page.locator(".workbench-drag-shield").count(), 0)
  await separator.focus()
  await separator.press("ArrowRight")
  assert.equal(Number(await separator.getAttribute("aria-valuenow")), start + 16)
  results.push({ check: "resize-pointer-cancel-keyboard", passed: true })

  await page.getByRole("button", { name: /^执行过程/ }).click()
  await page.getByRole("heading", { name: /任务依赖图/ }).waitFor()
  await page.screenshot({ path: resolve(output, "desktop-process-dark.png") })
  await page.getByRole("button", { name: /^成果\d/ }).click()
  await page.getByRole("button", { name: "对话", exact: true }).click()
  results.push({ check: "process-results-navigation", passed: true })

  for (const width of [1024, 390]) for (const theme of ["light", "dark"]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    if (await page.locator("html").getAttribute("data-theme") !== theme)
      await page.getByRole("button", { name: theme === "dark" ? "切换到暗色模式" : "切换到亮色模式" }).click()
    await page.waitForFunction(() => !document.documentElement.hasAttribute("data-theme-changing"))
    assert(await page.locator("html").evaluate(el => el.scrollWidth <= el.clientWidth), "No document overflow")
    assert(await composer.isVisible())
    await page.screenshot({ path: resolve(output, `${width}-${theme}.png`) })
    results.push({ check: `${width}-${theme}`, passed: true })
  }
  await page.emulateMedia({ reducedMotion: "reduce" })
  const motion = await page.locator(".disclosure-grid").first().evaluate(el => getComputedStyle(el).transitionDuration)
  assert.equal(motion, "0s")
  results.push({ check: "reduced-motion", passed: true })
  await page.reload({ waitUntil: "domcontentloaded" })
  await composer.waitFor()
  await page.waitForFunction(() => document.documentElement.dataset.theme === "dark")
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark")
  results.push({ check: "theme-persistence", passed: true })
  assert.deepEqual(errors, [])
  await writeFile(resolve(output, "result.json"), JSON.stringify({ evidence: "Actual UI; read-only API requests; isolated fixture data supplied by operator; no model runs", browser: browser.version(), results, errors }, null, 2))
  console.log(JSON.stringify({ checks: results.length, errors, output }))
} finally { await browser.close() }
