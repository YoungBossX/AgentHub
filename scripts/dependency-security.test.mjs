import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import test from "node:test";

// Resolve through the real ESLint importer chain. A stale or unapplied pnpm
// patch must fail here even if an unrelated copy of braces is patched.
const web = createRequire(new URL("../apps/web/package.json", import.meta.url));
const config = createRequire(web.resolve("eslint-config-next"));
const plugin = createRequire(config.resolve("@next/eslint-plugin-next"));
const glob = plugin("fast-glob");
const globRequire = createRequire(plugin.resolve("fast-glob"));
const micromatch = globRequire("micromatch");
const braces = createRequire(globRequire.resolve("micromatch"))("braces");
const depthError = { name: "RangeError", message: "braces AST depth exceeds local limit (128)" };
const nested = (depth, open = "{", close = "}") => open.repeat(depth) + "a" + close.repeat(depth);

function installedPackage(importer, name) {
  // Some packages deliberately do not export package.json. Start at the real
  // consumer's entry point, then locate that package's own manifest.
  let directory = path.dirname(importer.resolve(name));
  while (path.dirname(directory) !== directory) {
    const filename = path.join(directory, "package.json");
    if (fs.existsSync(filename)) {
      const manifest = JSON.parse(fs.readFileSync(filename, "utf8"));
      if (manifest.name === name) return { ...manifest, filename };
    }
    directory = path.dirname(directory);
  }
  throw new Error(`Cannot locate the actual ${name} package manifest`);
}

function securityFloor(version, major, minor, patch) {
  assert.match(version, /^\d+\.\d+\.\d+$/, "Only stable versions establish the security floor");
  const actual = version.split(".").map(Number);
  assert.equal(actual[0], major, "Preserve the reviewed compatible major branch");
  assert(actual[1] > minor || actual[1] === minor && actual[2] >= patch,
    `Installed ${version} is below ${major}.${minor}.${patch}`);
}

test("actual Next and ESLint config resolve the matching patched 16.x release", () => {
  const next = installedPackage(web, "next"), eslintConfig = installedPackage(web, "eslint-config-next");
  securityFloor(next.version, 16, 4, 1);
  assert.equal(eslintConfig.version, next.version);
});

test("Demo and both actual test importers retain distinct patched Vite branches", () => {
  const demo = createRequire(new URL("../apps/demo/package.json", import.meta.url));
  securityFloor(installedPackage(demo, "vite").version, 7, 3, 7);
  const vitest = installedPackage(web, "vitest"), vitestRequire = createRequire(vitest.filename);
  const mocker = installedPackage(vitestRequire, "@vitest/mocker");
  securityFloor(vitest.version, 4, 1, 12);
  securityFloor(mocker.version, 4, 1, 12);
  securityFloor(installedPackage(vitestRequire, "vite").version, 8, 1, 6);
  securityFloor(installedPackage(createRequire(mocker.filename), "vite").version, 8, 1, 6);
});

