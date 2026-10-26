import { execFile } from "node:child_process";
import net from "node:net";
import path from "node:path";

// Chromium net/base/port_util.cc ports >=1024, checked 2026-10-08.
export const browserBlockedPorts = new Set([
  1719, 1720, 1723, 2049, 3659, 4045, 5060, 5061, 6000, 6566,
  6665, 6666, 6667, 6668, 6669, 6697, 10080,
]);
const host = "127.0.0.1";

function probePort(port) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen({ host, port, exclusive: true }, () => server.close(error => error ? reject(error) : resolve()));
  });
}

function readWindowsExcludedPorts() {
  const command = path.win32.join(process.env.SystemRoot || "C:\\Windows", "System32", "netsh.exe");
  return new Promise((resolve, reject) => {
    execFile(command, ["interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
      { timeout: 3000, maxBuffer: 65536, windowsHide: true },
      (error, stdout) => error ? reject(error) : resolve(stdout));
  });
}

function excludedRange(output, port) {
  if (typeof output !== "string" || output.length > 65536) return null;
  for (const line of output.split(/\r?\n/)) {
    const match = /^\s*(\d{1,5})\s+(\d{1,5})(?:\s+\*)?\s*$/.exec(line);
    if (!match) continue;
    const start = Number(match[1]), end = Number(match[2]);
    if (start >= 1 && end <= 65535 && start <= port && port <= end) return { start, end };
  }
  return null;
}

async function alternativeCommand(port, label, options) {
  const key = label === "API" ? "apiPort" : label === "Web" ? "webPort" : null;
  if (!key || !options) return "";
  const peers = new Set([port, options.apiPort, options.webPort, ...(options.demoApi ? [5174] : [])]);
  const candidates = key === "apiPort" ? [18000, 18001, 19000, 28000] : [3001, 3002, 13000, 13001];
  for (const candidate of candidates) {
    if (peers.has(candidate) || browserBlockedPorts.has(candidate)) continue;
    try { await probePort(candidate); } catch { continue; }
    const next = { ...options, [key]: candidate };
    const args = `--api-port ${next.apiPort} --web-port ${next.webPort}${next.demoApi ? " --demo-api" : ""}`;
    return `已探测可用端口 ${candidate}，可运行：\npnpm doctor:local ${args}\npnpm dev:local ${args}\n探测只反映当前状态，正式启动会再次检查端口。`;
  }
  return "未找到已确认可用的替代端口，请自行选择端口后运行 pnpm doctor:local。";
}

export async function checkLocalPort(port, label, {
  platform = process.platform, readExcludedPorts = readWindowsExcludedPorts, launchOptions,
} = {}) {
  try { await probePort(port); return; }
  catch (cause) {
    const code = cause.code || "UNKNOWN";
    let reason = "监听失败，请检查本机网络状态和启动配置。";
    if (code === "EADDRINUSE") reason = "已有程序监听此端口，请核对服务归属或选择其他端口。";
    else if (code === "EACCES") {
      reason = "系统拒绝绑定此端口，请检查本机网络策略或选择其他端口。";
      if (platform === "win32") {
        let range;
        try { range = excludedRange(await readExcludedPorts(), port); } catch { /* Diagnosis stays unknown. */ }
        reason = range ? `Windows 已保留 TCP 端口范围 ${range.start}–${range.end}，请选择范围外的端口。`
          : "未能确认 Windows 保留端口范围，请检查本机网络策略，或运行 netsh interface ipv4 show excludedportrange protocol=tcp。";
      }
    }
    const hint = label === "Demo API" ? "内置 Demo API 端口固定为 5174；可处理端口问题后重试，或省略 --demo-api。"
      : ["EACCES", "EADDRINUSE"].includes(code) ? await alternativeCommand(port, label, launchOptions) : "";
    const error = new Error(`${label} 端口 ${port} 不可用 [${code}]：${reason}${hint ? `\n${hint}` : ""}`, { cause });
    error.code = code;
    throw error;
  }
}
