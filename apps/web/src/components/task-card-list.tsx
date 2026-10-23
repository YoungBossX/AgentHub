"use client"

import { Disclosure } from "./disclosure"

import { type ReactNode, useEffect, useMemo, useState } from "react"

import { ArtifactMessageCards, type ArtifactContextIntent } from "./artifact-message-cards"
export type { ArtifactContextIntent } from "./artifact-message-cards"
import { PlanReviewSummary, PMODecisionSummary } from "./task-plan-summary"
import {
  plannerEvidenceFromPlan, pmoDecisionFromPlan, planReviewMetadataFromPlan,
  taskSupportsPreview, schedulerMeta, shortId, type SchedulerMeta,
} from "./task-card-data"

import { ExecutionTrace } from "./execution-trace"
import { McpEvidence } from "./mcp-evidence"
import { ContextBudgetEvidence } from "./context-budget-evidence"
import { DagSummary } from "./dag-summary"
import type { ArtifactPanelItem } from "./preview-card"
import { healthLabel, statusClasses, statusLabel } from "./task-card"
import { qaLabel } from "./qa-evidence"
import { RunControls } from "./task-run-controls"
import { cn } from "@/lib/utils"
import {
  listTaskRunDeployments,
  listTaskRunDiffs,
  listTaskRunPreviews,
  listTaskRunReviews,
  type AgentContact,
  type DeploymentArtifact,
  type DiffArtifact,
  type PreviewArtifact,
  type ReviewArtifact,
  type SessionTask,
  type TaskRun,
} from "../lib/api"

function customAgentName(task: SessionTask): string | null {
  const selection = task.taskRuns.at(-1)?.metricsJson.agentSelection as { customProfile?: { displayName?: unknown } } | undefined
  const name = selection?.customProfile?.displayName ?? task.planJson.agentProfileDisplayName
  return typeof name === "string" ? name : null
}

type TaskCardListProps = {
  compact?: boolean
  agents?: AgentContact[]
  tasks: SessionTask[]
  artifactRefreshKey?: number
  backendUrl?: string
  busy?: boolean
  fetcher?: typeof fetch
  onArtifactError?: (error: unknown) => void
  onApproveRun?: (taskRunId: string) => void
  onArtifactsChange?: (artifacts: ArtifactPanelItem[]) => void
  onCreateDeploy?: (previewId: string) => void
  onCreateReview?: (taskRunId: string) => void
  onCreateRun?: (taskId: string) => void
  onDenyRun?: (taskRunId: string) => void
  onForceCodexFailure?: (taskId: string) => void
  onInterruptRun?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onApprovePlan?: (taskId: string) => void
  onRejectPlan?: (taskId: string) => void
  onRequestClarification?: (taskId: string) => void
  onRefreshPreviews?: (taskRunId: string) => void
  onRetryRun?: (taskRunId: string) => void
  onRetryWithFallback?: (taskRunId: string) => void
  onSelectArtifact?: (artifactId: string) => void
  onStartPreview?: (taskRunId: string) => void
  onStopPreview?: (previewId: string) => void
  onUseArtifactContext?: (
    artifact: ArtifactPanelItem,
    intent?: ArtifactContextIntent,
  ) => void
  selectedArtifactId?: string | null
}

