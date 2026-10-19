#!/usr/local/bin/node
// Image-owned controller. CLI paths, stages and environment are fixed.
import { constants, lstatSync, mkdirSync, openSync, closeSync, readFileSync, readdirSync,
  readlinkSync, symlinkSync, writeFileSync } from "node:fs"
import { createHash } from "node:crypto"
import { spawnSync } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const PROFILE = "vite-build-smoke-v1"
const hash = (raw) => createHash("sha256").update(raw).digest("hex")
const hex = /^[0-9a-f]{64}$/
const dependencyPath = "/opt/agenthub/apps/demo/node_modules"

export function portablePath(path) {
  if (typeof path !== "string" || path.normalize("NFC") !== path || Buffer.byteLength(path) > 240 ||
      /[\\:\x00-\x1f\x7f]/.test(path)) throw new Error("unsafe_path")
  const parts = path.split("/")
  if (parts.length > 16 || parts.some(p => !p || p === "." || p === ".." || /[. ]$/.test(p) ||
      Buffer.byteLength(p) > 120 || /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(p) ||
      /^(?:\.git|\.env(?:\..*)?|secrets|node_modules)$/i.test(p))) throw new Error("unsafe_path")
  return path
}

export function validateManifest(value) {
  if (value?.schemaVersion !== "agenthub.container_input.v1" || value.profile !== PROFILE ||
      !hex.test(value.sourceFingerprint) || !value.sourceFiles || Array.isArray(value.sourceFiles))
    throw new Error("invalid_manifest")
  const entries = Object.entries(value.sourceFiles)
  if (!entries.length || entries.length > 512) throw new Error("input_budget")
  const seen = new Set()
  for (const [path, checksum] of entries) {
    portablePath(path)
    const key = path.toLocaleLowerCase("en-US")
    if (!path.startsWith("apps/demo/") || path.startsWith("apps/demo/dist/") || !hex.test(checksum) || seen.has(key))
      throw new Error("invalid_manifest")
    seen.add(key)
  }
  return value
}

function regularBytes(root, path, limit) {
  const parts = path.split("/")
  for (let i = 1; i < parts.length; i++) {
    const info = lstatSync(resolve(root, ...parts.slice(0, i)))
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error("unsafe_directory")
  }
  const file = resolve(root, path)
  const info = lstatSync(file)
  if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > limit) throw new Error("unsafe_file")
  const fd = openSync(file, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0))
  try {
    const raw = readFileSync(fd)
    if (raw.length > limit) throw new Error("file_budget")
    return raw
  } finally { closeSync(fd) }
}

export function copyInput(input, work) {
  const manifest = validateManifest(JSON.parse(regularBytes(input, "manifest.json", 256 * 1024).toString("utf8")))
  let total = 0
  for (const [path, checksum] of Object.entries(manifest.sourceFiles)) {
    const raw = regularBytes(input, path, 512 * 1024)
    total += raw.length
    if (total > 16 * 1024 * 1024 || hash(raw) !== checksum) throw new Error("input_mismatch")
    const output = resolve(work, path)
    mkdirSync(dirname(output), { recursive: true })
    writeFileSync(output, raw, { flag: "wx", mode: 0o600 })
  }
  symlinkSync(dependencyPath, resolve(work, "apps/demo/node_modules"), "dir")
  return manifest
}

function walk(root, relative = "", result = [], { source = false } = {}) {
  for (const entry of readdirSync(resolve(root, relative), { withFileTypes: true })) {
    if (result.length > 1024) throw new Error("entry_budget")
    const path = relative ? `${relative}/${entry.name}` : entry.name
    if (source && !relative && entry.name === "node_modules") {
      if (!entry.isSymbolicLink() || readlinkSync(resolve(root, path)) !== dependencyPath) throw new Error("dependency_link")
      continue
    }
    if (source && !relative && entry.name === "dist") continue
    portablePath(path)
    if (entry.isSymbolicLink()) throw new Error("unsafe_link")
    result.push(path)
    if (entry.isDirectory()) walk(root, path, result, { source: false })
  }
  return result
}

