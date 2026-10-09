import assert from "node:assert/strict";
import { createRequire } from "node:module";
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