test("Monaco's actual patched sanitizer importer binds patched DOMPurify", () => {
  const monaco = installedPackage(web, "monaco-editor");
  assert.equal(monaco.version, "0.56.0");
  const sanitizer = path.join(path.dirname(monaco.filename), "esm/vs/base/browser/domSanitize.js");
  const source = fs.readFileSync(sanitizer, "utf8");
  assert.match(source, /import purify from ['"]dompurify['"]/);
  assert.doesNotMatch(source, /from ['"]\.\/dompurify\/dompurify\.js['"]/);
  const purifier = createRequire(sanitizer)("dompurify");
  securityFloor(purifier.version, 3, 4, 17);
});

test("the actual ESLint hooks consumer resolves patched Zod without a new app dependency", () => {
  const hooks = createRequire(config.resolve("eslint-plugin-react-hooks/package.json"));
  securityFloor(installedPackage(hooks, "zod").version, 4, 6, 6);
  const manifest = web("./package.json");
  assert.equal(manifest.dependencies.zod, undefined);
});

test("braces preserves ordinary file globs, ranges, escaping and incomplete input", () => {
  const cases = [
    ["{a,b}", "(a|b)", ["a", "b"], "{a,b}"],
    ["src/**/*.{ts,tsx}", "src/**/*.(ts|tsx)", ["src/**/*.ts", "src/**/*.tsx"], "src/**/*.{ts,tsx}"],
    ["a/{b,{c,d}}/e", "a/(b|(c|d))/e", ["a/b/e", "a/c/e", "a/d/e"], "a/{b,{c,d}}/e"],
    ["{1..5}", "([1-5])", ["1", "2", "3", "4", "5"], "{1..5}"],
    ["file\\{name\\}", "file{name}", ["file{name}"], "file{name}"],
    ["{foo,bar}/(x)", "(foo|bar)/(x)", ["foo/(x)", "bar/(x)"], "{foo,bar}/(x)"],
    ["{broken", "{broken", ["{broken"], "{broken"],
    ['"{quoted}"', "{quoted}", ["{quoted}"], "{quoted}"],
    ["a/{01..03}", "a/(0[1-3])", ["a/01", "a/02", "a/03"], "a/{01..03}"],
    ["a,b", "a,b", ["a,b"], "a,b"],
    ["[{}]", "[{}]", ["[{}]"], "[{}]"],
  ];
  for (const [input, compiled, expanded, stringified] of cases) {
    assert.equal(braces.compile(input), compiled);
    assert.deepEqual(braces.expand(input), expanded);
    assert.equal(braces.stringify(input), stringified);
  }
});

test("braces rejects deep patterns below the existing character limit without stack exhaustion", () => {
  for (const input of [nested(4500), nested(4500, "(", ")"), nested(1500, "({", "})"), "{".repeat(4500)]) {
    assert(input.length < 10000);
    for (const method of ["parse", "compile", "stringify", "expand"]) {
      assert.throws(() => braces[method](input), depthError);
    }
    assert.throws(() => braces(input, { expand: true, rangeLimit: false, maxLength: 100000 }), depthError);
  }
});

test("braces bounds simultaneous nesting rather than total groups or literal punctuation", () => {
  for (const input of [nested(127), nested(127, "(", ")"), "{a}".repeat(400)]) {
    assert.equal(braces.stringify(input), input);
    assert.equal(braces.compile(input), input);
    assert.deepEqual(braces.expand(input), [input]);
  }
  for (const input of [nested(128), nested(128, "(", ")"), nested(64, "({", "})")]) {
    assert.throws(() => braces.parse(input), depthError);
  }
  for (const input of ['"' + nested(500) + '"', "[" + nested(500) + "]", "\\{".repeat(500) + "\\}".repeat(500)]) {
    assert.doesNotThrow(() => braces.compile(input));
    assert.doesNotThrow(() => braces.expand(input));
  }
});

test("caller-supplied ASTs cannot bypass the recursion guard", () => {
  for (const method of ["compile", "stringify", "expand"]) {
    const ast = { type: "root", nodes: [] };
    let node = ast;
    for (let index = 0; index < 2000; index++) {
      const child = { type: "root", nodes: [] };
      node.nodes.push(child);
      node = child;
    }
    node.nodes.push({ type: "text", value: "a" });
    assert.throws(() => braces[method](ast), depthError);
    const cycle = { type: "root", nodes: [] };
    cycle.nodes.push(cycle);
    assert.throws(() => braces[method](cycle), depthError);
  }
});

test("the real micromatch and fast-glob importers retain normal matching", () => {
  assert.deepEqual(micromatch(["src/a.ts", "src/b.tsx", "src/c.css"], "src/*.{ts,tsx}"), ["src/a.ts", "src/b.tsx"]);
  const tasks = glob.generateTasks(["src/**/*.{ts,tsx}", "!src/**/*.test.ts"]);
  assert(tasks.length > 0);
  assert.throws(() => micromatch.braces(nested(4500)), depthError);
  assert.throws(() => glob.generateTasks(nested(4500)), depthError);
});
