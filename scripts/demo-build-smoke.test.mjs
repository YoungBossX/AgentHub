// Trusted build-output tests. Never import or execute the generated application.
import assert from "node:assert/strict"
import { readFileSync, readdirSync, statSync } from "node:fs"
import { resolve, relative, isAbsolute } from "node:path"
import test from "node:test"

const output = resolve(process.env.AGENTHUB_VALIDATION_OUTPUT ?? "apps/demo/dist")
const html = readFileSync(resolve(output, "index.html"), "utf8")

test("built HTML has the React mount point and a module entry", () => {
  assert.match(html, /id=["']root["']/)
  assert.match(html, /<script\b[^>]*type=["']module["'][^>]*src=/)
})

test("every local script and stylesheet reference resolves to a nonempty output", () => {
  const references = [...html.matchAll(/<(?:script|link)\b[^>]*(?:src|href)=["']([^"']+)["']/g)]
  assert.ok(references.length > 0, "No entry resources")
  for (const [, url] of references) {
    assert.ok(!/^(?:[a-z]+:|\/\/)/i.test(url), `Unexpected external resource: ${url}`)
    const file = resolve(output, decodeURIComponent(url.split(/[?#]/)[0]).replace(/^\//, ""))
    const within = relative(output, file)
    assert.ok(within && !within.startsWith("..") && !isAbsolute(within), "Resource escapes output")
    assert.ok(statSync(file).isFile() && statSync(file).size > 0, `Missing/empty resource: ${url}`)
  }
})

test("production assets include nonempty JavaScript and contain no unresolved source entry", () => {
  const assets = readdirSync(resolve(output, "assets"))
  assert.ok(assets.some((name) => name.endsWith(".js") && statSync(resolve(output, "assets", name)).size > 0))
  assert.doesNotMatch(html, /(?:src|href)=["'][^"']*\/src\/[^"']*\.(?:tsx?|jsx?)["']/)
})
