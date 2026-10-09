"use client"

import { useRef, useState } from "react"
import { saveCustomAgent, type AgentDirectoryEntry, type AgentProfile, type CustomAgentInput, type TargetProject } from "@/lib/api"

const POLICIES = [
  { id: "codex_coding", provider: "local-codex-cli", roles: ["frontend", "backend"], label: "Codex · 原生编码工具", description: "沿用 CLI 工作区沙箱、命令与文件范围检查。" },
  { id: "claude_file_edit", provider: "local-claude-code-cli", roles: ["frontend", "backend"], label: "Claude Code · 文件编辑", description: "Read / Write / Edit / MultiEdit，不开放 Bash。" },
  { id: "claude_read_only", provider: "local-claude-code-cli", roles: ["review"], label: "Claude Code · 只读评审", description: "只开放 Read，不开放写入和 Bash。" },
  { id: "planner_no_tools", provider: "claude-cli-planner", roles: ["orchestrator"], label: "Claude Planner · 无执行工具", description: "仅返回规划 JSON，由平台校验后生成任务。" },
]
const CAPABILITIES: Record<string, string[]> = {
  frontend: ["code_write", "diff_analysis", "preview"], backend: ["code_write", "diff_analysis"],
  review: ["code_review", "diff_analysis"], orchestrator: ["code_review", "diff_analysis"],
}
const field = "min-h-10 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 text-sm font-normal text-[var(--foreground)] outline-none focus:border-[var(--primary-border)]"

