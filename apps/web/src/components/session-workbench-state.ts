import type { ArtifactPanelItem } from "./preview-card"
import type { SessionTask } from "@/lib/api"

export type WorkspaceView = "conversation" | "process" | "results"
export type StageState = "pending" | "ready" | "active" | "failed"
export type WorkbenchStage = { label: string; state: StageState; detail: string }

export const activeStates = new Set([
  "created", "queued", "streaming", "running", "active", "waiting_approval",
  "applying_changes", "collecting_diff", "starting_preview",
])

export function latestTaskState(task: SessionTask) {
  return task.taskRuns.at(-1)?.state ?? task.status
}

export function sessionStages(
  tasks: SessionTask[], artifacts: ArtifactPanelItem[], hasRequirement: boolean,
): WorkbenchStage[] {
  const runIds = new Set(tasks.flatMap((task) => task.taskRuns.at(-1)?.id ?? []))
  const current = artifacts.filter((item) => runIds.has(item.taskRunId))
  const finished = tasks.length > 0 && tasks.every((task) => latestTaskState(task) === "completed")
  const failed = tasks.some((task) => ["failed", "interrupted", "blocked", "cancelled"].includes(latestTaskState(task)))
  const active = tasks.some((task) => activeStates.has(latestTaskState(task)))
  const diffs = current.filter((item) => item.kind === "diff" && item.artifact.status === "ready" && item.artifact.patchText.trim() && item.artifact.changedFiles.length)
  const previews = current.filter((item) => item.kind === "preview" && item.artifact.status === "ready" && item.artifact.healthStatus === "healthy")
  const deployments = current.filter((item) => item.kind === "deployment" && ["ready", "deployed"].includes(item.artifact.status))
  return [
    { label: "需求", state: hasRequirement ? "ready" : "pending", detail: hasRequirement ? "已收到消息" : "等待你的需求" },
    { label: "计划", state: tasks.length ? "ready" : "pending", detail: tasks.length ? `${tasks.length} 个任务` : "尚未生成计划" },
    { label: "执行", state: failed ? "failed" : finished ? "ready" : active ? "active" : "pending", detail: failed ? "有任务需处理" : finished ? "任务已结束" : active ? "正在执行 / 排队" : "等待开始" },
    { label: "Diff", state: diffs.length ? "ready" : "pending", detail: diffs.length ? `${diffs.length} 份变更` : "尚无本次变更" },
    { label: "预览", state: previews.length ? "ready" : "pending", detail: previews.length ? "健康预览可用" : "尚无健康预览" },
    { label: "交付", state: deployments.length ? "ready" : "pending", detail: deployments.length ? "已有部署记录（查看提供方）" : "尚无部署记录" },
  ]
}

export function dependencyLayout(tasks: SessionTask[]) {
  const ids = new Set(tasks.map((task) => task.id))
  const ranks = new Map<string, number>()
  const pending = new Set(ids)
  while (pending.size) {
    let progressed = false
    for (const task of tasks) {
      if (!pending.has(task.id)) continue
      const known = task.dependsOnTaskIds.filter((id) => ids.has(id))
      if (known.every((id) => ranks.has(id))) {
        ranks.set(task.id, known.length ? Math.max(...known.map((id) => ranks.get(id)!)) + 1 : 0)
        pending.delete(task.id)
        progressed = true
      }
    }
    if (!progressed) break
  }
  const cyclic = pending.size > 0
  const fallbackRank = ranks.size ? Math.max(...ranks.values()) + 1 : 0
  const rows = new Map<number, number>()
  const nodes = tasks.map((task) => {
    const rank = ranks.get(task.id) ?? fallbackRank
    const row = rows.get(rank) ?? 0
    rows.set(rank, row + 1)
    return { task, x: 16 + rank * 248, y: 16 + row * 106 }
  })
  return { nodes, cyclic, missing: tasks.some((task) => task.dependsOnTaskIds.some((id) => !ids.has(id))),
    width: Math.max(280, ...nodes.map((node) => node.x + 232)),
    height: Math.max(112, ...nodes.map((node) => node.y + 94)) }
}
