"use client"

import { useEffect, useState } from "react"
import type { AgentDirectoryEntry } from "@/lib/api"
import { listSkills, saveSkill, type WorkspaceSkill } from "@/lib/skills-api"
import { readSkillText, referenceRows, SkillReferencesEditor, validateReferenceRows, type ReferenceDraft } from "./skill-references-editor"

const roles = [{ key: "frontend", label: "前端" }, { key: "backend", label: "后端" },
  { key: "review", label: "评审" }, { key: "planner", label: "规划" }]
const field = "rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-sm"
const empty: WorkspaceSkill = { name: "", description: "", markdown: "---\nname: my-skill\ndescription: 描述技能用途及适用场景\n---\n\n写下操作步骤与验收要求。\n",
  references: {}, roles: ["frontend"], defaultAgents: [], enabled: true, revision: 0, source: "workspace" }

type Props = {
  backendUrl: string; workspaceId?: string; agents: AgentDirectoryEntry[]
}
export function SkillSettings(props: Props) { return <WorkspaceSkillSettings key={`${props.backendUrl}:${props.workspaceId}`} {...props} /> }
function WorkspaceSkillSettings({ backendUrl, workspaceId, agents }: Props) {
  const [skills, setSkills] = useState<WorkspaceSkill[]>([])
  const [draft, setDraft] = useState<WorkspaceSkill | null>(null)
  const [resources, setResources] = useState<ReferenceDraft[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState("")
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let current = true
    if (workspaceId) listSkills(backendUrl, workspaceId).then(value => { if (current) { setSkills(value); setNotice("") } })
      .catch(error => { if (current) setNotice(error instanceof Error ? error.message : "技能库加载失败") })
    return () => { current = false }
  }, [backendUrl, workspaceId, reload])
  const identities = [...roles.map(r => ({ key: r.key, role: r.key, label: `${r.label}默认 Agent` })),
    ...agents.filter(a => a.toolPolicy).map(a => ({ key: a.agentProfileId, role: a.role === "orchestrator" ? "planner" : a.role === "qa" ? "review" : a.role, label: a.displayName }))]
  function edit(value: WorkspaceSkill) { setDraft(structuredClone(value)); setResources(referenceRows(value.references)); setNotice("") }
  return <section aria-label="技能库" className="grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-semibold">Skills · 技能库</h2>
      <p className="mt-1 text-xs text-[var(--muted-foreground)]">将开发与审查流程保存为可复用技能，按 Agent 设置默认值，也可在发送消息时选择。</p></div>
      <div className="flex gap-2"><button type="button" className={field} onClick={() => setReload(v => v + 1)} disabled={busy}>刷新技能</button>
      <button type="button" className={field} disabled={!workspaceId || busy} onClick={() => edit(empty)}>新建技能</button></div></div>
    {notice ? <p role="status" className="text-xs text-[var(--muted-foreground)]">{notice}</p> : null}
    <div className="grid gap-2 md:grid-cols-3">{skills.map(skill => <button type="button" disabled={busy} key={skill.name} onClick={() => edit(skill)} className={`${field} text-left`}>
      <span className="font-medium">{skill.name}</span><span className="ml-2 text-xs text-[var(--muted-foreground)]">{skill.enabled ? "可用" : "已停用"} · v{skill.revision}</span>
      <p className="mt-2 text-xs">{skill.description}</p><p className="mt-2 text-xs text-[var(--muted-foreground)]">{skill.defaultAgents.length ? `默认绑定 ${skill.defaultAgents.length} 个 Agent` : "未设置默认绑定"}</p>
    </button>)}</div>
    {draft ? <form className="grid gap-3 border-t border-[var(--border)] pt-3" onSubmit={async event => {
      event.preventDefault(); if (!workspaceId || busy) return
      setBusy(true); setNotice("")
      try { const references = validateReferenceRows(resources, draft.markdown); await saveSkill(backendUrl, workspaceId, { ...draft, references });
        setSkills(await listSkills(backendUrl, workspaceId)); setDraft(null); setNotice("技能已保存，新运行将使用新版本。")
      } catch (error) { setNotice(error instanceof Error ? error.message : "技能保存失败") }
      finally { setBusy(false) }
    }}>
      <label className="grid gap-1 text-xs">导入 SKILL.md<input type="file" accept=".md" disabled={busy} onChange={async event => {
        const file = event.currentTarget.files?.[0]; event.currentTarget.value = ""; if (!file) return
        setBusy(true); setNotice("")
        try { setDraft({ ...draft, markdown: await readSkillText(file, 16000) }) }
        catch (error) { setNotice(error instanceof TypeError ? "请选择 UTF-8 文本。" : error instanceof Error ? error.message : "导入失败") }
        finally { setBusy(false) }
      }} /></label>
      <label className="grid gap-1 text-xs">SKILL.md<textarea aria-label="SKILL.md" className={`${field} min-h-48 font-mono`} maxLength={16000} value={draft.markdown} disabled={busy}
        onChange={event => setDraft({ ...draft, markdown: event.target.value })} /></label>
      <fieldset className="flex flex-wrap gap-3" disabled={busy}><legend className="mb-2 text-xs">适用角色</legend>{roles.map(role => <label className="text-xs" key={role.key}>
        <input type="checkbox" checked={draft.roles.includes(role.key)} onChange={event => {
          const nextRoles = event.target.checked ? [...draft.roles, role.key] : draft.roles.filter(r => r !== role.key)
          setDraft({ ...draft, roles: nextRoles, defaultAgents: draft.defaultAgents.filter(key => identities.some(i => i.key === key && nextRoles.includes(i.role))) })
        }} /> {role.label}</label>)}</fieldset>
      <fieldset className="flex flex-wrap gap-3" disabled={busy}><legend className="mb-2 text-xs">默认绑定 Agent</legend>{identities.filter(i => draft.roles.includes(i.role)).map(i => <label className="text-xs" key={i.key}>
        <input type="checkbox" checked={draft.defaultAgents.includes(i.key)} onChange={event => setDraft({ ...draft,
          defaultAgents: event.target.checked ? [...draft.defaultAgents, i.key] : draft.defaultAgents.filter(k => k !== i.key) })} /> {i.label}</label>)}</fieldset>
      <SkillReferencesEditor rows={resources} markdown={draft.markdown} busy={busy} onChange={setResources} onBusyChange={setBusy} onNotice={setNotice} />
      <label className="text-xs"><input type="checkbox" checked={draft.enabled} disabled={busy} onChange={event => setDraft({ ...draft, enabled: event.target.checked })} /> 启用技能</label>
      <div className="flex gap-2"><button className={field} disabled={busy} type="submit">{busy ? "保存中…" : "保存技能"}</button><button className={field} disabled={busy} type="button" onClick={() => setDraft(null)}>取消</button></div>
    </form> : null}
  </section>
}
