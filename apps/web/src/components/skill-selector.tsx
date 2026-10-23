"use client"

import { Disclosure } from "./disclosure"

import { useEffect, useState } from "react"
import { listSkills, type WorkspaceSkill } from "@/lib/skills-api"

export function SkillSelector({ backendUrl, workspaceId, selected, onChange, disabled }: {
  backendUrl: string; workspaceId: string; selected: string[] | null; onChange: (ids: string[] | null) => void; disabled: boolean
}) {
  const [skills, setSkills] = useState<WorkspaceSkill[]>([])
  const [error, setError] = useState("")
  const [reload, setReload] = useState(0)
  useEffect(() => { let current = true
    listSkills(backendUrl, workspaceId).then(value => { if (current) { setSkills(value); setError("") } })
      .catch(error => { if (current) setError(error instanceof Error ? error.message : "技能加载失败") })
    return () => { current = false }
  }, [backendUrl, workspaceId, reload])
  return <Disclosure className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs" summaryClassName="cursor-pointer" summary={<>本次技能 · {selected === null ? "使用 Agent 默认" : selected.length ? selected.join("、") : "不使用技能"}</>}>

    <div className="mt-2 flex flex-wrap gap-3"><button type="button" disabled={disabled} onClick={() => onChange(null)} className="text-[var(--primary)]">使用默认</button>
      <button type="button" disabled={disabled} onClick={() => onChange([])}>全部取消</button><button type="button" disabled={disabled} onClick={() => setReload(v => v + 1)}>刷新技能</button></div>
    {error ? <p role="status" className="mt-2">{error}</p> : null}
    <fieldset disabled={disabled} className="mt-2 grid gap-2">{skills.filter(s => s.enabled).map(skill => <label key={skill.name} className="flex items-start gap-2">
      <input type="checkbox" checked={selected?.includes(skill.name) ?? false} disabled={!selected?.includes(skill.name) && (selected?.length ?? 0) >= 3}
        onChange={event => onChange(event.target.checked ? [...(selected ?? []), skill.name] : (selected ?? []).filter(id => id !== skill.name))} />
      <span><span className="font-medium">{skill.name}</span><span className="ml-2 text-[var(--muted-foreground)]">{skill.description}</span></span>
    </label>)}</fieldset>
  </Disclosure>
}
