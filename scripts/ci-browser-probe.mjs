import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, errors } from "playwright";

export async function verifySandboxedBrowser(browserType, { channel = "chrome", log = console.log, warn = console.warn } = {}) {
  let browser;
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      browser = await browserType.launch({ channel, headless: true, chromiumSandbox: true, timeout: 60000 });
      break;
    } catch (error) {
      if (!(error instanceof errors.TimeoutError) || attempt === 2) throw error;
      warn("Browser launch timed out (attempt 1/2); retrying once with the sandbox still enabled.");
    }
  }
  try {
    const page = await browser.newPage();
    await page.setContent("<h1>Browser ready</h1>", { timeout: 10000 });
    if (await page.locator("h1").innerText({ timeout: 10000 }) !== "Browser ready") throw new Error("Browser probe failed");
    const version = browser.version();
    log(`Sandboxed ${channel} ready: ${version}`);
    return version;
  } finally { await browser.close(); }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  verifySandboxedBrowser(chromium, { channel: process.env.AGENTHUB_VALIDATION_BROWSER_CHANNEL ?? "chrome" })
    .catch(error => { console.error(error); process.exitCode = 1; });
}
