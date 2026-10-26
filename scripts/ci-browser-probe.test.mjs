import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { errors } from "playwright";
import { verifySandboxedBrowser } from "./ci-browser-probe.mjs";

function fixture({ launchFailures = [], text = "Browser ready", readinessFailure, pageFailure, closeFailure } = {}) {
  const calls = { launches: [], closed: 0, content: [], warnings: [], logs: [] };
  const browser = {
    version: () => "test-browser",
    async newPage() {
      if (pageFailure) throw pageFailure;
      return {
        async setContent(value, options) {
          calls.content.push({ value, options });
          if (readinessFailure) throw readinessFailure;
        },
        locator(selector) {
          assert.equal(selector, "h1");
          return { async innerText(options) { calls.textOptions = options; return text; } };
        },
      };
    },
    async close() { calls.closed++; if (closeFailure) throw closeFailure; },
  };
  return {
    calls,
    chromium: { async launch(options) {
      calls.launches.push(options);
      const failure = launchFailures[calls.launches.length - 1];
      if (failure) throw failure;
      return browser;
    } },
    options: { channel: "chrome", log: value => calls.logs.push(value), warn: value => calls.warnings.push(value) },
  };
}

test("probe renders the trusted page and closes the sandboxed browser", async () => {
  const f = fixture();
  assert.equal(await verifySandboxedBrowser(f.chromium, f.options), "test-browser");
  assert.deepEqual(f.calls.launches, [{ channel: "chrome", headless: true, chromiumSandbox: true, timeout: 60000 }]);
  assert.equal(f.calls.closed, 1);
  assert.deepEqual(f.calls.content, [{ value: "<h1>Browser ready</h1>", options: { timeout: 10000 } }]);
  assert.deepEqual(f.calls.textOptions, { timeout: 10000 });
  assert.equal(f.calls.warnings.length, 0);
  assert.match(f.calls.logs[0], /Sandboxed chrome ready: test-browser/);
});

test("a launch timeout gets one fresh attempt with the identical sandbox policy", async () => {
  const f = fixture({ launchFailures: [new errors.TimeoutError("cold startup")] });
  assert.equal(await verifySandboxedBrowser(f.chromium, f.options), "test-browser");
  assert.equal(f.calls.launches.length, 2);
  assert.deepEqual(f.calls.launches[0], f.calls.launches[1]);
  assert.equal(f.calls.launches[1].chromiumSandbox, true);
  assert.equal(f.calls.warnings.length, 1);
  assert.equal(f.calls.closed, 1);
});

test("two launch timeouts propagate the last failure without a third attempt", async () => {
  const last = new errors.TimeoutError("still unavailable");
  const f = fixture({ launchFailures: [new errors.TimeoutError("slow"), last] });
  await assert.rejects(verifySandboxedBrowser(f.chromium, f.options), error => error === last);
  assert.equal(f.calls.launches.length, 2);
  assert.equal(f.calls.closed, 0);
  assert.equal(f.calls.logs.length, 0);
});

for (const message of ["Executable doesn't exist", "No usable sandbox", "invalid channel configuration"]) {
  test(`launch failure stays fatal without retry: ${message}`, async () => {
    const failure = new Error(message), f = fixture({ launchFailures: [failure] });
    await assert.rejects(verifySandboxedBrowser(f.chromium, f.options), error => error === failure);
    assert.equal(f.calls.launches.length, 1);
    assert.equal(f.calls.warnings.length, 0);
  });
}

test("incorrect readiness content fails and still closes the browser", async () => {
  const f = fixture({ text: "not ready" });
  await assert.rejects(verifySandboxedBrowser(f.chromium, f.options), /Browser probe failed/);
  assert.equal(f.calls.launches.length, 1);
  assert.equal(f.calls.closed, 1);
  assert.equal(f.calls.logs.length, 0);
});

test("a page readiness timeout is closed and is not retried as a launch timeout", async () => {
  const failure = new errors.TimeoutError("page stalled"), f = fixture({ readinessFailure: failure });
  await assert.rejects(verifySandboxedBrowser(f.chromium, f.options), error => error === failure);
  assert.equal(f.calls.launches.length, 1);
  assert.equal(f.calls.closed, 1);
});

test("page creation failure still closes the returned browser", async () => {
  const failure = new Error("page creation failed"), f = fixture({ pageFailure: failure });
  await assert.rejects(verifySandboxedBrowser(f.chromium, f.options), error => error === failure);
  assert.equal(f.calls.closed, 1);
});

test("cleanup failure cannot turn into a successful probe", async () => {
  const failure = new Error("close failed"), f = fixture({ closeFailure: failure });
  await assert.rejects(verifySandboxedBrowser(f.chromium, f.options), error => error === failure);
  assert.equal(f.calls.closed, 1);
});

test("CI uses the tested probe with an overall bound and local tests include these regressions", () => {
  const workflow = fs.readFileSync(new URL("../.github/workflows/ci.yml", import.meta.url), "utf8");
  assert.match(workflow, /name: Verify sandboxed browser for requirement validation\r?\n\s+timeout-minutes: 3\r?\n\s+run: node scripts\/ci-browser-probe\.mjs/);
  assert.match(workflow, /AGENTHUB_VALIDATION_BROWSER_CHANNEL: chrome/);
  const manifest = JSON.parse(fs.readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.match(manifest.scripts["test:local"], /scripts\/ci-browser-probe\.test\.mjs/);
});
