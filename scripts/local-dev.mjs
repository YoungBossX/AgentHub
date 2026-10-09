import { spawn, execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { access, constants } from "node:fs/promises";
import { createRequire } from "node:module";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const host = "127.0.0.1";
// Ports >=1024 from Chromium's net/base/port_util.cc (checked 2026-10-08).
const browserBlockedPorts = new Set([
  1719, 1720, 1723, 2049, 3659, 4045, 5060, 5061, 6000, 6566,
  6665, 6666, 6667, 6668, 6669, 6697, 10080,
]);
const systemKeys = new Set([
  "APPDATA", "CI", "COLORTERM", "COMSPEC", "COREPACK_HOME", "FORCE_COLOR",
  "HOME", "HOMEDRIVE", "HOMEPATH", "LANG", "LC_ALL", "LC_CTYPE", "LOCALAPPDATA",
  "NODE_ENV", "NO_COLOR", "PATH", "PATHEXT", "PNPM_HOME", "PNPM_STORE_PATH",
  "SHELL", "SYSTEMROOT", "TEMP", "TERM", "TMP", "TMPDIR", "TZ", "USERPROFILE", "WINDIR",
]);

export function parseOptions(args, env = process.env) {
  const options = {
    apiPort: env.AGENTHUB_API_PORT || "8000",
    webPort: env.AGENTHUB_WEB_PORT || "3000",
    demoApi: false, doctor: false, help: false,
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--") continue; // pnpm run forwarding separator
    if (arg === "--demo-api") options.demoApi = true;
    else if (arg === "--doctor") options.doctor = true;
    else if (arg === "--help" || arg === "-h") options.help = true;
    else if (arg === "--api-port" || arg === "--web-port") {
      if (!args[index + 1] || args[index + 1].startsWith("--")) {
        throw new Error(`${arg} requires a numeric port.`);
      }
      options[arg === "--api-port" ? "apiPort" : "webPort"] = args[++index];
    } else throw new Error("Unsupported option. Run pnpm dev:local --help.");
  }
  if (options.help) return options;
  for (const key of ["apiPort", "webPort"]) {
    const raw = String(options[key]);
    if (!/^\d+$/.test(raw) || Number(raw) < 1024 || Number(raw) > 65535) {
      throw new Error(`${key}: use a port between 1024 and 65535.`);
    }
    options[key] = Number(raw);
    if (browserBlockedPorts.has(options[key])) {
      throw new Error(`${key}: this port is blocked by browsers; use 3001 or 8001 instead.`);
    }
  }
  const ports = [options.apiPort, options.webPort, ...(options.demoApi ? [5174] : [])];
  if (new Set(ports).size !== ports.length) throw new Error("Selected service ports must be distinct.");
  return options;
}

export function projectEnvironment(env) {
  return Object.fromEntries(Object.entries(env).filter(([key]) =>
    systemKeys.has(key.toUpperCase()) || /^(NEXT_PUBLIC_|PUBLIC_|VITE_)/i.test(key)));
}

export function serviceEnvironments(options, env = process.env) {
  return {
    api: { ...env, AGENTHUB_FRONTEND_ORIGIN: `http://${host}:${options.webPort}`, PYTHONIOENCODING: "utf-8" },
    web: { ...projectEnvironment(env), BACKEND_URL: `http://${host}:${options.apiPort}`, NEXT_TELEMETRY_DISABLED: "1" },
    demoApi: { ...projectEnvironment(env), PYTHONIOENCODING: "utf-8" },
  };
}

function commandOutput(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: 15000, maxBuffer: 65536, windowsHide: true, ...options }, (error, stdout) => {
      if (error) reject(new Error("Command failed or timed out."));
      else resolve(stdout.trim());
    });
  });
}

async function executable(candidate) {
  try {
    await access(candidate, process.platform === "win32" ? constants.F_OK : constants.X_OK);
    return true;
  } catch { return false; }
}

export async function resolvePython(root, env = process.env) {
  if (env.AGENTHUB_PYTHON_BIN) {
    const override = path.resolve(root, env.AGENTHUB_PYTHON_BIN);
    if (!await executable(override)) throw new Error("AGENTHUB_PYTHON_BIN is not executable. Set it to an installed Python 3.11+ interpreter.");
    return override;
  }
  const candidates = [path.join(root, ".venv/bin/python"), path.join(root, ".venv/Scripts/python.exe")];
  try {
    const common = await commandOutput("git", ["-C", root, "rev-parse", "--git-common-dir"]);
    const commonRoot = path.dirname(path.resolve(root, common));
    candidates.push(path.join(commonRoot, ".venv/bin/python"), path.join(commonRoot, ".venv/Scripts/python.exe"));
  } catch { /* Git diagnostics below report a missing command separately. */ }
  if (env.CONDA_PREFIX) candidates.push(path.join(env.CONDA_PREFIX, "bin/python"), path.join(env.CONDA_PREFIX, "python.exe"));
  for (const candidate of candidates) if (await executable(candidate)) return candidate;
  throw new Error("Missing Python environment. Create .venv, activate Conda, or set AGENTHUB_PYTHON_BIN; see docs/local-usage.md.");
}

