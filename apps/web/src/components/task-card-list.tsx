"use client"

import {
  Check,
  CircleAlert,
  Code2,
  FileDiff,
  GitBranch,
  Monitor,
  Play,
  Rocket,
  RotateCcw,
  SearchCheck,
  Shuffle,
  Square,
  X,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import type { ArtifactPanelItem } from "./preview-card"
import { healthLabel, reviewLabel, statusClasses, statusLabel } from "./task-card"
import { Button } from "./ui/button"
import { cn } from "@/lib/utils"
import {
  listTaskRunDeployments,
  listTaskRunDiffs,
  listTaskRunPreviews,
  listTaskRunReviews,
  type DeploymentArtifact,
  type DiffArtifact,
  type PlanReviewMetadata,
  type PreviewArtifact,
  type ReviewArtifact,
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
  onCreateReview?: (taskRunId: string) => void
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
  onUseArtifactContext?: (artifact: ArtifactPanelItem) => void
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

export function TaskCardList({
  tasks,
  artifactRefreshKey = 0,
  backendUrl,
  busy = false,
  fetcher = fetch,
  onApproveRun,
  onArtifactsChange,
  onCreateDeploy,
  onCreateReview,
  onCreateRun,
  onDenyRun,
  onForceCodexFailure,
  onInterruptRun,
  onOpenPreview,
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
        const reviews = await listTaskRunReviews(backendUrl, taskRunId, fetcher)
        return [taskRunId, reviews] as const
      }),
    ).then((entries) => {
      if (!cancelled) {
        setReviewsByRunId(Object.fromEntries(entries))
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
        const taskReviews = task.taskRuns.flatMap(
          (taskRun) => reviewsByRunId[taskRun.id] ?? [],
        )
        const taskArtifactItems = artifactItems.filter((item) =>
          task.taskRuns.some((taskRun) => taskRun.id === item.taskRunId),
        )
        const stateStyle = statusClasses(task.status)
        const scheduler = schedulerMeta(task)
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
              <PlanReviewSummary
                metadata={task.planReviewMetadata ?? planReviewMetadataFromPlan(task)}
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

function ArtifactMessageCards({
  deployments,
  onCreateDeploy,
  onCreateReview,
  onOpenPreview,
  onSelectArtifact,
  onUseArtifactContext,
  reviews,
  selectedArtifactId,
  taskArtifactItems,
}: {
  deployments: DeploymentArtifact[]
  onCreateDeploy?: (previewId: string) => void
  onCreateReview?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onSelectArtifact?: (artifactId: string) => void
  onUseArtifactContext?: (artifact: ArtifactPanelItem) => void
  reviews: ReviewArtifact[]
  selectedArtifactId: string | null
  taskArtifactItems: ArtifactPanelItem[]
}) {
  if (taskArtifactItems.length === 0) {
    return null
  }

  return (
    <section
      aria-label="Artifact message cards"
      className="mt-3 grid gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
          Artifact Cards
        </p>
        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500">
          {taskArtifactItems.length} session-scoped
        </span>
      </div>

      <div className="grid gap-2">
        {[...taskArtifactItems].sort(compareArtifactCards).map((item) => (
          <ArtifactMessageCard
            deployments={deployments}
            item={item}
            key={`${item.id}:${item.taskRunId}`}
            onCreateDeploy={onCreateDeploy}
            onCreateReview={onCreateReview}
            onOpenPreview={onOpenPreview}
            onSelectArtifact={onSelectArtifact}
            onUseArtifactContext={onUseArtifactContext}
            reviews={reviews}
            selected={selectedArtifactId === item.id}
          />
        ))}
      </div>
    </section>
  )
}

function PlanReviewSummary({ metadata }: { metadata: PlanReviewMetadata | null }) {
  if (!metadata) {
    return null
  }
  const plannedFiles = metadata.plannedFiles ?? []
  const acceptanceCriteria = metadata.acceptanceCriteria ?? []
  const validationExpectations = metadata.validationExpectations ?? []
  const taskBreakdown = metadata.taskBreakdown ?? []
  const hasContent = Boolean(
    metadata.plannerMode ||
      metadata.rationale ||
      metadata.targetId ||
      plannedFiles.length ||
      acceptanceCriteria.length ||
      validationExpectations.length ||
      taskBreakdown.length,
  )
  if (!hasContent) {
    return null
  }

  return (
    <section className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-bold text-slate-700">计划审阅</span>
        {metadata.plannerMode ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600">
            {metadata.plannerMode}
          </span>
        ) : null}
        {metadata.targetId ? (
          <span className="rounded-full bg-white px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
            {metadata.targetId}
          </span>
        ) : null}
        {metadata.readOnly ? (
          <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
            read-only
          </span>
        ) : null}
      </div>
      {metadata.rationale ? (
        <p className="mt-2 line-clamp-2 text-slate-600">{metadata.rationale}</p>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-medium text-slate-500">
        {metadata.assignedRole ? (
          <span className="rounded bg-slate-50 px-2 py-0.5">@{metadata.assignedRole}</span>
        ) : null}
        {taskBreakdown.length > 0 ? (
          <span className="rounded bg-slate-50 px-2 py-0.5">
            task graph {taskBreakdown.length}
          </span>
        ) : null}
        {plannedFiles.slice(0, 3).map((file) => (
          <span className="rounded bg-slate-50 px-2 py-0.5 font-mono" key={file}>
            {file}
          </span>
        ))}
        {plannedFiles.length > 3 ? (
          <span className="rounded bg-slate-50 px-2 py-0.5">
            +{plannedFiles.length - 3} files
          </span>
        ) : null}
        {acceptanceCriteria.length > 0 ? (
          <span className="rounded bg-green-50 px-2 py-0.5 text-green-700">
            acceptance {acceptanceCriteria.length}
          </span>
        ) : null}
        {validationExpectations.length > 0 ? (
          <span className="rounded bg-blue-50 px-2 py-0.5 text-blue-700">
            validation {validationExpectations.length}
          </span>
        ) : null}
      </div>
    </section>
  )
}

function planReviewMetadataFromPlan(task: SessionTask): PlanReviewMetadata | null {
  const plan = task.planJson
  const planDraft = objectValue(plan.planDraft)
  const taskGraph = objectValue(plan.taskGraph)
  return {
    plannerMode: stringValue(plan.plannerMode) || stringValue(plan.planner) || stringValue(planDraft.plannerMode),
    rationale: stringValue(plan.rationale) || stringValue(planDraft.rationale),
    assignedRole: stringValue(plan.assignedRole) || task.assignedAgentRole || undefined,
    targetId:
      stringValue(plan.targetId) ||
      stringValue(plan.frontendTargetId) ||
      stringValue(plan.backendTargetId),
    dependencies: task.dependsOnTaskIds,
    plannedFiles:
      stringList(plan.plannedFiles) ||
      stringList(plan.files) ||
      stringList(planDraft.plannedFiles),
    acceptanceCriteria:
      stringList(plan.acceptanceCriteria) || stringList(planDraft.acceptanceCriteria),
    validationExpectations:
      stringList(plan.validationExpectations) || stringList(planDraft.validationExpectations),
    taskBreakdown: taskBreakdownFromPlan(taskGraph.tasks),
    readOnly: true,
    sourceTaskId: task.id,
  }
}

function taskBreakdownFromPlan(value: unknown): PlanReviewMetadata["taskBreakdown"] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    .map((item) => ({
      title: stringValue(item.title) || stringValue(item.name),
      role: stringValue(item.role) || stringValue(item.assignedRole),
      targetId: stringValue(item.targetId),
      dependsOn: stringList(item.dependsOn) ?? [],
      plannedFiles: stringList(item.plannedFiles) || stringList(item.files) || [],
    }))
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}

function stringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined
  }
  const values = value.filter((item): item is string => typeof item === "string" && item.length > 0)
  return values.length > 0 ? values : undefined
}

type SchedulerMeta = {
  state?: string
  runnable?: boolean
  reason?: string
  dependencyIds?: string[]
  blockingDependencyIds?: string[]
  targetId?: string | null
  writeLockRequired?: boolean
  lockHolderTaskRunIds?: string[]
  retryable?: boolean
  fallbackAvailable?: boolean
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

function schedulerMeta(task: SessionTask): SchedulerMeta | null {
  const scheduler = task.planJson.scheduler
  if (!scheduler || typeof scheduler !== "object" || Array.isArray(scheduler)) {
    return null
  }
  return scheduler as SchedulerMeta
}

function shortId(value: string) {
  return value.slice(0, 8)
}

function ArtifactMessageCard({
  deployments,
  item,
  onCreateDeploy,
  onCreateReview,
  onOpenPreview,
  onSelectArtifact,
  onUseArtifactContext,
  reviews,
  selected,
}: {
  deployments: DeploymentArtifact[]
  item: ArtifactPanelItem
  onCreateDeploy?: (previewId: string) => void
  onCreateReview?: (taskRunId: string) => void
  onOpenPreview?: (preview: PreviewArtifact) => void
  onSelectArtifact?: (artifactId: string) => void
  onUseArtifactContext?: (artifact: ArtifactPanelItem) => void
  reviews: ReviewArtifact[]
  selected: boolean
}) {
  const meta = artifactCardMeta(item)
  const reviewed = item.kind === "diff" && reviews.some(
    (review) =>
      review.reviewedDiffArtifactId === item.artifact.artifactId ||
      review.taskRunId === item.taskRunId,
  )
  const deployed = item.kind === "preview" && deployments.some(
    (deployment) => deployment.taskRunId === item.taskRunId,
  )

  return (
    <article
      className={cn(
        "rounded-lg border bg-white p-3 shadow-sm",
        artifactCardBorder(item.kind),
        selected && "ring-2 ring-[var(--primary-border)]",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            artifactCardIconClass(item.kind),
          )}
        >
          <ArtifactKindIcon kind={item.kind} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold uppercase tracking-normal text-slate-600">
              {artifactCardKindLabel(item.kind)}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
              run {item.taskRunId.slice(0, 8)}
            </span>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
              {meta.status}
            </span>
          </div>
          <h4 className="mt-2 line-clamp-1 text-sm font-semibold text-slate-950">
            {meta.title}
          </h4>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">
            {meta.summary}
          </p>
          <dl className="mt-2 grid gap-2 text-[11px] sm:grid-cols-3">
            {meta.rows.map((row) => (
              <div className="min-w-0 rounded-md bg-slate-50 px-2 py-1.5" key={row.label}>
                <dt className="text-slate-500">{row.label}</dt>
                <dd className="mt-0.5 truncate font-semibold text-slate-800">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 line-clamp-1 text-[11px] text-slate-500">
            Source task: {item.taskTitle}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          className="h-8 px-3 text-xs"
          disabled={!onSelectArtifact}
          onClick={() => onSelectArtifact?.(item.id)}
          type="button"
          variant="secondary"
        >
          {artifactInspectLabel(item.kind)}
        </Button>
        {item.kind === "diff" ? (
          <>
            <Button
              className="h-8 px-3 text-xs"
              disabled={!onUseArtifactContext}
              onClick={() => onUseArtifactContext?.(item)}
              type="button"
              variant="secondary"
            >
              Use this diff as context
            </Button>
            <Button
              className="h-8 px-3 text-xs"
              disabled={!onCreateReview || reviewed}
              onClick={() => onCreateReview?.(item.taskRunId)}
              type="button"
              variant="secondary"
            >
              {reviewed ? "Review ready" : "Review this diff"}
            </Button>
          </>
        ) : null}
        {item.kind === "review" ? (
          <Button
            className="h-8 px-3 text-xs"
            disabled={!onUseArtifactContext}
            onClick={() => onUseArtifactContext?.(item)}
            type="button"
            variant="secondary"
          >
            Use review as context
          </Button>
        ) : null}
        {item.kind === "preview" ? (
          <>
            <Button
              className="h-8 px-3 text-xs"
              disabled={!onOpenPreview}
              onClick={() => onOpenPreview?.(item.artifact)}
              type="button"
              variant="secondary"
            >
              Open preview
            </Button>
            <Button
              className="h-8 px-3 text-xs"
              disabled={
                !onCreateDeploy || deployed || item.artifact.healthStatus !== "healthy"
              }
              onClick={() => onCreateDeploy?.(item.artifact.id)}
              type="button"
              variant="secondary"
            >
              {deployed ? "Mock deploy ready" : "Create mock deploy"}
            </Button>
          </>
        ) : null}
      </div>
    </article>
  )
}

function compareArtifactCards(a: ArtifactPanelItem, b: ArtifactPanelItem) {
  const order: Record<ArtifactPanelItem["kind"], number> = {
    deployment: 3,
    diff: 0,
    preview: 2,
    review: 1,
  }
  return order[a.kind] - order[b.kind]
}

function artifactCardMeta(item: ArtifactPanelItem) {
  if (item.kind === "diff") {
    return {
      rows: [
        { label: "Files", value: String(item.artifact.stats.filesChanged) },
        { label: "Added", value: `+${item.artifact.stats.additions}` },
        { label: "Deleted", value: `-${item.artifact.stats.deletions}` },
      ],
      status: statusLabel(item.artifact.status),
      summary: item.artifact.changedFiles[0] ?? "Git diff captured for this run.",
      title: item.artifact.title,
    }
  }

  if (item.kind === "review") {
    return {
      rows: [
        { label: "Risk", value: item.artifact.riskLevel },
        { label: "Files", value: String(item.artifact.filesReviewed.length) },
        { label: "Adapter", value: item.artifact.adapterType },
      ],
      status: reviewLabel(item.artifact.status),
      summary: item.artifact.summary,
      title: item.artifact.title,
    }
  }

  if (item.kind === "preview") {
    return {
      rows: [
        { label: "Health", value: healthLabel(item.artifact.healthStatus) },
        { label: "Status", value: statusLabel(item.artifact.status) },
        { label: "Port", value: String(item.artifact.port) },
      ],
      status: healthLabel(item.artifact.healthStatus),
      summary: item.artifact.url,
      title: item.artifact.title,
    }
  }

  return {
    rows: [
      { label: "Provider", value: item.artifact.provider },
      { label: "Environment", value: item.artifact.environment },
      { label: "URL", value: item.artifact.url ?? "mock://pending" },
    ],
    status: statusLabel(item.artifact.status),
    summary: "Mock deploy card for local demo evidence. Not a production deployment.",
    title: item.artifact.title,
  }
}

function artifactCardKindLabel(kind: ArtifactPanelItem["kind"]) {
  const labels: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "Mock Deploy",
    diff: "Diff",
    preview: "Preview",
    review: "Review",
  }
  return labels[kind]
}

function artifactInspectLabel(kind: ArtifactPanelItem["kind"]) {
  const labels: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "View mock deploy",
    diff: "View diff",
    preview: "View preview",
    review: "View review",
  }
  return labels[kind]
}

function ArtifactKindIcon({ kind }: { kind: ArtifactPanelItem["kind"] }) {
  if (kind === "deployment") {
    return <Rocket aria-hidden="true" size={17} />
  }
  if (kind === "preview") {
    return <Monitor aria-hidden="true" size={17} />
  }
  if (kind === "review") {
    return <SearchCheck aria-hidden="true" size={17} />
  }
  return <FileDiff aria-hidden="true" size={17} />
}

function artifactCardIconClass(kind: ArtifactPanelItem["kind"]) {
  const classes: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "bg-violet-50 text-violet-700",
    diff: "bg-cyan-50 text-cyan-700",
    preview: "bg-green-50 text-green-700",
    review: "bg-amber-50 text-amber-700",
  }
  return classes[kind]
}

function artifactCardBorder(kind: ArtifactPanelItem["kind"]) {
  const classes: Record<ArtifactPanelItem["kind"], string> = {
    deployment: "border-violet-200",
    diff: "border-cyan-200",
    preview: "border-green-200",
    review: "border-amber-200",
  }
  return classes[kind]
}

type TraceStatus = "active" | "completed" | "failed" | "skipped" | "warning"

type TraceNode = {
  adapterType: string
  artifactId?: string | null
  detail: string
  identity: string
  key: string
  label: string
  status: TraceStatus
}

function ExecutionTrace({
  deployments,
  diffs,
  onSelectArtifact,
  previews,
  reviews,
  selectedArtifactId,
  task,
  taskArtifactItems,
}: {
  deployments: DeploymentArtifact[]
  diffs: DiffArtifact[]
  onSelectArtifact?: (artifactId: string) => void
  previews: PreviewArtifact[]
  reviews: ReviewArtifact[]
  selectedArtifactId: string | null
  task: SessionTask
  taskArtifactItems: ArtifactPanelItem[]
}) {
  const nodes = buildTraceNodes({
    deployments,
    diffs,
    previews,
    reviews,
    task,
    taskArtifactItems,
  })
  const fallbackNode = task.taskRuns.find(
    (run) =>
      run.adapterType === "scripted_mock" &&
      (run.metricsJson.retryOfRunId || run.metricsJson.fallbackFromRunId),
  )
  const warningReview = reviews.find((review) => review.status === "warning")
  const scheduler = schedulerMeta(task)

  return (
    <section
      aria-label="Multi-agent execution trace"
      className="mt-3 rounded-lg border border-slate-200 bg-white p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-bold uppercase tracking-normal text-[var(--text-muted)]">
          执行链路
        </p>
        <div className="flex flex-wrap gap-1.5">
          {fallbackNode ? (
            <TraceFlag className="bg-purple-50 text-purple-700" label="Fallback" />
          ) : null}
          {warningReview ? (
            <TraceFlag className="bg-amber-50 text-amber-700" label="Review warning" />
          ) : null}
          {scheduler?.state &&
          ["waiting_dependency", "waiting_target_lock", "blocked"].includes(
            scheduler.state,
          ) ? (
            <TraceFlag className="bg-slate-100 text-slate-700" label={statusLabel(scheduler.state)} />
          ) : null}
        </div>
      </div>

      <ol className="mt-3 grid gap-2 lg:grid-cols-2">
        {nodes.map((node, index) => {
          const Icon = traceIcon(node.key)
          const selected = Boolean(node.artifactId && node.artifactId === selectedArtifactId)
          const canSelect = Boolean(node.artifactId && onSelectArtifact)
          return (
            <li
              className={cn(
                "grid gap-2 rounded-lg border p-3 text-xs",
                traceStatusClasses(node.status),
                selected && "ring-2 ring-[var(--primary-border)]",
              )}
              key={node.key}
            >
              <div className="flex items-start gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/80 text-slate-700 shadow-sm">
                  <Icon aria-hidden="true" size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-[11px] font-bold text-slate-500">
                      {index + 1}
                    </span>
                    <span className="font-semibold text-slate-950">{node.label}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                        traceBadgeClasses(node.status),
                      )}
                    >
                      {traceStatusLabel(node.status)}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-[11px] font-medium text-slate-600">
                    {node.identity} · {node.adapterType}
                  </p>
                  <p className="mt-1 line-clamp-2 text-slate-700">{node.detail}</p>
                </div>
              </div>
              {canSelect ? (
                <button
                  className="justify-self-start rounded-full bg-white px-2.5 py-1 font-semibold text-[var(--primary)] shadow-sm transition hover:ring-2 hover:ring-[var(--primary-border)]"
                  onClick={() => node.artifactId && onSelectArtifact?.(node.artifactId)}
                  type="button"
                >
                  查看产物
                </button>
              ) : null}
            </li>
          )
        })}
      </ol>
    </section>
  )
}

function buildTraceNodes({
  deployments,
  diffs,
  previews,
  reviews,
  task,
  taskArtifactItems,
}: {
  deployments: DeploymentArtifact[]
  diffs: DiffArtifact[]
  previews: PreviewArtifact[]
  reviews: ReviewArtifact[]
  task: SessionTask
  taskArtifactItems: ArtifactPanelItem[]
}): TraceNode[] {
  const latestRun = task.taskRuns[task.taskRuns.length - 1] ?? null
  const latestDiff = diffs[diffs.length - 1] ?? null
  const latestReview = reviews[reviews.length - 1] ?? null
  const latestPreview = previews[previews.length - 1] ?? null
  const latestDeployment = deployments[deployments.length - 1] ?? null
  const codingStatus = latestRun ? traceStatusForRun(latestRun.state) : "skipped"
  const fallback = task.taskRuns.find(
    (run) =>
      run.adapterType === "scripted_mock" &&
      (run.metricsJson.retryOfRunId || run.metricsJson.fallbackFromRunId),
  )

  return [
    {
      adapterType: "scripted_mock",
      detail: task.createdByMessageId
        ? "Manager created a persisted task plan for this requirement."
        : "Task is present without a linked source message.",
      identity: "Manager Agent · @orchestrator",
      key: "manager",
      label: "Manager planned",
      status: task.status === "failed" ? "failed" : "completed",
    },
    {
      adapterType: latestRun?.adapterType ?? "not started",
      detail: latestRun
        ? fallback
          ? `Fallback recovered from ${String(
              fallback.metricsJson.retryOfRunId ?? fallback.metricsJson.fallbackFromRunId,
            ).slice(0, 8)}.`
          : `Latest run ${latestRun.id.slice(0, 8)} is ${statusLabel(latestRun.state)}.`
        : "Waiting for UI Start run.",
      identity: `${agentLabel(task.assignedAgentRole)} · @${
        task.assignedAgentRole ?? "unassigned"
      }`,
      key: "coding",
      label: "Coding Agent ran",
      status: fallback ? "warning" : codingStatus,
    },
    {
      adapterType: "git diff service",
      artifactId: latestArtifactId("diff", taskArtifactItems),
      detail: latestDiff
        ? `${latestDiff.stats.filesChanged} file(s): ${
            latestDiff.changedFiles[0] ?? "changed files captured"
          }`
        : "No diff artifact yet.",
      identity: "Diff Service",
      key: "diff",
      label: "Diff produced",
      status: latestDiff ? "completed" : latestRun?.state === "collecting_diff" ? "active" : "skipped",
    },
    {
      adapterType: latestReview?.adapterType ?? "scripted_mock",
      artifactId: latestArtifactId("review", taskArtifactItems),
      detail: latestReview
        ? latestReview.summary
        : latestDiff
          ? "Review artifact has not been loaded yet."
          : "Waiting for a diff before review.",
      identity: "Review Agent · @review",
      key: "review",
      label: "Review Agent reviewed",
      status: traceStatusForReview(latestReview),
    },
    {
      adapterType: "Vite preview service",
      artifactId: latestArtifactId("preview", taskArtifactItems),
      detail: latestPreview
        ? `${statusLabel(latestPreview.healthStatus)} · ${latestPreview.url}`
        : "Preview has not been started.",
      identity: "Preview Service",
      key: "preview",
      label: "Preview healthy",
      status: traceStatusForPreview(latestPreview),
    },
    {
      adapterType: latestDeployment?.provider ?? "mock",
      artifactId: latestArtifactId("deployment", taskArtifactItems),
      detail: latestDeployment
        ? `${latestDeployment.environment} · ${statusLabel(latestDeployment.status)}`
        : "Mock deploy card has not been created.",
      identity: "Mock Deploy Service",
      key: "deployment",
      label: "Mock deploy ready",
      status: traceStatusForDeployment(latestDeployment),
    },
  ]
}

function agentLabel(role: string | null) {
  const labels: Record<string, string> = {
    backend: "Backend Agent",
    frontend: "Frontend Agent",
    orchestrator: "Manager Agent",
    qa: "QA Agent",
  }
  return labels[role ?? ""] ?? "Coding Agent"
}

function traceStatusForRun(state: string): TraceStatus {
  if (state === "completed") {
    return "completed"
  }
  if (state === "failed" || state === "interrupted") {
    return "failed"
  }
  if (activeRunStates.has(state)) {
    return "active"
  }
  return "skipped"
}

function traceStatusForReview(review: ReviewArtifact | null | undefined): TraceStatus {
  if (!review) {
    return "skipped"
  }
  if (review.status === "failed") {
    return "failed"
  }
  if (review.status === "warning") {
    return "warning"
  }
  return "completed"
}

function traceStatusForPreview(preview: PreviewArtifact | null | undefined): TraceStatus {
  if (!preview) {
    return "skipped"
  }
  if (preview.healthStatus === "healthy") {
    return "completed"
  }
  if (preview.healthStatus === "unhealthy" || preview.healthStatus === "stopped") {
    return "warning"
  }
  return "active"
}

function traceStatusForDeployment(
  deployment: DeploymentArtifact | null | undefined,
): TraceStatus {
  if (!deployment) {
    return "skipped"
  }
  if (deployment.status === "ready") {
    return "completed"
  }
  if (deployment.status === "failed") {
    return "failed"
  }
  return "active"
}

function traceStatusLabel(status: TraceStatus) {
  const labels: Record<TraceStatus, string> = {
    active: "进行中",
    completed: "完成",
    failed: "失败",
    skipped: "等待",
    warning: "注意",
  }
  return labels[status]
}

function traceStatusClasses(status: TraceStatus) {
  const classes: Record<TraceStatus, string> = {
    active: "border-blue-200 bg-blue-50/50",
    completed: "border-green-200 bg-green-50/50",
    failed: "border-red-200 bg-red-50/50",
    skipped: "border-slate-200 bg-slate-50/80",
    warning: "border-amber-200 bg-amber-50/70",
  }
  return classes[status]
}

function traceBadgeClasses(status: TraceStatus) {
  const classes: Record<TraceStatus, string> = {
    active: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    skipped: "bg-slate-100 text-slate-500",
    warning: "bg-amber-100 text-amber-700",
  }
  return classes[status]
}

function traceIcon(key: string) {
  const icons: Record<string, typeof GitBranch> = {
    coding: Code2,
    deployment: Rocket,
    diff: FileDiff,
    manager: GitBranch,
    preview: Monitor,
    review: SearchCheck,
  }
  return icons[key] ?? GitBranch
}

function TraceFlag({ className, label }: { className: string; label: string }) {
  return (
    <span className={cn("rounded-full px-2 py-1 text-[11px] font-semibold", className)}>
      {label}
    </span>
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
      {reviews.length > 0 ? (
        <EvidenceChip
          className="bg-amber-50 text-amber-700"
          label={`评审${reviewLabel(reviews[reviews.length - 1]?.status ?? "")}`}
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
