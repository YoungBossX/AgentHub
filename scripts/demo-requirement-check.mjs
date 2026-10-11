// Trusted browser harness. Expected values are data; app console output is ignored.
import assert from "node:assert/strict"
import { readFile, lstat } from "node:fs/promises"
import { resolve, relative, isAbsolute, extname } from "node:path"
import { randomUUID } from "node:crypto"
import { chromium } from "playwright"

const schemaVersion = "agenthub.requirement_validation.v1"
const contract = JSON.parse(process.env.AGENTHUB_REQUIREMENT_CONTRACT ?? "null")
const output = resolve(process.env.AGENTHUB_VALIDATION_OUTPUT ?? "apps/demo/dist")
const origin = "http://agenthub-validation.invalid"
const checks = []
let browser
let browserVersion
let unavailable = false

async function check(id, operation) {
  try {
    await operation()
    checks.push({ id, status: "passed" })
  } catch (error) {
    checks.push({ id, status: "failed", detail: String(error.message).slice(0, 500) })
  }
}

async function staticResponse(route) {
  const url = new URL(route.request().url())
  assert.equal(url.origin, origin, "External requests are blocked")
  assert.equal(route.request().method(), "GET", "Only static GET is supported")
  const decoded = decodeURIComponent(url.pathname)
  assert.ok(!decoded.includes("\\") && !decoded.includes("\0"))
  const path = resolve(output, "." + (decoded === "/" ? "/index.html" : decoded))
  const inside = relative(output, path)
  assert.ok(inside && !inside.startsWith("..") && !isAbsolute(inside))
  let current = output
  for (const component of inside.split(/[\\/]/)) {
    current = resolve(current, component)
    const stat = await lstat(current)
    assert.ok(!stat.isSymbolicLink() && (stat.isDirectory() || stat.nlink === 1), "Linked output is not served")
  }
  const stat = await lstat(path)
  assert.ok(stat.isFile() && stat.size <= 5 * 1024 * 1024, "Invalid output file")
  const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2" }
  await route.fulfill({ status: 200, contentType: types[extname(path)] ?? "application/octet-stream", body: await readFile(path) })
}

try {
  assert.equal(contract?.schemaVersion, schemaVersion)
  assert.ok(["login_page", "demo_heading_text", "primary_action_button_text"].includes(contract.target))
  const channel = process.env.AGENTHUB_VALIDATION_BROWSER_CHANNEL ?? (process.platform === "win32" ? "msedge" : "chromium")
  assert.ok(["msedge", "chrome", "chromium"].includes(channel))
  browser = await chromium.launch({ headless: true, chromiumSandbox: true, timeout: 10000,
    ...(channel === "chromium" ? {} : { channel }) })
  browserVersion = browser.version()
  for (const [view, width] of [["desktop", 1280], ["narrow", 390]]) {
    const context = await browser.newContext({ viewport: { width, height: 850 }, serviceWorkers: "block",
      acceptDownloads: false, permissions: [], reducedMotion: "reduce" })
    let blocked = 0
    const errors = []
    await context.route("**/*", async (route) => {
      try { await staticResponse(route) } catch { blocked++; await route.abort().catch(() => {}) }
    })
    await context.routeWebSocket("**/*", (socket) => { blocked++; socket.close() })
    const page = await context.newPage()
    context.on("page", (popup) => { blocked++; void popup.close() })
    page.on("pageerror", (error) => errors.push(error.message.slice(0, 200)))
    page.on("dialog", (dialog) => { blocked++; void dialog.dismiss() })
    page.setDefaultTimeout(1800)
    try {
      await page.goto(origin, { waitUntil: "load", timeout: 10000 })
      if (contract.target === "login_page") {
        const form = page.locator('[data-agenthub-target="login-page-slot"] form')
        const email = form.locator('input[type="email"]')
        const password = form.locator('input[type="password"]')
        const submit = form.locator('button[type="submit"], input[type="submit"], button:not([type])')
        const counter = "validation_" + randomUUID().replaceAll("-", "")
        await check(`${view}.fields`, async () => {
          assert.equal(await form.count(), 1, "Expected one login form in the assigned slot")
          for (const input of [email, password]) {
            assert.ok(await input.isVisible() && await input.isEnabled(), "Input must be visible and editable")
            assert.ok(await input.evaluate((node) => Boolean(node.getAttribute("aria-label")?.trim()
              || [...node.labels].some((label) => label.textContent.trim()))), "Input needs an accessible label")
          }
          await form.evaluate((node, key) => {
            window[key] = 0
            node.addEventListener("submit", (event) => {
              if (event.isTrusted) window[key]++
              event.preventDefault() // No account authentication or navigation in acceptance tests.
            }, true)
          }, counter)
        })
        await check(`${view}.empty`, async () => {
          for (const [address, secret] of [["", ""], ["demo@example.invalid", ""], ["", "demo-test-password"]]) {
            await email.fill(address); await password.fill(secret); await submit.click()
            assert.equal(await page.evaluate((key) => window[key], counter), 0, "Each required field must reject empty input")
            assert.equal(await form.evaluate((node) => node.checkValidity()), false)
          }
        })
        await check(`${view}.invalid_email`, async () => {
          await email.fill("invalid-address"); await password.fill("demo-test-password"); await submit.click()
          assert.equal(await page.evaluate((key) => window[key], counter), 0, "Invalid email must not submit")
        })
        await check(`${view}.submit`, async () => {
          await email.fill("demo@example.invalid"); await password.fill("demo-test-password"); await submit.click()
          assert.equal(await page.evaluate((key) => window[key], counter), 1, "Valid fields must dispatch one submit")
        })
      } else {
        const locator = page.locator(contract.target === "demo_heading_text" ? "h1#demo-heading" : '[data-agenthub-target="primary-action-button"]')
        await check(`${view}.text`, async () => {
          assert.equal(await locator.count(), 1, "Expected one deterministic target")
          assert.ok(await locator.isVisible(), "Expected visible text")
          assert.equal((await locator.innerText()).trim().replace(/\s+/g, " "), contract.expectedText.replace(/\s+/g, " "))
        })
        if (contract.target === "primary_action_button_text") {
          await check(`${view}.click`, async () => { await locator.click() })
        }
      }
      await check(`${view}.runtime`, async () => {
        await page.waitForTimeout(100)
        assert.equal(errors.length, 0, "Browser runtime errors: " + errors.join("; "))
        assert.equal(blocked, 0, "Unexpected network, resource, dialog or popup activity")
      })
    } finally { await context.close() }
  }
} catch {
  unavailable = true
} finally {
  if (browser) await browser.close()
}
const status = unavailable ? "unavailable" : checks.length > 0 && checks.every((c) => c.status === "passed") ? "passed" : "failed"
console.log(JSON.stringify({ schemaVersion, contract, status, checks, browserVersion }))
process.exitCode = status === "passed" ? 0 : status === "unavailable" ? 2 : 1
