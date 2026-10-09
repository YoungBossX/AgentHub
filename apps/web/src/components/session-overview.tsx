"use client"
import { ArrowUpRight, FileDiff, Monitor, SearchCheck, FileText, Rocket } from "lucide-react"
import type { AgentContact, SessionTask } from "@/lib/api"
import type { ArtifactPanelItem } from "./preview-card"
import { activeStates, latestTaskState } from "./session-workbench-state"

export function SessionProgress({ tasks, agents, onOpenProcess }: { tasks: SessionTask[]; agents: AgentContact[]; onOpenProcess: () => void }) {
  if (!tasks.length) return null
  const completed = tasks.filter((task) => latestTaskState(task) === "completed").length
  return <section
    aria-label="协作进度"
    className="min-w-0 rounded-xl border border-[var(--border)] bg-white p-4"
  >
    <div className="flex items-center justify-between gap-2">
      <h3 className="text-sm font-semibold">协作计划</h3>
      <button
        onClick={onOpenProcess}
        className="flex items-center gap-1 text-xs text-[var(--primary)]"
      >
        查看过程
        <ArrowUpRight size={13} />
      </button>
    </div>
    <div className="mt-3 flex items-center gap-3">
      <div
        role="progressbar"
        aria-label="任务完成进度"
        aria-valuemin={0}
        aria-valuemax={tasks.length}
        aria-valuenow={completed}
        className="h-1.5 flex-1 overflow-hidden rounded bg-slate-100"
      >
        <div
          className="h-full bg-[var(--primary)]"
          style={{ width: `${completed / tasks.length * 100}%` }}
        />
      </div>
      <span className="text-[11px] text-slate-500">
        {`${completed} / ${tasks.length}`}
      </span>
    </div>
    <ol className="mt-3 grid min-w-0 grid-cols-1 gap-2">
      {tasks.map((task) => {
      const state = latestTaskState(task)
      const agent = (agents.find((agent) => agent.id === task.assignedAgentId) ?? agents.find((agent) => agent.role === task.assignedAgentRole))
      return <li
        key={task.id}
        className="flex min-w-0 items-center gap-2 text-xs"
      >
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${state === "completed" ? "bg-emerald-500" : ["failed", "interrupted", "blocked"].includes(state) ? "bg-red-500" : activeStates.has(state) ? "bg-blue-500" : "bg-slate-300"}`} />
        <span className="min-w-0 flex-1 truncate">{task.title}</span>
        <span className="text-[10px] text-slate-400">{agent?.displayName ?? task.assignedAgentRole}</span>
        <span className="text-[10px] text-slate-500">{state === "completed" ? "已完成" : activeStates.has(state) ? "执行中 / 排队" : state === "failed" ? "失败" : state === "interrupted" ? "已中断" : state === "blocked" ? "受阻" : state === "cancelled" ? "已取消" : "待执行"}</span>
      </li>
    })}
    </ol>
  </section>
}
const kinds = { diff: { label: "代码变更", icon: FileDiff }, preview: { label: "网页预览", icon: Monitor }, review: { label: "评审报告", icon: SearchCheck }, deployment: { label: "部署记录", icon: Rocket }, workbench: { label: "文档产物", icon: FileText } }
export function SessionResults({ artifacts, tasks, onSelect, compact = false }: { artifacts: ArtifactPanelItem[]; tasks: SessionTask[]; onSelect: (id: string) => void; compact?: boolean }) {
  const latestIds = new Set(tasks.flatMap((task) => task.taskRuns.at(-1)?.id ?? []))
  const items = compact ? artifacts.filter((item) => latestIds.has(item.taskRunId)).slice(-4) : artifacts
  return <section
    aria-label={compact ? "对话成果" : "会话成果"}
    className="mt-4 min-w-0"
  >
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-sm font-semibold">{compact ? "已生成成果" : "成果工作台"}</h3>
      <span className="text-[11px] text-slate-400">
        {`${items.length} 份`}
      </span>
    </div>
    {!items.length ? <div className="rounded-xl border border-dashed border-slate-200 px-5 py-10 text-center text-sm text-slate-400">执行后，代码变更、网页预览和评审结果会出现在这里。</div> : <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
      {items.map((item) => {
      const { icon: Icon, label } = kinds[item.kind]
      const detail = item.kind === "diff" ? `${item.artifact.stats.filesChanged} 个文件 · +${item.artifact.stats.additions} / −${item.artifact.stats.deletions}` : item.kind === "preview" ? `${item.artifact.status} · ${item.artifact.healthStatus}` : item.kind === "review" ? `${item.artifact.status} · ${item.artifact.summary}` : item.kind === "deployment" ? `${item.artifact.status} · ${item.artifact.providerType === "mock" ? "模拟部署" : item.artifact.providerType}` : `版本 ${item.artifact.version} · ${item.artifact.status}`
      return <button
        key={item.id}
        onClick={() => onSelect(item.id)}
        className="group min-w-0 rounded-xl border border-[var(--border)] bg-white p-4 text-left transition hover:border-blue-300 hover:bg-blue-50/30"
      >
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-xs font-medium text-[var(--primary)]">
            <Icon size={15} />
            {label}
          </span>
          <ArrowUpRight
            size={13}
            className="text-slate-400"
          />
        </div>
        <p className="mt-3 truncate text-sm font-medium text-slate-800">{item.taskTitle}</p>
        <p className="mt-1 line-clamp-2 break-words text-[11px] text-slate-500">{detail}</p>
        {item.kind === "diff" && item.artifact.stats.additions + item.artifact.stats.deletions > 0 ? <div className="mt-3 flex h-1 gap-0.5 overflow-hidden rounded bg-slate-100">
          <span
            className="bg-emerald-400"
            style={{ width: `${item.artifact.stats.additions / Math.max(1, item.artifact.stats.additions + item.artifact.stats.deletions) * 100}%` }}
          />
          <span className="flex-1 bg-red-300" />
        </div> : null}
        <p className="mt-3 text-[10px] text-slate-400">
          {`${latestIds.has(item.taskRunId) ? "当前运行" : "历史成果"} · Run ${item.taskRunId.slice(0, 8)}`}
        </p>
      </button>
    })}
    </div>}
  </section>
}
