import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, writeFile, rm, readFile } from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import {
  parseOptions, projectEnvironment, serviceEnvironments, resolvePython,
  checkPort, startService, waitReady, stopServices,
} from "./local-dev.mjs";

async function unusedPort() {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

test("port overrides, forwarding and fixed demo contract stay coherent", () => {
  const options = parseOptions(["--", "--api-port", "8007", "--web-port", "3001", "--demo-api"], { AGENTHUB_API_PORT: "bad" });
  assert.equal(options.apiPort, 8007);
  assert.equal(options.webPort, 3001);
  const environments = serviceEnvironments(options, { BACKEND_URL: "http://incorrect", AGENTHUB_FRONTEND_ORIGIN: "http://incorrect" });
  assert.equal(environments.web.BACKEND_URL, "http://127.0.0.1:8007");
  assert.equal(environments.api.AGENTHUB_FRONTEND_ORIGIN, "http://127.0.0.1:3001");
  for (const args of [
    ["--api-port", "3000"], ["--api-port", "5174", "--demo-api"],
    ["--web-port", "1719"], ["--api-port", "6000"], ["--web-port", "65536"],
    ["--web-port", "3000x"], ["--web-port", "0"], ["--api-port"], ["--host", "0.0.0.0"],
  ]) assert.throws(() => parseOptions(args, {}));
});

test("Web and demo API do not inherit private backend or tool configuration", () => {
  const source = { Path: "system", USERPROFILE: "home", NEXT_PUBLIC_LABEL: "public", VITE_NAME: "public",
    ANTHROPIC_API_KEY: "private", OPENAI_API_KEY: "private", AGENTHUB_DATABASE_URL: "private",
    NODE_OPTIONS: "--require private", PYTHONPATH: "private", BACKEND_URL: "private" };
  assert.deepEqual(Object.keys(projectEnvironment(source)).sort(), ["NEXT_PUBLIC_LABEL", "Path", "USERPROFILE", "VITE_NAME"].sort());
  const environments = serviceEnvironments(parseOptions([], {}), source);
  assert.equal(environments.api.ANTHROPIC_API_KEY, "private");
  for (const env of [environments.web, environments.demoApi]) {
    assert.equal(env.ANTHROPIC_API_KEY, undefined);
    assert.equal(env.AGENTHUB_DATABASE_URL, undefined);
    assert.equal(env.NODE_OPTIONS, undefined);
    assert.equal(env.PYTHONPATH, undefined);
  }
});

test("invalid explicit Python fails rather than falling back; paths with spaces resolve", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "agenthub launcher space "));
  try {
    const selected = path.join(root, ".venv/Scripts/python.exe");
    await mkdir(path.dirname(selected), { recursive: true });
    await writeFile(selected, "", { mode: 0o700 });
    await assert.rejects(resolvePython(root, { AGENTHUB_PYTHON_BIN: "missing" }), /AGENTHUB_PYTHON_BIN/);
    assert.equal(await resolvePython(root, { AGENTHUB_PYTHON_BIN: selected }), selected);
    assert.equal(await resolvePython(root, {}), selected);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("occupied port detection retains the original listener", async () => {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  try {
    await assert.rejects(checkPort(port, "API"), /occupied or unavailable/);
    assert.equal(server.listening, true);
  } finally { await new Promise(resolve => server.close(resolve)); }
  await checkPort(port, "API");
});

const fixture = `
  const http = require('node:http');
  const fs = require('node:fs');
  const [port, name, trace] = process.argv.slice(1);
  const server = http.createServer((req, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({service:name})); });
  server.listen(Number(port), '127.0.0.1', () => console.log('fixture-ready'));
  function stop() { server.close(() => { if(trace) fs.writeFileSync(trace, 'graceful'); process.exit(0); }); }
  process.stdin.on('data', data => { if(data.toString().includes('stop')) stop(); });
  process.stdin.on('end', stop);
  process.stdin.resume();
`;

async function startFixture(name = "fixture-api", graceful = true, trace = "") {
  const port = await unusedPort();
  return startService({
    label: "Fixture", command: process.execPath, args: ["-e", fixture, String(port), name, trace],
    cwd: os.tmpdir(), env: projectEnvironment(process.env), graceful,
    readyMarker: "fixture-ready", healthName: "fixture-api", url: `http://127.0.0.1:${port}/`, port,
  }, { quiet: true });
}

test("owned readiness plus HTTP identity, graceful cleanup and repeat cleanup", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "agenthub-launcher-cleanup-"));
  const trace = path.join(root, "cleanup.txt");
  const service = await startFixture("fixture-api", true, trace);
  try {
    await waitReady(service, [service], () => false, 5000);
    await stopServices([service], 5000);
    assert.equal(await readFile(trace, "utf8"), "graceful");
    await stopServices([service], 5000);
    await checkPort(service.port, "Fixture");
  } finally { await stopServices([service]); await rm(root, { recursive: true, force: true }); }
});

