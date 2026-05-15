"use client"

import { ChevronDown, ChevronUp, FileCode2 } from "lucide-react"
import { useMemo, useState } from "react"
import { DiffEditor } from "@monaco-editor/react"

import { Button } from "./ui/button"
import type { DiffArtifact } from "@/lib/api"
import { cn } from "@/lib/utils"

type DiffCardProps = {
  diff: DiffArtifact
}

type ParsedFileDiff = {
  path: string
  original: string
  modified: string
  patch: string
}

export function DiffCard({ diff }: DiffCardProps) {
  const [expanded, setExpanded] = useState(false)
  const parsedFiles = useMemo(() => parseUnifiedDiff(diff.patchText), [diff.patchText])
  const [selectedPath, setSelectedPath] = useState(diff.changedFiles[0] ?? "")
  const selectedFile =
    parsedFiles.find((file) => file.path === selectedPath) ?? parsedFiles[0] ?? null
  const filesChanged = diff.stats.filesChanged || diff.changedFiles.length

  return (
    <article className="rounded-md border border-[var(--border)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <FileCode2 aria-hidden="true" size={14} />
            Diff artifact
          </p>
          <h4 className="mt-1 text-sm font-semibold">{diff.title}</h4>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {formatFilesChanged(filesChanged)} · {shortRef(diff.baseRef)} to{" "}
            {shortRef(diff.headRef)}
          </p>
        </div>
        <div className="flex shrink-0 gap-2 text-xs font-semibold">
          <span className="rounded-sm bg-emerald-50 px-2 py-1 text-emerald-700">
            +{diff.stats.additions}
          </span>
          <span className="rounded-sm bg-rose-50 px-2 py-1 text-rose-700">
            -{diff.stats.deletions}
          </span>
        </div>
      </div>

      <ul className="mt-3 grid gap-1" aria-label="Changed files">
        {diff.changedFiles.map((file) => (
          <li
            className="truncate rounded-sm border border-[var(--border)] bg-slate-50 px-2 py-1 text-xs"
            key={file}
          >
            {file}
          </li>
        ))}
      </ul>

      <Button
        className="mt-3 h-8 px-3 text-xs"
        onClick={() => setExpanded((current) => !current)}
        type="button"
        variant="secondary"
      >
        {expanded ? <ChevronUp aria-hidden="true" size={14} /> : <ChevronDown aria-hidden="true" size={14} />}
        {expanded ? "Collapse diff" : "Expand diff"}
      </Button>

      {expanded ? (
        <div className="mt-3 grid gap-3">
          {parsedFiles.length > 1 ? (
            <div className="flex flex-wrap gap-2" aria-label="Diff files">
              {parsedFiles.map((file) => (
                <button
                  className={cn(
                    "rounded-sm border px-2 py-1 text-xs",
                    file.path === selectedFile?.path
                      ? "border-blue-600 bg-blue-50 text-blue-700"
                      : "border-[var(--border)] bg-white text-[var(--muted-foreground)]",
                  )}
                  key={file.path}
                  onClick={() => setSelectedPath(file.path)}
                  type="button"
                >
                  {file.path}
                </button>
              ))}
            </div>
          ) : null}

          {selectedFile ? (
            <div className="overflow-hidden rounded-md border border-[var(--border)]">
              <div className="border-b border-[var(--border)] bg-slate-50 px-3 py-2 text-xs font-medium">
                {selectedFile.path}
              </div>
              <DiffEditor
                height="320px"
                language={languageForPath(selectedFile.path)}
                modified={selectedFile.modified}
                original={selectedFile.original}
                options={{
                  minimap: { enabled: false },
                  readOnly: true,
                  renderSideBySide: true,
                  scrollBeyondLastLine: false,
                }}
                theme="vs"
              />
            </div>
          ) : (
            <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-slate-50">
              {diff.patchText}
            </pre>
          )}
        </div>
      ) : null}
    </article>
  )
}

export function parseUnifiedDiff(patchText: string): ParsedFileDiff[] {
  const files: ParsedFileDiff[] = []
  let current: ParsedFileDiff | null = null
  let inHunk = false

  for (const line of patchText.split("\n")) {
    if (line.startsWith("diff --git ")) {
      if (current) {
        files.push(current)
      }
      const match = line.match(/^diff --git a\/(.+) b\/(.+)$/)
      const path = match?.[2] ?? "changed-file"
      current = { path, original: "", modified: "", patch: `${line}\n` }
      inHunk = false
      continue
    }

    if (!current) {
      continue
    }

    current.patch += `${line}\n`
    if (line.startsWith("@@")) {
      inHunk = true
      continue
    }
    if (!inHunk || line.startsWith("\\ No newline")) {
      continue
    }
    if (line.startsWith("+") && !line.startsWith("+++")) {
      current.modified += `${line.slice(1)}\n`
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      current.original += `${line.slice(1)}\n`
    } else if (line.startsWith(" ")) {
      current.original += `${line.slice(1)}\n`
      current.modified += `${line.slice(1)}\n`
    }
  }

  if (current) {
    files.push(current)
  }

  return files
}

function formatFilesChanged(filesChanged: number) {
  return filesChanged === 1 ? "1 file changed" : `${filesChanged} files changed`
}

function shortRef(ref: string) {
  return ref.length > 12 ? ref.slice(0, 12) : ref
}

function languageForPath(path: string) {
  if (path.endsWith(".tsx") || path.endsWith(".ts")) {
    return "typescript"
  }
  if (path.endsWith(".jsx") || path.endsWith(".js")) {
    return "javascript"
  }
  if (path.endsWith(".css")) {
    return "css"
  }
  if (path.endsWith(".json")) {
    return "json"
  }
  return "plaintext"
}
