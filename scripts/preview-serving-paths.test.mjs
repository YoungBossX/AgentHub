import assert from "node:assert/strict";
import test from "node:test";
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
