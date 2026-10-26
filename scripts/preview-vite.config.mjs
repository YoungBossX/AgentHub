// Server-owned preview profile. Project code cannot broaden serving permissions.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { previewFileId as fileId, previewRequestPath } from "./preview-serving-paths.mjs";

const platform = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const requireDemo = createRequire(path.join(platform, "apps/demo/package.json"));
const { default: react } = await import(pathToFileURL(requireDemo.resolve("@vitejs/plugin-react")).href);
const requireVite = createRequire(requireDemo.resolve("vite/package.json"));
const picomatch = requireVite("picomatch");
const postcss = requireVite("postcss");
const root = fs.realpathSync(process.cwd());
const dependencyAliases = [path.join(root, "node_modules"), path.join(platform, "node_modules"),
  path.join(platform, "apps/demo/node_modules"), process.env.AGENTHUB_PREVIEW_CACHE_DIR].filter(p => p && fs.existsSync(p));
const dependencies = dependencyAliases.map(p => fs.realpathSync(p));
const roots = [root, ...dependencyAliases, ...dependencies];
const denied = JSON.parse(process.env.AGENTHUB_PREVIEW_DENIED_PATHS ?? "[]");
const denyTargetPath = picomatch(denied.flatMap(pattern => [pattern, `${pattern}/**`]), { dot: true, nocase: true });
const inside = (base, value) => { const relative = path.relative(base, value); return relative === "" || (!relative.startsWith(".." + path.sep) && relative !== ".." && !path.isAbsolute(relative)); };
const protectedPath = value => value.split(/[\\/]/).some(part => {
  part = part.toLowerCase();
  return part === ".git" || part === "secrets" || part.startsWith(".env") || part === ".npmrc"
    || part === ".yarnrc.yml" || /\.(?:crt|pem|key|p12|pfx|cer|der)$/.test(part);
});

function permitted(filename) {
  const lexical = path.resolve(filename);
  if (protectedPath(lexical) || !roots.some(base => inside(base, lexical))) return false;
  let canonical;
  let exists = true;
  try { canonical = fs.realpathSync(lexical); } catch {
    // Vite resolves optimized modules before their cache files are materialized.
    exists = false;
    let ancestor = path.dirname(lexical);
    while (!fs.existsSync(ancestor) && path.dirname(ancestor) !== ancestor) ancestor = path.dirname(ancestor);
    try { canonical = path.join(fs.realpathSync(ancestor), path.relative(ancestor, lexical)); } catch { return false; }
  }
  if (protectedPath(canonical) || !roots.some(base => inside(base, canonical))) return false;
  const dependency = [...dependencyAliases, ...dependencies].some(base => inside(base, lexical)) && dependencies.some(base => inside(base, canonical));
  if (!dependency && (!inside(root, canonical) || denyTargetPath(path.relative(root, lexical).replaceAll("\\", "/"))
    || denyTargetPath(path.relative(root, canonical).replaceAll("\\", "/")))) return false;
  // Dependency stores may use hardlinks; ordinary project source must not alias
  // unrelated files through hardlinks or node_modules-looking directories.
  const info = exists ? fs.statSync(canonical) : null;
  if (!dependency && (lexical.split(path.sep).includes("node_modules") || (info?.isFile() && info.nlink > 1))) return false;
  return true;
}

function checkCssImports(code, filename) {
  const pending = [[code, filename]], visited = new Set();
  let bytes = 0;
  while (pending.length) {
    const [text, importer] = pending.pop();
    if (visited.has(importer)) continue;
    visited.add(importer); bytes += Buffer.byteLength(text);
    if (visited.size > 512 || bytes > 16 * 1024 * 1024) throw new Error("Preview CSS exceeds its scope-check budget.");
    postcss.parse(text, { from: importer }).walkAtRules("import", rule => {
      // Reject unsupported escapes/data imports rather than interpreting them
      // differently from Vite's internal PostCSS resolver.
      const match = /^(?:url\(\s*(?:"([^"]+)"|'([^']+)'|([^\s)]+))\s*\)|"([^"]+)"|'([^']+)')/.exec(rule.params);
      const specifier = match && match.slice(1).find(Boolean);
      if (!specifier || /[\\%]/.test(specifier) || /^(?:https?:|data:|\/\/)/i.test(specifier)) throw new Error("Preview CSS import is not allowed.");
      let candidate;
      if (specifier.startsWith("/@fs/")) candidate = fileId(specifier);
      else if (path.isAbsolute(specifier)) candidate = fs.existsSync(specifier) ? specifier : path.resolve(root, "." + specifier);
      else if (specifier.startsWith(".")) candidate = path.resolve(path.dirname(importer), specifier);
      else candidate = createRequire(importer).resolve(specifier);
      if (!permitted(candidate)) throw new Error("Preview CSS import is outside its serving scope.");
      pending.push([fs.readFileSync(candidate, "utf8"), candidate]);
    });
  }
}

const guard = {
  name: "agenthub-preview-serving-boundary",
  enforce: "pre",
  async resolveId(source, importer, options) {
    if (source.startsWith("\0") || source === "/@react-refresh") return null;
    const resolved = await this.resolve(source, importer, { ...options, skipSelf: true });
    if (resolved && path.isAbsolute(fileId(resolved.id)) && !permitted(fileId(resolved.id))) throw new Error("Preview import is outside its serving scope.");
    return resolved;
  },
  load(id) {
    if (id.startsWith("\0") || id === "/@react-refresh") return null;
    const filename = fileId(id);
    if (path.isAbsolute(filename) && !permitted(filename)) throw new Error("Preview module is outside its serving scope.");
    return null;
  },
  transform(code, id) {
    if (fileId(id).endsWith(".css")) checkCssImports(code, fileId(id));
    return null;
  },
  configureServer(server) {
    server.middlewares.use((request, response, next) => {
      let pathname;
      try { pathname = previewRequestPath(request.url ?? "/"); }
      catch { response.statusCode = 400; response.end("Invalid preview path."); return; }
      // Connect's reserved route is case-insensitive and accepts / or . suffixes.
      // A view-only preview never grants access to the host's editor process.
      if (/^\/__open-in-editor(?:[/.]|$)/i.test(pathname)) {
        response.statusCode = 403; response.end("Preview editor access is not allowed."); return;
      }
      if (pathname.includes("\0") || protectedPath(pathname)) { response.statusCode = 403; response.end("Preview path is not allowed."); return; }
      if (pathname.startsWith("/@vite/") || pathname === "/@react-refresh" || pathname.startsWith("/@id/")) { next(); return; }
      const filename = pathname.startsWith("/@fs/") ? fileId(pathname) : path.resolve(root, "." + pathname);
      const publicFile = path.resolve(root, "public", "." + pathname);
      if (!permitted(filename) && !(!pathname.startsWith("/@fs/") && inside(root, publicFile) && fs.existsSync(publicFile) && permitted(publicFile))) {
        response.statusCode = 403; response.end("Preview path is outside its serving scope."); return;
      }
      next();
    });
  },
};

export default {
  root, plugins: [guard, react()], envDir: false,
  // Keep preview caches out of protected installed dependencies.
  cacheDir: process.env.AGENTHUB_PREVIEW_CACHE_DIR,
  server: { host: "127.0.0.1", strictPort: true, fs: { strict: true, allow: roots,
    deny: ["**/.git", "**/.git/**", "**/.env*", "**/secrets", "**/secrets/**", "**/.npmrc", "**/.yarnrc.yml", "**/*.{crt,pem,key,p12,pfx,cer,der}"] } },
};