export function TaskCardList({
  compact = false,
  agents = [],
  tasks,
  artifactRefreshKey = 0,
  backendUrl,
  busy = false,
  fetcher = fetch,
  onArtifactError,
  onApproveRun,
  onArtifactsChange,
  onCreateDeploy,
  onCreateReview,
  onCreateRun,
  onDenyRun,
  onForceCodexFailure,
  onInterruptRun,
  onOpenPreview,
  onApprovePlan,
  onRejectPlan,
  onRequestClarification,
  onRetryRun,
  onRetryWithFallback,
  onSelectArtifact,
  onStartPreview,
  onUseArtifactContext,
  selectedArtifactId = null,
}: TaskCardListProps) {
  const [deploymentsByRunId, setDeploymentsByRunId] = useState<
    Record<string, DeploymentArtifact[]>
  >({})
  const [diffsByRunId, setDiffsByRunId] = useState<Record<string, DiffArtifact[]>>({})
  const [previewsByRunId, setPreviewsByRunId] = useState<Record<string, PreviewArtifact[]>>({})
  const [reviewsByRunId, setReviewsByRunId] = useState<Record<string, ReviewArtifact[]>>({})
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
          ...(reviewsByRunId[taskRun.id] ?? []).map(
            (review): ArtifactPanelItem => ({
              artifact: review,
              id: `review:${review.id}`,
              kind: "review",
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
    [deploymentsByRunId, diffsByRunId, previewsByRunId, reviewsByRunId, tasks],
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
    }).catch((error: unknown) => {
      if (!cancelled) {
        setDiffsByRunId({})
        onArtifactError?.(error)
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds, onArtifactError])

  useEffect(() => {
    if (!backendUrl || taskRunIds.length === 0) {
      return
    }

    let cancelled = false
    Promise.all(
      taskRunIds.map(async (taskRunId) => {
        const reviews = await listTaskRunReviews(backendUrl, taskRunId, fetcher)
        return [taskRunId, reviews] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setReviewsByRunId(Object.fromEntries(entries))
      }
    }).catch((error: unknown) => {
      if (!cancelled) {
        setReviewsByRunId({})
        onArtifactError?.(error)
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds, onArtifactError])

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
    }).catch((error: unknown) => {
      if (!cancelled) {
        setDeploymentsByRunId({})
        onArtifactError?.(error)
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds, onArtifactError])

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
    }).catch((error: unknown) => {
      if (!cancelled) {
        setPreviewsByRunId({})
        onArtifactError?.(error)
      }
    })

    return () => {
      cancelled = true
    }
  }, [artifactRefreshKey, backendUrl, fetcher, taskRunIds, onArtifactError])

  if (tasks.length === 0) {
    return null
  }

  return (
    <>
    <DagSummary tasks={tasks} agents={agents} />
    <ol className="relative grid gap-3.5 pl-8 before:absolute before:bottom-5 before:left-3 before:top-5 before:w-px before:bg-[var(--border-strong)]">
      {tasks.map((task, index) => {
        const latestRun = task.taskRuns[task.taskRuns.length - 1] ?? null
        const taskDiffs = task.taskRuns.flatMap((taskRun) => diffsByRunId[taskRun.id] ?? [])
        const taskDeployments = task.taskRuns.flatMap(
          (taskRun) => deploymentsByRunId[taskRun.id] ?? [],
        )
        const taskPreviews = task.taskRuns.flatMap(
          (taskRun) => previewsByRunId[taskRun.id] ?? [],
        )
        const taskReviews = task.taskRuns.flatMap(
          (taskRun) => reviewsByRunId[taskRun.id] ?? [],
        )
        const taskArtifactItems = artifactItems.filter((item) =>
          task.taskRuns.some((taskRun) => taskRun.id === item.taskRunId),
        )
        const stateStyle = statusClasses(task.status)
        const scheduler = schedulerMeta(task)
        const pmoDecision = pmoDecisionFromPlan(task)
        return (
          <li className="relative scroll-mt-4" id={`task-${task.id}`} key={task.id}>
            <span
              className={cn(
                "absolute -left-8 top-5 z-10 flex h-6 w-6 items-center justify-center rounded-full border-4 border-[var(--trace-border)] text-[10px] font-bold shadow-sm",
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
                "rounded-lg border bg-white p-4 shadow-sm ring-1 ring-transparent transition hover:shadow-md",
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
                    <span className="rounded-full bg-[var(--surface-muted)] px-2.5 py-1 font-mono text-xs text-slate-600">
                      任务 {index + 1}
                    </span>
                    <span className="rounded-full border border-[var(--border)] bg-white px-2.5 py-1 font-mono text-xs text-[var(--muted-foreground)]">
                      {customAgentName(task) ?? (agents.find((agent) => agent.id === task.assignedAgentId) ?? agents.find((agent) => agent.role === task.assignedAgentRole))?.displayName ?? `@${task.assignedAgentRole ?? "unassigned"}`}
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
              <ProcessDisclosure compact={compact} label="规划依据与文件范围">
              <PlanReviewSummary
                metadata={task.planReviewMetadata ?? planReviewMetadataFromPlan(task)}
                plannerEvidence={plannerEvidenceFromPlan(task)}
              />
              </ProcessDisclosure>
              <PMODecisionSummary
                decision={pmoDecision}
                onApprove={onApprovePlan ? () => onApprovePlan(task.id) : undefined}
                onReject={onRejectPlan ? () => onRejectPlan(task.id) : undefined}
                onRequestClarification={
                  onRequestClarification ? () => onRequestClarification(task.id) : undefined
                }
              />
              <SchedulerSummary scheduler={scheduler} />
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
                reviews={taskReviews}
                selectedArtifactId={selectedArtifactId}
                taskArtifactItems={taskArtifactItems}
              />
              <ProcessDisclosure compact={compact} label="执行链路与制品状态">
              {latestRun?.metricsJson.mcp ? <McpEvidence key={latestRun.id} backendUrl={backendUrl ?? "http://127.0.0.1:8000"} runId={latestRun.id} refreshKey={artifactRefreshKey ?? 0} /> : null}
              <ExecutionTrace
                deployments={taskDeployments}
                diffs={taskDiffs}
                onSelectArtifact={onSelectArtifact}
                previews={taskPreviews}
                reviews={taskReviews}
                selectedArtifactId={selectedArtifactId}
                task={task}
                taskArtifactItems={taskArtifactItems}
              />
              </ProcessDisclosure>
              <ArtifactMessageCards
                deployments={taskDeployments}
                onCreateDeploy={onCreateDeploy}
                onCreateReview={onCreateReview}
                onOpenPreview={onOpenPreview}
                onSelectArtifact={onSelectArtifact}
                onUseArtifactContext={onUseArtifactContext}
                reviews={taskReviews}
                selectedArtifactId={selectedArtifactId}
                taskArtifactItems={taskArtifactItems}
              />
              {task.taskRuns.length > 0 ? (
                <div className="mt-3 grid gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)]/80 p-3">
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
                      scriptedReview={task.planJson.planner === "explicit_group_v1" && task.planJson.readOnly === true}
                    />
                  ))}
                  <RecoverySummary
                    artifactReady={taskArtifactItems.length > 0}
                    runs={task.taskRuns}
                  />
                </div>
              ) : null}
              {!(compact && task.status === "completed" && !latestRun) ? <RunControls
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
                  latestRun && onStartPreview && taskSupportsPreview(task)
                    ? () => onStartPreview(latestRun.id)
                    : undefined
                }
              /> : null}
            </article>
          </li>
        )
      })}
    </ol>
    </>
  )
}

