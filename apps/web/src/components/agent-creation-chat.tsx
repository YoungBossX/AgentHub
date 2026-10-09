"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { MessageSquarePlus } from "lucide-react"
import { CustomAgentEditor } from "./custom-agent-editor"
import { generateAgentConfiguration, type AgentCreationResult, type AgentCreationTurn, type CustomAgentInput, type TargetProject } from "@/lib/api"

type Props = { backendUrl: string; workspaceId?: string; targets: TargetProject[]; onSaved: () => Promise<void> }
type DraftState = {
  version: 1; history: AgentCreationTurn[]; draft: CustomAgentInput | null; prompt: string
  provenance: AgentCreationResult["provenance"] | null; saved: { id: string; alias: string; enabled: boolean } | null
}
const EMPTY: DraftState = { version: 1, history: [], draft: null, prompt: "", provenance: null, saved: null }
const field = "min-w-0 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-border)] disabled:opacity-50"

function isDraft(value: unknown): value is CustomAgentInput {
  if (!value || typeof value !== "object") return false
  const item = value as Record<string, unknown>
  return ["displayName", "mentionAlias", "providerId", "systemPrompt", "description", "avatarInitials"].every((key) => typeof item[key] === "string")
    && ["frontend", "backend", "review", "orchestrator"].includes(String(item.role))
    && ["codex_coding", "claude_file_edit", "claude_read_only", "planner_no_tools"].includes(String(item.toolPolicy))
    && [item.supportedTargets, item.capabilityTags].every((values) => Array.isArray(values) && values.length <= 16 && values.every((v) => typeof v === "string"))
    && typeof item.enabled === "boolean"
}

function restore(key: string): { state: DraftState; notice: string } {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return { state: EMPTY, notice: "" }
    const value = JSON.parse(raw) as DraftState
    if (raw.length > 64000 || value.version !== 1 || typeof value.prompt !== "string" || value.prompt.length > 4000
      || !Array.isArray(value.history) || value.history.length > 10 || value.history.some((turn) => !turn || !["user", "assistant"].includes(turn.role) || typeof turn.content !== "string" || turn.content.length > 4000)
      || (value.draft !== null && !isDraft(value.draft))
      || (value.saved !== null && (!value.saved || typeof value.saved.alias !== "string" || typeof value.saved.id !== "string" || typeof value.saved.enabled !== "boolean"))
      || (value.provenance !== null && (!value.provenance || typeof value.provenance.providerId !== "string" || typeof value.provenance.plannerSource !== "string"))) {
      return { state: EMPTY, notice: "本标签页的旧草稿格式无效，请重新描述需求。" }
    }
    return { state: value, notice: "已恢复本标签页的创建草稿。未返回的生成请求不会自动重发。" }
  } catch { return { state: EMPTY, notice: "浏览器草稿存储不可用；本次编辑仅保留在当前页面。" } }
}

export function AgentCreationChat(props: Props) {
  const [opened, setOpened] = useState(false)
  const [started, setStarted] = useState(false)
  return <section id="create-agent" className="min-w-0 rounded-xl border border-[var(--primary-border)] bg-[var(--primary-soft)] p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0"><h2 className="flex items-center gap-2 text-base font-semibold"><MessageSquarePlus size={18} />通过对话创建 Agent</h2><p className="mt-1 text-xs leading-5 text-[var(--muted-foreground)]">描述职责、目标和输出偏好，再检查生成的配置。保存前不会创建 Agent 或执行代码。</p></div>
      <button type="button" aria-expanded={opened} disabled={!props.workspaceId} className={field} onClick={() => { setStarted(true); setOpened((value) => !value) }}>{opened ? "收起创建对话" : "打开创建对话"}</button>
    </div>
    {started && props.workspaceId ? <div hidden={!opened}><CreationConversation key={`${props.backendUrl}:${props.workspaceId}`} {...props} workspaceId={props.workspaceId} /></div> : null}
  </section>
}