export function CustomAgentEditor({ backendUrl, workspaceId, targets, editing, initialDraft, disabled = false, onDraftChange, onSavingChange, onSaved, onCancel }: {
  backendUrl: string; workspaceId?: string; targets: TargetProject[]; editing: AgentDirectoryEntry | null
  initialDraft?: CustomAgentInput; disabled?: boolean; onDraftChange?: (draft: CustomAgentInput) => void; onSavingChange?: (saving: boolean) => void
  onSaved: (profile: AgentProfile) => Promise<void>; onCancel: () => void
}) {
  const [draft, setDraft] = useState<CustomAgentInput>(() => initialDraft ?? ({
    displayName: editing?.displayName ?? "", mentionAlias: editing?.mentionAlias ?? "",
    role: editing?.role ?? "frontend", providerId: editing?.providerId ?? "local-codex-cli",
    toolPolicy: editing?.toolPolicy ?? "codex_coding", supportedTargets: editing?.supportedTargets ?? ["demo-frontend"],
    capabilityTags: editing?.capabilityTags ?? CAPABILITIES.frontend, systemPrompt: editing?.systemPrompt ?? "",
    description: editing?.description ?? "", avatarInitials: editing?.avatarInitials ?? "",
    enabled: editing ? editing.status === "available" : true,
  }))
  const [busy, setBusy] = useState(false)
  const saving = useRef(false)
  const savedId = useRef(editing?.id)
  const [error, setError] = useState<string | null>(null)
  const policy = POLICIES.find((item) => item.id === draft.toolPolicy)
  const allowedTargets = targets.filter((target) => !target.requiresPlatformMode && target.allowedAgents.includes(draft.role === "orchestrator" ? "qa" : draft.role))
  function patch(next: Partial<CustomAgentInput>) { const value = { ...draft, ...next }; setDraft(value); onDraftChange?.(value) }

  return <form className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm" onSubmit={async (event) => {
    event.preventDefault()
    if (saving.current || disabled) return
    if (!workspaceId) { setError("请先选择工作区。"); return }
    saving.current = true; setBusy(true); setError(null); onSavingChange?.(true)
    try {
      const profile = await saveCustomAgent(backendUrl, workspaceId, draft, savedId.current)
      savedId.current = profile.id
      await onSaved(profile)
    }
    catch (error) { setError(error instanceof Error ? error.message : "保存失败。") }
    finally { saving.current = false; setBusy(false); onSavingChange?.(false) }
  }}>
    <div><h2 className="text-base font-semibold">{editing ? `编辑 ${editing.displayName}` : initialDraft ? "检查生成的 Agent 配置" : "自定义 Agent"}</h2><p className="mt-1 text-xs leading-5 text-[var(--muted-foreground)]">名称与角色分开管理。保存后可通过 @ 别名指派，也可在运行设置中选作默认 Agent。</p></div>
    <fieldset disabled={busy || disabled} className="grid min-w-0 gap-4 disabled:opacity-60 [&_input]:min-w-0 [&_select]:min-w-0 [&_textarea]:min-w-0">
      <div className="grid gap-3 md:grid-cols-3">
        <label className="grid gap-1 text-xs font-semibold">自定义名称<input required maxLength={80} className={field} value={draft.displayName} onChange={(event) => patch({ displayName: event.target.value })} /></label>
        <label className="grid gap-1 text-xs font-semibold">@ 别名<input required pattern="[a-zA-Z][a-zA-Z0-9_-]{1,63}" maxLength={64} placeholder="例如 ui-designer" className={field} value={draft.mentionAlias} onChange={(event) => patch({ mentionAlias: event.target.value.toLowerCase() })} /></label>
        <label className="grid gap-1 text-xs font-semibold">执行角色<select className={field} value={draft.role} onChange={(event) => {
          const role = event.target.value, policy = POLICIES.find((item) => item.roles.includes(role))!
          patch({ role, toolPolicy: policy.id, providerId: policy.provider, capabilityTags: CAPABILITIES[role], supportedTargets: [role === "backend" ? "demo-backend" : "demo-frontend"] })
        }}>{[["frontend", "前端"], ["backend", "后端"], ["review", "评审"], ["orchestrator", "规划"]].map(([role, label]) => <option key={role} value={role}>{label}</option>)}</select></label>
      </div>
      <label className="grid gap-1 text-xs font-semibold">工具权限<select className={field} value={draft.toolPolicy} onChange={(event) => {
        const policy = POLICIES.find((item) => item.id === event.target.value)!
        patch({ toolPolicy: policy.id, providerId: policy.provider })
      }}>{POLICIES.filter((item) => item.roles.includes(draft.role)).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select><span className="font-normal text-[var(--muted-foreground)]">{policy?.description} 网络和目标目录限制继续生效。</span></label>
      <fieldset className="grid gap-2"><legend className="mb-2 text-xs font-semibold">可操作目标</legend><div className="flex flex-wrap gap-3">{allowedTargets.map((target) => <label className="flex items-center gap-2 text-xs" key={target.targetId}><input type="checkbox" checked={draft.supportedTargets.includes(target.targetId)} onChange={(event) => patch({ supportedTargets: event.target.checked ? [...draft.supportedTargets, target.targetId] : draft.supportedTargets.filter((id) => id !== target.targetId) })} />{target.name}</label>)}</div>{!allowedTargets.length ? <p className="text-xs text-[var(--muted-foreground)]">没有兼容的已注册目标。</p> : null}</fieldset>
      <fieldset className="grid gap-2"><legend className="mb-2 text-xs font-semibold">能力</legend><div className="flex flex-wrap gap-3">{CAPABILITIES[draft.role].map((capability, index) => <label className="flex items-center gap-2 text-xs" key={capability}><input type="checkbox" disabled={index === 0} checked={draft.capabilityTags.includes(capability)} onChange={(event) => patch({ capabilityTags: event.target.checked ? [...draft.capabilityTags, capability] : draft.capabilityTags.filter((tag) => tag !== capability) })} />{capability}</label>)}</div></fieldset>
      <label className="grid gap-1 text-xs font-semibold">自定义 System Prompt<textarea maxLength={8000} rows={5} className={`${field} resize-y py-2`} placeholder="描述职责、偏好和输出格式" value={draft.systemPrompt} onChange={(event) => patch({ systemPrompt: event.target.value })} /><span className="font-normal text-[var(--muted-foreground)]">仅影响后续运行；运行设置中的提示词可覆盖此项。提示词不能授予额外权限。</span></label>
      <label className="grid gap-1 text-xs font-semibold">职责说明<input maxLength={1000} className={field} value={draft.description} onChange={(event) => patch({ description: event.target.value })} /></label>
      <label className="flex items-center gap-2 text-xs font-semibold"><input type="checkbox" checked={draft.enabled} onChange={(event) => patch({ enabled: event.target.checked })} />启用自定义 Agent</label>
    </fieldset>
    {error ? <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
    <div className="flex flex-wrap justify-end gap-2"><button type="button" disabled={busy || disabled} className={field} onClick={onCancel}>取消自定义编辑</button><button type="submit" disabled={busy || disabled || !workspaceId} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "保存中…" : "保存自定义 Agent"}</button></div>
  </form>
}
