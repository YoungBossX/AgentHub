"use client"

import { Check, CircleAlert, Play, RotateCcw, Shuffle, Square, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import type { ArtifactPanelItem } from "./preview-card"
import { Button } from "./ui/button"
import { cn } from "@/lib/utils"
import {
  listTaskRunDeployments,
  listTaskRunDiffs,
  listTaskRunPreviews,
  type DeploymentArtifact,
  type DiffArtifact,
  type PreviewArtifact,
  type SessionTask,
  type TaskRun,
} from "../lib/api"

type TaskCardListProps = {
  tasks: SessionTask[]
  artifactRefreshKey?: number
  backendUrl?: string
  busy?: boolean
  fetcher?: typeof fetch
  onApproveRun?: (taskRunId: string) => void
  onArtifactsChange?: (artifacts: ArtifactPanelItem[]) => void
  onCreateDeploy?: (previewId: string) => void
  onCreateRun?: (taskId: string) => void
  onDenyRun?: (taskRunId: string) => void
  onForceCodexFailure?: (taskId: string) => void
  onInterruptRun?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onRefreshPreviews?: (taskRunId: string) => void
  onRetryRun?: (taskRunId: string) => void
  onRetryWithFallback?: (taskRunId: string) => void
  onSelectArtifact?: (artifactId: string) => void
  onStartPreview?: (taskRunId: string) => void
  onStopPreview?: (previewId: string) => void
  selectedArtifactId?: string | null
}

const activeRunStates = new Set([
  "created",
  "queued",
  "streaming",
  "waiting_approval",
  "applying_changes",
  "collecting_diff",
  "starting_preview",
])
const retryableRunStates = new Set(["failed", "interrupted"])

function statusClasses(status: string) {
  if (status === "completed") {
    return {
      badge: "bg-green-50 text-green-700 border-green-200",
      border: "border-l-green-600",
    }
  }
  if (status === "failed") {
    return {
      badge: "bg-red-50 text-red-700 border-red-200",
      border: "border-l-red-600",
    }
  }
  if (status === "waiting_approval") {
    return {
      badge: "bg-amber-50 text-amber-700 border-amber-200",
      border: "border-l-amber-500",
    }
  }
  if (status === "running" || status === "active") {
    return {
      badge: "bg-blue-50 text-blue-700 border-blue-200",
      border: "border-l-blue-600",
    }
  }

  return {
    badge: "bg-slate-50 text-slate-600 border-slate-200",
    border: "border-l-slate-300",
  }
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    active: "运行中",
    applying_changes: "应用变更",
    collecting_diff: "收集 Diff",
    completed: "已完成",
    created: "已创建",
    failed: "失败",
    interrupted: "已中断",
    pending: "待处理",
    queued: "排队中",
    running: "运行中",
    starting_preview: "启动预览",
    streaming: "执行中",
    waiting_approval: "等待审批",
  }
  return labels[status] ?? status
}

function healthLabel(health: string) {
  const labels: Record<string, string> = {
    healthy: "健康",
    pending: "等待中",
    starting: "启动中",
    stopped: "已停止",
    unhealthy: "异常",
  }
  return labels[health] ?? health
}

