import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import test from "node:test"

const controlUrl = new URL("./frontend-control.mjs", import.meta.url)

test("frontend CLI rejects arbitrary stages and extra paths before filesystem access", () => {
  for (const args of [["shell"], ["test", "/arbitrary/path"], ["export", "../escape"]]) {
    const result = spawnSync(process.execPath, [controlUrl.pathname.replace(/^\/(?=[A-Za-z]:)/, ""), ...args])
    assert.equal(result.status, 2)
    assert.match(result.stderr.toString(), /unsupported_stage/)
  }
})

test("frontend stage maps only to trusted installed tools", async () => {
  const { stageCommand } = await import(controlUrl)
  assert.deepEqual(stageCommand("build"), ["/usr/local/bin/node", "/opt/agenthub/scripts/demo-validation-build.mjs"])
  assert.throws(() => stageCommand("npm install"))
})

test("frontend manifest rejects unsafe or cross-profile source paths", async () => {
  const { validateManifest } = await import(controlUrl)
  for (const path of ["../bad", "apps/demo/.env", "apps/demo/node_modules/x", "C:/bad", "apps/demo/a\\b",
                      "apps/demo/CON.js", "apps/demo/a:b", "apps/demo/a.", "apps/demo-api/app/main.py"]) {
    assert.throws(() => validateManifest({ schemaVersion: "agenthub.container_input.v1",
      profile: "vite-build-smoke-v1", sourceFingerprint: "f".repeat(64), sourceFiles: { [path]: "a".repeat(64) } }))
  }
})
