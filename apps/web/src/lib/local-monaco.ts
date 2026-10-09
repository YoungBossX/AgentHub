import { loader } from "@monaco-editor/react"
import * as monaco from "monaco-editor/editor/editor.api"
import "monaco-editor/languages/definitions/typescript/register"
import "monaco-editor/languages/definitions/javascript/register"
import "monaco-editor/languages/definitions/css/register"
import "monaco-editor/languages/features/json/register"

// Imported only after the user opens the comparison. Keep the editor and its
// worker on the audited local dependency graph instead of the loader's CDN.
self.MonacoEnvironment = {
  getWorker(_moduleId, label) {
    if (label === "json") {
      return new Worker(new URL("monaco-editor/languages/features/json/json.worker.js", import.meta.url), {
        type: "module",
      })
    }
    return new Worker(new URL("monaco-editor/editor/editor.worker.js", import.meta.url), {
      type: "module",
    })
  },
}

loader.config({ monaco })
