"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { applyCodeEdit, listCodeEdits, resolveCodeEdit, type CodeEditOperation } from "@/lib/api"

type CodeEditContext = { backendUrl: string; sessionId: string | null; revision: number; refresh: () => void }
const Context = createContext<CodeEditContext | null>(null)
export const useCodeEditContext = () => useContext(Context)

export function CodeEditProvider({ backendUrl, sessionId, children }: { backendUrl: string; sessionId: string | null; children: ReactNode }) {
  const [revision, setRevision] = useState(0)
  return <Context.Provider value={{ backendUrl, sessionId, revision, refresh: () => setRevision(value => value + 1) }}>{children}</Context.Provider>
}

export const codeEditStateLabel = (state: string) => ({ prepared: "待应用", applying: "应用中", applied: "已应用", conflict: "版本冲突", failed: "未应用", unresolved: "需核对", resolved: "已保留当前文件" }[state] ?? state)

export function UserCodeEditStatus() {
  const context = useCodeEditContext()
  return context?.sessionId ? <SessionEditStatus key={`${context.backendUrl}:${context.sessionId}`} context={context} /> : null
}

function SessionEditStatus({ context }: { context: CodeEditContext }) {
  const [result, setResult] = useState<{ key: string; operations: CodeEditOperation[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const key = `${context?.backendUrl}:${context?.sessionId}`
  useEffect(() => {
    if (!context?.sessionId) return
    let active = true
    listCodeEdits(context.backendUrl, context.sessionId).then(operations => {
      if (active) { setResult({ key, operations }); setError(null) }
    }).catch(() => { if (active) setError("暂时无法核对用户修改记录，请刷新面板后再确认预览来源。") })
    return () => { active = false }
  }, [context?.backendUrl, context?.sessionId, context?.revision, key])
  if (!context?.sessionId) return null
  const operations = result?.key === key ? result.operations : []
  const unresolved = operations.filter(operation => ["unresolved", "applying"].includes(operation.state))
  const applied = operations.find(operation => ["applied", "resolved"].includes(operation.state))
  return <>
    {error ? <p role="status" className="rounded border border-[var(--border)] p-2 text-xs">{error}</p> : null}
    {applied ? <p className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900" data-testid="user-revision-notice">
      此会话包含用户代码修改 · {applied.id.slice(0, 8)}。网页预览读取当前文件；修改前 Agent 的 Diff 和评审仍为原始记录，不能验证这些手工修改。
    </p> : null}
    {unresolved.map(operation => <div key={operation.id} className="space-y-2 rounded border border-amber-300 p-3 text-xs">
      <p>用户修改 {operation.id.slice(0, 8)} · {codeEditStateLabel(operation.state)}。核对完成前暂停后续执行。</p>
      <pre className="max-h-48 overflow-auto">{operation.patch}</pre>
      {operation.state === "unresolved" ? <button disabled={busy} className="rounded border border-[var(--border)] px-2 py-1" type="button" onClick={async () => {
        setBusy(true)
        try { await resolveCodeEdit(context.backendUrl, context.sessionId!, operation.id, "keep_current"); context.refresh() }
        catch (error) { setError(error instanceof Error ? error.message : "核对失败") }
        finally { setBusy(false) }
      }}>已核对，保留当前文件并恢复执行</button> : null}
    </div>)}
    {operations.length ? <details className="min-w-0 rounded border border-[var(--border)] p-3 text-xs">
      <summary className="cursor-pointer">用户修改记录 · 最近 {operations.length} 项</summary>
      <div className="mt-2 space-y-2">{operations.map(operation => <details key={operation.id} className="min-w-0 rounded border border-[var(--border)] p-2">
        <summary className="cursor-pointer break-all">{operation.id.slice(0, 8)} · {codeEditStateLabel(operation.state)} · {operation.files.length} 个文件</summary>
        <p className="mt-2 break-all text-[var(--muted-foreground)]">来源 Diff {operation.sourceArtifactId.slice(0, 8)} · {operation.targetId}</p>
        <pre className="my-2 max-h-64 overflow-auto">{operation.patch}</pre>
        {operation.state === "prepared" ? <button type="button" disabled={busy} className="rounded border border-[var(--border)] px-2 py-1" onClick={async () => {
          setBusy(true)
          try { await applyCodeEdit(context.backendUrl, context.sessionId!, operation.id); context.refresh() }
          catch (error) { setError(error instanceof Error ? error.message : "应用失败") }
          finally { setBusy(false) }
        }}>应用此记录中的差异</button> : null}
      </details>)}</div>
    </details> : null}
  </>
}