function SchedulerSummary({ scheduler }: { scheduler: SchedulerMeta | null }) {
  if (!scheduler?.state) {
    return null
  }

  const blockingIds = scheduler.blockingDependencyIds ?? []
  const lockHolderIds = scheduler.lockHolderTaskRunIds ?? []
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/80 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-bold text-slate-700">调度状态</span>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 font-semibold",
            statusClasses(scheduler.state).badge,
          )}
        >
          {statusLabel(scheduler.state)}
        </span>
        {scheduler.targetId ? (
          <span className="rounded bg-white px-2 py-0.5 font-mono text-[11px] text-slate-600">
            {scheduler.targetId}
          </span>
        ) : null}
      </div>
      {scheduler.reason ? (
        <p className="mt-1 line-clamp-2 text-slate-600">{scheduler.reason}</p>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-medium text-slate-500">
        {blockingIds.length > 0 ? (
          <span className="rounded bg-white px-2 py-0.5">
            阻塞依赖 {blockingIds.map(shortId).join(", ")}
          </span>
        ) : null}
        {lockHolderIds.length > 0 ? (
          <span className="rounded bg-white px-2 py-0.5">
            锁持有者 {lockHolderIds.map(shortId).join(", ")}
          </span>
        ) : null}
        {scheduler.writeLockRequired ? (
          <span className="rounded bg-white px-2 py-0.5">写锁</span>
        ) : null}
        {scheduler.fallbackAvailable ? (
          <span className="rounded bg-purple-50 px-2 py-0.5 text-purple-700">
            fallback available
          </span>
        ) : null}
        {scheduler.retryable ? (
          <span className="rounded bg-white px-2 py-0.5">retryable</span>
        ) : null}
      </div>
    </div>
  )
}