export function TaskCardList({
  tasks,
  artifactRefreshKey = 0,
  backendUrl,
  busy = false,
  fetcher = fetch,
  onApproveRun,
  onArtifactsChange,
  onCreateRun,
  onDenyRun,
  onForceCodexFailure,
  onInterruptRun,
  onRetryRun,
  onRetryWithFallback,
  onSelectArtifact,
  onStartPreview,
  selectedArtifactId = null,
}: TaskCardListProps) {
  const [deploymentsByRunId, setDeploymentsByRunId] = useState<
    Record<string, DeploymentArtifact[]>
  >({})
  const [diffsByRunId, setDiffsByRunId] = useState<Record<string, DiffArtifact[]>>({})
  const [previewsByRunId, setPreviewsByRunId] = useState<Record<string, PreviewArtifact[]>>({})
  const taskRunIds = useMemo(
    () => tasks.flatMap((task) => task.taskRuns.map((taskRun) => taskRun.id)),
    [tasks],
  )
  const artifactItems = useMemo(
    () =>
      tasks.flatMap((task) =>
        task.taskRuns.flatMap((taskRun) => [
          ...(diffsByRunId[taskRun.id] ?? []).map(
            (diff): ArtifactPanelItem => ({
              artifact: diff,
              id: `diff:${diff.id}`,
              kind: "diff",
              taskRunId: taskRun.id,
              taskTitle: task.title,
            }),
          ),
          ...(previewsByRunId[taskRun.id] ?? []).map(
            (preview): ArtifactPanelItem => ({
              artifact: preview,
              id: `preview:${preview.id}`,
              kind: "preview",
              taskRunId: taskRun.id,
              taskTitle: task.title,
            }),
          ),
          ...(deploymentsByRunId[taskRun.id] ?? []).map(
            (deployment): ArtifactPanelItem => ({
              artifact: deployment,
              id: `deployment:${deployment.id}`,
              kind: "deployment",
              taskRunId: taskRun.id,
              taskTitle: task.title,
            }),
          ),
        ]),
      ),
    [deploymentsByRunId, diffsByRunId, previewsByRunId, tasks],
  )

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const diffs = await listTaskRunDiffs(backendUrl, taskRunId, fetcher)
        return [taskRunId, diffs] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setDiffsByRunId(Object.fromEntries(entries))
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds])

  useEffect(() => {
    onArtifactsChange?.(artifactItems)
  }, [artifactItems, onArtifactsChange])

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const deployments = await listTaskRunDeployments(backendUrl, taskRunId, fetcher)
        return [taskRunId, deployments] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setDeploymentsByRunId(Object.fromEntries(entries))
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds])

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const previews = await listTaskRunPreviews(backendUrl, taskRunId, fetcher)
        return [taskRunId, previews] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setPreviewsByRunId(Object.fromEntries(entries))
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds])

  if (tasks.length === 0) {
    return null
  }

  return (
    <ol className="relative grid gap-3.5 pl-8 before:absolute before:bottom-5 before:left-3 before:top-5 before:w-px before:bg-slate-200">
      {tasks.map((task, index) => {
        const latestRun = task.taskRuns[task.taskRuns.length - 1] ?? null
        const taskDiffs = task.taskRuns.flatMap((taskRun) => diffsByRunId[taskRun.id] ?? [])
        const taskDeployments = task.taskRuns.flatMap(
          (taskRun) => deploymentsByRunId[taskRun.id] ?? [],
        )
        const taskPreviews = task.taskRuns.flatMap(
          (taskRun) => previewsByRunId[taskRun.id] ?? [],
        )
        const taskArtifactItems = artifactItems.filter((item) =>
          task.taskRuns.some((taskRun) => taskRun.id === item.taskRunId),
        )
        const stateStyle = statusClasses(task.status)
        return (
          <li className="relative" key={task.id}>
            <span
              className={cn(
                "absolute -left-8 top-5 z-10 flex h-6 w-6 items-center justify-center rounded-full border-4 border-white text-[10px] font-bold shadow-sm",
                task.status === "completed" && "bg-green-600 text-white",
                task.status === "failed" && "bg-red-600 text-white",
                task.status === "waiting_approval" && "bg-amber-500 text-white",
                (task.status === "running" || task.status === "active") &&
                  "bg-blue-600 text-white",
                !["completed", "failed", "waiting_approval", "running", "active"].includes(
                  task.status,
                ) && "bg-slate-200 text-slate-600",
              )}
            >
              {index + 1}
            </span>
            <article
              className={cn(
                "rounded-xl border bg-white p-4 shadow-sm ring-1 ring-transparent transition hover:shadow-md",
                task.status === "completed"
                  ? "border-green-200"
                  : "border-[var(--border)]",
                selectedArtifactId &&
                  taskArtifactItems.some((item) => item.id === selectedArtifactId) &&
                  "ring-[var(--primary-border)]",
                stateStyle.border,
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-600">
                      任务 {index + 1}
                    </span>
                    <span className="rounded border border-[var(--border)] bg-white px-2 py-1 font-mono text-xs text-[var(--muted-foreground)]">
                      @{task.assignedAgentRole ?? "unassigned"}
                    </span>
                  </div>
                  <h3 className="mt-2 text-[17px] font-semibold leading-6 text-slate-950">
                    {task.title}
                  </h3>
                </div>
                <span
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-semibold",
                    stateStyle.badge,
                  )}
                >
                    {statusLabel(task.status)}
                </span>
              </div>
              {task.dependsOnTaskIds.length > 0 ? (
                <p className="mt-2 truncate text-xs font-medium text-[var(--muted-foreground)]">
                  依赖 {task.dependsOnTaskIds.join(", ")}
                </p>
              ) : null}
              <ArtifactChips
                deployments={taskDeployments}
                diffs={taskDiffs}
                onSelectArtifact={onSelectArtifact}
                previews={taskPreviews}
                recovered={Boolean(
                  task.taskRuns.find(
                    (run) =>
                      run.adapterType === "scripted_mock" &&
                      (run.metricsJson.retryOfRunId || run.metricsJson.fallbackFromRunId),
                  ),
                )}
                selectedArtifactId={selectedArtifactId}
                taskArtifactItems={taskArtifactItems}
              />
              {task.taskRuns.length > 0 ? (
                <div className="mt-3 grid gap-2 rounded-lg border border-slate-200 bg-slate-50/80 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
                      运行记录
                    </p>
                    <p className="text-[11px] font-medium text-slate-500">
                      {task.taskRuns.length} 次运行
                    </p>
                  </div>
                  {task.taskRuns.map((taskRun, runIndex) => (
                    <RunSummary
                      artifactReady={Boolean(
                        taskArtifactItems.find((item) => item.taskRunId === taskRun.id),
                      )}
                      key={taskRun.id}
                      run={taskRun}
                      runIndex={runIndex}
                    />
                  ))}
                  <RecoverySummary
                    artifactReady={taskArtifactItems.length > 0}
                    runs={task.taskRuns}
                  />
                </div>
              ) : null}
              <RunControls
                busy={busy}
                latestRun={latestRun}
                onApproveRun={
                  latestRun && onApproveRun ? () => onApproveRun(latestRun.id) : undefined
                }
                onCreateRun={onCreateRun ? () => onCreateRun(task.id) : undefined}
                onDenyRun={
                  latestRun && onDenyRun ? () => onDenyRun(latestRun.id) : undefined
                }
                onForceCodexFailure={
                  !latestRun && onForceCodexFailure
                    ? () => onForceCodexFailure(task.id)
                    : undefined
                }
                onInterruptRun={
                  latestRun && onInterruptRun ? () => onInterruptRun(latestRun.id) : undefined
                }
                onRetryRun={latestRun && onRetryRun ? () => onRetryRun(latestRun.id) : undefined}
                onRetryWithFallback={
                  latestRun && onRetryWithFallback
                    ? () => onRetryWithFallback(latestRun.id)
                    : undefined
                }
                onStartPreview={
                  latestRun && onStartPreview ? () => onStartPreview(latestRun.id) : undefined
                }
              />
            </article>
          </li>
        )
      })}
    </ol>
  )
}

