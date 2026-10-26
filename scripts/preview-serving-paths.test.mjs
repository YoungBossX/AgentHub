import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { previewFileId } from "./preview-serving-paths.mjs";

async function withPreviewBoundary(label, operation) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "agenthub-preview-route-"));
  fs.mkdirSync(path.join(root, "src"));
  fs.writeFileSync(path.join(root, "src", "main.tsx"), "export const value = 1;");
  const previous = process.cwd();
  try {
    process.chdir(root);
    const { default: config } = await import(new URL(`./preview-vite.config.mjs?route-${label}`, import.meta.url));
    const guard = config.plugins.find(plugin => plugin.name === "agenthub-preview-serving-boundary");
    let middleware;
    guard.configureServer({ middlewares: { use(value) { middleware = value; } } });
    const request = url => {
      const result = { status: 200, next: false, body: null };
      const response = { statusCode: 200, end(body) { result.status = this.statusCode; result.body = body; } };
      middleware({ url }, response, () => { result.next = true; });
      return result;
    };
    await operation(request);
  } finally {
    process.chdir(previous);
    fs.unlinkSync(path.join(root, "src", "main.tsx"));
    fs.rmdirSync(path.join(root, "src")); fs.rmdirSync(root);
  }
}

for (const [index, url] of [
  "/__open-in-editor", "/__OPEN-IN-EDITOR", "/__open-in-editor/child", "/__open-in-editor.json",
  "/%5f%5fopen-in-editor", "http://127.0.0.1:5173/__open-in-editor",
  "http://127.0.0.1:5173/__OPEN-IN-EDITOR.child?file=synthetic",
  "http:/__open-in-editor", "http:///__open-in-editor",
  "http:\\__OPEN-IN-EDITOR.child", "http:/%5f%5fopen-in-editor",
  "http://localhost/__open-in-editor/../safe",
  "http://localhost/__open-in-editor/%2e%2e/safe",
  "http:///__open-in-editor/child", "http:///__open-in-editor.child",
].entries()) {
  test(`preview rejects host-editor route alias ${index} before downstream middleware`, async () => {
    await withPreviewBoundary(`editor-${index}`, request => {
      const result = request(url);
      assert.equal(result.status, 403);
      assert.equal(result.next, false);
    });
  });
}

test("preview route boundary preserves assets and Vite controls and existing rejection semantics", async () => {
  await withPreviewBoundary("controls", request => {
    for (const url of ["/", "/src/main.tsx", "/@vite/client", "/@react-refresh", "/src/main.tsx?file=/__open-in-editor",
      "/__open-in-editorial", "//src/main.tsx", "http://127.0.0.1:5173/src/main.tsx", "http:/src/main.tsx"]) {
      assert.equal(request(url).next, true, url);
    }
    assert.equal(request("/.env").status, 403);
    assert.equal(request("/%").status, 400);
  });
});

test("Vite POSIX fs URLs retain the absolute root for scope checks", () => {
  assert.equal(previewFileId("/@fs/home/runner/node_modules/react/index.js?v=1"), "/home/runner/node_modules/react/index.js");
  assert.equal(previewFileId("/@fs/tmp/cache/deps/react.js"), "/tmp/cache/deps/react.js");
  assert.equal(previewFileId("/@fs/etc/private-file?raw"), "/etc/private-file");
});

test("Windows volumes, explicit POSIX roots and virtual IDs retain their identity", () => {
  assert.equal(previewFileId("/@fs/C:/project/node_modules/react/index.js?v=1"), "C:/project/node_modules/react/index.js");
  assert.equal(previewFileId("/@fs//home/runner/file.css?raw#fragment"), "/home/runner/file.css");
  assert.equal(previewFileId("\0virtual:react"), "\0virtual:react");
  assert.equal(previewFileId("/src/main.tsx?import"), "/src/main.tsx");
});

test("preview accepts canonical installed dependency paths and keeps other paths denied", async () => {
  const batch = fs.mkdtempSync(path.join(os.tmpdir(), "agenthub-preview-dependency-"));
  const project = path.join(batch, "project"), installed = path.join(batch, "installed");
  fs.mkdirSync(project); fs.mkdirSync(installed);
  const dependency = path.join(installed, "entry.js"), protectedFile = path.join(installed, ".env");
  fs.writeFileSync(dependency, "export default 1;"); fs.writeFileSync(protectedFile, "synthetic");
  const alias = path.join(project, "node_modules"), outside = path.join(batch, "outside.js");
  fs.writeFileSync(outside, "export default 2;");
  fs.symlinkSync(installed, alias, process.platform === "win32" ? "junction" : "dir");
  const previousCwd = process.cwd();
  try {
    process.chdir(project);
    const { default: config } = await import(new URL("./preview-vite.config.mjs?dependency-regression", import.meta.url));
    const guard = config.plugins.find(plugin => plugin.name === "agenthub-preview-serving-boundary");
    assert.equal(guard.load(path.join(alias, "entry.js")), null);
    assert.equal(guard.load(fs.realpathSync(dependency)), null);
    assert.throws(() => guard.load(outside), /outside its serving scope/);
    assert.throws(() => guard.load(protectedFile), /outside its serving scope/);
  } finally {
    process.chdir(previousCwd);
    fs.unlinkSync(alias);
    for (const filename of [dependency, protectedFile, outside]) fs.unlinkSync(filename);
    fs.rmdirSync(project); fs.rmdirSync(installed); fs.rmdirSync(batch);
  }
});
