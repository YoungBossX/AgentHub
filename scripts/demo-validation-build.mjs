// Server-owned configuration: never discover configuration in the copied app.
import { createRequire } from "node:module"
import { pathToFileURL } from "node:url"

const require = createRequire(new URL("../apps/demo/package.json", import.meta.url))
const { build } = await import(pathToFileURL(require.resolve("vite")).href)
const { default: react } = await import(pathToFileURL(require.resolve("@vitejs/plugin-react")).href)
await build({
  root: process.cwd(), configFile: false, envFile: false,
  plugins: [react()], css: { postcss: {} },
  build: { outDir: "dist", emptyOutDir: true },
})
