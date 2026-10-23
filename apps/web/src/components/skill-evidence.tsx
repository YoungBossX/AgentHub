import { Disclosure } from "./disclosure"

import type { SkillReceipt } from "@/lib/skills-api"

const labels: Record<string, string> = { selected: "已选择，等待载入", loaded: "已载入调用指令", incompatible_role: "角色不适用", unsupported_adapter: "脚本模式不执行技能" }
export function SkillEvidence({ value }: { value: unknown }) {
  if (!value || typeof value !== "object" || !Array.isArray((value as SkillReceipt).skills)) return null
  const receipt = value as SkillReceipt
  if (!receipt.skills.length) return null
  return <Disclosure className="mt-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-xs" summaryClassName="cursor-pointer font-medium" summary={<>技能加载 · {receipt.skills.length} 项</>}>

    <p className="mt-2 text-[var(--muted-foreground)]">来源：{receipt.source === "message" ? "本次消息选择" : "Agent 默认"}。载入表示已加入调用指令，执行结果仍以 Diff 和 QA 为准。</p>
    <ul className="mt-2 grid gap-2">{receipt.skills.map(skill => <li key={skill.name} className="rounded bg-[var(--surface-muted)] p-2">
      <p className="font-medium">{skill.name} · v{skill.revision} · {labels[skill.status] ?? "状态未知"}</p><p className="mt-1 break-all text-[var(--muted-foreground)]">{skill.description}<br />版本指纹：{skill.sha256}</p>
      {skill.resources.length ? <p className="mt-1">参考资料：{skill.resources.join("、")}</p> : null}
    </li>)}</ul>
  </Disclosure>
}
