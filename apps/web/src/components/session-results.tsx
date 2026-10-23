"use client"

import { ArrowUpRight, FileDiff, Monitor, SearchCheck, FileText, Rocket } from "lucide-react"
import type { SessionTask } from "@/lib/api"
import type { ArtifactPanelItem } from "./preview-card"
import { Disclosure } from "./disclosure"
import { groupSessionResults, type ResultBatch } from "./session-result-groups"
import { statusLabel, healthLabel } from "./task-card"

const kinds = { diff: { label: "代码变更", icon: FileDiff }, preview: { label: "网页预览", icon: Monitor }, review: { label: "评审报告", icon: SearchCheck }, deployment: { label: "部署记录", icon: Rocket }, workbench: { label: "文档产物", icon: FileText } }
const resultStatus = (value: string) => ({ passed: "通过", warning: "有提醒", ready: "就绪", healthy: "健康", unhealthy: "不健康", stopped: "已停止" }[value] ?? statusLabel(value))

function ResultCard({ item, onSelect }: { item: ArtifactPanelItem; onSelect: (id: string) => void }) {
  const { icon: Icon, label } = kinds[item.kind]
  const detail = item.kind === "diff" ? `${item.artifact.stats.filesChanged} 个文件 · +${item.artifact.stats.additions} / −${item.artifact.stats.deletions}`
    : item.kind === "preview" ? `${resultStatus(item.artifact.status)} · ${healthLabel(item.artifact.healthStatus)}`
    : item.kind === "review" ? `${resultStatus(item.artifact.status)} · ${item.artifact.summary}`
    : item.kind === "deployment" ? `${resultStatus(item.artifact.status)} · ${item.artifact.providerType === "mock" ? "模拟部署" : item.artifact.providerType ?? item.artifact.provider}`
    : resultStatus(item.artifact.status)
  return <div className="min-w-0 rounded-xl bg-[var(--surface)] p-4">
    <button type="button" onClick={() => onSelect(item.id)} className="group grid w-full min-w-0 gap-2 rounded-lg text-left">
      <span className="flex items-center justify-between gap-2 text-xs font-medium text-[var(--primary)]"><span className="inline-flex items-center gap-2"><Icon aria-hidden="true" size={16} />{label}</span><ArrowUpRight aria-hidden="true" size={14} /></span>
      <span className="flex min-w-0 items-center gap-2 text-sm font-medium"><span className="truncate">{item.artifact.title || item.taskTitle}</span>{item.kind === "workbench" ? <span className="shrink-0 text-xs text-[var(--muted-foreground)]">v{item.artifact.version}</span> : null}</span>
      <span className="line-clamp-2 break-words text-xs text-[var(--muted-foreground)]">{detail}</span>
    </button>
    {item.kind === "diff" && item.artifact.stats.additions + item.artifact.stats.deletions > 0 ? <div className="mt-3 flex h-1 gap-0.5 overflow-hidden rounded bg-[var(--muted)]" aria-hidden="true"><span className="bg-emerald-500" style={{ width: `${item.artifact.stats.additions / (item.artifact.stats.additions + item.artifact.stats.deletions) * 100}%` }} /><span className="flex-1 bg-red-400" /></div> : null}
    {item.kind === "workbench" && item.artifact.versions.length > 1 ? <Disclosure summary={`文档版本 · ${item.artifact.versions.length} 个`} className="mt-3 text-xs text-[var(--muted-foreground)]"><ol className="mt-2 space-y-2">{[...item.artifact.versions].sort((a, b) => b.version - a.version).map(version => <li key={version.id} className="break-words">v{version.version} · {version.summary || "无版本说明"}{version.version === item.artifact.version ? " · 当前文档版本" : ""}</li>)}</ol><p className="mt-2">打开文档后可在成果面板查看具体版本。</p></Disclosure> : null}
  </div>
}
function Batch({ batch, current, compact, onSelect }: { batch: ResultBatch; current: boolean; compact: boolean; onSelect: (id: string) => void }) {
  return <div className="mt-3 min-w-0">
    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)]"><span>{current ? "当前运行" : "历史运行"}{batch.ordinal ? ` · 第 ${batch.ordinal} 次` : ""}</span><span className="font-mono">{batch.runId.slice(0, 8)}</span>{batch.run ? <span className="rounded-full bg-[var(--surface)] px-2 py-0.5">{statusLabel(batch.run.state)}</span> : null}</div>
    {batch.items.length ? <div className="grid min-w-0 gap-3 sm:grid-cols-2">{(compact && current ? batch.items.slice(-4) : batch.items).map(item => <ResultCard key={item.id} item={item} onSelect={onSelect} />)}</div> : <p className="py-2 text-sm text-[var(--muted-foreground)]">当前运行尚无成果，历史结果不能替代本次验收。</p>}
    {compact && current && batch.items.length > 4 ? <p className="mt-2 text-xs text-[var(--muted-foreground)]">显示最近 4 份当前成果，完整内容可在成果页查看。</p> : null}
  </div>
}
export function SessionResults({ artifacts, tasks, onSelect, compact = false }: { artifacts: ArtifactPanelItem[]; tasks: SessionTask[]; onSelect: (id: string) => void; compact?: boolean }) {
  const groups = groupSessionResults(tasks, artifacts)
  return <section aria-label={compact ? "对话成果" : "会话成果"} className="mt-4 min-w-0">
    <div className="mb-3 flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">{compact ? "已生成成果" : "成果工作台"}</h3><span className="text-xs text-[var(--muted-foreground)]">{artifacts.length} 份 · 按任务与运行组织</span></div>
    {!groups.length ? <div className="rounded-xl bg-[var(--surface-muted)] px-5 py-10 text-center text-sm text-[var(--muted-foreground)]">执行后，代码变更、网页预览和评审结果会出现在这里。</div> : <div className="grid gap-4">{groups.map(group => <section key={group.id} aria-label={`任务成果 · ${group.title}`} className="min-w-0 rounded-2xl bg-[var(--surface-muted)] p-4">
      <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold">{group.title}</h4>{!group.associated ? <span className="text-xs text-[var(--muted-foreground)]">未关联任务 · 仅保留历史证据</span> : null}</div>
      {group.current ? <Batch batch={group.current} current compact={compact} onSelect={onSelect} /> : null}
      {group.history.some(batch => batch.items.length) ? <Disclosure summary={`历史成果 · ${group.history.filter(batch => batch.items.length).length} 次运行`} className="mt-3 text-xs text-[var(--muted-foreground)]">{group.history.filter(batch => batch.items.length).map(batch => <Batch key={batch.runId} batch={batch} current={false} compact={false} onSelect={onSelect} />)}</Disclosure> : null}
    </section>)}</div>}
  </section>
}