function preferredPreview(previews: PreviewArtifact[]) {
  return [...previews].reverse().find((preview) => preview.healthStatus === "healthy") ??
    previews[previews.length - 1] ??
    null
}

function RunSummary({
  artifactReady,
  run,
  runIndex,
  scriptedReview,
}: {
  artifactReady: boolean
  run: TaskRun
  runIndex: number
  scriptedReview: boolean
}) {
  const failed = run.state === "failed"
  const completed = run.state === "completed"
  const review = scriptedReview && run.adapterType === "scripted_mock"
  const fallback = run.adapterType === "scripted_mock" && !review
  const label = failed
    ? review ? "脚本评审失败" : "Codex 失败"
    : completed && review
      ? "只读脚本评审完成"
    : completed && fallback
      ? "兜底已恢复"
      : completed
        ? "已完成"
        : statusLabel(run.state)
  return (
    <>
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
    <ContextBudgetEvidence receipt={run.metricsJson.contextBudget} />
    </>
  )
}

function ArtifactChips({
  deployments,
  diffs,
  onSelectArtifact,
  previews,
  recovered,
  reviews,
  selectedArtifactId,
  taskArtifactItems,
}: {
  deployments: DeploymentArtifact[]
  diffs: DiffArtifact[]
  onSelectArtifact?: (artifactId: string) => void
  previews: PreviewArtifact[]
  recovered: boolean
  reviews: ReviewArtifact[]
  selectedArtifactId: string | null
  taskArtifactItems: ArtifactPanelItem[]
}) {
  if (
    diffs.length === 0 &&
    previews.length === 0 &&
    reviews.length === 0 &&
    deployments.length === 0 &&
    !recovered
  ) {
    return null
  }
  const displayedPreview = preferredPreview(previews)

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
          label={`预览${healthLabel(displayedPreview?.healthStatus ?? "")}`}
          onClick={selectLatestArtifact("preview", taskArtifactItems, onSelectArtifact)}
          selected={selectedArtifactId === latestArtifactId("preview", taskArtifactItems)}
        />
      ) : null}
      {reviews.length > 0 ? (
        <EvidenceChip
          className="bg-amber-50 text-amber-700"
          label={qaLabel(reviews[reviews.length - 1])}
          onClick={selectLatestArtifact("review", taskArtifactItems, onSelectArtifact)}
          selected={selectedArtifactId === latestArtifactId("review", taskArtifactItems)}
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
  const matching = [...items].reverse().filter((item) => item.kind === kind)
  if (kind === "preview") {
    const previewItems = matching.filter(
      (item): item is Extract<ArtifactPanelItem, { kind: "preview" }> =>
        item.kind === "preview",
    )
    return (
      previewItems.find((item) => item.artifact.healthStatus === "healthy") ??
      previewItems[0] ??
      null
    )?.id ?? null
  }
  return matching[0]?.id ?? null
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

function ProcessDisclosure({ compact, label, children }: { compact: boolean; label: string; children: ReactNode }) {
  return compact ? <Disclosure className="mt-3" summaryClassName="cursor-pointer text-xs font-medium text-slate-500" summary={<>{label}</>}>{children}</Disclosure> : children
}
