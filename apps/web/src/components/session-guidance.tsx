"use client"

import type { ChatMessage, SessionTask } from "@/lib/api"
import type { ArtifactPanelItem } from "./preview-card"
import { latestTaskState, type WorkspaceView } from "./session-workbench-state"

type Guidance = { phase: string; detail: string; next: string; action: string; view: WorkspaceView; taskId?: string }
const object = (value: unknown): Record<string, unknown> => value && typeof value === "object" ? value as Record<string, unknown> : {}
const text = (value: unknown) => typeof value === "string" ? value.slice(0, 280) : ""
const running = new Set(["running", "active", "streaming", "applying_changes", "collecting_diff", "starting_preview"])

export function sessionGuidance(tasks: SessionTask[], artifacts: ArtifactPanelItem[], messages: ChatMessage[]): Guidance {
  const user = [...messages].reverse().find(message => message.senderType === "user")
  const live = tasks.find(task => running.has(latestTaskState(task)))
  const newest = [...tasks].sort((a, b) => a.createdAt.localeCompare(b.createdAt)).at(-1)
  const groupId = user?.id ?? newest?.createdByMessageId
  const group = groupId ? tasks.filter(task => task.createdByMessageId === groupId) : tasks
  const focus = live ?? group.find(task => latestTaskState(task) !== "completed") ?? group.at(-1)
  const process = (phase: string, detail: string, next: string, action = "查看当前任务"): Guidance => ({ phase, detail, next, action, view: "process", taskId: focus?.id })
  if (live) {
    const checking = latestTaskState(live) === "collecting_diff"
    return process(checking ? "收集差异与复验" : "执行中", live.title,
      checking ? "等待本次 Diff 与检查回执；需要停止时可在任务中中断。" : "查看任务输出；需要停止时使用现有中断操作。")
  }
  if (!focus) {
    const rejected = [...messages].reverse().find(message => object(message.contextBudget).status === "rejected")
    if (rejected && (!user || messages.indexOf(rejected) > messages.indexOf(user))) {
      return { phase: "上下文超限", detail: "本次请求尚未调用模型。", next: "减少新请求的引用、附件或 Skills 后重新发送。", action: "编辑新请求", view: "conversation" }
    }
    return { phase: user ? "需求讨论" : "等待需求", detail: user ? "当前消息尚无执行计划；讨论回复不代表已执行。" : "描述要修改的项目与预期结果。",
      next: "向协调 Agent 说明目标与验收要求，或直接选择对应角色。", action: "填写需求", view: "conversation" }
  }
  const state = latestTaskState(focus), run = focus.taskRuns.at(-1)
  const scheduler = object(focus.planJson.scheduler), pmo = object(focus.planJson.pmoDecision)
  const reason = text(run?.errorMessage) || text(scheduler.reason) || focus.title
  if (state === "waiting_approval" || (!run && ["pending", "pending_approval", "awaiting_approval", "waiting_approval"].includes(text(pmo.state))))
    return process("等待确认", reason, "先核对计划和修改范围，再批准或拒绝当前任务。", "处理待确认任务")
  if (["failed", "interrupted", "cancelled"].includes(state))
    return process(state === "interrupted" ? "执行已中断" : state === "cancelled" ? "任务已取消" : "执行失败", reason, "查看失败原因和已有改动，再决定重试、修改需求或保留当前结果。", "处理当前任务")
  const waiting = text(scheduler.state) || state
  if (["waiting_dependency", "waiting_target_lock", "blocked", "waiting_lock"].includes(waiting) || state === "blocked")
    return process(waiting === "waiting_dependency" ? "等待前置任务" : waiting.includes("lock") ? "等待目标写锁" : "任务受阻", reason, "查看阻塞任务及依赖；修复前置失败或等待当前目标释放。", "查看阻塞原因")
  if (["created", "queued", "pending", "ready"].includes(state))
    return process(state === "queued" ? "排队中" : "准备执行", text(object(run?.sessionQueue).blockedReason) || focus.title, "查看队列与任务状态；尚未排队的任务可使用开始运行。")
  const currentIds = new Set(group.flatMap(task => task.taskRuns.at(-1)?.id ?? []))
  const current = artifacts.filter(item => currentIds.has(item.taskRunId))
  const reviews = current.filter(item => item.kind === "review")
  const qa = reviews.map(item => item.kind === "review" ? item.artifact.qaAssessment : null)
  const failedChecks = qa.some(value => value?.status === "blocked")
  if (failedChecks) return { phase: "复验待处理", detail: "本次评审存在未通过检查。", next: "打开评审报告，核对失败项后准备修复草稿。", action: "查看评审与结果", view: "results" }
  return { phase: "执行已结束，待核对结果", detail: qa.length && qa.every(value => value?.status === "passed" && value.currentness === "current")
      ? "已有当前版本的分项验收证据，请核对其实际覆盖范围。" : "执行完成不等于功能验收通过；缺少或过期的证据仍需核对。",
    next: "查看 Diff、评审和预览；模拟部署记录不代表生产上线。", action: "查看结果与证据", view: "results" }
}

export function SessionGuidance({ tasks, artifacts, messages, onNavigate }: { tasks: SessionTask[]; artifacts: ArtifactPanelItem[]; messages: ChatMessage[]; onNavigate: (view: WorkspaceView, taskId?: string) => void }) {
  const guide = sessionGuidance(tasks, artifacts, messages)
  return <section aria-label="当前阶段与下一步" className="mb-4 min-w-0 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3 text-xs">
    <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><p className="font-semibold">当前阶段 · {guide.phase}</p><p className="mt-1 break-words text-[var(--muted-foreground)]">{guide.detail}</p></div>
      <button type="button" className="shrink-0 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1" onClick={() => onNavigate(guide.view, guide.taskId)}>{guide.action}</button></div>
    <p className="mt-2 break-words">下一步：{guide.next}</p>
  </section>
}
