"use client"

import { useRef, useState } from "react"
import { RotateCcw } from "lucide-react"
import type { ChatMessage } from "@/lib/api"

const stateLabels: Record<string, string> = {
  preparing: "正在准备新请求…", submitted: "新请求已生成 · 执行结果见任务", failed: "本次生成未完成 · 已保留记录",
  calling: "正在重新汇总…", completed: "重新汇总已完成", superseded: "汇总输入已更新",
}

export function RegenerationLineage({ message }: { message: ChatMessage }) {
  const info = message.regeneration
  if (!info) return null
  return <div className="mt-2 rounded border border-[var(--border)] px-2 py-1 text-xs text-[var(--text-secondary)]">
    <a href={`#message-${info.sourceMessageId}`} className="text-[var(--primary)] underline">查看原消息</a>
    <span className="ml-2" role={info.state === "preparing" || info.state === "calling" ? "status" : undefined}>{stateLabels[info.state] ?? info.state}</span>
    {info.errorCode === "REGENERATION_PREPARATION_INTERRUPTED" ? <p>上次准备被服务重启中断，未自动重发。请检查已有任务。</p> : null}
  </div>
}

export function MessageRegeneration({ message, onRun, disabled }: {
  message: ChatMessage; onRun: (message: ChatMessage) => Promise<void>; disabled?: boolean
}) {
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submitting = useRef(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const action = message.regenerationAction
  if (!action) return null
  const label = action.kind === "summary" ? "重新汇总" : "重新生成"
  async function submit() {
    if (submitting.current) return
    submitting.current = true; setBusy(true); setError(null)
    try { await onRun(message); setConfirm(false) }
    catch (cause) { setError(cause instanceof Error ? cause.message : "暂时无法重新生成，请稍后重试。") }
    finally { submitting.current = false; setBusy(false) }
  }
  return <div className="mt-2">
    <button ref={trigger} type="button" disabled={disabled || busy || !action.available} title={action.reason ?? label} aria-expanded={confirm}
      onClick={() => { setConfirm(!confirm); setError(null) }}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-50">
      <RotateCcw aria-hidden="true" size={13} />{label}
    </button>
    {confirm ? <div role="group" aria-label={`确认${label}`} className="mt-2 space-y-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] p-3 text-xs">
      <p>{action.kind === "summary" ? "使用协调 Agent 的原有配置，重新总结当前运行与成果证据。任务不会重新执行，原汇总保留。" : "按原请求和附件重新处理，使用当前代码、上下文和 Agent 配置，可能创建并执行新的代码任务。原消息与成果保留，已有修改不会撤销。"}</p>
      {error ? <p role="alert" className="text-rose-700 dark:text-rose-300">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={busy || disabled || !action.available} onClick={() => void submit()} className="rounded bg-[var(--primary)] px-3 py-1.5 text-[var(--primary-foreground)] disabled:opacity-50">{busy ? "正在处理…" : `确认${label}`}</button>
        <button type="button" disabled={busy} onClick={() => { setConfirm(false); trigger.current?.focus() }} className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5">取消</button>
      </div>
    </div> : null}
  </div>
}