function CreationConversation({ backendUrl, workspaceId, targets, onSaved }: Props & { workspaceId: string }) {
  const storageKey = `agenthub:agent-creation:v1:${backendUrl}:${workspaceId}`
  const [initial] = useState(() => restore(storageKey))
  const [state, setState] = useState(initial.state)
  const [notice, setNotice] = useState(initial.notice)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [revision, setRevision] = useState(0)
  const [confirmReset, setConfirmReset] = useState(false)
  const pending = useRef(false), live = useRef(true)
  useEffect(() => { live.current = true; return () => { live.current = false } }, [])
  function update(next: DraftState) {
    if (!live.current) return
    setState(next)
    try { sessionStorage.setItem(storageKey, JSON.stringify(next)) }
    catch { setNotice("浏览器草稿存储不可用；本次编辑仅保留在当前页面。") }
  }
  async function generate() {
    const message = state.prompt.trim()
    if (!message || pending.current || saving || state.saved) return
    pending.current = true; setBusy(true); setError(null)
    const history = state.history.slice(-10)
    while (history.reduce((total, turn) => total + turn.content.length, message.length) > 16000) history.shift()
    try {
      const result = await generateAgentConfiguration(backendUrl, workspaceId, { message, history, currentDraft: state.draft })
      if (!live.current) return
      if (!["draft", "clarification"].includes(result.kind) || typeof result.reply !== "string" || !result.provenance || (result.kind === "draft" && !isDraft(result.draft))) throw new Error("生成结果格式无效，当前草稿已保留。")
      update({ ...state, prompt: "", draft: result.draft ?? state.draft, provenance: result.provenance,
        history: [...history, { role: "user", content: message }, { role: "assistant", content: result.reply }].slice(-10) as AgentCreationTurn[] })
      setRevision((value) => value + 1)
    } catch (failure) { if (live.current) setError(failure instanceof Error ? failure.message : "生成失败，当前草稿已保留。") }
    finally { pending.current = false; if (live.current) setBusy(false) }
  }
  return <div className="mt-4 grid min-w-0 gap-4">
    {notice ? <p role="status" className="text-xs text-[var(--muted-foreground)]">{notice}</p> : null}
    <ol aria-label="Agent 创建对话" className="grid max-h-80 min-w-0 gap-2 overflow-y-auto">
      {state.history.map((turn, index) => <li key={index} className={`min-w-0 rounded-lg border border-[var(--border)] p-3 text-sm [overflow-wrap:anywhere] ${turn.role === "user" ? "ml-4 bg-[var(--surface-muted)]" : "mr-4 bg-[var(--surface)]"}`}><p className="mb-1 text-[10px] font-semibold text-[var(--muted-foreground)]">{turn.role === "user" ? "你" : "配置助手"}</p><p className="whitespace-pre-wrap">{turn.content}</p></li>)}
    </ol>
    {state.saved ? <div role="status" className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm [overflow-wrap:anywhere]">已保存 @{state.saved.alias}，{state.saved.enabled ? "已启用，可返回聊天通过别名指派。" : "尚未启用，可在下方目录中编辑并启用。"} <Link href="/" className="font-semibold text-[var(--primary)] underline">返回聊天</Link></div> : <form className="grid min-w-0 gap-2" onSubmit={(event) => { event.preventDefault(); void generate() }}>
      <label className="grid min-w-0 gap-2 text-xs font-semibold">{state.draft ? "补充或调整 Agent 要求" : "描述你想创建的 Agent"}<textarea rows={3} maxLength={4000} disabled={busy || saving} className={`${field} w-full resize-y font-normal`} value={state.prompt} placeholder="例如：创建一个只读前端评审助手，关注可访问性，用中文列出问题和建议。" onChange={(event) => update({ ...state, prompt: event.target.value })} /></label>
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-[var(--muted-foreground)]">使用运行设置中的 Planner；最近 10 条对话和当前草稿参与生成。</p><button type="submit" disabled={busy || saving || !state.prompt.trim()} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "正在生成配置…" : state.draft ? "发送调整要求" : "生成配置草稿"}</button></div>
    </form>}
    {error ? <p role="alert" className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm text-[var(--foreground)] [overflow-wrap:anywhere]">{error} <Link href="/settings/runtime" className="text-[var(--primary)] underline">检查运行设置</Link></p> : null}
    {state.provenance ? <p className="text-[10px] text-[var(--muted-foreground)] [overflow-wrap:anywhere]">生成来源：{state.provenance.providerId} · {state.provenance.plannerSource === "real_llm" ? "原生模型" : "测试提供方"} · 输出 {state.provenance.outputSha256?.slice(0, 12)}</p> : null}
    {state.draft && !state.saved ? <>
      <p className="text-xs leading-5 text-[var(--muted-foreground)]">草稿可直接编辑，也可继续对话调整。确认目标和工具权限后，勾选“启用自定义 Agent”并保存即可使用；不勾选则保存为停用状态。</p>
      <CustomAgentEditor key={revision} backendUrl={backendUrl} workspaceId={workspaceId} targets={targets} editing={null} initialDraft={state.draft} disabled={busy} onDraftChange={(draft) => update({ ...state, draft })} onSavingChange={setSaving} onCancel={() => setConfirmReset(true)} onSaved={async (profile) => {
        if (!live.current) return
        update({ ...state, saved: { id: profile.id, alias: profile.mentionAlias ?? state.draft!.mentionAlias, enabled: profile.status === "available" } })
        try { await onSaved() } catch { if (live.current) setError("Agent 已保存，目录刷新失败。请刷新页面核对，无需重复创建。") }
      }} />
    </> : null}
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {confirmReset ? <><span>清除本标签页的创建对话和未保存草稿？</span><button type="button" className={field} disabled={busy || saving} onClick={() => { update(EMPTY); setRevision((value) => value + 1); setError(null); setNotice(""); setConfirmReset(false) }}>确认重新开始</button><button type="button" className={field} onClick={() => setConfirmReset(false)}>保留草稿</button></> : <button type="button" disabled={busy || saving} className={field} onClick={() => setConfirmReset(true)}>开始新的创建对话</button>}
      <span className="text-[var(--muted-foreground)]">草稿仅在当前浏览器标签页保存；清除草稿不删除已保存的 Agent。</span>
    </div>
  </div>
}
