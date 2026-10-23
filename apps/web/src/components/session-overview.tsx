"use client"
import { ArrowUpRight } from "lucide-react"
import type { AgentContact, SessionTask } from "@/lib/api"
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
export { SessionResults } from "./session-results"
