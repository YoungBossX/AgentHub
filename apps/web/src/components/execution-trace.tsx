"use client"

import {
  Code2,
  FileDiff,
  GitBranch,
  Monitor,
  Rocket,
  SearchCheck,
} from "lucide-react"

import type { ArtifactPanelItem } from "./preview-card"
import { statusLabel } from "./task-card"
import { cn } from "@/lib/utils"
import type {
  DeploymentArtifact,
  DiffArtifact,
  PreviewArtifact,
  ReviewArtifact,
  SessionTask,
} from "../lib/api"

const activeRunStates = new Set([
  "created",
  "queued",
  "streaming",
  "waiting_approval",
  "applying_changes",
  "collecting_diff",
  "starting_preview",
])

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

export function ExecutionTrace({
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
  const latestPreview = preferredPreview(previews)
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

function preferredPreview(previews: PreviewArtifact[]) {
  return [...previews].reverse().find((preview) => preview.healthStatus === "healthy") ??
    previews[previews.length - 1] ??
    null
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

function schedulerMeta(task: SessionTask): SchedulerMeta | null {
  const scheduler = task.planJson.scheduler
  if (!scheduler || typeof scheduler !== "object" || Array.isArray(scheduler)) {
    return null
  }
  return scheduler as SchedulerMeta
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