function RunSummary({
  artifactReady,
  run,
  runIndex,
}: {
  artifactReady: boolean
  run: TaskRun
  runIndex: number
}) {
  const failed = run.state === "failed"
  const completed = run.state === "completed"
  const fallback = run.adapterType === "scripted_mock"
  const label = failed
    ? "Codex 失败"
    : completed && fallback
      ? "兜底已恢复"
      : completed
        ? "已完成"
        : statusLabel(run.state)
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-xs shadow-sm",
        failed && "border-red-200 bg-red-50/50",
        completed && !fallback && "border-green-200 bg-green-50/50",
        completed && fallback && "border-purple-200 bg-purple-50/50",
        !failed && !completed && "border-blue-200 bg-blue-50/50",
      )}
    >
      <span className="min-w-0 truncate">
        <span className="font-semibold text-slate-800">第 {runIndex + 1} 次</span>{" "}
        · <span className="font-mono">{run.adapterType}</span> · {label}
      </span>
      {artifactReady ? (
        <span className="text-green-700">产物就绪</span>
      ) : run.errorCode ? (
        <span className="truncate text-red-700">{run.errorCode}</span>
      ) : null}
    </div>
  )
}

function ArtifactChips({
  deployments,
  diffs,
  onSelectArtifact,
  previews,
  recovered,
  selectedArtifactId,
  taskArtifactItems,
}: {
  deployments: DeploymentArtifact[]
  diffs: DiffArtifact[]
  onSelectArtifact?: (artifactId: string) => void
  previews: PreviewArtifact[]
  recovered: boolean
  selectedArtifactId: string | null
  taskArtifactItems: ArtifactPanelItem[]
}) {
  if (
    diffs.length === 0 &&
    previews.length === 0 &&
    deployments.length === 0 &&
    !recovered
  ) {
    return null
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {recovered ? (
        <EvidenceChip className="bg-purple-50 text-purple-700" label="已恢复" />
      ) : null}
      {diffs.length > 0 ? (
        <EvidenceChip
          className="bg-cyan-50 text-cyan-700"
          label={`Diff 就绪 · ${diffs[0]?.stats.filesChanged ?? diffs.length} 个文件`}
          onClick={selectLatestArtifact("diff", taskArtifactItems, onSelectArtifact)}
          selected={selectedArtifactId === latestArtifactId("diff", taskArtifactItems)}
        />
      ) : null}
      {diffs[0]?.changedFiles[0] ? (
        <EvidenceChip
          className="bg-slate-100 font-mono text-slate-700"
          label={`已变更：${diffs[0].changedFiles[0]}`}
          onClick={selectLatestArtifact("diff", taskArtifactItems, onSelectArtifact)}
          selected={selectedArtifactId === latestArtifactId("diff", taskArtifactItems)}
        />
      ) : null}
      {previews.length > 0 ? (
        <EvidenceChip
          className="bg-green-50 text-green-700"
          label={`预览${healthLabel(previews[previews.length - 1]?.healthStatus ?? "")}`}
          onClick={selectLatestArtifact("preview", taskArtifactItems, onSelectArtifact)}
          selected={selectedArtifactId === latestArtifactId("preview", taskArtifactItems)}
        />
      ) : null}
      {deployments.length > 0 ? (
        <EvidenceChip
          className="bg-[var(--primary-soft)] text-[var(--primary)]"
          label="模拟部署就绪"
          onClick={selectLatestArtifact(
            "deployment",
            taskArtifactItems,
            onSelectArtifact,
          )}
          selected={selectedArtifactId === latestArtifactId("deployment", taskArtifactItems)}
        />
      ) : null}
    </div>
  )
}

