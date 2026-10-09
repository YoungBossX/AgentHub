"use client"

import { ChevronDown, ChevronUp, FileCode2 } from "lucide-react"
import { useMemo, useState } from "react"
import { LocalDiffEditor } from "./local-diff-editor"
import { UserCodeEditor } from "./user-code-editor"

import { Button } from "./ui/button"
import type { DiffArtifact } from "@/lib/api"
import { cn } from "@/lib/utils"
import { useTheme } from "./theme-toggle"

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
  const theme = useTheme()
  const [expanded, setExpanded] = useState(false)
  const [sideBySide, setSideBySide] = useState(false)
  const parsedFiles = useMemo(() => parseUnifiedDiff(diff.patchText), [diff.patchText])
  const [selectedPath, setSelectedPath] = useState(diff.changedFiles[0] ?? "")
  const selectedFile =
    parsedFiles.find((file) => file.path === selectedPath) ?? parsedFiles[0] ?? null
  const filesChanged = diff.stats.filesChanged || diff.changedFiles.length

  return (
    <article className="min-w-0 rounded-md border border-[var(--border)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1 text-xs font-medium uppercase tracking-normal text-[var(--muted-foreground)]">
            <FileCode2 aria-hidden="true" size={14} />
            Diff 产物
          </p>
          <h4 className="mt-1 text-sm font-semibold">
            {diff.title === "Git diff" ? "Git Diff" : diff.title}
          </h4>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {formatFilesChanged(filesChanged)} · {shortRef(diff.baseRef)} 到{" "}
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

      <ul className="mt-3 grid gap-1" aria-label="变更文件">
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
        {expanded ? "收起 Diff" : "展开 Diff"}
      </Button>

      {expanded ? (
        <div className="mt-3 grid gap-3">
          {parsedFiles.length > 1 ? (
            <div className="flex flex-wrap gap-2" aria-label="Diff 文件">
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
                <div className="mt-2 flex gap-2">
                  <button aria-pressed={!sideBySide} className="rounded border border-slate-200 bg-white px-2 py-1" onClick={() => setSideBySide(false)}>补丁</button>
                  <button aria-pressed={sideBySide} className="rounded border border-slate-200 bg-white px-2 py-1" onClick={() => setSideBySide(true)}>并排对比</button>
                </div>
              </div>
              {sideBySide ? <>
              <p className="px-3 py-2 text-[10px] text-slate-400">并排内容为 Diff 片段，不是完整源文件。</p>
              <LocalDiffEditor
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
                theme={theme === "dark" ? "vs-dark" : "vs"}
                loading={<PatchView patch={selectedFile.patch} />}
              />
              </> : <PatchView patch={selectedFile.patch} />}
            </div>
          ) : (
            <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-slate-50">
              {diff.patchText}
            </pre>
          )}
        </div>
      ) : null}
      <UserCodeEditor artifactId={diff.artifactId} paths={diff.changedFiles} />
    </article>
  )
}

function PatchView({ patch }: { patch: string }) {
  return <pre aria-label="代码补丁" className="max-h-96 overflow-auto bg-white py-2 text-[11px] leading-5">
    {patch.split("\n").map((line, index) => <div key={index} className={cn("min-w-max px-3", line.startsWith("+") && !line.startsWith("+++") ? "bg-emerald-50 text-emerald-800" : line.startsWith("-") && !line.startsWith("---") ? "bg-red-50 text-red-800" : line.startsWith("@@") ? "bg-blue-50 text-blue-600" : "text-slate-500")}><span className="mr-3 inline-block w-5 select-none text-right text-slate-300" aria-hidden="true">{index + 1}</span>{line || " "}</div>)}
  </pre>
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
  return filesChanged === 1 ? "1 个文件变更" : `${filesChanged} 个文件变更`
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