export function exportResult(work, manifest) {
  validateManifest(manifest)
  const sourceFiles = {}
  const project = resolve(work, "apps/demo")
  for (const path of walk(project, "", [], { source: true })) {
    if (!lstatSync(resolve(project, path)).isFile()) continue
    const inputPath = `apps/demo/${path}`
    sourceFiles[inputPath] = hash(regularBytes(project, path, 512 * 1024))
  }
  if (JSON.stringify(Object.entries(sourceFiles).sort()) !== JSON.stringify(Object.entries(manifest.sourceFiles).sort()))
    throw new Error("source_changed")
  const output = resolve(project, "dist")
  if (!lstatSync(output).isDirectory() || lstatSync(output).isSymbolicLink()) throw new Error("unsafe_output")
  let total = 0
  const files = walk(output).filter(path => lstatSync(resolve(output, path)).isFile()).map(path => {
    const raw = regularBytes(output, path, 5 * 1024 * 1024)
    total += raw.length
    if (total > 32 * 1024 * 1024) throw new Error("output_budget")
    return { path, sha256: hash(raw), base64: raw.toString("base64") }
  })
  if (!files.length || files.length > 512) throw new Error("output_budget")
  return { schemaVersion: "agenthub.container_export.v1", sourceFingerprint: manifest.sourceFingerprint, sourceFiles, files }
}

export function stageCommand(stage) {
  const commands = {
    check: ["/usr/local/bin/node", "/opt/agenthub/apps/demo/node_modules/typescript/bin/tsc", "--project", "tsconfig.app.json",
      "--incremental", "--tsBuildInfoFile", "/work/check.tsbuildinfo"],
    build: ["/usr/local/bin/node", "/opt/agenthub/scripts/demo-validation-build.mjs"],
    test: ["/usr/local/bin/node", "--test", "/opt/agenthub/scripts/demo-build-smoke.test.mjs"],
  }
  if (!Object.hasOwn(commands, stage)) throw new Error("unsupported_stage")
  return commands[stage]
}

function assertNoBackgroundProcesses() {
  let keepers = 0
  for (const name of readdirSync("/proc")) {
    if (!/^\d+$/.test(name) || Number(name) === process.pid || name === "1") continue
    let cmd
    try { cmd = readFileSync(`/proc/${name}/cmdline`).toString().split("\0").filter(Boolean) }
    catch (error) { if (error.code === "ENOENT") continue; throw error }
    if (cmd.length === 3 && cmd[1] === "/opt/agenthub/control" && cmd[2] === "hold" &&
        readlinkSync(`/proc/${name}/exe`) === "/usr/local/bin/node") keepers++
    else throw new Error("unexpected_process")
  }
  if (keepers !== 1) throw new Error("keeper_missing")
}

export function main(args) {
  const stage = args[0]
  if (args.length !== 1 || !["hold", "prepare", "check", "build", "test", "export"].includes(stage)) {
    console.error("unsupported_stage")
    return 2
  }
  if (stage === "hold") { setTimeout(() => process.exit(0), 180000); return null }
  if (stage === "prepare") { copyInput("/input", "/work"); return 0 }
  if (stage === "export") {
    assertNoBackgroundProcesses()
    const manifest = JSON.parse(regularBytes("/input", "manifest.json", 256 * 1024))
    const raw = JSON.stringify(exportResult("/work", manifest))
    if (Buffer.byteLength(raw) > 48 * 1024 * 1024) throw new Error("transport_budget")
    process.stdout.write(raw)
    return 0
  }
  const [command, ...argv] = stageCommand(stage)
  const result = spawnSync(command, argv, { cwd: "/work/apps/demo", stdio: "inherit", timeout: 60000,
    env: { PATH: "/usr/local/bin:/usr/bin:/bin", CI: "1", NODE_ENV: "production", HOME: "/tmp", TMPDIR: "/tmp",
      LANG: "C.UTF-8", AGENTHUB_VALIDATION_OUTPUT: "/work/apps/demo/dist" } })
  return result.status ?? 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { const status = main(process.argv.slice(2)); if (status !== null) process.exitCode = status }
  catch { console.error("controller_failed"); process.exitCode = 1 }
}
