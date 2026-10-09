"use client"

import { useEffect, useRef, useState } from "react"
import { applyCodeEdit, listCodeEdits, loadCodeEditSource, prepareCodeEdit, type CodeEditOperation, type CodeEditSource } from "@/lib/api"
import { LocalCodeEditor } from "./local-code-editor"
import { useCodeQuote } from "./code-quote-context"
import { codeEditStateLabel, useCodeEditContext } from "./user-code-edit-context"

type Draft = { source: CodeEditSource | null; content: string; patch: string; mode: "file" | "patch"; operationId: string }

export function UserCodeEditor({ artifactId, paths }: { artifactId: string; paths: string[] }) {
  const context = useCodeEditContext()
  const [open, setOpen] = useState(false)
  if (!context?.sessionId) return null
  return <div className="mt-3 min-w-0 border-t border-[var(--border)] pt-3">
    <button type="button" className="rounded border border-[var(--border)] px-3 py-2 text-xs font-medium" onClick={() => setOpen(current => !current)}>{open ? "收起源码编辑" : "编辑完整源码 / 应用补丁"}</button>
    {open ? <EditorSession key={`${context.backendUrl}:${context.sessionId}:${artifactId}`} backendUrl={context.backendUrl} sessionId={context.sessionId}
      artifactId={artifactId} paths={paths} onChanged={context.refresh} /> : null}
  </div>
}