test("wrong HTTP identity times out even when its own ready marker exists", async () => {
  const service = await startFixture("wrong-service");
  try { await assert.rejects(waitReady(service, [service], () => false, 1200), /did not become ready/); }
  finally { await stopServices([service]); }
  await checkPort(service.port, "Fixture");
});

test("child start failure and early exit cannot be reported ready", async () => {
  const missing = startService({ label: "Missing", command: path.join(os.tmpdir(), "agenthub-missing-command"), args: [], readyMarker: "ready" }, { quiet: true });
  await assert.rejects(waitReady(missing, [missing], () => false, 3000), /could not start/);
  await stopServices([missing]);
  const early = startService({ label: "Early", command: process.execPath, args: ["-e", "process.exit(7)"], readyMarker: "ready" }, { quiet: true });
  await assert.rejects(waitReady(early, [early], () => false, 3000), /exited \(7\)/);
  await stopServices([early]);
});

test("a sibling exit aborts readiness and startup cancellation cleans siblings", async () => {
  const service = await startFixture();
  try {
    const failed = { ended: true, failure: "API stopped" };
    await assert.rejects(waitReady(service, [service, failed], () => false, 3000), /API stopped/);
    await assert.rejects(waitReady(service, [service], () => true, 3000), /cancelled/);
  } finally { await stopServices([service]); }
  await checkPort(service.port, "Fixture");
});

test("stdin EOF stops the managed service instead of orphaning it", async () => {
  const service = await startFixture();
  try {
    await waitReady(service, [service], () => false, 5000);
    service.child.stdin.end();
    await Promise.race([service.exit, delay(3000)]);
    assert.equal(service.ended, true);
  } finally { await stopServices([service]); }
});

test("Python control pipe is private; subprocess stdin reaches EOF while launcher stays open", async () => {
  const root = path.resolve(import.meta.dirname, "..");
  const python = await resolvePython(root);
  const source = `
import importlib.util, subprocess, sys
spec = importlib.util.spec_from_file_location('local_api', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
control = module.launcher_input()
result = subprocess.run([sys.executable, '-c', 'import sys; print(len(sys.stdin.read()))'], capture_output=True, text=True, timeout=3)
assert result.returncode == 0 and result.stdout.strip() == '0'
git = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True, timeout=3)
assert git.returncode == 0
print('private-input-ready', flush=True)
assert control.readline().strip() == 'stop'
control.close()
`;
  const service = startService({ label: "Private control", command: python,
    args: ["-u", "-c", source, path.join(root, "scripts/local-api.py")], cwd: root,
    env: projectEnvironment(process.env), graceful: true, readyMarker: "private-input-ready",
  }, { quiet: true });
  try {
    const deadline = Date.now() + 7000;
    while (!service.ready && !service.ended && Date.now() < deadline) await delay(50);
    assert.equal(service.ready, true, "Child inherited the open control input or failed Git");
    assert.equal(service.ended, false);
    await stopServices([service], 3000);
    assert.equal(service.child.exitCode, 0);
  } finally { await stopServices([service]); }
});

test("forced cleanup stops an owned child tree while another listener survives", async () => {
  const foreign = await startFixture();
  const port = await unusedPort();
  const parent = startService({
    label: "Tree", command: process.execPath,
    args: ["-e", `const {spawn}=require('node:child_process'); const child=spawn(process.execPath,['-e',${JSON.stringify(fixture)},${JSON.stringify(String(port))},'fixture-api',''],{stdio:['pipe','pipe','inherit']}); child.stdout.pipe(process.stdout); setInterval(()=>{},1000);`],
    env: projectEnvironment(process.env), cwd: os.tmpdir(), graceful: false,
    readyMarker: "fixture-ready", url: `http://127.0.0.1:${port}/`, healthName: "fixture-api",
  }, { quiet: true });
  try {
    await waitReady(foreign, [foreign], () => false, 5000);
    await waitReady(parent, [parent], () => false, 5000);
    await stopServices([parent], 1500);
    await checkPort(port, "Owned descendant");
    assert.equal((await fetch(foreign.url)).status, 200);
    assert.equal(foreign.ended, false);
  } finally { await stopServices([parent, foreign]); }
});

test("CLI rejects bad arguments before spawning services", async () => {
  const cli = spawn(process.execPath, [path.join(import.meta.dirname, "local-dev.mjs"), "--api-port", "3000"], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  let error = "";
  cli.stderr.on("data", chunk => { error += chunk; });
  const code = await new Promise(resolve => cli.on("close", resolve));
  assert.equal(code, 1);
  assert.match(error, /ports must be distinct/);
});
