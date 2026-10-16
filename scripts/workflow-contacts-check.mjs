// Fixed independent integration checks. No selectors/scripts from a model plan.
import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { createInterface } from "node:readline"
import { readFile, lstat } from "node:fs/promises"
import { resolve, relative, isAbsolute, extname } from "node:path"
import { fileURLToPath } from "node:url"
import { randomUUID } from "node:crypto"
import { chromium } from "playwright"

const output = resolve(process.env.AGENTHUB_VALIDATION_OUTPUT)
const origin = "http://agenthub-workflow.invalid"
const contract = process.env.AGENTHUB_CONTACTS_CONTRACT ?? "contacts-create-v1"
const resilience = contract === "contacts-resilience-v2"
const checks = [], requests = [], pending = new Map()
let browser, child, closed, unavailable = false, browserVersion, id = 0, outputBytes = 0
let readyResolve, readyReject
const ready = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject })
let stderr = ""
async function check(id, operation) {
  try { await operation(); checks.push({ id, status: "passed" }) }
  catch (error) { checks.push({ id, status: "failed", detail: String(error.message).slice(0, 400) }) }
}
function request(method, path, body) {
  return new Promise((resolve, reject) => {
    const key = ++id
    const timer = setTimeout(() => { pending.delete(key); reject(new Error("ASGI transport timeout")) }, 6000)
    pending.set(key, { resolve: value => { clearTimeout(timer); resolve(value) }, reject: error => { clearTimeout(timer); reject(error) } })
    child.stdin.write(JSON.stringify({ id: key, method, path, body }) + "\n")
  })
}
try {
  assert.ok(["contacts-create-v1", "contacts-resilience-v2"].includes(contract))
  const channel = process.env.AGENTHUB_VALIDATION_BROWSER_CHANNEL ?? (process.platform === "win32" ? "msedge" : "chromium")
  assert.ok(["msedge", "chrome", "chromium"].includes(channel))
  child = spawn(process.env.AGENTHUB_WORKFLOW_PYTHON, ["-I", "-B", fileURLToPath(new URL("./workflow-api-bridge.py", import.meta.url)),
    process.env.AGENTHUB_WORKFLOW_BACKEND, process.env.AGENTHUB_WORKFLOW_DATA], { stdio: ["pipe", "pipe", "pipe"], windowsHide: true })
  closed = new Promise(resolve => child.once("close", resolve))
  child.stdin.on("error", () => {})
  child.stdout.on("data", chunk => { outputBytes += chunk.length; if (outputBytes > 256 * 1024) { readyReject(new Error("ASGI output budget exceeded")); child.kill() } })
  child.stderr.on("data", chunk => { stderr = (stderr + chunk.toString()).slice(0, 1000) })
  child.on("error", error => readyReject(error))
  child.on("exit", () => {
    const error = new Error("ASGI transport exited")
    readyReject(error)
    for (const item of pending.values()) item.reject(error)
    pending.clear()
  })
  createInterface({ input: child.stdout }).on("line", line => {
    try {
      assert.ok(line.length < 25000)
      const message = JSON.parse(line)
      if (message.ready === true) readyResolve()
      else if (pending.has(message.id)) { pending.get(message.id).resolve(message); pending.delete(message.id) }
    } catch { readyReject(new Error("Invalid ASGI transport output")) }
  })
  const timer = setTimeout(() => readyReject(new Error("ASGI startup timeout")), 10000)
  try { await ready } finally { clearTimeout(timer) }
  browser = await chromium.launch({ headless: true, chromiumSandbox: true, timeout: 30000,
    ...(channel === "chromium" ? {} : { channel }) })
  browserVersion = browser.version()
  for (const [view, width] of [["desktop", 1280], ["narrow", 390]]) {
    const context = await browser.newContext({ viewport: { width, height: 850 }, serviceWorkers: "block", acceptDownloads: false, permissions: [] })
    const errors = [], activity = []
    let failNextPost = false
    let blocked = 0
    await context.route("**/*", async route => {
      try {
        const req = route.request(), url = new URL(req.url())
        assert.equal(url.origin, origin)
        if (url.pathname === "/api/contacts") {
          assert.ok(["GET", "POST"].includes(req.method()) && !url.search)
          assert.ok(requests.length + pending.size < 128, "Workflow API request budget exceeded")
          const injected = req.method() === "POST" && failNextPost
          if (injected) failNextPost = false
          const result = injected ? { status: 503, body: { detail: "Temporary evaluation failure" } }
            : await request(req.method(), "/contacts", req.method() === "POST" ? req.postDataJSON() : undefined)
          assert.ok(Number.isInteger(result.status))
          activity.push({ method: req.method(), status: result.status, body: result.body })
          requests.push({ view, method: req.method(), status: result.status, ...(injected ? { injected: "fixed_503" } : {}) })
          return await route.fulfill({ status: result.status, contentType: "application/json", body: JSON.stringify(result.body) })
        }
        assert.equal(req.method(), "GET")
        const decoded = decodeURIComponent(url.pathname)
        assert.ok(!decoded.includes("\\") && !decoded.includes("\0"))
        const path = resolve(output, "." + (decoded === "/" ? "/index.html" : decoded))
        const inside = relative(output, path)
        assert.ok(inside && !inside.startsWith("..") && !isAbsolute(inside))
        let current = output
        for (const part of inside.split(/[\\/]/)) {
          current = resolve(current, part)
          const info = await lstat(current)
          assert.ok(!info.isSymbolicLink() && (info.isDirectory() || info.nlink === 1))
        }
        const info = await lstat(path)
        assert.ok(info.isFile() && info.size < 5 * 1024 * 1024)
        const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml" }
        await route.fulfill({ status: 200, contentType: types[extname(path)] ?? "application/octet-stream", body: await readFile(path) })
      } catch { blocked++; await route.abort().catch(() => {}) }
    })
    await context.routeWebSocket("**/*", socket => { blocked++; socket.close() })
    const page = await context.newPage()
    page.setDefaultTimeout(3500)
    context.on("page", popup => { blocked++; void popup.close() })
    page.on("pageerror", error => errors.push(error.message.slice(0, 150)))
    page.on("dialog", dialog => { blocked++; void dialog.dismiss() })
    try {
      await page.goto(origin, { waitUntil: "load", timeout: 10000 })
      const list = page.getByRole("list", { name: "Contacts", exact: true })
      let initial
      await check(`${view}.initial`, async () => {
        await list.getByText("Ada Lovelace", { exact: true }).waitFor()
        initial = activity.find(r => r.method === "GET" && r.status === 200)?.body
        assert.ok(Array.isArray(initial) && initial.length >= 2)
        for (const contact of initial) assert.ok(await list.getByText(contact.name, { exact: true }).isVisible())
        assert.equal(await list.getByRole("listitem").count(), initial.length)
      })
      const name = `Workflow ${randomUUID().slice(0, 8)}`, email = `${randomUUID()}@example.invalid`
      const submit = page.getByRole("button", { name: "Create contact", exact: true })
      const nameInput = page.getByLabel("Name", { exact: true }), emailInput = page.getByLabel("Email", { exact: true })
      await check(`${view}.create`, async () => {
        await page.getByLabel("Name", { exact: true }).fill(name)
        await page.getByLabel("Email", { exact: true }).fill(email)
        await page.getByRole("button", { name: "Create contact", exact: true }).click()
        await list.getByText(name, { exact: true }).waitFor()
        const created = activity.find(r => r.method === "POST" && r.status === 201)?.body
        assert.equal(created?.name, name); assert.equal(created?.email, email)
        assert.equal(await list.getByRole("listitem").count(), initial.length + 1)
      })
      const recoveryName = `Recovery ${randomUUID().slice(0, 8)}`, recoveryEmail = `${randomUUID()}@example.invalid`
      if (resilience) {
        async function rejectedFields(expectedName, expectedEmail, before, count) {
          const alert = page.getByRole("alert").first()
          await alert.waitFor({ state: "visible" })
          assert.ok((await alert.innerText()).trim())
          assert.equal(await nameInput.inputValue(), expectedName)
          assert.equal(await emailInput.inputValue(), expectedEmail)
          assert.equal(await list.getByRole("listitem").count(), count)
          for (const contact of before) assert.ok(await list.getByText(contact.name, { exact: true }).isVisible(), "Rejection changed an existing contact")
          assert.deepEqual((await request("GET", "/contacts")).body, before, "Rejection changed backend records")
        }
        await check(`${view}.duplicate`, async () => {
          const before = (await request("GET", "/contacts")).body, start = activity.length
          const duplicateName = `Duplicate ${randomUUID().slice(0, 8)}`
          await nameInput.fill(duplicateName); await emailInput.fill(email)
          const response = page.waitForResponse(r => r.url() === `${origin}/api/contacts` && r.request().method() === "POST" && r.status() === 409)
          await submit.click()
          await response
          await page.waitForFunction(() => document.querySelector('[role="alert"]')?.textContent?.trim())
          assert.ok(activity.slice(start).some(r => r.method === "POST" && r.status === 409), "No real duplicate rejection observed")
          await rejectedFields(duplicateName, email, before, initial.length + 1)
          assert.equal(await list.getByText(duplicateName, { exact: true }).count(), 0)
        })
        await check(`${view}.invalid`, async () => {
          const start = activity.filter(r => r.method === "POST").length
          await nameInput.fill(""); await emailInput.fill(recoveryEmail)
          await submit.click()
          assert.equal(await nameInput.evaluate(input => input.validity.valid), false, "Empty Name needs browser validation")
          await nameInput.fill(recoveryName); await emailInput.fill("invalid-email")
          await submit.click()
          await page.waitForLoadState("networkidle")
          assert.equal(await emailInput.evaluate(input => input.validity.valid), false, "Invalid email needs browser validation")
          assert.equal(activity.filter(r => r.method === "POST").length, start, "Invalid form submitted to the API")
          assert.equal(await list.getByRole("listitem").count(), initial.length + 1)
        })
        await check(`${view}.server_failure`, async () => {
          const before = (await request("GET", "/contacts")).body, start = activity.length
          await nameInput.fill(recoveryName); await emailInput.fill(recoveryEmail)
          failNextPost = true
          const response = page.waitForResponse(r => r.url() === `${origin}/api/contacts` && r.request().method() === "POST" && r.status() === 503)
          await submit.click()
          await response
          await page.waitForFunction(() => document.querySelector('[role="alert"]')?.textContent?.trim())
          assert.ok(activity.slice(start).some(r => r.method === "POST" && r.status === 503), "No synthetic rejection observed")
          await rejectedFields(recoveryName, recoveryEmail, before, initial.length + 1)
          assert.equal(await list.getByText(recoveryName, { exact: true }).count(), 0)
        })
        await check(`${view}.retry`, async () => {
          const start = activity.length
          await submit.click()
          await list.getByText(recoveryName, { exact: true }).waitFor()
          assert.ok(activity.slice(start).some(r => r.method === "POST" && r.status === 201 && r.body?.email === recoveryEmail), "Retry did not use the real backend")
          assert.equal(await list.getByRole("listitem").count(), initial.length + 2)
          for (const contact of activity.filter(r => r.method === "GET").at(-1).body) {
            assert.ok(await list.getByText(contact.name, { exact: true }).isVisible(), "Reload list differs from persisted API records")
          }
          assert.ok((await page.getByRole("alert").allTextContents()).every(text => !text.trim()), "Successful retry kept a stale error")
        })
      }
      await check(`${view}.persist`, async () => {
        await page.reload({ waitUntil: "load" })
        await list.getByText(name, { exact: true }).waitFor()
        assert.ok(activity.filter(r => r.method === "GET" && r.status === 200).length >= 2)
        assert.ok(activity.filter(r => r.method === "GET").at(-1).body.some(c => c.name === name && c.email === email))
        if (resilience) {
          await list.getByText(recoveryName, { exact: true }).waitFor()
          assert.ok(activity.filter(r => r.method === "GET").at(-1).body.some(c => c.name === recoveryName && c.email === recoveryEmail))
          assert.equal(await list.getByRole("listitem").count(), initial.length + 2)
        }
      })
      await check(`${view}.layout`, async () => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)))
      await check(`${view}.runtime`, async () => { assert.equal(errors.length, 0, errors.join("; ")); assert.equal(blocked, 0) })
    } finally { await context.close() }
  }
} catch { unavailable = true }
finally {
  if (browser) await browser.close()
  if (child) {
    child.stdin.end()
    if (child.exitCode === null && child.signalCode === null) {
      const timer = setTimeout(() => child.kill(), 1500)
      await closed
      clearTimeout(timer)
    }
  }
}
const status = unavailable ? "unavailable" : checks.length === (resilience ? 18 : 10) && checks.every(c => c.status === "passed") ? "passed" : "failed"
console.log(JSON.stringify({ schemaVersion: resilience ? "agenthub.workflow_contacts.v2" : "agenthub.workflow_contacts.v1", contract, status, checks, browserVersion, requests,
  diagnosticCode: unavailable ? "workflow_transport_or_browser_unavailable" : null }))
process.exitCode = status === "passed" ? 0 : status === "unavailable" ? 2 : 1
