import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { previewFileId } from "./preview-serving-paths.mjs";

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