function EditorSession({ backendUrl, sessionId, artifactId, paths, onChanged }: {
  backendUrl: string; sessionId: string; artifactId: string; paths: string[]; onChanged: () => void
}) {
  const quoteCode = useCodeQuote()
  const storageKey = `agenthub:code-edit:${backendUrl}:${sessionId}:${artifactId}`
  const [draft, setDraft] = useState<Draft>(() => {
    try {
      const value = JSON.parse(sessionStorage.getItem(storageKey) ?? "null")
      const source = value?.source
      const validSource = source === null || (source && typeof source.path === "string" && typeof source.binding === "string"
        && (source.content === null || typeof source.content === "string") && (source.sha256 === null || typeof source.sha256 === "string"))
      if (value && validSource && typeof value.content === "string" && typeof value.patch === "string" && typeof value.operationId === "string" && ["file", "patch"].includes(value.mode)) return value
    } catch { /* Browser storage is optional. */ }
    return { source: null, content: "", patch: "", mode: "file", operationId: crypto.randomUUID() }
  })
  const [path, setPath] = useState(draft.source?.path ?? paths[0] ?? "")
  const [operation, setOperation] = useState<CodeEditOperation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const active = useRef(true)
  const pending = useRef(false)
  const initialOperationId = useRef(draft.operationId)
  const currentOperationId = useRef(draft.operationId)
  useEffect(() => { currentOperationId.current = draft.operationId }, [draft.operationId])
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  useEffect(() => {
    try { sessionStorage.setItem(storageKey, JSON.stringify(draft)) } catch { /* Keep the live draft if quota is exhausted. */ }
  }, [storageKey, draft])
  useEffect(() => {
    let current = true
    listCodeEdits(backendUrl, sessionId).then(operations => {
      if (current && currentOperationId.current === initialOperationId.current)
        setOperation(operations.find(item => item.id === initialOperationId.current) ?? null)
    }).catch(() => { /* A repeated prepare/apply with the saved ID remains safe. */ })
    return () => { current = false }
  }, [backendUrl, sessionId])
  const edit = (update: Partial<Draft>) => {
    setDraft(current => ({ ...current, ...update, operationId: crypto.randomUUID() }))
    setOperation(null)
  }
  const editContent = (content: string) => {
    const original = draft.source?.content ?? ""
    // Textareas normalize CRLF in their DOM value. Preserve a uniform source
    // convention so a one-line edit does not silently rewrite the whole file.
    const crlf = original.includes("\r\n") && !original.replaceAll("\r\n", "").includes("\n")
    edit({ content: crlf ? content.replace(/\r?\n/g, "\r\n") : content })
  }
  const execute = async (action: () => Promise<void>) => {
    if (pending.current) return
    pending.current = true; setBusy(true); setError(null)
    try { await action() }
    catch (error) { if (active.current) setError(error instanceof Error ? error.message : "请求失败，草稿已保留") }
    finally { pending.current = false; if (active.current) setBusy(false) }
  }
  const load = () => execute(async () => {
    const source = await loadCodeEditSource(backendUrl, sessionId, artifactId, path)
    if (active.current) edit({ source, content: source.content ?? "" })
  })
  return <section aria-label="用户代码编辑" className="mt-3 min-w-0 space-y-3 text-xs">
    <p className="text-[var(--muted-foreground)]">读取当前完整文件后编辑，先查看拟应用差异，再明确应用。原 Agent Diff 是历史记录；手工修改不会自动通过测试或评审。</p>
    <div className="flex flex-wrap gap-2">
      <button disabled={busy} aria-pressed={draft.mode === "file"} type="button" className="rounded border px-2 py-1" onClick={() => edit({ mode: "file" })}>完整源码</button>
      <button disabled={busy} aria-pressed={draft.mode === "patch"} type="button" className="rounded border px-2 py-1" onClick={() => edit({ mode: "patch" })}>输入补丁</button>
    </div>
    {draft.mode === "file" ? <>
      <label className="block">目标文件<select aria-label="编辑文件" disabled={busy} value={path} onChange={event => setPath(event.target.value)} className="mt-1 w-full min-w-0 rounded border border-[var(--border)] bg-[var(--surface)] p-2">
        {paths.map(path => <option key={path} value={path}>{path}</option>)}
      </select></label>
      <button disabled={busy || !path} type="button" onClick={load} className="rounded border border-[var(--border)] px-2 py-1">{draft.source ? "重新读取文件并替换草稿" : "读取完整源码"}</button>
      {draft.source ? <><p className="break-all text-[var(--muted-foreground)]">编辑中：{draft.source.path} · 版本 {draft.source.sha256?.slice(0, 12) ?? "文件尚不存在"}</p>
        <LocalCodeEditor key={draft.source.path} value={draft.content} onChange={editContent} disabled={busy} path={draft.source.path}
          onQuote={quoteCode ? text => quoteCode({ artifactId, path: draft.source!.path, text }) : undefined} />
      </> : null}
    </> : <label className="block">统一 Diff 补丁<textarea aria-label="待应用补丁" spellCheck={false} disabled={busy} value={draft.patch}
      onChange={event => edit({ patch: event.target.value })} className="mt-1 h-64 w-full min-w-0 rounded border border-[var(--border)] bg-[var(--surface)] p-2 font-mono" /></label>}
    <button disabled={busy || (draft.mode === "file" ? !draft.source || draft.source.path !== path : !draft.patch)} type="button" className="rounded bg-[var(--primary)] px-3 py-2 text-[var(--primary-foreground)]" onClick={() => execute(async () => {
      const result = await prepareCodeEdit(backendUrl, sessionId, { operationId: draft.operationId, sourceArtifactId: artifactId,
        ...(draft.mode === "patch" ? { patch: draft.patch } : { path: draft.source!.path, content: draft.content, expectedSha256: draft.source!.sha256, expectedBinding: draft.source!.binding }) })
      if (active.current) { setOperation(result); onChanged() }
    })}>检查并生成差异</button>
    {error ? <p role="alert" className="break-words text-red-600">{error}。草稿保留，可重新读取或重试。</p> : null}
    {operation ? <div className="min-w-0 space-y-2 rounded border border-[var(--border)] p-2">
      <p className="font-medium">用户修改 · {codeEditStateLabel(operation.state)} · {operation.id.slice(0, 8)}</p>
      <pre aria-label="拟应用差异" className="max-h-80 overflow-auto rounded bg-[var(--surface-muted)] p-2">{operation.patch}</pre>
      {operation.files.map(file => <p className="break-all font-mono text-[10px]" key={file.path}>{file.path}: {file.beforeSha256?.slice(0, 12) ?? "不存在"} → {file.afterSha256?.slice(0, 12) ?? "删除"}</p>)}
      {operation.state === "prepared" ? <button disabled={busy} type="button" className="rounded bg-[var(--primary)] px-3 py-2 text-[var(--primary-foreground)]" onClick={() => execute(async () => {
        const applied = await applyCodeEdit(backendUrl, sessionId, operation.id)
        if (active.current) { setOperation(applied); onChanged() }
      })}>应用以上差异</button> : <p role="status">{operation.state === "applied" ? "文件已更新。打开或刷新网页预览查看当前结果；尚未运行本次修改的测试和评审。" : "应用状态已保留。冲突时请重新读取，需核对时请检查当前文件。"}</p>}
    </div> : null}
  </section>
}
