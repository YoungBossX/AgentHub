"use client"

import { type ReactNode } from "react"

import {
  Check,
  Circle,
  CircleDot,
  Radio,
  UserRound,
  Users,
} from "lucide-react"

import { cn } from "@/lib/utils"

export function WorkspaceHeader({
  conversationMode,
  hasCompletedRun,
  hasRecoveredRun,
  hasRequirement,
  hasRunningTask,
  healthSlot,
  onModeChange,
  selectedSessionTitle,
  taskCount,
}: {
  conversationMode: "direct" | "group"
  hasCompletedRun: boolean
  hasRecoveredRun: boolean
  hasRequirement: boolean
  hasRunningTask: boolean
  healthSlot?: ReactNode
  onModeChange: (mode: "direct" | "group") => void
  selectedSessionTitle: string
  taskCount: number
}) {
  return (
    <header
      className="shrink-0 border-b border-[var(--border)] bg-white/95 px-5 py-4"
      data-region="top-header"
    >
      <div className="rounded-lg border border-[var(--border)] bg-white px-4 py-3 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold text-[var(--text-muted)]">
              AgentHub
            </span>
            <span className="text-slate-300">›</span>
            <span className="inline-flex shrink-0 items-center gap-1.5 font-semibold text-slate-950">
              <Radio aria-hidden="true" size={15} />
              当前会话
            </span>
          </div>
          <div className="hidden shrink-0 sm:flex">{healthSlot}</div>
        </div>

        <div className="mt-5 flex flex-col gap-4">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold leading-tight text-slate-950 xl:text-2xl">
              {selectedSessionTitle}
            </h2>
            <p className="mt-2 truncate text-sm text-[var(--muted-foreground)]">
              {taskCount} 个任务 · {hasCompletedRun ? "已有执行证据" : "等待运行"}
            </p>
          </div>

          <ConversationModeSwitch
            mode={conversationMode}
            onModeChange={onModeChange}
          />

          <DemoPipeline
            hasCompletedRun={hasCompletedRun}
            hasRecoveredRun={hasRecoveredRun}
            hasRequirement={hasRequirement}
            hasRunningTask={hasRunningTask}
            hasTasks={taskCount > 0}
          />
          <div className="sm:hidden">{healthSlot}</div>
        </div>
      </div>
    </header>
  )
}

export function ConversationModeSwitch({
  mode,
  onModeChange,
}: {
  mode: "direct" | "group"
  onModeChange: (mode: "direct" | "group") => void
}) {
  return (
    <section className="flex justify-end rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2">
      <div className="grid grid-cols-2 rounded-full bg-white p-1 shadow-sm">
        <button
          aria-pressed={mode === "direct"}
          className={cn(
            "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-full px-3 text-xs font-semibold transition",
            mode === "direct"
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-100",
          )}
          onClick={() => onModeChange("direct")}
          type="button"
        >
          <UserRound aria-hidden="true" size={14} />
          单聊
        </button>
        <button
          aria-pressed={mode === "group"}
          className={cn(
            "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-full px-3 text-xs font-semibold transition",
            mode === "group"
              ? "bg-slate-950 text-white"
              : "text-slate-600 hover:bg-slate-100",
          )}
          onClick={() => onModeChange("group")}
          type="button"
        >
          <Users aria-hidden="true" size={14} />
          群聊
        </button>
      </div>
    </section>
  )
}

export function DemoPipeline({
  hasCompletedRun,
  hasRecoveredRun,
  hasRequirement,
  hasRunningTask,
  hasTasks,
}: {
  hasCompletedRun: boolean
  hasRecoveredRun: boolean
  hasRequirement: boolean
  hasRunningTask: boolean
  hasTasks: boolean
}) {
  const stages = [
    { label: "需求", state: hasRequirement ? "complete" : "pending" },
    { label: "计划", state: hasTasks ? "complete" : "pending" },
    {
      label: "运行",
      state: hasRecoveredRun
        ? "recovered"
        : hasCompletedRun
          ? "complete"
          : hasRunningTask
            ? "running"
            : "pending",
    },
    { label: "Diff", state: hasCompletedRun ? "ready" : "pending" },
    { label: "预览", state: "pending" },
    { label: "部署", state: "pending" },
  ]

  return (
    <div className="flex max-w-full flex-col items-start gap-2">
      <ol className="flex max-w-full items-center gap-2 overflow-x-auto pb-1 text-xs font-semibold [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {stages.map((stage, index) => (
          <li className="flex shrink-0 items-center gap-2" key={stage.label}>
            <span
              className={cn(
                "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3",
                (stage.state === "complete" || stage.state === "ready") &&
                  "border-black bg-black text-white",
                stage.state === "running" && "border-blue-200 bg-blue-50 text-blue-700",
                stage.state === "recovered" &&
                  "border-emerald-200 bg-emerald-50 text-emerald-700",
                stage.state === "pending" &&
                  "border-transparent bg-[var(--surface-muted)] text-slate-500",
              )}
            >
              {stage.state === "pending" ? (
                <Circle aria-hidden="true" size={12} />
              ) : stage.state === "running" ? (
                <CircleDot aria-hidden="true" size={12} />
              ) : (
                <Check aria-hidden="true" size={12} />
              )}
              {stage.label}
            </span>
            {index < stages.length - 1 ? (
              <span className="text-slate-300" aria-hidden="true">
                /
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}