function EvidenceChip({
  className,
  label,
  onClick,
  selected = false,
}: {
  className: string
  label: string
  onClick?: () => void
  selected?: boolean
}) {
  const chipClassName = cn(
    "rounded-full px-2.5 py-1 text-xs font-semibold",
    onClick && "transition hover:ring-2 hover:ring-[var(--primary-border)]",
    selected && "ring-2 ring-[var(--primary-border)]",
    className,
  )

  if (onClick) {
    return (
      <button className={chipClassName} onClick={onClick} type="button">
        {label}
      </button>
    )
  }

  return (
    <span className={chipClassName}>{label}</span>
  )
}

function latestArtifactId(
  kind: ArtifactPanelItem["kind"],
  items: ArtifactPanelItem[],
) {
  return [...items].reverse().find((item) => item.kind === kind)?.id ?? null
}

function selectLatestArtifact(
  kind: ArtifactPanelItem["kind"],
  items: ArtifactPanelItem[],
  onSelectArtifact?: (artifactId: string) => void,
) {
  const artifactId = latestArtifactId(kind, items)
  if (!artifactId || !onSelectArtifact) {
    return undefined
  }

  return () => onSelectArtifact(artifactId)
}

function RecoverySummary({
  artifactReady,
  runs,
}: {
  artifactReady: boolean
  runs: TaskRun[]
}) {
  const hasFailedCodex = runs.some(
    (run) => run.adapterType === "codex" && run.state === "failed",
  )
  const hasRecoveredFallback = runs.some(
    (run) => run.adapterType === "scripted_mock" && run.state === "completed",
  )

  if (!hasFailedCodex || !hasRecoveredFallback) {
    return null
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-purple-200 bg-white px-3 py-2 text-xs">
      <EvidenceChip className="bg-red-50 text-red-700" label="Codex 失败" />
      <span className="font-semibold text-slate-300">-&gt;</span>
      <EvidenceChip className="bg-purple-50 text-purple-700" label="兜底已恢复" />
      {artifactReady ? (
        <>
          <span className="font-semibold text-slate-300">-&gt;</span>
          <EvidenceChip className="bg-green-50 text-green-700" label="产物就绪" />
        </>
      ) : null}
    </div>
  )
}