export async function checkPort(port, label) {
  await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", () => reject(new Error(`${label} port ${port} is occupied or unavailable. Stop its owner yourself or choose another port; existing listeners are untouched.`)));
    server.listen({ host, port, exclusive: true }, () => server.close(error => error ? reject(error) : resolve()));
  });
}

export async function preflight(options, root = repoRoot, env = process.env) {
  const [major, minor] = process.versions.node.split(".").map(Number);
  if (!((major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major >= 24)) {
    throw new Error("Node must match ^20.19.0 || ^22.12.0 || >=24.0.0.");
  }
  try { await commandOutput("git", ["-C", root, "rev-parse", "--show-toplevel"]); }
  catch { throw new Error("Git is missing from PATH or this directory is not a Git checkout."); }
  let nextCli;
  try {
    const webRequire = createRequire(path.join(root, "apps/web/package.json"));
    nextCli = webRequire.resolve("next/dist/bin/next");
    for (const name of ["react", "react-dom", "@tailwindcss/postcss"]) webRequire.resolve(name);
    const demoRequire = createRequire(path.join(root, "apps/demo/package.json"));
    for (const name of ["vite", "react", "react-dom"]) demoRequire.resolve(name);
  } catch { throw new Error("Missing Web/Demo dependencies. Run the documented pnpm install/setup commands explicitly first."); }
  const python = await resolvePython(root, env);
  let version;
  try {
    version = await commandOutput(python, ["-c", "import sys; assert sys.version_info >= (3, 11); import fastapi, uvicorn, sqlmodel, pydantic_settings, httpx; from pypdf import apply_configuration; from PIL import Image, ImageOps; print('.'.join(map(str, sys.version_info[:3])))"], { cwd: root, env });
  } catch { throw new Error("Python must be 3.11+ with apps/api/requirements.txt installed in the selected environment. No packages were installed."); }
  // Do not import app.main: doctor must not create SQLite or run startup workers.
  await checkPort(options.apiPort, "API");
  await checkPort(options.webPort, "Web");
  if (options.demoApi) await checkPort(5174, "Demo API");
  return { python, nextCli, pythonVersion: version };
}

export function startService(spec, { quiet = false } = {}) {
  const child = spawn(spec.command, spec.args, {
    cwd: spec.cwd, env: spec.env, shell: false, windowsHide: true,
    detached: process.platform !== "win32", stdio: ["pipe", "pipe", "pipe"],
  });
  const service = { ...spec, child, ready: false, ended: false, failure: null };
  let tail = "";
  child.stdout.on("data", data => {
    if (!quiet) process.stdout.write(data);
    tail = (tail + data.toString()).slice(-4096).replace(/\x1b\[[0-9;]*m/g, "");
    if (tail.includes(spec.readyMarker)) service.ready = true;
  });
  child.stderr.on("data", data => { if (!quiet) process.stderr.write(data); });
  child.stdin.on("error", () => {}); // A child may exit before a stop write.
  service.exit = new Promise(resolve => {
    child.once("error", () => {
      service.failure = `${spec.label} could not start.`;
      service.ended = true;
      resolve();
    });
    child.once("close", (code, signal) => {
      service.failure ||= `${spec.label} exited (${signal || code}).`;
      service.ended = true;
      resolve();
    });
  });
  return service;
}

export async function waitReady(service, services, cancelled = () => false, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (cancelled()) throw new Error("Startup cancelled.");
    const failed = services.find(item => item.ended);
    if (failed) throw new Error(failed.failure);
    if (service.ready) {
      try {
        const response = await fetch(service.url, { signal: AbortSignal.timeout(1500), redirect: "error" });
        if (response.ok) {
          const matches = !service.healthName || (await response.json()).service === service.healthName;
          await response.body?.cancel().catch(() => {});
          if (matches && !service.ended) return;
        } else await response.body?.cancel();
      } catch { /* Wait for our own service to finish initializing. */ }
    }
    await delay(100);
  }
  throw new Error(`${service.label} did not become ready in ${Math.round(timeoutMs / 1000)}s. Check its startup log; spawned services will be stopped.`);
}

async function forceTree(service) {
  // Never act on a cached PID after its owned child handle has exited.
  if (service.ended || service.child.exitCode !== null || service.child.signalCode !== null) return;
  if (process.platform === "win32") {
    await commandOutput("taskkill", ["/PID", String(service.child.pid), "/T", "/F"]);
  } else process.kill(-service.child.pid, "SIGKILL");
}

export async function stopServices(services, graceMs = 15000) {
  const errors = [];
  for (const service of services) {
    if (service.ended) continue;
    if (service.graceful) service.child.stdin.end("stop\n");
    else {
      try {
        if (process.platform === "win32") await forceTree(service);
        else process.kill(-service.child.pid, "SIGTERM");
      } catch { if (!service.ended) errors.push(`${service.label} stop signal failed.`); }
    }
  }
  await Promise.all(services.map(async service => {
    if (service.ended) return;
    // Cancel the timer on normal exit so it does not hold the launcher open.
    const timer = new AbortController();
    await Promise.race([service.exit, delay(graceMs, null, { signal: timer.signal }).catch(() => {})]);
    timer.abort();
    if (!service.ended) {
      try { await forceTree(service); }
      catch { if (!service.ended) errors.push(`${service.label} forced cleanup failed.`); }
      await Promise.race([service.exit, delay(1000)]);
    }
    if (!service.ended) errors.push(`${service.label} is still running; inspect the owned process.`);
  }));
  if (errors.length) throw new Error(errors.join(" "));
}

export async function runLocal(args, env = process.env) {
  const options = parseOptions(args, env);
  if (options.help) {
    console.log("pnpm dev:local [--api-port 8000] [--web-port 3000] [--demo-api]\npnpm doctor:local [same port options]\nOnly 127.0.0.1; demo API uses 5174. Ctrl+C stops owned services. See docs/local-usage.md.");
    return;
  }
  let stopping = false;
  let wake;
  let exitCode = 0;
  const stopped = new Promise(resolve => { wake = resolve; });
  const requestStop = () => { stopping = true; wake(); };
  const input = data => { if (data.toString().split(/\r?\n/).some(line => line.trim() === "stop")) requestStop(); };
  const services = [];
  if (!options.doctor) {
    process.on("SIGINT", requestStop);
    process.on("SIGTERM", requestStop);
    process.stdin.on("data", input);
    process.stdin.on("end", requestStop);
    process.stdin.resume();
  }
  try {
    const installed = await preflight(options, repoRoot, env);
    console.log(`[local] Dependencies and ports OK: Node ${process.versions.node}, Python ${installed.pythonVersion}.`);
    if (options.doctor || stopping) return;
    const environments = serviceEnvironments(options, env);
    const token = randomUUID();
    const specs = [{
      label: "API", command: installed.python, cwd: path.join(repoRoot, "apps/api"), env: environments.api,
      args: ["-u", path.join(repoRoot, "scripts/local-api.py"), "--service", "api", "--port", String(options.apiPort), "--ready-token", token],
      readyMarker: `[agenthub-ready:${token}]`, healthName: "agenthub-api", graceful: true,
      url: `http://${host}:${options.apiPort}/health`,
    }];
    if (options.demoApi) specs.push({
      label: "Demo API", command: installed.python, cwd: path.join(repoRoot, "apps/demo-api"), env: environments.demoApi,
      args: ["-u", path.join(repoRoot, "scripts/local-api.py"), "--service", "demo-api", "--port", "5174", "--ready-token", token],
      readyMarker: `[agenthub-ready:${token}]`, healthName: "agenthub-demo-api", graceful: true,
      url: `http://${host}:5174/health`,
    });
    specs.push({
      label: "Web", command: process.execPath, cwd: path.join(repoRoot, "apps/web"), env: environments.web,
      args: [installed.nextCli, "dev", "--hostname", host, "--port", String(options.webPort)],
      readyMarker: "Ready in", graceful: false, url: `http://${host}:${options.webPort}/`,
    });
    for (const spec of specs) {
      if (stopping) break;
      console.log(`[local] Starting ${spec.label}.`);
      const service = startService(spec);
      services.push(service);
      service.exit.then(() => { if (!stopping) { exitCode = 1; console.error(`[local] ${service.failure}`); requestStop(); } });
      await waitReady(service, services, () => stopping);
    }
    if (!stopping) {
      console.log(`[local] Ready: http://${host}:${options.webPort}/ (API http://${host}:${options.apiPort})`);
      if (options.demoApi) console.log(`[local] Demo API: http://${host}:5174`);
      console.log("[local] Ctrl+C to stop. API source changes require a restart; dev:api retains reload mode.");
      await stopped;
    }
  } catch (error) {
    if (!stopping) { exitCode = 1; console.error(`[local] ${error.message}`); }
  } finally {
    stopping = true;
    let cleaned = false;
    try { await stopServices(services); cleaned = true; }
    catch (error) { exitCode = 1; console.error(`[local] ${error.message}`); }
    if (services.length && cleaned) console.log("[local] Owned services stopped. Sessions and worktrees retained.");
    process.removeListener("SIGINT", requestStop);
    process.removeListener("SIGTERM", requestStop);
    process.stdin.removeListener("data", input);
    process.stdin.removeListener("end", requestStop);
    if (!options.doctor) process.stdin.pause();
    process.exitCode = exitCode;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runLocal(process.argv.slice(2)).catch(error => { console.error(`[local] ${error.message}`); process.exitCode = 1; });
}
