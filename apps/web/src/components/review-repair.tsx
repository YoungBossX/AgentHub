"use client"

import { createContext, useContext, useEffect, useState } from "react"
import { reviewRepairRequest, type RepairDraft, type RepairState } from "@/lib/review-repair-api"

export const ReviewRepairContext = createContext<{
  backendUrl: string; sessionId: string | null; revision: number
  onDraft: (sessionId: string, draft: RepairDraft) => void
  onOpenArtifact: (artifactId: string) => void
} | null>(null)

const outcomeLabel = (value?: string) => ({ checks_recovered: "匹配检查已恢复通过", user_confirmed: "用户已确认当前版本", unverified: "仍待核验" }[value ?? ""] ?? "仍待核验")
const stateLabel = (value: string) => ({ waiting: "等待规划或执行", completed: "执行完成", failed: "执行失败", interrupted: "已中断", running: "执行中", streaming: "执行中", collecting_diff: "收集差异与复验中", queued: "排队中" }[value] ?? value)

export function ReviewRepair({ artifactId }: { artifactId: string }) {
  const context = useContext(ReviewRepairContext)
  return context?.sessionId ? <RepairControl key={`${context.sessionId}:${artifactId}`} context={context} artifactId={artifactId} /> : null
}

function RepairControl({ context, artifactId }: { context: NonNullable<React.ContextType<typeof ReviewRepairContext>>; artifactId: string }) {
  const [data, setData] = useState<RepairState | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let active = true
    reviewRepairRequest<RepairState>(context.backendUrl, context.sessionId!, artifactId).then(value => {
      if (active) { setData(value); setError(null); setSelected(old => old.filter(id => value.issues.some(issue => issue.id === id))) }
    }).catch(error => { if (active) setError(error instanceof Error ? error.message : "读取失败") })
    return () => { active = false }
  }, [context.backendUrl, context.sessionId, context.revision, artifactId, refresh])
  return <section className="mt-4 min-w-0 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-3 text-xs" aria-label="评审修复">
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold">修复与复验</h4><button type="button" disabled={busy} onClick={() => setRefresh(v => v + 1)} className="rounded border border-[var(--border)] px-2 py-1">刷新修复状态</button></div>
    {error ? <p role="alert" className="break-words text-[var(--muted-foreground)]">{error}</p> : null}
    {!data && !error ? <p>正在核对问题与源码版本…</p> : null}
    {data ? <>
      <p className="text-[var(--muted-foreground)]">选择问题后生成可编辑草稿，由你发送。模型建议须人工核验；固定检查只报告匹配检查的恢复情况。</p>
      {data.reason ? <p className="break-words">{data.reason}</p> : null}
      {data.sourceFingerprint ? <p className="font-mono text-[var(--muted-foreground)]">评审版本 {data.sourceFingerprint.slice(0, 12)}</p> : null}
      {data.issues.map(issue => <label key={issue.id} className="flex min-w-0 items-start gap-2 rounded border border-[var(--border)] bg-[var(--surface)] p-2">
        <input type="checkbox" checked={selected.includes(issue.id)} disabled={busy || !data.canPrepare || (!selected.includes(issue.id) && selected.length >= 8)}
          onChange={event => setSelected(old => event.target.checked ? [...old, issue.id] : old.filter(id => id !== issue.id))} />
        <span className="min-w-0 break-words">{issue.message}{issue.file ? <span className="block break-all text-[var(--muted-foreground)]">{issue.file}{issue.line ? `:${issue.line}` : ""}</span> : null}<span className="block text-[var(--muted-foreground)]">{issue.autoVerifiable ? "可匹配固定检查复验" : "需人工核验"}</span></span>
      </label>)}
      {!data.issues.length ? <p>这份报告没有可选择的具体问题。</p> : null}
      <button type="button" disabled={busy || !data.canPrepare || !selected.length} className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-2 disabled:opacity-50" onClick={async () => {
        setBusy(true); setError(null)
        try {
          const draft = await reviewRepairRequest<RepairDraft>(context.backendUrl, context.sessionId!, artifactId, "/prepare", { issueIds: selected })
          context.onDraft(context.sessionId!, draft)
        } catch (error) { setError(error instanceof Error ? error.message : "准备失败") }
        finally { setBusy(false) }
      }}>准备修复草稿（{selected.length}/8）</button>
      {data.history.length ? <details open className="min-w-0"><summary className="cursor-pointer">修复历史 · {data.history.length}</summary><div className="mt-2 space-y-2">
        {data.history.map(entry => <div key={entry.messageId} className="min-w-0 rounded border border-[var(--border)] bg-[var(--surface)] p-2">
          <p>修复请求 {entry.messageId.slice(0, 8)} · {stateLabel(entry.state)}</p>
          <p className="mt-1 text-[var(--muted-foreground)]">{entry.checksCurrent ? "当前源码有对应复验记录" : "尚无可确认的当前版本复验"}</p>
          {entry.runs.map(run => <p key={run.id} className="mt-1 break-all text-[var(--muted-foreground)]">执行 {run.id.slice(0, 8)} · {stateLabel(run.state)}{run.errorCode ? ` · ${run.errorCode}` : ""}</p>)}
          {entry.issues.map(issue => <div className="mt-2 border-t border-[var(--border)] pt-2" key={issue.id}><p className="break-words">{issue.message} · {outcomeLabel(issue.outcome)}</p>
            {entry.canConfirm && issue.outcome === "unverified" ? <button type="button" disabled={busy} className="mt-1 rounded border border-[var(--border)] px-2 py-1" onClick={async () => {
              setBusy(true); setError(null)
              try { setData(await reviewRepairRequest<RepairState>(context.backendUrl, context.sessionId!, artifactId, "/confirm", {
                messageId: entry.messageId, issueId: issue.id, sourceFingerprint: entry.sourceFingerprint, revision: entry.revision,
              })) } catch (error) { setError(error instanceof Error ? error.message : "确认失败") }
              finally { setBusy(false) }
            }}>我已核验此问题（当前源码）</button> : null}</div>)}
          {entry.confirmations.length ? <details className="mt-2"><summary className="cursor-pointer">人工确认记录（旧版本记录保留）</summary>{entry.confirmations.map((item, i) => <p key={i} className="mt-1 break-all text-[var(--muted-foreground)]">版本 {item.sourceFingerprint.slice(0, 12)} · {item.confirmedAt}</p>)}</details> : null}
          <div className="mt-2 flex flex-wrap gap-2">{entry.artifactIds.map(id => <button key={id} type="button" className="rounded border border-[var(--border)] px-2 py-1" onClick={() => context.onOpenArtifact(id)}>查看产物 {id.slice(0, 8)}</button>)}</div>
        </div>)}
      </div></details> : null}
    </> : null}
  </section>
}