function RunControls({
  busy,
  latestRun,
  onApproveRun,
  onCreateRun,
  onDenyRun,
  onForceCodexFailure,
  onInterruptRun,
  onRetryRun,
  onRetryWithFallback,
  onStartPreview,
}: {
  busy: boolean
  latestRun: TaskRun | null
  onApproveRun?: () => void
  onCreateRun?: () => void
  onDenyRun?: () => void
  onForceCodexFailure?: () => void
  onInterruptRun?: () => void
  onRetryRun?: () => void
  onRetryWithFallback?: () => void
  onStartPreview?: () => void
}) {
  if (!latestRun) {
    return (
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onCreateRun}
          onClick={onCreateRun}
          type="button"
        >
          <Play aria-hidden="true" size={14} />
          开始运行
        </Button>
        {onForceCodexFailure ? (
          <Button
            className="h-8 px-3 text-xs"
            disabled={busy}
            onClick={onForceCodexFailure}
            type="button"
            variant="secondary"
          >
            <CircleAlert aria-hidden="true" size={14} />
            模拟 Codex 失败
          </Button>
        ) : null}
      </div>
    )
  }

  if (latestRun.state === "waiting_approval") {
    return (
      <ApprovalRequestCard
        busy={busy}
        onApproveRun={onApproveRun}
        onDenyRun={onDenyRun}
        run={latestRun}
      />
    )
  }

  if (activeRunStates.has(latestRun.state)) {
    return (
      <div className="mt-3">
        <Button
          disabled={busy || !onInterruptRun}
          className="h-8 px-3 text-xs"
          onClick={onInterruptRun}
          type="button"
          variant="secondary"
        >
          <Square aria-hidden="true" size={14} />
          中断
        </Button>
      </div>
    )
  }

  if (retryableRunStates.has(latestRun.state)) {
    return (
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onRetryRun}
          onClick={onRetryRun}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={14} />
          重试
        </Button>
        {latestRun.adapterType === "codex" ? (
          <Button
            disabled={busy || !onRetryWithFallback}
            className="h-8 px-3 text-xs"
            onClick={onRetryWithFallback}
            type="button"
            variant="secondary"
          >
            <Shuffle aria-hidden="true" size={14} />
            使用兜底重试
          </Button>
        ) : null}
      </div>
    )
  }

  if (latestRun.state === "completed") {
    return (
      <div className="mt-3">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onStartPreview}
          onClick={onStartPreview}
          type="button"
          variant="secondary"
        >
          <Play aria-hidden="true" size={14} />
          启动预览
        </Button>
      </div>
    )
  }

  return null
}

function ApprovalRequestCard({
  busy,
  onApproveRun,
  onDenyRun,
  run,
}: {
  busy: boolean
  onApproveRun?: () => void
  onDenyRun?: () => void
  run: TaskRun
}) {
  const request = run.approvalRequest
  return (
    <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-normal text-amber-800">
            需要审批
          </p>
          <p className="mt-1 text-sm font-medium text-amber-950">
            {request?.requestedAction ?? "查看请求动作"}
          </p>
        </div>
        <span className="rounded-sm border border-amber-300 bg-white px-2 py-0.5 text-xs text-amber-800">
          {request?.approvalType ?? "审批"}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-amber-950">
        {request?.reason ?? "这次运行正在等待用户确认，确认后才能继续。"}
      </p>
      {request?.command || request?.path ? (
        <dl className="mt-2 grid gap-1 text-xs text-amber-900">
          {request.command ? (
            <div className="grid gap-1">
              <dt className="font-semibold">命令</dt>
              <dd className="truncate font-mono">{request.command}</dd>
            </div>
          ) : null}
          {request.path ? (
            <div className="grid gap-1">
              <dt className="font-semibold">路径</dt>
              <dd className="truncate font-mono">{request.path}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onApproveRun}
          onClick={onApproveRun}
          type="button"
        >
          <Check aria-hidden="true" size={14} />
          批准
        </Button>
        <Button
          className="h-8 px-3 text-xs"
          disabled={busy || !onDenyRun}
          onClick={onDenyRun}
          type="button"
          variant="secondary"
        >
          <X aria-hidden="true" size={14} />
          拒绝
        </Button>
      </div>
    </div>
  )
}
